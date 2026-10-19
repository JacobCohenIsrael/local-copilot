"""Prove read-only root and tiny tmpfs quota using a harmless cached Python image."""
import argparse
import json
from pathlib import Path
import uuid

import build_guard

ROOT = build_guard.base.ROOT / '.runtime/offline-quota'
FIXTURE = '''import errno, json, os, signal, subprocess
signal.alarm(4)
subprocess.run(['/bin/sh', '-n', '/input/compile_offline.sh'], check=True, timeout=1)
readonly = False
try:
    open('/tmp/readonly-proof', 'wb').write(b'x')
except OSError as error:
    readonly = error.errno == errno.EROFS
count = 0
full = False
fd = os.open('/quota/proof', os.O_WRONLY | os.O_CREAT, 0o600)
try:
    for _ in range(32):
        count += os.write(fd, b'x' * 4096)
except OSError as error:
    full = error.errno == errno.ENOSPC
finally:
    os.close(fd)
print(json.dumps({'readonlyRoot': readonly, 'quotaEnforced': full, 'shellSyntaxChecked': True,
                  'writtenBytes': count, 'modelStarted': False}), flush=True)
raise SystemExit(0 if readonly and full and 0 < count <= 65536 else 3)
'''


def verify():
    session = ROOT / uuid.uuid4().hex
    inputs = session / 'input'
    inputs.mkdir(parents=True)
    (inputs / 'fixture.py').write_text(FIXTURE, encoding='utf-8')
    (inputs / 'compile_offline.sh').write_bytes(Path(__file__).with_name('compile_offline.sh').read_bytes().replace(b'\r\n', b'\n'))
    name = 'copilot-offline-quota-' + session.name
    docker = build_guard.base.Docker()
    image = build_guard.base.IMAGE
    args = ['create', '--name', name, '--label', 'local-copilot.kind=offline-quota-rehearsal',
            '--label', 'local-copilot.session=' + session.name, '--platform', 'linux/amd64',
            '--pull=never', '--runtime', 'runc', '--network', 'none', '--read-only',
            '--cpus', '0.5', '--memory', '64m', '--memory-swap', '64m', '--pids-limit', '16',
            '--user', '65532:65532', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--restart', 'no', '--log-driver', 'json-file', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
            '--tmpfs', '/quota:rw,noexec,nosuid,nodev,size=65536,mode=1777',
            '--mount', f'type=bind,source={inputs},target=/input,readonly',
            '--entrypoint', '/usr/local/bin/python3', image, '-I', '-B', '/input/fixture.py']
    result = {'version': 1, 'passed': False, 'cleanupComplete': False, 'compilerStarted': False,
              'modelStarted': False, 'imagePulled': False}
    owned_id = None
    try:
        docker.call('image', 'inspect', image)
        owned_id = docker.call(*args).strip()
        def inspect():
            info = docker.inspect(name)
            if info is not None:
                host, config = info['HostConfig'], info['Config']
                if (info['Id'] != owned_id or info['Name'] != '/' + name or config['Image'] != image or
                        config['Labels'].get('local-copilot.session') != session.name or
                        config['Labels'].get('local-copilot.kind') != 'offline-quota-rehearsal' or
                        host['Runtime'] != 'runc' or not host['ReadonlyRootfs'] or host['NetworkMode'] != 'none' or
                        host.get('DeviceRequests') or host.get('Devices') or host['Memory'] != 67108864 or
                        host['MemorySwap'] != 67108864 or host['NanoCpus'] != 500000000 or host['PidsLimit'] != 16 or
                        host['Privileged'] or host.get('PortBindings') or 'ALL' not in host.get('CapDrop', []) or
                        config['User'] != '65532:65532' or host['RestartPolicy']['Name'] != 'no' or
                        host.get('Tmpfs') != {'/quota': 'rw,noexec,nosuid,nodev,size=65536,mode=1777'} or
                        config['Entrypoint'] != ['/usr/local/bin/python3'] or config['Cmd'] != ['-I', '-B', '/input/fixture.py'] or
                        {(m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW']) for m in info['Mounts'] if m['Type'] == 'bind'} !=
                        {(str(inputs).replace('\\', '/').lower(), '/input', False)}):
                    raise ValueError('Quota fixture identity/resource mismatch; refusing control')
            return info
        inspect()
        output = docker.call('start', '--attach', owned_id, timeout=6)
        if len(output) > 4096:
            raise ValueError('Quota proof output exceeds limit')
        proof = json.loads(output)
        info = inspect()
        if (info is None or info['State']['Running'] or info['State'].get('OOMKilled') or
                info['State']['ExitCode'] != 0 or not proof['readonlyRoot'] or not proof['quotaEnforced'] or
                not 0 < proof['writtenBytes'] <= 65536):
            raise ValueError('Quota proof failed')
        result.update(passed=True, proof=proof)
    finally:
        if owned_id is not None:
            info = inspect()
            if info is not None:
                docker.call('rm', '--force', owned_id)
            if inspect() is not None:
                raise ValueError('Quota fixture cleanup not confirmed')
            result['cleanupComplete'] = True
        build_guard.base.atomic(session / 'result.json', result)
    print(json.dumps({'session': str(session), **result}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.parse_args()
    verify()
