"""Owned Windows VHDX -> WSL bridge. No arbitrary disk adoption or global stop."""
import ctypes as c
import hashlib
import json
from pathlib import Path
import re
import subprocess

import isolated_store as disk

WSL = 'C:/Windows/System32/wsl.exe'


def validate_scan(value):
    if (set(value) != {'device', 'majorMinor', 'diskSequence', 'logicalBytes'} or
            not re.fullmatch('/dev/sd[a-z]{1,2}', value.get('device', '')) or
            not re.fullmatch('[0-9]{1,4}:[0-9]{1,6}', value.get('majorMinor', '')) or
            type(value.get('diskSequence')) is not int or value['diskSequence'] <= 0 or
            value.get('logicalBytes') != 128 * disk.MIB):
        raise ValueError('BRIDGE_DEVICE_PROOF_INVALID')
    return value


class WindowsMarker:
    def __init__(self, backend):
        self.backend, self.api, self.kernel = backend, backend.api, backend.kernel
        api, kernel = self.api, self.kernel
        api.AttachVirtualDisk.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint32, c.c_void_p, c.c_void_p]
        api.DetachVirtualDisk.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32]
        api.GetVirtualDiskPhysicalPath.argtypes = [c.c_void_p, c.POINTER(c.c_uint32), c.c_wchar_p]
        for name in ('AttachVirtualDisk', 'DetachVirtualDisk', 'GetVirtualDiskPhysicalPath'):
            getattr(api, name).restype = c.c_uint32
        kernel.CreateFileW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32, c.c_void_p]
        kernel.CreateFileW.restype = c.c_void_p
        kernel.DeviceIoControl.argtypes = [c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32,
                                           c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32), c.c_void_p]
        kernel.DeviceIoControl.restype = c.c_int
        kernel.SetFilePointerEx.argtypes = [c.c_void_p, c.c_int64, c.c_void_p, c.c_uint32]
        kernel.SetFilePointerEx.restype = c.c_int
        for name in ('ReadFile', 'WriteFile'):
            getattr(kernel, name).argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32), c.c_void_p]
            getattr(kernel, name).restype = c.c_int
        kernel.FlushFileBuffers.argtypes, kernel.FlushFileBuffers.restype = [c.c_void_p], c.c_int

    def guard(self):
        if self.backend.allowed() is not True:
            raise ValueError('BRIDGE_GUARD_LOST')

    def mark(self, store):
        self.guard()
        store.check(self.backend)
        handle, raw = c.c_void_p(), None
        attached, detached = False, False
        params = disk.OpenParameters(1, 1)
        self.backend.checked(self.api.OpenVirtualDisk(c.byref(self.backend.storage), str(store.path),
            0xE0000, 0, c.byref(params), c.byref(handle)))
        try:
            self.guard()
            attach = (c.c_uint32 * 2)(1, 0)
            self.backend.checked(self.api.AttachVirtualDisk(handle, None, 2, 0, c.byref(attach), None))
            attached = True
            path, length = c.create_unicode_buffer(256), c.c_uint32(512)
            self.backend.checked(self.api.GetVirtualDiskPhysicalPath(handle, c.byref(length), path))
            if not re.fullmatch(re.escape('\\\\.\\PhysicalDrive') + '[0-9]{1,4}', path.value):
                raise ValueError('BRIDGE_PHYSICAL_PATH_INVALID')
            raw = self.kernel.CreateFileW(path.value, 0xC0000000, 3, None, 3, 0x80000000, None)
            if raw in (None, c.c_void_p(-1).value):
                raise OSError('BRIDGE_RAW_OPEN_FAILED')
            def checked(result):
                if not result:
                    raise OSError(c.get_last_error(), 'BRIDGE_RAW_IO_FAILED')
            def ioctl(code, buffer):
                used = c.c_uint32()
                checked(self.kernel.DeviceIoControl(raw, code, None, 0, c.byref(buffer), c.sizeof(buffer), c.byref(used), None))
                if used.value != c.sizeof(buffer):
                    raise ValueError('BRIDGE_RAW_IDENTITY_SIZE')
            size, number = c.c_int64(), (c.c_uint32 * 3)()
            ioctl(0x7405C, size)
            ioctl(0x2D1080, number)
            if size.value != store.spec.logical_bytes or number[0] != 7 or number[1] != int(path.value.rsplit('Drive', 1)[1]):
                raise ValueError('BRIDGE_RAW_DISK_IDENTITY')
            store.check(self.backend)
            def read():
                checked(self.kernel.SetFilePointerEx(raw, 0, None, 0))
                buffer, count = c.create_string_buffer(4096), c.c_uint32()
                checked(self.kernel.ReadFile(raw, buffer, 4096, c.byref(count), None))
                if count.value != 4096:
                    raise ValueError('BRIDGE_RAW_READ_SIZE')
                return buffer.raw
            if read() != b'\0' * 4096:
                raise ValueError('BRIDGE_NEW_DISK_NOT_EMPTY')
            self.guard()
            expected = store.marker.ljust(4096, b'\0')
            checked(self.kernel.SetFilePointerEx(raw, 0, None, 0))
            count, data = c.c_uint32(), c.create_string_buffer(expected)
            checked(self.kernel.WriteFile(raw, data, 4096, c.byref(count), None))
            if count.value != 4096:
                raise ValueError('BRIDGE_RAW_WRITE_SIZE')
            checked(self.kernel.FlushFileBuffers(raw))
            if read() != expected:
                raise ValueError('BRIDGE_MARKER_READBACK')
            self.kernel.CloseHandle(raw)
            raw = None
            self.backend.checked(self.api.DetachVirtualDisk(handle, 0, 0))
            detached = True
            return {'markerSha256': hashlib.sha256(store.marker).hexdigest(), 'windowsDetachConfirmed': True}
        finally:
            if raw not in (None, c.c_void_p(-1).value):
                self.kernel.CloseHandle(raw)
            # Attachment has handle lifetime, not permanent lifetime. Attempt
            # explicit detach of this exact owned handle, never another disk.
            try:
                if attached and not detached:
                    self.backend.checked(self.api.DetachVirtualDisk(handle, 0, 0))
            finally:
                if handle.value:
                    self.kernel.CloseHandle(handle)


