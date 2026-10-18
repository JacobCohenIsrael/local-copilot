"""Admitted empty-engine native canary inside a private Docker PID namespace."""
import ctypes
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import threading
import time

import isolated_agent as agent

SCOPE = 'one-small-empty-store-engine-canary-no-image-import'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def approved(packet, decision):
    digest = hashlib.sha256(canonical(packet)).hexdigest()
    if (type(decision.get('version')) is not int or decision['version'] != 1 or
            decision.get('status') != 'owner-approved-one-native-isolation-canary' or
            decision.get('reviewSha256') != digest or decision.get('scope') != SCOPE or
            decision.get('nativeRehearsalEnabled') is not True or decision.get('maximumAttempts') != 1 or
            type(decision.get('maximumAttempts')) is not int or decision.get('synthetic') is not False or
            decision.get('sourceEvidenceSha256') != packet['sourceEvidenceSha256'] or
            decision.get('acceptSourceLimitation') != packet['acceptSourceLimitation'] or
            decision.get('thermalPolicySha256') != hashlib.sha256(canonical(packet['thermalPolicy'])).hexdigest() or
            decision.get('acceptUnknownThrottleForThisScope') is not True or
            decision.get('acceptCapsulePrivilegesSha256') != hashlib.sha256(canonical(packet['capsulePrivileges'])).hexdigest() or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip() or
            any(decision.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('NATIVE_CANARY_APPROVAL_INVALID')
    return digest


def inputs():
    packet = json.loads(agent.bounded('/control/review.json', 131072))
    decision = json.loads(agent.bounded('/control/approval.json', 16384))
    digest = approved(packet, decision)
    if os.environ.get('COPILOT_REVIEW_SHA256') != digest:
        raise ValueError('GUEST_REVIEW_BINDING_INVALID')
    for name in ('isolated_agent.py', 'isolated_guest.py'):
        raw = agent.bounded('/control/' + name, 131072).replace(b'\r\n', b'\n')
        expected = packet['helperSha256']['containers/strata-proposal/' + name]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('GUEST_HELPER_CHANGED')
    launch = json.loads(agent.bounded('/control/launch.json', 8192))
    if launch['reviewSha256'] != digest or launch['sessionId'] != packet['sessionId'] or launch['logicalBytes'] != 134217728:
        raise ValueError('GUEST_LAUNCH_INVALID')
    raw = agent.bounded('/control/runtime.json', 65536)
    if hashlib.sha256(raw).hexdigest() != packet['runtime']['manifestSha256']:
        raise ValueError('GUEST_RUNTIME_MANIFEST_CHANGED')
    runtime = json.loads(raw)
    if (json.loads(agent.bounded('/control/dockerd.json', 16384)) != packet['daemonConfiguration'] or
            agent.bounded('/control/containerd.toml', 16384).decode() != packet['containerdConfiguration']):
        raise ValueError('GUEST_ENGINE_CONFIGURATION_CHANGED')
    return packet, launch, runtime


def envelope():
    expected = {'cpu.max': '100000 100000', 'memory.max': '4294967296', 'memory.swap.max': '0', 'pids.max': '128'}
    if agent.cgroup_values() != expected:
        raise ValueError('GUEST_RESOURCE_ENVELOPE_INVALID')
    memory = agent.bounded('/proc/meminfo').decode()
    swap = [int(r.split()[1]) for r in memory.splitlines() if r.startswith('SwapTotal:')]
    if swap != [0] or sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo']:
        raise ValueError('GUEST_SWAP_OR_NETWORK_INVALID')
    if any(Path('/dev').glob('nvidia*')) or Path('/dev/dxg').exists() or Path('/dev/dri').exists():
        raise ValueError('GUEST_GPU_DEVICE_PRESENT')
    rows = agent.mount_rows(agent.bounded('/proc/self/mountinfo'))
    for name in ('/', '/control', '/runtime', '/sys/fs/cgroup'):
        found = [r for r in rows if r['path'] == name]
        if len(found) != 1 or 'ro' not in found[0]['options']:
            raise ValueError('GUEST_READONLY_ROOT_REQUIRED')
    validate_tmpfs(rows)
    return expected


def validate_tmpfs(rows):
    for name, cap in {'/exec': 268435456, '/run': 67108864, '/tmp': 65536, '/store': 4096, '/dev/shm': 65536}.items():
        found = [r for r in rows if r['path'] == name]
        if len(found) != 1 or found[0]['fstype'] != 'tmpfs':
            raise ValueError('GUEST_TMPFS_REQUIRED')
        row = found[0]
        sizes = [v[5:] for v in row['superOptions'] if v.startswith('size=')]
        match = re.fullmatch(r'([0-9]+)([kmg]?)', sizes[0]) if len(sizes) == 1 else None
        if (match is None or int(match[1]) * {'': 1, 'k': 1024, 'm': 1024**2, 'g': 1024**3}[match[2]] != cap or
                not {'rw', 'nosuid', 'nodev'}.issubset(row['options']) or
                (('noexec' in row['options']) != (name != '/exec'))):
            raise ValueError('GUEST_TMPFS_ENVELOPE_INVALID')


def copy_runtime(runtime, check):
    total = 0
    for relative, expected in runtime['files'].items():
        if (PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts or
                not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', relative)):
            raise ValueError('GUEST_RUNTIME_PATH')
        total += expected['bytes']
        if total > 256 * 1024**2:
            raise ValueError('GUEST_RUNTIME_BYTE_LIMIT')
        source, target = Path('/runtime') / relative, Path('/exec') / relative
        for parent in (source, *source.parents):
            if parent.is_symlink():
                raise ValueError('GUEST_RUNTIME_LINK')
        if source.stat().st_nlink != 1 or source.stat().st_size != expected['bytes']:
            raise ValueError('GUEST_RUNTIME_INPUT_CHANGED')
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, count = hashlib.sha256(), 0
        with source.open('rb') as incoming, target.open('xb') as output:
            while True:
                check()
                raw = incoming.read(min(65536, expected['bytes'] - count + 1))
                if not raw:
                    break
                count += len(raw)
                if count > expected['bytes']:
                    raise ValueError('GUEST_RUNTIME_SIZE_CHANGED')
                digest.update(raw)
                output.write(raw)
        if count != expected['bytes'] or digest.hexdigest() != expected['sha256']:
            raise ValueError('GUEST_RUNTIME_HASH_CHANGED')
        target.chmod(0o555 if relative.startswith(('elf/', 'bin/')) or relative == runtime['loader'] else 0o444)
    for name, relative in runtime['commands'].items():
        check()
        if name in runtime['staticCommands']:
            continue
        probe = subprocess.run(['/exec/' + runtime['loader'], '--library-path', '/exec/lib', '--list', '/exec/' + relative],
                               capture_output=True, check=True, timeout=3)
        if len(probe.stdout) + len(probe.stderr) > 16384:
            raise ValueError('GUEST_LOADER_OUTPUT_LIMIT')
        for line in probe.stdout.decode().splitlines():
            paths = re.findall(r'(?<!\S)(/[^\s]+)', line)
            if any(not path.startswith('/exec/') for path in paths):
                raise ValueError('GUEST_LOADER_ESCAPES_RUNTIME')
    Path('/exec/.qualified').write_bytes(b'qualified-for-this-canary-only')


class UnixApi(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(1)
        self.sock.connect('/run/copilot/docker.sock')


def engine_info():
    connection = UnixApi('localhost', timeout=1)
    try:
        connection.request('GET', '/info')
        response = connection.getresponse()
        raw = response.read(65537)
        if response.status != 200 or len(raw) > 65536:
            raise ValueError('GUEST_ENGINE_INFO_INVALID')
        value = json.loads(raw)
        if (value.get('DockerRootDir') != '/store/docker' or value.get('Images') != 0 or
                value.get('Containers') != 0 or value.get('Containerd', {}).get('Address') != '/run/copilot/containerd.sock' or
                value.get('OSType') != 'linux' or value.get('Architecture') not in ('x86_64', 'amd64')):
            raise ValueError('GUEST_PRIVATE_ENGINE_IDENTITY_INVALID')
        return {'DockerRootDir': value['DockerRootDir'], 'Images': 0, 'Containers': 0,
                'containerdSocket': value['Containerd']['Address'], 'ServerVersion': value.get('ServerVersion')}
    finally:
        connection.close()


def run():
    if sys.platform != 'linux' or os.getpid() != 1:
        raise ValueError('GUEST_PRIVATE_PID_ONE_REQUIRED')
    packet, launch, runtime = inputs()
    limits = envelope()
    stopped, commands, device, mounted, fuse_fd = [False], [], None, False, None
    signal.signal(signal.SIGTERM, lambda *_: stopped.__setitem__(0, True))
    fuse_pid, fuse_fd = agent.namespace_fuse('/control/owner.pulse')
    reason, error, lease_ready = None, None, False
    logs, threads = [], []
    def check():
        nonlocal reason, lease_ready
        if select.select([fuse_fd], [], [], 0)[0]:
            data = os.read(fuse_fd, 4096)
            if b'B' in data:
                lease_ready = True
            if not data or any(byte in data for byte in (b'L', b'D', b'I')):
                reason = 'OWNER_LEASE_EXPIRED' if b'L' in data else 'GUEST_FUSE_FAULT'
        if stopped[0] or reason:
            raise ValueError(reason or 'HOST_CANCELLED')
    def start(name, args):
        check()
        process = subprocess.Popen([sys.executable, '-I', '-B', '/exec/launcher.py', name, *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True,
            env={'PATH': '/exec/bin:/usr/local/bin:/usr/bin:/bin', 'HOME': '/store/home', 'TMPDIR': '/store/tmp',
                 'MOBY_DISABLE_PIGZ': '1', 'NVIDIA_VISIBLE_DEVICES': 'void'})
        commands.append(process)
        output = bytearray()
        logs.append(output)
        def drain():
            while True:
                raw = process.stdout.read(4096)
                if not raw:
                    break
                if len(output) + len(raw) > 65536:
                    stopped[0] = True
                    break
                output.extend(raw)
        thread = threading.Thread(target=drain, daemon=True)
        thread.start(); threads.append(thread)
        return process
    proof = {'deviceToken': launch['deviceToken'], 'unmounted': False, 'exclusiveDeviceClaim': False,
             'enginesStopped': False, 'ready': False, 'fault': None, 'imageImportEnabled': False,
             'buildEnabled': False, 'modelLaunchEnabled': False}
    try:
        # A stale pulse from a previous/dead Windows owner cannot admit work:
        # require a new growth event after the guest fuse has been armed.
        while not lease_ready:
            check()
            time.sleep(.05)
        copy_runtime(runtime, check)
        device = agent.BlockDevice(bytes.fromhex(launch['markerHex']), launch['logicalBytes'])
        if device.sequence != launch['diskSequence'] or device.device != launch['majorMinor']:
            raise ValueError('GUEST_DEVICE_MAPPING_CHANGED')
        wrapper = lambda name: [sys.executable, '-I', '-B', '/exec/launcher.py', name]
        device.format(wrapper('mkfs.ext4'), packet['sessionId'])
        check()
        device.mount(wrapper('mount'))
        mounted = True
        for directory in ('docker', 'containerd', 'tmp', 'home'):
            (Path('/store') / directory).mkdir(mode=0o700)
        Path('/run/copilot').mkdir()
        start('containerd', ['--config', '/control/containerd.toml'])
        end = time.monotonic() + 10
        while not Path('/run/copilot/containerd.sock').exists():
            check()
            if time.monotonic() > end or any(p.poll() is not None for p in commands):
                raise ValueError('GUEST_CONTAINERD_START_FAILED')
            time.sleep(.05)
        start('dockerd', ['--config-file', '/control/dockerd.json'])
        end = time.monotonic() + 20
        while True:
            check()
            try:
                info = engine_info()
                break
            except (OSError, http.client.HTTPException):
                if time.monotonic() > end or any(p.poll() is not None for p in commands):
                    raise ValueError('GUEST_DOCKER_START_FAILED')
                time.sleep(.1)
        proof['ready'] = True
        print(json.dumps({'event': 'READY', 'deviceToken': launch['deviceToken'], 'limits': limits, 'engine': info}), flush=True)
        # The reviewed native test deliberately withholds this lease while the
        # Windows CPU monitor keeps running. No image API is exposed or called.
        while True:
            check()
            if any(p.poll() is not None for p in commands):
                raise ValueError('GUEST_ENGINE_EARLY_EXIT')
            time.sleep(.05)
    except BaseException as failure:
        error = str(failure) if re.fullmatch('[A-Z_]{1,80}', str(failure)) else type(failure).__name__
    finally:
        try:
            if fuse_fd is not None and select.select([fuse_fd], [], [], 0)[0]:
                if b'L' in os.read(fuse_fd, 4096):
                    reason = 'OWNER_LEASE_EXPIRED'
        except OSError:
            pass
        proof['fault'] = reason or error or 'GUEST_UNEXPECTED_COMPLETION'
        # Kill all namespace descendants (including escaped daemon sessions)
        # from PID 1; never from the Windows host or a shared PID namespace.
        os.kill(-1, signal.SIGKILL)
        end = time.monotonic() + 3
        for process in commands:
            try:
                process.wait(timeout=max(.01, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        others = ['unconfirmed']
        while time.monotonic() < end:
            try:
                while os.waitpid(-1, os.WNOHANG)[0] != 0:
                    pass
            except ChildProcessError:
                pass
            others = [p.name for p in Path('/proc').iterdir() if p.name.isdecimal() and p.name != '1']
            if not others:
                break
            time.sleep(.02)
        proof['enginesStopped'] = not others
        if device is not None:
            try:
                device.check()
                if mounted:
                    libc = ctypes.CDLL(None, use_errno=True)
                    libc.umount2.argtypes, libc.umount2.restype = [ctypes.c_char_p, ctypes.c_int], ctypes.c_int
                    if libc.umount2(b'/store', 0) != 0:
                        raise OSError(ctypes.get_errno(), 'GUEST_UNMOUNT_FAILED')
                proof['unmounted'] = True
                device.close()
                fd = os.open('/dev/copilot-store', os.O_RDONLY | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC)
                os.close(fd)
                proof['exclusiveDeviceClaim'] = True
            except (OSError, ValueError):
                proof['unmounted'] = False
        for thread in threads:
            thread.join(timeout=.1)
        proof['diagnostics'] = [bytes(value[-8192:]).decode(errors='replace') for value in logs]
        print(json.dumps({'event': 'STOPPED', **proof}), flush=True)
    return 0 if (proof['ready'] and proof['fault'] == 'OWNER_LEASE_EXPIRED' and
                 all(proof[k] for k in ('enginesStopped', 'unmounted', 'exclusiveDeviceClaim'))) else 3
