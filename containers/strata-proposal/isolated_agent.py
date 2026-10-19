"""Linux device primitives and lease fuse for one exactly approved native canary."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import struct
import subprocess
import sys
import time
import uuid

MARKER_PREFIX = b'LOCAL-COPILOT-OWNED-VHDX-V1\0'


def device_marker(session, nonce):
    if type(nonce) is not bytes or len(nonce) != 32 or nonce == b'\0' * 32:
        raise ValueError('ISOLATED_MARKER_NONCE_INVALID')
    body = MARKER_PREFIX + uuid.UUID(hex=session).bytes + nonce
    return (body + hashlib.sha256(body).digest()).ljust(512, b'\0')


def validate_marker(raw):
    end = len(MARKER_PREFIX) + 48
    if (type(raw) is not bytes or len(raw) != 512 or not raw.startswith(MARKER_PREFIX) or
            raw[len(MARKER_PREFIX) + 16:end] == b'\0' * 32 or
            raw[end:end + 32] != hashlib.sha256(raw[:end]).digest() or
            raw[end + 32:] != b'\0' * (512 - end - 32)):
        raise ValueError('ISOLATED_DEVICE_MARKER_INVALID')
    return True


def bounded(path, maximum=65536):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        raw = bytearray()
        while len(raw) <= maximum:
            chunk = os.read(fd, min(4096, maximum + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > maximum:
            raise ValueError('ISOLATED_GUEST_METADATA_LIMIT')
        return bytes(raw)
    finally:
        os.close(fd)


def mount_rows(raw):
    if len(raw) > 65536:
        raise ValueError('ISOLATED_GUEST_METADATA_LIMIT')
    result = []
    for line in raw.decode('ascii').splitlines():
        left, right = line.split(' - ', 1)
        fields, fs = left.split(), right.split()
        result.append({'device': fields[2], 'root': fields[3], 'path': fields[4],
                       'options': fields[5].split(','), 'fstype': fs[0], 'superOptions': fs[2].split(',')})
    return result


def cgroup_values():
    return {name: bounded('/sys/fs/cgroup/' + name, 64).decode('ascii').strip()
            for name in ('cpu.max', 'memory.max', 'memory.swap.max', 'pids.max')}


def qualified_command(command, *, expected):
    # A qualified private loader prefix may be needed for bundled dynamic ELFs.
    if command in (['/usr/local/bin/python3', '-I', '-B', '/runtime/launcher.py', expected],
                   ['/usr/local/bin/python3', '-I', '-B', '/exec/launcher.py', expected]):
        return command
    if (not isinstance(command, list) or not 1 <= len(command) <= 8 or
            any(not isinstance(v, str) or not v or any(ch in v for ch in ('\n', '\r', '\0')) for v in command) or
            not command[0].startswith('/runtime/') or '..' in Path(command[0]).parts or
            len(command) not in (1, 4) or Path(command[-1]).name != expected or
            not command[-1].startswith('/runtime/') or '..' in Path(command[-1]).parts):
        raise ValueError('ISOLATED_RUNTIME_COMMAND_INVALID')
    if len(command) == 4 and (command[1] != '--library-path' or
            not Path(command[0]).name.startswith('ld-') or
            any(not p.startswith('/runtime/') or '..' in Path(p).parts for p in command[2].split(':'))):
        raise ValueError('ISOLATED_RUNTIME_COMMAND_INVALID')
    return command


class BlockDevice:
    """Require host-written nonce, exact capacity and stable kernel disk sequence.

    A pathname or new sdX name alone never authorizes formatting.
    """
    def __init__(self, expected_marker, expected_bytes):
        if (type(expected_marker) is not bytes or len(expected_marker) != 512 or
                type(expected_bytes) is not int or expected_bytes not in (128 * 1024**2, 32 * 1024**3)):
            raise ValueError('ISOLATED_DEVICE_PROOF_INVALID')
        validate_marker(expected_marker)
        import fcntl
        self.ioctl, self.fd = fcntl.ioctl, None
        try:
            self.fd = os.open('/dev/copilot-store', os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            info = os.fstat(self.fd)
            if not stat.S_ISBLK(info.st_mode):
                raise ValueError('ISOLATED_DEVICE_NOT_BLOCK')
            self.device = f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
            self.identity, self.logical_bytes = info.st_rdev, expected_bytes
            self.sequence = self.number(0x80081280)  # BLKGETDISKSEQ
            if self.number(0x80081272) != expected_bytes:  # BLKGETSIZE64
                raise ValueError('ISOLATED_DEVICE_SIZE_CHANGED')
            if os.pread(self.fd, 512, 0) != expected_marker:
                raise ValueError('ISOLATED_DEVICE_MARKER_MISMATCH')
            self.formatted = False
        except BaseException:
            self.close()
            raise

    def number(self, operation):
        return struct.unpack('Q', self.ioctl(self.fd, operation, b'\0' * 8))[0]

    def check(self):
        node = os.stat('/dev/copilot-store', follow_symlinks=False)
        if (not stat.S_ISBLK(node.st_mode) or node.st_rdev != self.identity or
                os.fstat(self.fd).st_rdev != self.identity or self.number(0x80081280) != self.sequence or
                self.number(0x80081272) != self.logical_bytes):
            raise ValueError('ISOLATED_DEVICE_IDENTITY_CHANGED')

    def format(self, command, filesystem_id, *, run=subprocess.run):
        self.check()
        if self.formatted or not re.fullmatch('[0-9a-f]{32}', filesystem_id):
            raise ValueError('ISOLATED_FORMAT_NOT_FRESH')
        if any(r['device'] == self.device for r in mount_rows(bounded('/proc/self/mountinfo'))):
            raise ValueError('ISOLATED_DEVICE_ALREADY_MOUNTED')
        run([*qualified_command(command, expected='mkfs.ext4'), '-q', '-F', '-m', '0', '-U', str(uuid.UUID(hex=filesystem_id)),
             '-E', 'nodiscard,lazy_itable_init=0,lazy_journal_init=0', '/dev/copilot-store'],
            check=True, timeout=30, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.check()
        self.formatted = True

    def mount(self, command, *, run=subprocess.run):
        self.check()
        if not self.formatted:
            raise ValueError('ISOLATED_DEVICE_NOT_FORMATTED')
        run([*qualified_command(command, expected='mount'), '-t', 'ext4', '-o', 'rw,nosuid,nodev',
             '/dev/copilot-store', '/store'], check=True, timeout=5,
             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.check()
        if os.stat('/store').st_dev != self.identity:
            raise ValueError('ISOLATED_STORE_MOUNT_MISMATCH')

    def close(self):
        if getattr(self, 'fd', None) is not None:
            os.close(self.fd)
            self.fd = None


def namespace_fuse(control, *, lease_seconds=3, deadline_seconds=180):
    """Independent forked child fences a PRIVATE capsule after owner lease loss.

    Requires PID 1 plus prior host inspection of private PID/cgroup/network
    namespaces and effective limits. Parent must install a TERM handler before
    arming and treat any byte/EOF on the returned pipe as a permanent fault.
    It must never respawn engines or disarm the child before outer teardown.
    Native qualification is pending the separately approved canary.
    """
    if sys.platform != 'linux' or os.getpid() != 1 or lease_seconds != 3 or deadline_seconds != 180:
        raise ValueError('ISOLATED_PRIVATE_PID_ONE_REQUIRED')
    read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    initial = os.stat(control, follow_symlinks=False)
    if not stat.S_ISREG(initial.st_mode) or not 0 < initial.st_size <= 4096:
        os.close(read_fd); os.close(write_fd)
        raise ValueError('GUEST_INITIAL_LEASE_INVALID')
    pid = os.fork()
    if pid:
        os.close(write_fd)
        return pid, read_fd
    os.close(read_fd)
    started, changed, prior, tripped = time.monotonic(), time.monotonic(), initial.st_size, False
    ready_sent = False
    reason = b'I'
    while True:
        try:
            now = time.monotonic()
            info = os.stat(control, follow_symlinks=False)
            size = info.st_size
            if (not stat.S_ISREG(info.st_mode) or size < prior or not 0 < size <= 4096 or
                    (info.st_dev, info.st_ino) != (initial.st_dev, initial.st_ino)):
                tripped = True
            if not tripped and size > prior:
                changed, prior = now, size
                if not ready_sent:
                    os.write(write_fd, b'B')
                    ready_sent = True
            if now - changed >= lease_seconds or now - started >= deadline_seconds:
                tripped = True
                reason = b'D' if now - started >= deadline_seconds else b'L'
        except (OSError, ValueError):
            tripped = True
        if tripped:
            try:
                os.write(write_fd, reason)
            except OSError:
                pass
            # Linux excludes PID 1 and the caller from kill(-1). Repeat to fence
            # descendants even if parent briefly races with fault notification.
            # This must NEVER execute outside the inspected private namespace.
            try:
                os.kill(-1, signal.SIGKILL)
                os.kill(1, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(.05 if tripped else .1)


def main():
    if sys.platform == 'linux' and os.getpid() == 1:
        sys.path.insert(0, '/control')
        from isolated_guest import run
        return run()
    print(json.dumps({'status': 'NATIVE_ISOLATION_BOOTSTRAP_DISABLED',
                      'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}))
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
