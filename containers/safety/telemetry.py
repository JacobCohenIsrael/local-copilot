"""One read-only Windows sensor availability snapshot. Never authorizes live work."""
import ctypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SMI = r'C:\Windows\System32\nvidia-smi.exe'
POWERSHELL = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
REQUIRED = ('gpuTemperatureC', 'gpuPowerW', 'vramUsedMiB', 'cpuTemperatureC',
            'ramUsedMiB', 'acConnected', 'gpuThermalThrottling', 'cpuThermalThrottling')


def utc():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        result = float(str(value).split()[0])
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, IndexError):
        return None


def flag(value):
    return {'Active': True, 'Not Active': False}.get(value)


def parse_gpu(xml):
    root = ET.fromstring(xml)
    gpu = root.find('gpu')
    if gpu is None or len(root.findall('gpu')) != 1:
        raise ValueError('Expected exactly the selected GPU')
    def first(*paths):
        return next((gpu.findtext(p) for p in paths if gpu.findtext(p) is not None), None)
    thermal = [flag(first(f'clocks_event_reasons/clocks_event_reason_{kind}_thermal_slowdown',
                          f'clocks_throttle_reasons/clocks_throttle_reason_{kind}_thermal_slowdown'))
               for kind in ('sw', 'hw')]
    return {
        'identity': {'name': gpu.findtext('product_name'), 'driver': root.findtext('driver_version'),
                     'driverReportedCuda': root.findtext('cuda_version')},
        'values': {
            'gpuTemperatureC': number(gpu.findtext('temperature/gpu_temp')),
            'gpuPowerW': number(first('gpu_power_readings/instant_power_draw',
                                     'gpu_power_readings/power_draw', 'power_readings/power_draw')),
            'vramUsedMiB': number(gpu.findtext('fb_memory_usage/used')),
            'vramTotalMiB': number(gpu.findtext('fb_memory_usage/total')),
            'gpuThermalThrottling': True if True in thermal else (False if thermal == [False, False] else None),
        },
    }


def native_windows():
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_uint32), ('load', ctypes.c_uint32)] + [
            (name, ctypes.c_uint64) for name in ('totalPhysical', 'availablePhysical', 'totalPage',
                                               'availablePage', 'totalVirtual', 'availableVirtual', 'extended')]
    class Power(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_ubyte), ('batteryFlag', ctypes.c_ubyte),
                    ('batteryPercent', ctypes.c_ubyte), ('reserved', ctypes.c_ubyte),
                    ('lifeSeconds', ctypes.c_uint32), ('fullSeconds', ctypes.c_uint32)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    memory, power = Memory(), Power()
    memory.length = ctypes.sizeof(memory)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.GetSystemPowerStatus(ctypes.byref(power)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'ramUsedMiB': (memory.totalPhysical - memory.availablePhysical) / 1048576,
            'ramTotalMiB': memory.totalPhysical / 1048576,
            'acConnected': {0: False, 1: True}.get(power.ac)}


def provider_query():
    # Read only already-registered WMI providers; no services, drivers or sensor apps started.
    script = r'''
$ErrorActionPreference = 'Stop'
$providers = @()
foreach ($ns in @('root/LibreHardwareMonitor', 'root/OpenHardwareMonitor')) {
    try {
        $sensors = @(Get-CimInstance -Namespace $ns -ClassName Sensor -OperationTimeoutSec 2 |
            Where-Object { $_.SensorType -eq 'Temperature' } |
            Select-Object Identifier,Parent,Name,Value)
        $providers += @{ namespace=$ns; available=$true; sensors=$sensors }
    } catch { $providers += @{ namespace=$ns; available=$false; error=$_.Exception.Message } }
}
$acpi = @()
$acpiError = $null
try {
    $acpi = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -OperationTimeoutSec 2 |
        Select-Object CurrentTemperature)
} catch { $acpiError = $_.Exception.Message }
@{ providers=$providers; acpiZones=$acpi; acpiError=$acpiError } | ConvertTo-Json -Depth 7 -Compress
'''
    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=10, check=True)
    return json.loads(result.stdout)


def cpu_temperature(providers):
    candidates = []
    for provider in providers:
        if not provider.get('available'):
            continue
        for sensor in provider.get('sensors', []):
            identity = str(sensor.get('Identifier', '')).lower()
            value = number(sensor.get('Value'))
            if any(part in identity for part in ('/intelcpu/', '/amdcpu/', '/cpu/')) and value is not None:
                candidates.append({'value': value, 'source': provider['namespace'], 'sensor': sensor['Name']})
    # Keep the maximum reported CPU temperature; no ACPI/GPU substitution.
    return max(candidates, key=lambda item: item['value']) if candidates else None


def availability(channels):
    return [key for key in REQUIRED if channels.get(key, {}).get('value') is None]


def snapshot():
    if os.name != 'nt':
        raise RuntimeError('This availability probe is Windows-only')
    result = {'version': 1, 'mode': 'read-only-telemetry-audit', 'startedAt': utc(),
              'channels': {}, 'errors': [], 'liveExecutionAllowed': False,
              'freshnessValidated': False, 'policyApproved': False}
    def add(values, source, started):
        for key, value in values.items():
            result['channels'][key] = {'value': value, 'source': source, 'receivedAt': utc(),
                                       'queryDurationSeconds': round(time.monotonic() - started, 3)}
    started = time.monotonic()
    try:
        add(native_windows(), 'Windows GlobalMemoryStatusEx/GetSystemPowerStatus', started)
    except Exception as error:
        result['errors'].append('Windows status: ' + str(error)[:512])
    started = time.monotonic()
    try:
        query = subprocess.run([SMI, '--id=0', '-q', '-x'], capture_output=True, text=True, timeout=5, check=True)
        if len(query.stdout) > 2 * 1024 * 1024:
            raise ValueError('GPU query output exceeds limit')
        gpu = parse_gpu(query.stdout)
        result['gpu'] = gpu['identity']
        add(gpu['values'], 'nvidia-smi read-only XML query, GPU index 0', started)
    except Exception as error:
        result['errors'].append('GPU query: ' + str(error)[:512])
    started = time.monotonic()
    try:
        result['existingProviders'] = provider_query()
        cpu = cpu_temperature(result['existingProviders']['providers'])
        add({'cpuTemperatureC': cpu['value'] if cpu else None}, cpu['source'] if cpu else 'No CPU provider', started)
        result['selectedCpuSensor'] = cpu
    except Exception as error:
        result['errors'].append('CPU provider query: ' + str(error)[:512])
    add({'cpuThermalThrottling': None}, 'No validated CPU thermal-throttle provider', time.monotonic())
    for key in REQUIRED:
        result['channels'].setdefault(key, {'value': None, 'source': 'Unavailable'})
    result['missingRequiredChannels'] = availability(result['channels'])
    result['telemetryComplete'] = not result['missingRequiredChannels']
    result['finishedAt'] = utc()
    return result


if __name__ == '__main__':
    output = ROOT / '.runtime' / 'safety-readiness'
    output.mkdir(parents=True, exist_ok=True)
    result = snapshot()
    target = output / ('telemetry-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'artifact': str(target), **result}, indent=2))
