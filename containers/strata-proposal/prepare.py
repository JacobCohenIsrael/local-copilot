"""Stage pinned source/build inputs and a disabled launch manifest; never run Docker."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STAGING = ROOT / '.runtime' / 'strata-build'
SOURCES = (
    ('strata', 'Niko1221/Strata', '296b59d2f73c8f04a805df29c2fa97655adace78'),
    ('llama', 'ggml-org/llama.cpp', '3cf03257f219afbe7334045ff7c6a06ac68c627d'),
)
MAX_DOWNLOAD = 96 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(url, target):
    if target.exists():
        return
    partial = target.with_suffix('.part')
    started = time.monotonic()
    with urllib.request.urlopen(url, timeout=20) as response, partial.open('xb') as stream:
        size = 0
        while chunk := response.read(65536):
            size += len(chunk)
            if size > MAX_DOWNLOAD or time.monotonic() - started > 180:
                raise RuntimeError('Source download budget exceeded; partial retained for investigation')
            stream.write(chunk)
    partial.rename(target)


def extract(archive, target, prefix, skip_ui=False):
    """Validate the entire member list before writing external archive paths."""
    if target.exists():
        raise ValueError('Source extraction never overwrites an existing directory')
    members = []
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as source:
        if len(source.infolist()) > 40000:
            raise ValueError('Too many archive entries')
        for member in source.infolist():
            path = PurePosixPath(member.filename)
            parts = path.parts
            mode = member.external_attr >> 16
            if (not parts or parts[0] != prefix or path.is_absolute() or
                    any(p in ('.', '..') or ':' in p or '\\' in p or p.endswith((' ', '.')) for p in parts) or
                    stat.S_ISLNK(mode)):
                raise ValueError('Unsafe source archive member: ' + member.filename)
            relative = PurePosixPath(*parts[1:])
            if not relative.parts or member.is_dir():
                continue
            if skip_ui and relative.parts[:2] == ('tools', 'ui'):
                continue  # Same unused web UI omission as upstream setup.get_llama_cpp.
            for part in relative.parts:
                if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
                    raise ValueError('Windows reserved source path')
            key = relative.as_posix().casefold()
            if key in seen:
                raise ValueError('Duplicate or case-aliased source member')
            seen.add(key)
            total += member.file_size
            if member.file_size > 32 * 1024 * 1024 or total > MAX_EXPANDED:
                raise ValueError('Expanded source budget exceeded')
            members.append((member, relative))
        target.mkdir(parents=True)
        for member, relative in members:
            destination = target.joinpath(*relative.parts)
            destination.resolve().relative_to(target.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as data, destination.open('xb') as output:
                shutil.copyfileobj(data, output, length=65536)
    return {'files': len(members), 'expandedBytes': total}


def prepare(fetch=False):
    STAGING.mkdir(parents=True, exist_ok=True)
    cache = STAGING / 'downloads'
    cache.mkdir(exist_ok=True)
    for label, repository, commit in SOURCES:
        archive = cache / f'{label}-{commit}.zip'
        if fetch:
            download(f'https://codeload.github.com/{repository}/zip/{commit}', archive)
        if not archive.exists():
            raise RuntimeError('Pinned archive missing; use --download-sources to stage source only')
    package = STAGING / uuid.uuid4().hex[:8]
    package.mkdir()
    inputs = package / 'input'
    inputs.mkdir()
    source_root = inputs / 'source'
    records = []
    for label, repository, commit in SOURCES:
        archive = cache / f'{label}-{commit}.zip'
        target = source_root if label == 'strata' else source_root / 'third_party/llama.cpp'
        record = {'repository': repository, 'commit': commit, 'archiveSha256': sha(archive),
                  'archiveBytes': archive.stat().st_size}
        record.update(extract(archive, target, repository.split('/')[1] + '-' + commit, skip_ui=label == 'llama'))
        records.append(record)
    # Cross-check the pinned source against the previously reviewed text snapshot.
    for relative, snapshot in [('Dockerfile', 'Dockerfile'), ('setup.py', 'setup.py'),
                               ('docker-entrypoint.sh', 'docker-entrypoint.sh'), ('serve/server.py', 'serve--server.py')]:
        reference = ROOT / '.runtime/strata-preflight/references' / snapshot
        if source_root.joinpath(relative).read_bytes() != reference.read_bytes():
            raise ValueError('Pinned source differs from reviewed snapshot: ' + relative)
    for name in ('compile.sh', 'bounded_build.py'):
        # Linux shell input always uses LF, regardless of Windows Git checkout settings.
        (inputs / name).write_bytes((HERE / name).read_bytes().replace(b'\r\n', b'\n'))
    proposal = json.loads((HERE / 'build-proposal.json').read_text())
    name = 'copilot-strata-compile-' + package.name
    command = ['create', '--name', name, '--label', 'local-copilot.kind=strata-compile-proposal',
               '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
               '--cpus', '1', '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '128',
               '--restart', 'no', '--network', 'bridge', '--security-opt', 'no-new-privileges',
               '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
               '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--entrypoint', '/usr/bin/timeout',
               '--mount', f'type=bind,source={inputs},target=/input,readonly',
               '--workdir', '/opt/strata', proposal['base']['image'],
               '--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile.sh']
    manifest = {'version': 1, 'status': 'prepared-not-approved', 'buildEnabled': False,
                'modelLaunchEnabled': False, 'preparedAt': datetime.now(timezone.utc).isoformat(),
                'sources': records, 'baseImage': proposal['base']['image'],
                'createArgs': command, 'inputHashes': {name: sha(inputs / name) for name in ('compile.sh', 'bounded_build.py')},
                'sourceHostMountReadOnly': True, 'gpuDeviceRequests': [], 'rootFilesystemWritableForPackages': True,
                'compilerJobs': 1, 'automaticRetry': False, 'sourceCodeExecutedDuringPreparation': False,
                'remainingGates': proposal['requiredBeforeBuild'],
                'notes': ['Only source archives downloaded; no CUDA image, dependencies or models downloaded.',
                          'Network is needed for apt/pip; no host credentials, model directories or Docker socket mounted.',
                          'Ordinary container uses standard Docker capabilities for package installation; no privileged mode or extra devices.',
                          'Final image creation is separate; do not commit a running/failed compiler or auto-start its engine.']}
    (package / 'build-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'package': str(package), 'sources': records, 'buildEnabled': False,
                      'modelLaunchEnabled': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-sources', action='store_true')
    prepare(parser.parse_args().download_sources)
