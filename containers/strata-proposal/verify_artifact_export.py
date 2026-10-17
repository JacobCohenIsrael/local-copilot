"""Synthetic cached-image export rehearsal only; no compiler/model launch path."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

import artifact_export as export
import build_guard

ROOT = build_guard.base.ROOT / '.runtime/artifact-export-rehearsals'
META = b'{"source":"synthetic-only","modelStarted":false}'
FIXTURE = r'''import signal, struct, sys, time
from pathlib import Path
signal.alarm(10)
engine = Path('/work/engine')
engine.mkdir()
def header(kind):
    data = bytearray(64)
    data[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', data, 16, kind, 62, 1)
    struct.pack_into('<H', data, 52, 64)
    return data
(engine / 'strata').write_bytes(header(2))
(engine / 'libstrata_kq.so').write_bytes(header(3))
(engine / 'BUILD.json').write_bytes(Path('/input/BUILD.json').read_bytes() if sys.argv[1] == 'success' else b'{}')
print('SYNTHETIC_OUTPUT_READY', flush=True)
while not Path('/work/export.complete').exists():
    time.sleep(.05)
print('EXPORT_ACK_OBSERVED', flush=True)
'''


def verify():
    session = ROOT / uuid.uuid4().hex
    inputs = session / 'input'
    inputs.mkdir(parents=True)
    (inputs / 'fixture.py').write_text(FIXTURE, encoding='utf-8')
    (inputs / 'BUILD.json').write_bytes(META)
    docker = build_guard.base.Docker()
    result = {'version': 1, 'passed': False, 'synthetic': True, 'compilerStarted': False,
              'modelStarted': False, 'imagePulled': False, 'cases': []}
    image = build_guard.base.IMAGE
    docker.call('image', 'inspect', image)  # pull=never below; never download a replacement.
    try:
        for scenario in ('success', 'wrong-metadata'):
            name = 'copilot-artifact-export-' + session.name + '-' + scenario
            args = ['create', '--name', name, '--label', 'local-copilot.kind=artifact-export-rehearsal',
                    '--label', 'local-copilot.session=' + session.name, '--platform', 'linux/amd64',
                    '--pull=never', '--runtime', 'runc', '--network', 'none', '--read-only',
                    '--cpus', '0.5', '--memory', '64m', '--memory-swap', '64m', '--pids-limit', '16',
                    '--user', '65532:65532', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                    '--restart', 'no', '--log-driver', 'json-file', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
                    '--env', 'NVIDIA_VISIBLE_DEVICES=void',
                    '--tmpfs', '/work:rw,noexec,nosuid,nodev,size=65536,mode=1777',
                    '--mount', f'type=bind,source={inputs},target=/input,readonly',
                    '--entrypoint', '/usr/local/bin/python3', image, '-I', '-B', '/input/fixture.py', scenario]
            owned_id = None
            row = {'scenario': scenario, 'cleanupComplete': False, 'passed': False}
            result['cases'].append(row)
            def inspect():
                info = docker.inspect(name)
                if info is None:
                    return None
                host, config = info['HostConfig'], info['Config']
                if (info['Id'] != owned_id or info['Name'] != '/' + name or config['Image'] != image or
                        config['Labels'].get('local-copilot.session') != session.name or
                        config['Labels'].get('local-copilot.kind') != 'artifact-export-rehearsal' or
                        host['Runtime'] != 'runc' or not host['ReadonlyRootfs'] or host['NetworkMode'] != 'none' or
                        host.get('DeviceRequests') or host.get('Devices') or host['Memory'] != 67108864 or
                        host['MemorySwap'] != 67108864 or host['NanoCpus'] != 500000000 or host['PidsLimit'] != 16 or
                        host['Privileged'] or host.get('PortBindings') or host.get('CapAdd') or
                        'ALL' not in host.get('CapDrop', []) or 'no-new-privileges' not in host.get('SecurityOpt', []) or
                        config['User'] != '65532:65532' or host['RestartPolicy']['Name'] != 'no' or
                        host.get('Tmpfs') != {'/work': 'rw,noexec,nosuid,nodev,size=65536,mode=1777'} or
                        config['Entrypoint'] != ['/usr/local/bin/python3'] or
                        config['Cmd'] != ['-I', '-B', '/input/fixture.py', scenario] or
                        {(m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW']) for m in info['Mounts'] if m['Type'] == 'bind'} !=
                        {(str(inputs).replace('\\', '/').lower(), '/input', False)}):
                    raise ValueError('Artifact fixture identity/resource mismatch')
                return info
            class Transport:
                def verify(self):
                    info = inspect()
                    return info is not None and info['State']['Running'] and not info['State'].get('OOMKilled')

                def copy(self, path, deadline):
                    export.capture_archive(owned_id, path, deadline)

                def acknowledge(self, deadline):
                    export.acknowledge_export(owned_id, deadline)
            try:
                owned_id = docker.call(*args).strip()
                if inspect() is None:
                    raise ValueError('Created fixture missing')
                docker.call('start', owned_id)
                ready_by = time.monotonic() + 3
                while 'SYNTHETIC_OUTPUT_READY' not in docker.call('logs', owned_id, timeout=1):
                    if time.monotonic() >= ready_by:
                        raise TimeoutError('Synthetic fixture did not become ready')
                    time.sleep(.05)
                try:
                    folder, receipt = export.collect(Transport(), container_id=owned_id,
                        plan_sha256=hashlib.sha256(FIXTURE.encode()).hexdigest(),
                        metadata_sha256=hashlib.sha256(META).hexdigest(), synthetic=True,
                        deadline=time.monotonic() + 5)
                    if scenario != 'success':
                        raise AssertionError('Bad metadata was accepted')
                    row.update(exportDirectory=str(folder), exportedBytes=sum(r['bytes'] for r in receipt['files']))
                except ValueError as error:
                    if scenario != 'wrong-metadata' or 'metadata differs' not in str(error):
                        raise
                    row['rejected'] = 'METADATA_MISMATCH'
                if scenario == 'success':
                    exit_code = docker.call('wait', owned_id, timeout=2).strip()
                    info = inspect()
                    logs = docker.call('logs', owned_id)
                    if exit_code != '0' or info['State']['Running'] or info['State'].get('OOMKilled') or 'EXPORT_ACK_OBSERVED' not in logs:
                        raise ValueError('Export acknowledgement/clean exit not confirmed')
                    row['ackObserved'] = True
                else:
                    info = inspect()
                    logs = docker.call('logs', owned_id)
                    if not info['State']['Running'] or 'EXPORT_ACK_OBSERVED' in logs:
                        raise ValueError('Failed export unexpectedly acknowledged or worker exited')
                    row['ackObserved'] = False
                row['passed'] = True
            finally:
                if owned_id is not None:
                    if inspect() is not None:
                        docker.call('rm', '--force', owned_id)
                    if inspect() is not None:
                        raise ValueError('Artifact fixture cleanup not confirmed')
                    row['cleanupComplete'] = True
                build_guard.base.atomic(session / 'result.json', result)
        result['passed'] = all(r['passed'] and r['cleanupComplete'] for r in result['cases'])
    finally:
        build_guard.base.atomic(session / 'result.json', result)
    print(json.dumps({'session': str(session), **result}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-only', action='store_true', required=True)
    parser.parse_args()
    verify()
