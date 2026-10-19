"""Read Windows-reported processor limits; never equate these with all CPU thermal flags."""
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def summarize(rows):
    if not rows or len({r['number'] for r in rows}) != len(rows):
        raise ValueError('Missing/duplicate processor records')
    for row in rows:
        if any(type(row[key]) is not int or row[key] < 0 for key in ('number', 'maxMhz', 'currentMhz', 'limitMhz')):
            raise ValueError('Invalid processor record')
        if row['maxMhz'] == 0 or row['limitMhz'] == 0:
            raise ValueError('Missing processor frequency limit')
    return {'source': 'Windows CallNtPowerInformation(ProcessorInformation), read-only level 11',
            'processors': rows,
            'osReportedLimitBelowMax': any(r['limitMhz'] < r['maxMhz'] for r in rows),
            'cpuThermalThrottling': None,
            'validatedHardwareThrottleSource': False,
            'note': 'OS-reported limits do not establish absence of hardware/firmware thermal throttling.'}


def read_limits():
    if os.name != 'nt':
        raise RuntimeError('Windows-only read')
    class ProcessorPower(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint32) for name in
                    ('number', 'maxMhz', 'currentMhz', 'limitMhz', 'maxIdleState', 'currentIdleState')]
    kernel = ctypes.WinDLL(r'C:\Windows\System32\kernel32.dll', use_last_error=True)
    kernel.GetActiveProcessorCount.argtypes = [ctypes.c_ushort]
    kernel.GetActiveProcessorCount.restype = ctypes.c_uint32
    count = kernel.GetActiveProcessorCount(0xffff)
    if not 0 < count <= 64:
        raise RuntimeError('Only a single processor group is supported by this diagnostic')
    records = (ProcessorPower * count)()
    power = ctypes.WinDLL(r'C:\Windows\System32\powrprof.dll')
    power.CallNtPowerInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32,
                                            ctypes.c_void_p, ctypes.c_uint32]
    power.CallNtPowerInformation.restype = ctypes.c_uint32
    # ProcessorInformation is a query. No input buffer and no other information level are accepted.
    status = power.CallNtPowerInformation(11, None, 0, ctypes.byref(records), ctypes.sizeof(records))
    if status != 0:
        raise RuntimeError(f'ProcessorInformation returned status 0x{status:08x}')
    return summarize([{field: int(getattr(record, field)) for field, _ in ProcessorPower._fields_}
                      for record in records])


if __name__ == '__main__':
    result = {'version': 1, 'mode': 'read-only-cpu-limit-diagnostic', 'settingsChanged': False,
              'recordedAt': datetime.now(timezone.utc).isoformat(), 'liveExecutionAllowed': False}
    try:
        result.update(read_limits())
    except Exception as error:
        result['error'] = str(error)
    target = Path(__file__).resolve().parents[2] / '.runtime/safety-readiness/windows-cpu-limits.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'artifact': str(target), **result}, indent=2))
