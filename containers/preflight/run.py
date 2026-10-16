"""Fixed, non-GPU diagnostic; deliberately cannot run Strata or arbitrary commands."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import uuid

IMAGE = 'docker.io/library/python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8'
DOCKER = r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path('D:/AI/strata-coder-iq1_m.json')
LABEL = 'local-copilot.kind=cpu-preflight'
SOURCE_FILES = [Path('D:/AI') / p for p in ('Dockerfile', 'docker-entrypoint.sh', 'run-coder-iq1_m.bat', 'strata-coder-iq1_m.json')]


def command(*args, timeout=30):
    return subprocess.run([DOCKER, *args], check=True, capture_output=True, text=True, timeout=timeout).stdout


def fingerprints():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE_FILES}


def model_paths(config):
    """Allow only the already identified paths; never pass an engine command through."""
    mounts = [
        ('D:/Strata-data/packs/coder-iq1_m', '/models/pack'),
        ('D:/Strata-data/models/coder-IQ1_M', '/models/gguf'),
        ('D:/Strata-data/mtp/rt', '/models/mtp'),
        ('D:/AI/data/expert-profile-coder.bin', '/models/expert-profile.bin'),
    ]
    def translate(value):
        source = PureWindowsPath(value)
        if '..' in source.parts or not source.is_absolute():
            raise ValueError('Model path must be absolute without traversal')
        for host, target in mounts:
            try:
                relative = source.relative_to(PureWindowsPath(host))
            except ValueError:
                continue
            return target + ('/' + relative.as_posix() if relative.parts else '')
        raise ValueError('Configured path is outside the explicitly allowed model mounts')
    paths = [{'role': 'tokenizer', 'container': translate(config['tokenizer'])}]
    args = config['args']
    for flag in ('--pack', '--native', '--ple-gguf', '--mtp', '--expert-profile'):
        if args.count(flag) != 1:
            raise ValueError('Expected exactly one ' + flag)
        paths.append({'role': flag, 'container': translate(args[args.index(flag) + 1])})
    paths.extend({'role': name, 'container': '/models/pack/' + name} for name in ('dense.bin', 'experts.bin'))
    return mounts, paths


def check_inspection(info, expected_mounts):
    hc = info['HostConfig']
    mounts = {(m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW']) for m in info['Mounts']}
    expected = {(str(h).replace('\\', '/').lower(), t, False) for h, t in expected_mounts}
    checks = [
        hc['Memory'] == 268435456, hc['MemorySwap'] == 268435456,
        hc['NanoCpus'] == 500000000, hc['PidsLimit'] == 32,
        hc['ReadonlyRootfs'], hc['NetworkMode'] == 'none', not hc['Privileged'],
        not hc.get('DeviceRequests'), not hc.get('Devices'), hc['Runtime'] == 'runc',
        hc['RestartPolicy']['Name'] == 'no', not hc.get('PortBindings'),
        hc['CapDrop'] == ['ALL'], not hc.get('CapAdd'),
        'no-new-privileges' in [s.split(':')[0] for s in hc['SecurityOpt']],
        info['Config']['User'] == '65534:65534',
        info['Config']['Entrypoint'] == ['/usr/local/bin/python3'],
        info['Config']['Cmd'] == ['-I', '-B', '/input/probe.py'],
        info['Config']['Labels'].get('local-copilot.kind') == 'cpu-preflight',
        mounts == expected,
    ]
    if not all(checks):
        raise ValueError('Created container failed isolation inspection; will not start')


def run(execute=False):
    session = uuid.uuid4().hex[:12]
    output = ROOT / '.runtime' / 'strata-preflight' / session
    stage = output / 'input'
    stage.mkdir(parents=True)
    before = fingerprints()
    mounts, paths = model_paths(json.loads(CONFIG.read_text()))
    mounts = [(str(Path(host).resolve()), target) for host, target in mounts]
    for host, _ in mounts:
        if not Path(host).exists():
            raise ValueError('Required mount is missing: ' + host)
    shutil.copyfile(Path(__file__).with_name('probe.py'), stage / 'probe.py')
    (stage / 'manifest.json').write_text(json.dumps({'paths': paths}, indent=2))
    mounts.append((str(stage.resolve()), '/input'))
    args = ['create', '--name', 'copilot-preflight-' + session, '--label', LABEL,
            '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
            '--cpus', '0.5', '--memory', '256m', '--memory-swap', '256m',
            '--pids-limit', '32', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '65534:65534',
            '--restart', 'no', '--env', 'NVIDIA_VISIBLE_DEVICES=void',
            '--entrypoint', '/usr/local/bin/python3']
    for host, target in mounts:
        args.extend(['--mount', f'type=bind,source={host},target={target},readonly'])
    args.extend([IMAGE, '-I', '-B', '/input/probe.py'])
    plan = {'kind': 'cpu-only-preflight', 'image': IMAGE, 'createArgs': args,
            'beforeFingerprints': before, 'paths': paths, 'runtimeDeadlineSeconds': 20,
            'liveStrataPolicyChanged': False}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2))
    print('Plan: ' + str(output / 'plan.json'), flush=True)
    if not execute:
        return
    container = None
    evidence = {'passed': False, 'containerRemoved': False}
    try:
        try:
            command('image', 'inspect', IMAGE)
        except subprocess.CalledProcessError:
            command('pull', '--platform', 'linux/amd64', IMAGE, timeout=180)
        container = command(*args).strip()
        info = json.loads(command('inspect', container))[0]
        (output / 'container-before.json').write_text(json.dumps(info, indent=2))
        check_inspection(info, mounts)
        stdout = command('start', '--attach', container, timeout=20)
        (output / 'probe.json').write_text(stdout)
        result = json.loads(stdout)
        state = json.loads(command('inspect', container))[0]['State']
        evidence.update({'probePassed': result['passed'], 'state': state,
                         'passed': result['passed'] and state['ExitCode'] == 0 and not state['OOMKilled']})
    except Exception as error:
        evidence['error'] = str(error)
        raise
    finally:
        try:
            if container:
                info = json.loads(command('inspect', container))[0]
                if info['Config']['Labels'].get('local-copilot.kind') != 'cpu-preflight':
                    raise RuntimeError('Refusing cleanup: container ownership label mismatch')
                command('rm', '--force', container)
                evidence['containerRemoved'] = True
        finally:
            evidence['afterFingerprints'] = fingerprints()
            evidence['originalFilesUnchanged'] = before == evidence['afterFingerprints']
            evidence['passed'] = evidence['passed'] and evidence['containerRemoved'] and evidence['originalFilesUnchanged']
            (output / 'result.json').write_text(json.dumps(evidence, indent=2))
            print('Result: ' + str(output / 'result.json'), flush=True)
    if not evidence['passed']:
        raise RuntimeError('Diagnostic did not pass; see result.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Run the fixed CPU-only diagnostic. Default: save plan only.')
    run(parser.parse_args().execute)
