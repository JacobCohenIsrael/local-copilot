"""Private engine capsule contract and owned Docker controls; no live CLI.

The capsule consumes a separately qualified block device and runtime. It never
mounts Desktop's socket/data root, pulls an image, or creates an image container.
Admission/guest-device mapping/runtime staging are deliberately separate.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re

import build_guard

GIB = 1024**3
CAPS = ('CHOWN', 'DAC_OVERRIDE', 'FOWNER', 'KILL', 'SETGID', 'SETUID', 'SETFCAP', 'SYS_ADMIN')
TMPFS = {'/run': 'rw,noexec,nosuid,nodev,size=67108864,mode=0755',
         '/tmp': 'rw,noexec,nosuid,nodev,size=65536,mode=1777',
         '/store': 'rw,noexec,nosuid,nodev,size=4096,mode=0755',
         '/exec': 'rw,exec,nosuid,nodev,size=268435456,mode=0700'}


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('sha256:[0-9a-f]{64}', value):
        raise ValueError('ISOLATED_IMAGE_ID_INVALID')
    return value


@dataclass(frozen=True)
class Spec:
    session: str
    image_id: str
    control: str
    runtime: str
    device: str
    review_sha: str = ''

    def __post_init__(self):
        if not re.fullmatch('[0-9a-f]{32}', self.session):
            raise ValueError('ISOLATED_SESSION_INVALID')
        digest(self.image_id)
        for path in (self.control, self.runtime):
            if not Path(path).is_absolute() or any(ch in path for ch in (',', '\n', '\r', '"')):
                raise ValueError('ISOLATED_BIND_PATH_INVALID')
        if not re.fullmatch('/dev/sd[a-z]{1,2}', self.device):
            raise ValueError('ISOLATED_DEVICE_PATH_INVALID')
        if self.review_sha and not re.fullmatch('[0-9a-f]{64}', self.review_sha):
            raise ValueError('ISOLATED_REVIEW_SHA_INVALID')

    @property
    def name(self):
        return 'copilot-isolated-' + self.session

    @property
    def labels(self):
        return {'local-copilot.kind': 'isolated-engine', 'local-copilot.session': self.session}


def create_args(spec):
    args = ['create', '--name', spec.name, '--platform', 'linux/amd64', '--pull=never',
        '--runtime', 'runc', '--cpus', '1', '--memory', str(4 * GIB), '--memory-swap', str(4 * GIB),
        '--pids-limit', '128', '--cgroupns', 'private', '--read-only', '--network', 'none',
        '--ipc', 'private', '--user', '0:0', '--restart', 'no', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--security-opt', 'apparmor=unconfined',
        '--shm-size', '65536', '--log-driver', 'json-file', '--log-opt', 'max-size=128k',
        '--log-opt', 'max-file=2', '--stop-timeout', '5',
        '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--no-healthcheck',
        '--device', spec.device + ':/dev/copilot-store:rw',
        '--mount', f'type=bind,source={spec.control},target=/control,readonly',
        '--mount', f'type=bind,source={spec.runtime},target=/runtime,readonly',
        '--workdir', '/run', '--entrypoint', '/usr/local/bin/python3']
    for cap in CAPS:
        args.extend(['--cap-add', cap])
    for path, options in TMPFS.items():
        args.extend(['--tmpfs', path + ':' + options])
    for key, value in spec.labels.items():
        args.extend(['--label', key + '=' + value])
    if spec.review_sha:
        args.extend(['--env', 'COPILOT_REVIEW_SHA256=' + spec.review_sha])
    return [*args, spec.image_id, '-I', '-B', '/control/isolated_agent.py']


def daemon_configuration():
    # Explicit standalone containerd prevents accidental Desktop socket reuse.
    return {'data-root': '/store/docker', 'exec-root': '/run/copilot/docker',
        'pidfile': '/run/copilot/dockerd.pid', 'hosts': ['unix:///run/copilot/docker.sock'],
        'containerd': '/run/copilot/containerd.sock', 'containerd-namespace': 'copilot',
        'containerd-plugins-namespace': 'copilot-plugins',
        'features': {'containerd-snapshotter': True},
        'bridge': 'none', 'iptables': False, 'ip6tables': False, 'ip-forward': False,
        'ip-masq': False, 'userland-proxy': False, 'live-restore': False,
        'log-driver': 'none', 'shutdown-timeout': 5, 'cdi-spec-dirs': ['/control/empty-cdi']}


def containerd_configuration():
    return '''version = 3
root = "/store/containerd"
state = "/run/copilot/containerd"
temp = "/store/tmp/containerd"
[grpc]
  address = "/run/copilot/containerd.sock"
'''


def validate_cgroup(values):
    expected = {'cpu.max': '100000 100000', 'memory.max': str(4 * GIB),
                'memory.swap.max': '0', 'pids.max': '128'}
    if values != expected:
        raise ValueError('ISOLATED_EFFECTIVE_CGROUP_INVALID')
    return True


def validate_mounts(rows, device, logical_bytes, *, visible_store_device):
    """Check decoded mountinfo tuples, not untrusted path prefixes."""
    by_path = {}
    for row in rows:
        if row['path'] in by_path and row['path'] != '/store':
            raise ValueError('ISOLATED_DUPLICATE_MOUNT')
        by_path.setdefault(row['path'], []).append(row)
    for path in ('/', '/control', '/runtime'):
        if path not in by_path or 'ro' not in by_path[path][0]['options']:
            raise ValueError('ISOLATED_READONLY_MOUNT_REQUIRED')
    candidates = [r for r in by_path.get('/store', []) if r.get('fstype') == 'ext4']
    if len(candidates) != 1:
        raise ValueError('ISOLATED_STORE_MOUNT_INVALID')
    store = candidates[0]
    if (len(by_path['/store']) > 2 or
            any(r is not store and r.get('fstype') != 'tmpfs' for r in by_path['/store']) or
            visible_store_device != device or store.get('root') != '/' or store.get('device') != device or
            'rw' not in store.get('options', ()) or
            any(r['path'].startswith('/store/') for r in rows) or
            type(logical_bytes) is not int or logical_bytes not in (128 * 1024**2, 32 * GIB)):
        raise ValueError('ISOLATED_STORE_MOUNT_INVALID')
    return True


class Capsule:
    """Own by immutable full ID. Isolation drift must not prevent owned stopping."""
    def __init__(self, spec, container_id, docker):
        if not re.fullmatch('[0-9a-f]{64}', container_id):
            raise ValueError('ISOLATED_FULL_CONTAINER_ID_REQUIRED')
        self.spec, self.id, self.docker = spec, container_id, docker

    def identity(self):
        row = self.docker.inspect(self.id)
        if (row is None or row.get('Id') != self.id or row.get('Name') != '/' + self.spec.name or
                row.get('Image') != self.spec.image_id or
                any(row.get('Config', {}).get('Labels', {}).get(k) != v for k, v in self.spec.labels.items())):
            raise ValueError('ISOLATED_CONTAINER_OWNERSHIP_LOST')
        return row

    def inspect(self):
        row = self.identity()
        config, host = row['Config'], row['HostConfig']
        expected = {'NanoCpus': 1000000000, 'Memory': 4 * GIB, 'MemorySwap': 4 * GIB,
            'PidsLimit': 128, 'Runtime': 'runc', 'ReadonlyRootfs': True,
            'NetworkMode': 'none', 'IpcMode': 'private', 'CgroupnsMode': 'private',
            'Privileged': False, 'ShmSize': 65536, 'Tmpfs': TMPFS,
            'LogConfig': {'Type': 'json-file', 'Config': {'max-size': '128k', 'max-file': '2'}}}
        mounts = sorted((m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW'])
                        for m in row['Mounts'] if m['Type'] == 'bind')
        wanted = sorted((p.replace('\\', '/').lower(), dest, False)
                        for p, dest in ((self.spec.control, '/control'), (self.spec.runtime, '/runtime')))
        if (any(host.get(k) != v for k, v in expected.items()) or mounts != wanted or
                any(m['Type'] != 'bind' and not (m['Type'] == 'tmpfs' and m['Destination'] in TMPFS)
                    for m in row['Mounts']) or
                set(host.get('CapDrop') or []) != {'ALL'} or set(host.get('CapAdd') or []) != set(CAPS) or
                set(host.get('SecurityOpt') or []) != {'no-new-privileges', 'apparmor=unconfined'} or
                host.get('Devices') != [{'PathOnHost': self.spec.device,
                    'PathInContainer': '/dev/copilot-store', 'CgroupPermissions': 'rw'}] or
                any(host.get(k) for k in ('DeviceRequests', 'DeviceCgroupRules', 'Binds', 'VolumesFrom',
                    'PortBindings', 'PublishAllPorts', 'PidMode', 'UTSMode', 'GroupAdd', 'Links')) or
                host.get('RestartPolicy', {}).get('Name') != 'no' or
                config.get('Image') != self.spec.image_id or config.get('User') != '0:0' or
                config.get('Entrypoint') != ['/usr/local/bin/python3'] or
                config.get('Cmd') != ['-I', '-B', '/control/isolated_agent.py'] or
                config.get('WorkingDir') != '/run' or config.get('Volumes') or
                'NVIDIA_VISIBLE_DEVICES=void' not in config.get('Env', []) or
                (self.spec.review_sha and 'COPILOT_REVIEW_SHA256=' + self.spec.review_sha not in config.get('Env', [])) or
                config.get('Healthcheck', {}).get('Test') != ['NONE']):
            raise ValueError('ISOLATED_CAPSULE_CONFIGURATION_CHANGED')
        return row

    def start(self):
        if self.inspect()['State'].get('Status') != 'created':
            raise ValueError('ISOLATED_CAPSULE_NOT_FRESH')
        self.docker.call('start', self.id, timeout=5)

    @staticmethod
    def stopped(row):
        state = row['State']
        return (state.get('Running') is False and state.get('Restarting') is False and
                type(state.get('Pid')) is int and state['Pid'] == 0 and
                state.get('Status') == 'exited' and type(state.get('ExitCode')) is int)

    def stop(self):
        """Never reread policy/config on emergency stop; ownership still required."""
        errors = []
        try:
            if self.stopped(self.identity()):
                return {'stopConfirmed': True, 'forced': False, 'errors': []}
            try:
                self.docker.call('stop', '--time', '5', self.id, timeout=6)
            except (ValueError, OSError, RuntimeError, build_guard.base.subprocess.SubprocessError):
                errors.append('GRACEFUL_STOP_FAILED')
            if self.stopped(self.identity()):
                return {'stopConfirmed': True, 'forced': False, 'errors': errors}
            self.docker.call('kill', '--signal', 'KILL', self.id, timeout=5)
            # Docker exit is only the outer namespace's proof. The guest lease
            # and native mount/device cleanup proof are additionally required.
            return {'stopConfirmed': self.stopped(self.identity()), 'forced': True, 'errors': errors}
        except (ValueError, OSError, RuntimeError, build_guard.base.subprocess.SubprocessError):
            return {'stopConfirmed': False, 'forced': True, 'errors': [*errors, 'STOP_UNCONFIRMED']}
