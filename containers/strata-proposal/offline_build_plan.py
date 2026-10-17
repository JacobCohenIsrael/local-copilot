"""Prepare an offline, read-only compiler proposal; never execute Docker/tools."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import uuid

import build_guard
import build_preflight
import stage_build_tools as tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / '.runtime/offline-build'
WORK_BYTES = 2 * 1024**3
TMP_BYTES = 128 * 1024**2
SHM_BYTES = 16 * 1024**2


def verified_tools(directory):
    directory = Path(directory).absolute()
    tools.plain(directory)
    if directory.parent != tools.ROOT or not re.fullmatch('[0-9a-f]{32}', directory.name):
        raise ValueError('Expected an owned staged-tool directory')
    receipt_file = directory / 'tools.json'
    if receipt_file.stat().st_size > 2 * 1024**2:
        raise ValueError('Tool receipt exceeds limit')
    receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
    locked, sha = tools.lock()
    if (receipt['status'] != 'staged-not-executed' or receipt['lockSha256'] != sha or
            receipt['archives'] != locked or receipt['toolsExecuted'] is not False or
            receipt['buildEnabled'] is not False or receipt['modelLaunchEnabled'] is not False):
        raise ValueError('Tool receipt differs from reviewed lock')
    expected = {}
    for row in receipt['files']:
        path = PurePosixPath(row['path'])
        if (path.is_absolute() or not path.parts or any(p in ('.', '..') or ':' in p or '\\' in p for p in path.parts) or
                row['path'].casefold() in expected or type(row['bytes']) is not int or not 0 <= row['bytes'] <= tools.FILE_BYTES):
            raise ValueError('Unsafe tool receipt path/size')
        expected[row['path'].casefold()] = row
    if len(expected) > tools.FILE_LIMIT or sum(r['bytes'] for r in expected.values()) > tools.EXPANDED_LIMIT:
        raise ValueError('Tool receipt budget exceeded')
    if not {'cmake/bin/cmake', 'ninja/bin/ninja'} <= set(expected):
        raise ValueError('Tool receipt is missing required executables')
    actual = set()
    for path in (directory / 'tools').rglob('*'):
        tools.plain(path)
        if not path.is_file():
            continue
        name = path.relative_to(directory / 'tools').as_posix().casefold()
        row = expected.get(name)
        if row is None or path.stat().st_size != row['bytes'] or tools.sha(path) != row['sha256']:
            raise ValueError('Staged tool tree changed')
        actual.add(name)
    if actual != set(expected):
        raise ValueError('Missing staged tool files')
    return receipt


def source_identity(source):
    """Match upstream's BUILD.json fingerprint without importing setup.py."""
    commit = '3cf03257f219afbe7334045ff7c6a06ac68c627d'
    fingerprint = hashlib.sha256(commit.encode())
    for part in ('CMakeLists.txt', 'cmake', 'src', 'include', 'third_party/ggml'):
        base = source / part
        for path in [base] if base.is_file() else sorted(p for p in base.rglob('*') if p.is_file()):
            tools.plain(path)
            if path.stat().st_size > 32 * 1024**2:
                raise ValueError('Source fingerprint file exceeds preparation limit')
            fingerprint.update(path.relative_to(source).as_posix().encode() + b'\0' + path.read_bytes().replace(b'\r\n', b'\n'))
    return fingerprint.hexdigest()[:16]


def create_args(session, source, directory, image):
    return ['create', '--name', 'copilot-offline-build-' + session.name,
            '--label', 'local-copilot.kind=offline-strata-build-proposal',
            '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
            '--cpus', '1', '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '128',
            '--restart', 'no', '--network', 'none', '--read-only', '--user', '65532:65532',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--shm-size', str(SHM_BYTES),
            '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
            '--env', 'NVIDIA_VISIBLE_DEVICES=void',
            '--tmpfs', f'/work:rw,nosuid,nodev,size={WORK_BYTES},mode=1777',
            '--tmpfs', f'/tmp:rw,noexec,nosuid,nodev,size={TMP_BYTES},mode=1777',
            '--mount', f'type=bind,source={source},target=/source,readonly',
            '--mount', f'type=bind,source={Path(directory) / "tools"},target=/tools,readonly',
            '--mount', f'type=bind,source={session / "input"},target=/input,readonly',
            '--workdir', '/work', '--entrypoint', '/usr/bin/timeout', image,
            '--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile_offline.sh']


