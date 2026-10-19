"""Run a pinned OpenCode version or fake-only probe in a capped offline container."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import stage_opencode as stage
import stage_opencode_runtime
import task_bundle

HERE = Path(__file__).resolve().parent
DOCKER = r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
IMAGE = 'docker.io/library/python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8'
RUNS = stage.ROOT / 'checks'


def docker(*args, timeout=15):
    return subprocess.run([DOCKER, *args], capture_output=True, check=True,
                          text=True, timeout=timeout).stdout


def artifact(path):
    path = Path(path).absolute()
    if path.parent != stage.ROOT or not re.fullmatch(r'2\.0\.26-musl-[0-9a-f]{8}', path.name):
        raise ValueError('FIXED_ARTIFACT_DIRECTORY_REQUIRED')
    task_bundle.plain(path, directory=True)
    lock = task_bundle.read_json(HERE / 'opencode-lock.json')
    binary = path / 'staged/opencode'
    task_bundle.plain(binary)
    if stage.sha(binary) != lock['binarySha256'] or binary.stat().st_size != lock['binaryBytes']:
        raise ValueError('PINNED_BINARY_MISMATCH')
    return path


def validate(info, name, source, kind='opencode-version-only'):
    hc, config = info['HostConfig'], info['Config']
    mounts = {(m['Source'].replace('\\', '/').casefold(), m['Destination'], m['RW']) for m in info['Mounts']}
    expected = {(str(source).replace('\\', '/').casefold(), '/input', False)}
    if not (info['Name'] == '/' + name and config['Labels'].get('local-copilot.kind') == kind
            and config['Image'] == IMAGE and config['User'] == '65532:65532'
            and config['Entrypoint'] == ['python'] and config['Cmd'] == ['-B', '/input/probe.py']
            and mounts == expected and hc['NanoCpus'] == 500000000 and hc['Memory'] == 536870912
            and hc['MemorySwap'] == 536870912 and hc['PidsLimit'] == 64 and hc['ReadonlyRootfs']
            and hc['NetworkMode'] == 'none' and hc['Runtime'] == 'runc'
            and not hc['Privileged'] and not hc.get('DeviceRequests') and not hc.get('Devices')
            and hc['CapDrop'] == ['ALL'] and not hc.get('CapAdd') and not hc.get('PortBindings')
            and hc['RestartPolicy']['Name'] == 'no'
            and 'no-new-privileges' in hc.get('SecurityOpt', [])
            and hc.get('Tmpfs') == {'/tmp': 'rw,noexec,nosuid,size=64m'}):
        raise ValueError('CONTAINER_ENVELOPE_MISMATCH')


def run(path, fake=False, scenario='reply', bundle_id=None):
    if scenario not in ('reply', 'edit', 'deny-shell', 'deny-external', 'deny-file-write'):
        raise ValueError('FIXED_SCENARIO_REQUIRED')
    if bundle_id is not None:
        if not fake or scenario != 'edit':
            raise ValueError('BUNDLE_REQUIRES_FAKE_EDIT')
        if task_bundle.collect(bundle_id)['changedFiles']:
            raise ValueError('PRISTINE_BUNDLE_REQUIRED')
        manifest = task_bundle.read_json(task_bundle.ROOT / bundle_id / 'manifest.json')
        if (set(manifest['files']) != {'example.py'} or
                task_bundle.bounded_read(task_bundle.ROOT / bundle_id / 'workspace/example.py') != b'VALUE = 1\n' or
                not isinstance(manifest.get('task'), str) or
                not 1 <= len(manifest['task']) <= task_bundle.MAX_TASK_CHARS):
            raise ValueError('SYNTHETIC_BUNDLE_REQUIRED')
    path = artifact(path)
    RUNS.mkdir(parents=True, exist_ok=True)
    task_bundle.plain(RUNS, directory=True)
    session = RUNS / uuid.uuid4().hex
    source = session / 'input'
    source.mkdir(parents=True)
    # Keep only the verified binary and this fixed helper in the mounted directory.
    shutil.copyfile(path / 'staged/opencode', source / 'opencode')
    helper = 'opencode_fake_probe.py' if fake else 'opencode_version_probe.py'
    shutil.copyfile(HERE / helper, source / 'probe.py')
    if fake:
        (source / 'scenario.json').write_text(json.dumps({'scenario': scenario}), encoding='utf-8')
        if bundle_id is not None:
            selected = source / 'bundle-workspace'
            selected.mkdir()
            shutil.copyfile(task_bundle.ROOT / bundle_id / 'workspace/example.py', selected / 'example.py')
            (source / 'bundle-task.json').write_text(json.dumps({'task': manifest['task']}), encoding='utf-8')
        for module in ('http_rehearsal.py', 'request_gate.py'):
            shutil.copyfile(HERE / module, source / module)
    libraries, runtime = stage_opencode_runtime.prepare()
    shutil.copytree(libraries, source / 'libs')
    kind = 'opencode-fake-only' if fake else 'opencode-version-only'
    name = 'copilot-' + kind + '-' + session.name
    args = ['create', '--name', name, '--label', 'local-copilot.kind=' + kind, '--pull=never', '--platform', 'linux/amd64',
            '--runtime', 'runc', '--network', 'none', '--cpus', '0.5', '--memory', '512m',
            '--memory-swap', '512m', '--pids-limit', '64', '--read-only', '--user', '65532:65532',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--restart', 'no',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--log-driver', 'json-file',
            '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
            '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--env', 'HOME=/tmp/home',
            '--env', 'LD_LIBRARY_PATH=/input/libs',
            '--env', 'OPENCODE_DISABLE_AUTOUPDATE=true', '--env', 'OPENCODE_DISABLE_MODELS_FETCH=true',
            '--mount', f'type=bind,source={source},target=/input,readonly',
            '--entrypoint', 'python', IMAGE, '-B', '/input/probe.py']
    receipt = {'mode': kind, 'container': name, 'image': IMAGE,
               'bundleRunId': bundle_id,
               'binarySha256': stage.sha(source / 'opencode'), 'modelEnabled': False,
               'network': 'none', 'gpuRequested': False, 'cleanupConfirmed': False,
               'runtimeLibraries': runtime['libraries']}
    created = False
    try:
        docker(*args)
        created = True
        info = json.loads(docker('inspect', name))[0]
        validate(info, name, source, kind)
        docker('start', name)
        receipt['containerExitCode'] = int(docker('wait', name, timeout=15).strip())
        info = json.loads(docker('inspect', name))[0]
        receipt['oomKilled'] = info['State']['OOMKilled']
        logs = docker('logs', name)
        receipt['probe'] = json.loads(logs)
        if not fake:
            receipt['versionMatched'] = (receipt['probe'].get('exitCode') == 0 and
                                         receipt['probe'].get('stdout', '').strip() == 'opencode v' + stage.VERSION)
    finally:
        if created:
            info = json.loads(docker('inspect', name))[0]
            validate(info, name, source, kind)
            docker('rm', '--force', name)
            receipt['cleanupConfirmed'] = not docker('ps', '-a', '--filter', 'name=^/' + name + '$',
                                                    '--format', '{{.ID}}').strip()
        (session / 'result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--execute-version-only', action='store_true')
    parser.add_argument('--execute-fake-only', action='store_true')
    parser.add_argument('--scenario', choices=('reply', 'edit', 'deny-shell', 'deny-external', 'deny-file-write'), default='reply')
    args = parser.parse_args()
    if args.execute_version_only == args.execute_fake_only:
        parser.error('Choose exactly one explicit probe: --execute-version-only or --execute-fake-only')
    result = run(args.artifact, fake=args.execute_fake_only, scenario=args.scenario)
    print(json.dumps(result, indent=2))
    passed = result['probe'].get('compatibilityPassed') if args.execute_fake_only else result.get('versionMatched')
    raise SystemExit(0 if passed and result['cleanupConfirmed'] else 2)