class WslBridge:
    def __init__(self, store, backend, script, *, call=None):
        self.store, self.backend, self.script = store, backend, Path(script)
        self.call = call or self._call
        self.proof = None

    @staticmethod
    def _call(args):
        result = subprocess.run([WSL, *args], capture_output=True, check=True, timeout=10)
        if len(result.stdout) > 8192 or len(result.stderr) > 8192:
            raise ValueError('BRIDGE_OUTPUT_LIMIT')
        return result.stdout.decode('utf-8').strip()

    def shell(self, *args):
        absolute = str(self.script.resolve()).replace('\\', '/')
        if not absolute.lower().startswith('c:/'):
            raise ValueError('BRIDGE_SCRIPT_MUST_BE_IN_WORKSPACE_ON_C')
        path = '/mnt/host/c/' + absolute[3:]
        return self.call(['--distribution', 'docker-desktop', '--user', 'root', '--exec', 'sh', path, *args])

    def attach(self):
        self.store.check(self.backend)
        marked = WindowsMarker(self.backend).mark(self.store)
        if self.backend.allowed() is not True:
            raise ValueError('BRIDGE_GUARD_LOST')
        # If this call times out the mapping remains uncertain and is retained.
        self.call(['--mount', '--vhd', str(self.store.path), '--bare'])
        scanned = validate_scan(json.loads(self.shell('scan', str(self.store.spec.logical_bytes), self.store.marker.hex())))
        proof = {**scanned, 'session': self.store.spec.session, 'vhdIdentifier': self.store.identifier,
            'hostFileIdentity': list(self.store.file_identity), 'markerReadBackMatches': True,
            'markerSha256': marked['markerSha256'], 'newOwnedDevice': True, 'mountedElsewhere': False}
        proof['deviceToken'] = hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()
        self.store.qualify_guest(proof)
        self.proof = proof
        return proof

    def detach(self, *, guest, capsule_stopped):
        if (capsule_stopped is not True or self.proof is None or guest.get('unmounted') is not True or
                guest.get('exclusiveDeviceClaim') is not True or guest.get('deviceToken') != self.proof['deviceToken'] or
                guest.get('enginesStopped') is not True):
            raise ValueError('BRIDGE_DETACH_WITHOUT_GUEST_STOP_PROOF')
        self.store.check(self.backend)
        release = json.loads(self.shell('release', str(self.store.spec.logical_bytes), self.proof['device'],
                                       str(self.proof['diskSequence']), self.store.spec.session))
        if release != {'releaseCheck': True}:
            raise ValueError('BRIDGE_RELEASE_CHECK_INVALID')
        self.call(['--unmount', str(self.store.path)])
        return True