def checked_proposal(directory, expected_sha):
    directory = Path(directory).absolute()
    tools.plain(directory)
    if directory.parent != ROOT or not re.fullmatch('[0-9a-f]{32}', directory.name):
        raise ValueError('Offline proposal outside owned namespace')
    file = directory / 'offline-plan.json'
    if file.stat().st_size > 2 * 1024**2 or tools.sha(file) != expected_sha:
        raise ValueError('Offline proposal changed')
    plan = json.loads(file.read_text(encoding='utf-8'))
    if (plan['status'] != 'offline-proposal-not-approved' or plan['buildEnabled'] is not False or
            plan['modelLaunchEnabled'] is not False):
        raise ValueError('Offline build must stay disabled')
    source = Path(plan['sourcePackage']) / 'input/source'
    source_package = build_guard.plan(Path(plan['sourcePackage']))
    if plan['sourceManifestSha256'] != source_package['buildManifestSha256']:
        raise ValueError('Offline source package changed')
    tool_directory = Path(plan['toolDirectory'])
    tools.plain(tool_directory)
    if tool_directory.parent != tools.ROOT or not re.fullmatch('[0-9a-f]{32}', tool_directory.name):
        raise ValueError('Unexpected tool directory')
    if tools.sha(tool_directory / 'tools.json') != plan['toolReceiptSha256']:
        raise ValueError('Tool receipt changed')
    if plan['createArgs'] != create_args(directory, source, tool_directory, source_package['image']):
        raise ValueError('Offline network/storage/resource profile changed')
    if (plan['compilerNetwork'] != 'none' or plan['rootReadOnly'] is not True or
            plan['aptOrPipDuringCompilation'] is not False or plan['cpuQuota'] != 1 or
            plan['ramBytes'] != 4294967296 or plan['swapBytes'] != 0 or plan['gpuDevices'] != [] or
            plan['mutableFilesystems'] != {'workBytes': WORK_BYTES, 'tmpBytes': TMP_BYTES, 'shmBytes': SHM_BYTES}):
        raise ValueError('Offline resource declarations disagree with fixed profile')
    if set(plan['inputHashes']) != {'BUILD.json', 'compile_offline.sh'}:
        raise ValueError('Missing offline build input hashes')
    for name, expected in plan['inputHashes'].items():
        if tools.sha(directory / 'input' / name) != expected:
            raise ValueError('Offline compiler input changed')
    return plan


def prepare(directory):
    receipt = verified_tools(directory)
    previous = build_preflight.report()
    source = Path(previous['candidatePackage']) / 'input/source'
    if not re.search(r'project\(strata VERSION 0\.1\.44\.1\b', (source / 'CMakeLists.txt').read_text(encoding='utf-8')):
        raise ValueError('Unexpected source version')
    session = ROOT / uuid.uuid4().hex
    tools.plain(ROOT)
    inputs = session / 'input'
    inputs.mkdir(parents=True)
    script = inputs / 'compile_offline.sh'
    script.write_bytes((HERE / script.name).read_bytes().replace(b'\r\n', b'\n'))
    metadata = {'source': 'local', 'version': '0.1.44.1', 'archs': [86], 'vision': 'none',
                'src': source_identity(source), 'vision_src': None,
                'cuda_dirs': ['/usr/local/cuda/bin', '/usr/local/cuda/lib64']}
    (inputs / 'BUILD.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    image = build_guard.plan()['image']
    args = create_args(session, source, Path(directory), image)
    plan = {'version': 1, 'status': 'offline-proposal-not-approved',
            'buildEnabled': False, 'modelLaunchEnabled': False, 'createArgs': args,
            'sourcePackage': previous['candidatePackage'], 'sourceManifestSha256': previous['preparedManifestSha256'],
            'toolDirectory': str(directory), 'toolReceiptSha256': tools.sha(Path(directory) / 'tools.json'),
            'lockedToolDownloadBytes': receipt['lockedDownloadBytes'], 'toolExpandedBytes': receipt['expandedBytes'],
            'inputHashes': {p.name: tools.sha(p) for p in inputs.iterdir()},
            'compilerNetwork': 'none', 'rootReadOnly': True, 'aptOrPipDuringCompilation': False,
            'mutableFilesystems': {'workBytes': WORK_BYTES, 'tmpBytes': TMP_BYTES, 'shmBytes': SHM_BYTES},
            'cpuQuota': 1, 'ramBytes': 4294967296, 'swapBytes': 0, 'gpuDevices': [],
            'remainingGates': ['Owner review/approval of this final filesystem and build manifest',
                'Bounded CUDA image staging, base tool/library compatibility and image disk capacity',
                'Validated CPU source and independent controller/watchdog connected to this identity',
                'Bounded artifact export before tmpfs unmount; never copy unlimited output',
                'First approved attempt validates resource fit; OOM/ENOSPC must stop without retries or cap increases'],
            'limitations': ['tmpfs counts against the same 4 GiB memory cap; it supplies no extra RAM',
                'A real compilation may fail with OOM/ENOSPC; no retry or automatic cap increase',
                'Docker image storage, logs and Windows paging are separate from compiler tmpfs bounds',
                'No tool, compiler, upstream source or model was executed during preparation']}
    (session / 'offline-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    print(json.dumps({'directory': str(session), 'planSha256': tools.sha(session / 'offline-plan.json'),
        'buildEnabled': False, 'modelLaunchEnabled': False, 'lockedToolDownloadBytes': receipt['lockedDownloadBytes']}))
    return session


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', required=True)
    prepare(parser.parse_args().tools)
