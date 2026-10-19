"""CPU-only container probe. Model files are stat'ed, never opened."""
import glob
import json
import os
from pathlib import Path


def collect(manifest):
    cg = Path('/sys/fs/cgroup')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    paths = []
    for item in manifest['paths']:
        path = Path(item['container'])
        stat = path.stat()  # Metadata only, including for GGUF/bin files.
        paths.append({**item, 'exists': True, 'isDirectory': path.is_dir(), 'bytes': stat.st_size})
    return {
        'kind': 'cpu-only-preflight', 'strataStarted': False,
        'modelContentsRead': False, 'hardwareTemperaturesMeasured': False,
        'uid': os.getuid(), 'effectiveCapabilities': status['CapEff'].strip(),
        'noNewPrivileges': status['NoNewPrivs'].strip(),
        'memoryMaxBytes': int((cg / 'memory.max').read_text()),
        'swapMaxBytes': int((cg / 'memory.swap.max').read_text()),
        'cpuMax': (cg / 'cpu.max').read_text().strip(),
        'pidsMax': int((cg / 'pids.max').read_text()),
        'procMemTotalBytes': int(mem['MemTotal'].split()[0]) * 1024,
        'networkInterfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()),
        'gpuDevices': glob.glob('/dev/nvidia*') + glob.glob('/dev/dxg') + glob.glob('/dev/dri/*'),
        'paths': paths,
    }


def validate(result):
    quota, period = map(int, result['cpuMax'].split())
    checks = {
        'memoryLimit': result['memoryMaxBytes'] == 256 * 1024 * 1024,
        'swapDisabled': result['swapMaxBytes'] == 0,
        'halfCpu': quota > 0 and period > 0 and quota * 2 == period,
        'processLimit': result['pidsMax'] == 32,
        'nonRoot': result['uid'] == 65534,
        'noCapabilities': int(result['effectiveCapabilities'], 16) == 0,
        'noNewPrivileges': result['noNewPrivileges'] == '1',
        'noGpuDevices': not result['gpuDevices'],
        'networkIsolated': result['networkInterfaces'] == ['lo'],
        'allPathsPresent': bool(result['paths']) and all(p['exists'] for p in result['paths']),
    }
    return checks


if __name__ == '__main__':
    result = collect(json.loads(Path('/input/manifest.json').read_text()))
    result['checks'] = validate(result)
    result['passed'] = all(result['checks'].values())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
