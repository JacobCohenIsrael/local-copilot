"""Freeze an offline proposal's inspect contract. No workload start authority."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

import offline_build_plan as offline


def binds(rows):
    return sorted((str(source).replace('\\', '/').lower(), destination, False)
                  for source, destination in rows)


def host_profile(*, fixture=False):
    return {
        'NanoCpus': 500000000 if fixture else 1000000000,
        'Memory': 67108864 if fixture else 4294967296,
        'MemorySwap': 67108864 if fixture else 4294967296,
        'PidsLimit': 16 if fixture else 128, 'Runtime': 'runc',
        'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Privileged': False,
        'ShmSize': offline.SHM_BYTES,
        'Tmpfs': {'/work': 'rw,noexec,nosuid,nodev,size=65536,mode=1777'} if fixture else {
            '/work': f'rw,nosuid,nodev,size={offline.WORK_BYTES},mode=1777',
            '/tmp': f'rw,noexec,nosuid,nodev,size={offline.TMP_BYTES},mode=1777'},
        'LogConfig': {'Type': 'json-file', 'Config': {
            'max-size': '64k' if fixture else '1m', 'max-file': '1' if fixture else '2'}}}


@dataclass(frozen=True)
class Target:
    container_id: str
    contract_json: str  # Immutable snapshot: stop never rereads approvals/manifests.
    plan_sha256: str
    metadata_sha256: str
    synthetic: bool = False

    def __post_init__(self):
        if any(not re.fullmatch('[0-9a-f]{64}', value)
               for value in (self.container_id, self.plan_sha256, self.metadata_sha256)):
            raise ValueError('Full immutable container/hash identities required')

    def inspect(self, docker):
        info = docker.inspect(self.container_id)
        if info is None:
            return None
        expected = json.loads(self.contract_json)
        config, host = info['Config'], info['HostConfig']
        actual_binds = sorted((m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW'])
                              for m in info['Mounts'] if m['Type'] == 'bind')
        other_mounts_ok = all(m['Type'] == 'bind' or (
            m['Type'] == 'tmpfs' and m['Destination'] in expected['host']['Tmpfs']) for m in info['Mounts'])
        if not all((
                info['Id'] == self.container_id, info['Name'] == '/' + expected['name'],
                'imageId' not in expected or info.get('Image') == expected['imageId'] or
                (expected.get('alternateImageId') is not None and info.get('Image') == expected['alternateImageId']),
                config['Image'] == expected['image'], config['User'] == '65532:65532',
                config['Entrypoint'] == expected['entrypoint'], config['Cmd'] == expected['command'],
                config['WorkingDir'] == '/work', 'NVIDIA_VISIBLE_DEVICES=void' in config.get('Env', []),
                all(config.get('Labels', {}).get(k) == v for k, v in expected['labels'].items()),
                all(host.get(k) == v for k, v in expected['host'].items()),
                host['RestartPolicy']['Name'] == 'no', set(host.get('CapDrop') or []) == {'ALL'},
                not host.get('CapAdd'), set(host.get('SecurityOpt') or []) == {'no-new-privileges'},
                not host.get('Devices'), not host.get('DeviceRequests'), not host.get('DeviceCgroupRules'),
                not host.get('PortBindings'), not host.get('PublishAllPorts'), not host.get('GroupAdd'),
                not host.get('PidMode'), not host.get('UTSMode'), host.get('IpcMode') == 'private',
                not host.get('Binds'), actual_binds == [tuple(row) for row in expected['binds']], other_mounts_ok)):
            raise ValueError('Offline target identity/isolation changed; refusing control')
        return info

    def matcher(self, docker, _spec):
        return self.inspect(docker)


def from_proposal(directory, plan_sha256, container_id):
    """Read/verify disabled proposal once; retain immutable emergency-stop contract."""
    directory = Path(directory)
    plan = offline.checked_proposal(directory, plan_sha256)
    source = Path(plan['sourcePackage']) / 'input/source'
    args = plan['createArgs']
    import image_plan
    contract = {'name': args[args.index('--name') + 1],
                'image': args[args.index('--entrypoint') + 2],
                'imageId': image_plan.metadata()['configDigest'],
                'alternateImageId': image_plan.metadata()['image'].split('@', 1)[1],
                'entrypoint': ['/usr/bin/timeout'],
                'command': ['--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile_offline.sh'],
                'labels': {'local-copilot.kind': 'offline-strata-build-proposal'},
                'host': host_profile(),
                'binds': binds([(source, '/source'), (Path(plan['toolDirectory']) / 'tools', '/tools'),
                                (directory / 'input', '/input')])}
    return Target(container_id, json.dumps(contract, sort_keys=True), plan_sha256, plan['inputHashes']['BUILD.json'])
