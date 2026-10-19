"""Small read-only storage probe using the already-cached Python image only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

import build_guard as guard
import image_plan
import offline_target

ROOT = image_plan.STORAGE_ROOT
PROBE = '''import json, os, signal
signal.alarm(3)
info = os.statvfs('/')
with open('/proc/meminfo', 'rb') as stream:
    memory = stream.read(65537)
swap = [int(line.split()[1]) * 1024 for line in memory.splitlines() if line.startswith(b'SwapTotal:')]
if len(memory) > 65536 or len(swap) != 1:
    raise ValueError('Guest swap metadata invalid')
with open('/proc/self/mountinfo', 'rb') as stream:
    rows = stream.read(65537)
if len(rows) > 65536:
    raise ValueError('Mount metadata exceeds limit')
root = [line.split(b' - ', 1)[1].split()[0].decode('ascii')
        for line in rows.splitlines() if line.split()[4] == b'/']
if len(root) != 1:
    raise ValueError('Root mount identification failed')
print(json.dumps({'guestRootAvailableBytes': info.f_bavail * info.f_frsize,
                  'guestSwapTotalBytes': swap[0],
                  'guestRootTotalBytes': info.f_blocks * info.f_frsize,
                  'guestRootFilesystemType': root[0]}), flush=True)
'''


def probe():
    image_plan.metadata()  # Check committed public metadata, never fetch it here.
    directory = ROOT / uuid.uuid4().hex
    inputs = directory / 'input'
    guard.base.no_links(ROOT)
    inputs.mkdir(parents=True)
    (inputs / 'probe.py').write_bytes(PROBE.encode())
    name = 'copilot-image-storage-' + directory.name
    digest = hashlib.sha256(PROBE.encode()).hexdigest()
    labels = {'local-copilot.kind': 'image-storage-probe', 'local-copilot.session': directory.name}
    contract = {'name': name, 'image': guard.base.IMAGE,
                'entrypoint': ['/usr/local/bin/python3'], 'command': ['-I', '-B', '/input/probe.py'],
                'labels': labels, 'host': offline_target.host_profile(fixture=True),
                'binds': offline_target.binds([(inputs, '/input')])}
    args = ['create', '--name', name, '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
            '--cpus', '0.5', '--memory', '64m', '--memory-swap', '64m', '--pids-limit', '16',
            '--read-only', '--network', 'none', '--user', '65532:65532', '--restart', 'no',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--shm-size', str(offline_target.offline.SHM_BYTES),
            '--log-driver', 'json-file', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
            '--env', 'NVIDIA_VISIBLE_DEVICES=void',
            '--tmpfs', '/work:rw,noexec,nosuid,nodev,size=65536,mode=1777',
            '--mount', f'type=bind,source={inputs},target=/input,readonly',
            '--workdir', '/work', '--entrypoint', '/usr/local/bin/python3']
    for key, value in labels.items():
        args.extend(['--label', key + '=' + value])
    args.extend([guard.base.IMAGE, '-I', '-B', '/input/probe.py'])
    result = {'version': 1, 'mode': 'read-only-image-storage-probe', 'image': image_plan.IMAGE,
              'probeImage': guard.base.IMAGE, 'cleanupComplete': False, 'probeExitCode': None,
              'imageDownloaded': False, 'imageImported': False, 'compilerStarted': False, 'modelStarted': False,
              'dockerBackingPathConfirmed': False}
    docker, target = guard.base.Docker(), None
    try:
        docker.call('image', 'inspect', guard.base.IMAGE)
        container_id = docker.call(*args).strip()
        result['containerId'] = container_id
        target = offline_target.Target(container_id, json.dumps(contract, sort_keys=True), digest, digest)
        target.inspect(docker)
        output = docker.call('start', '--attach', container_id, timeout=5)
        if len(output) > 4096:
            raise ValueError('Storage proof output exceeds limit')
        info = target.inspect(docker)
        if info is None or info['State']['Running'] or info['State'].get('OOMKilled') or info['State']['ExitCode'] != 0:
            raise ValueError('Read-only storage fixture failed')
        proof = json.loads(output)
        if (proof.get('guestRootFilesystemType') != 'overlay' or
                any(type(proof.get(k)) is not int or proof[k] <= 0
                    for k in ('guestRootAvailableBytes', 'guestRootTotalBytes')) or
                proof['guestRootAvailableBytes'] > proof['guestRootTotalBytes']):
            raise ValueError('Unexpected storage fixture observation')
        candidate = Path(os.environ['LOCALAPPDATA']) / 'Docker/wsl/disk/docker_data.vhdx'
        if candidate.is_file():
            image_plan.tools.plain(candidate)
        result.update(proof)
        result.update(probeExitCode=0, recordedAtUnix=time.time(), stageVolumeFreeBytes=shutil.disk_usage(ROOT).free,
                      dockerDiskCandidate=str(candidate), dockerDiskCandidateExists=candidate.is_file(),
                      dockerCandidateVolumeFreeBytes=shutil.disk_usage(candidate.parent).free if candidate.is_file() else None,
                      sameHostVolume=ROOT.anchor.lower() == candidate.anchor.lower(),
                      dockerDiskFileBytes=candidate.stat().st_size if candidate.is_file() else None)
        # A default-location file's existence alone does not prove active mapping.
    finally:
        if target is not None:
            stopped = guard.stop_target(docker, {}, target.container_id, matcher=target.matcher)
            result['cleanupComplete'] = stopped['cleanupComplete']
            result['stopConfirmed'] = stopped['stopConfirmed']
        guard.base.atomic(directory / 'result.json', result)
    if not result['cleanupComplete']:
        raise ValueError('Storage fixture removal unconfirmed')
    report = image_plan.report(result)
    guard.base.atomic(directory / 'image-plan.json', report)
    print(json.dumps({'directory': str(directory), 'observation': result,
                      'capacity': report['capacity'], 'budget': report['proposedStorageBudget']}, indent=2))
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only-probe', action='store_true', required=True)
    parser.parse_args()
    probe()
