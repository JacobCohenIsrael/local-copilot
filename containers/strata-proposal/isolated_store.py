"""Owned fixed VHDX creation and lifecycle. No attach/format CLI or cleanup delete.

Native creation is reachable only through the separately approved, one-attempt
canary. WSL attachment/device mapping is independently qualified.
"""
from dataclasses import dataclass
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

import stage_build_tools as tools
from isolated_agent import device_marker

ROOT = tools.HERE.parents[1] / '.runtime/isolated-stores'
MIB, GIB = 1024**2, 1024**3


@dataclass(frozen=True)
class Spec:
    session: str
    logical_bytes: int = 32 * GIB
    overhead_bytes: int = 256 * MIB
    reserve_bytes: int = 20 * GIB

    def __post_init__(self):
        if (uuid.UUID(self.session).hex != self.session or
                type(self.logical_bytes) is not int or self.logical_bytes not in (128 * MIB, 32 * GIB) or
                self.overhead_bytes != 256 * MIB or self.reserve_bytes != 20 * GIB):
            raise ValueError('ISOLATED_STORE_SPEC_INVALID')

    @property
    def maximum_file_bytes(self):
        return self.logical_bytes + self.overhead_bytes


def validate_properties(spec, value, identifier):
    if (value.get('identifier') != identifier or value.get('virtualBytes') != spec.logical_bytes or
            type(value.get('physicalBytes')) is not int or
            not spec.logical_bytes <= value['physicalBytes'] <= spec.maximum_file_bytes or
            value.get('providerSubtype') != 2 or value.get('sectorBytes') != 512):
        raise ValueError('ISOLATED_VHDX_PROPERTIES_INVALID')


class Store:
    """Single owned namespace. A failure retains the disk/claim and blocks reuse."""
    def __init__(self, spec, *, root=ROOT):
        self.spec, self.directory = spec, Path(root) / spec.session
        self.path = self.directory / 'store.vhdx'
        self.identifier = str(uuid.UUID(hex=spec.session))
        self.marker = device_marker(spec.session, os.urandom(32))
        self.file_identity = None
        self.guest = None

    def create(self, backend):
        tools.plain(self.directory)
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.directory.parent).free < self.spec.maximum_file_bytes + self.spec.reserve_bytes + 4 * MIB:
            raise ValueError('ISOLATED_HOST_RESERVE')
        self.directory.mkdir(exist_ok=False)
        tools.base.atomic(self.directory / 'owner.json', {
            'session': self.spec.session, 'identifier': self.identifier,
            'logicalBytes': self.spec.logical_bytes, 'maximumFileBytes': self.spec.maximum_file_bytes,
            'deviceMarkerHex': self.marker.hex(), 'deviceMarkerSha256': hashlib.sha256(self.marker).hexdigest(),
            'status': 'CLAIMED_NO_REUSE'})
        if self.path.exists():
            raise ValueError('ISOLATED_STORE_ALREADY_EXISTS')
        # The native API itself refuses an existing target; no truncate/replace.
        backend.create_fixed(self.path, self.spec.logical_bytes, self.identifier)
        properties = backend.properties(self.path)
        validate_properties(self.spec, properties, self.identifier)
        self.file_identity = self._identity()
        self.check(backend)
        receipt = {**properties, 'fileIdentity': self.file_identity, 'session': self.spec.session,
                   'physicalAllocationCeilingNativeProven': False}
        tools.base.atomic(self.directory / 'created.json', receipt)
        return receipt

    def _identity(self):
        tools.plain(self.path)
        info = self.path.stat()
        if (not self.path.is_file() or info.st_nlink != 1 or
                not 0 < info.st_size <= self.spec.maximum_file_bytes):
            raise ValueError('ISOLATED_STORE_FILE_INVALID')
        return (info.st_dev, info.st_ino)

    def check(self, backend):
        if self.file_identity is None or self._identity() != self.file_identity:
            raise ValueError('ISOLATED_STORE_REPLACED')
        validate_properties(self.spec, backend.properties(self.path), self.identifier)
        if shutil.disk_usage(self.directory).free < self.spec.reserve_bytes:
            raise ValueError('ISOLATED_HOST_RESERVE')

    def qualify_guest(self, proof):
        """Require a host-to-guest bridge's nonce/identity proof, not a guessed sdX.

        This validates the bridge result; it does not implement or authenticate
        the bridge. Native qualification is still required before this can
        become image or workload admission.
        """
        if (self.file_identity is None or proof.get('session') != self.spec.session or
                proof.get('vhdIdentifier') != self.identifier or
                proof.get('hostFileIdentity') != list(self.file_identity) or
                proof.get('logicalBytes') != self.spec.logical_bytes or
                proof.get('markerReadBackMatches') is not True or
                proof.get('markerSha256') != hashlib.sha256(self.marker).hexdigest() or
                proof.get('newOwnedDevice') is not True or proof.get('mountedElsewhere') is not False or
                not isinstance(proof.get('deviceToken'), str) or
                len(proof['deviceToken']) != 64 or any(ch not in '0123456789abcdef' for ch in proof['deviceToken'])):
            raise ValueError('ISOLATED_DEVICE_MAPPING_INVALID')
        self.guest = json.loads(json.dumps(proof))

    def detach(self, bridge, *, writers_stopped):
        if writers_stopped is not True or self.guest is None:
            raise ValueError('ISOLATED_DETACH_WITHOUT_STOP_PROOF')
        # Bridge must recheck exact owned mapping and absence of mounts/writers.
        result = bridge.detach_owned(self.path, dict(self.guest))
        if result is not True:
            raise ValueError('ISOLATED_DETACH_UNCONFIRMED')
        return True


class GUID(c.Structure):
    _fields_ = [('data', c.c_ubyte * 16)]

    @classmethod
    def from_uuid(cls, value):
        result = cls()
        result.data[:] = uuid.UUID(str(value)).bytes_le
        return result


class StorageType(c.Structure):
    _fields_ = [('device', c.c_uint32), ('vendor', GUID)]


class CreateV2(c.Structure):
    _fields_ = [('identifier', GUID), ('maximum', c.c_uint64), ('block', c.c_uint32),
                ('sector', c.c_uint32), ('physical_sector', c.c_uint32),
                ('parent', c.c_wchar_p), ('source', c.c_wchar_p), ('open_flags', c.c_uint32),
                ('parent_type', StorageType), ('source_type', StorageType), ('resiliency', GUID)]


class CreateParameters(c.Structure):
    _fields_ = [('version', c.c_uint32), ('v2', CreateV2)]


class OpenParameters(c.Structure):
    # Version 1 is sufficient for GET_INFO-only opens, including VHDX.
    _fields_ = [('version', c.c_uint32), ('read_write_depth', c.c_uint32)]


class Size(c.Structure):
    _fields_ = [('virtual', c.c_uint64), ('physical', c.c_uint64),
                ('block', c.c_uint32), ('sector', c.c_uint32)]


class InfoValue(c.Union):
    _fields_ = [('size', Size), ('identifier', GUID), ('subtype', c.c_uint32)]


class Info(c.Structure):
    _fields_ = [('version', c.c_uint32), ('value', InfoValue)]


class Overlapped(c.Structure):
    _fields_ = [('internal', c.c_size_t), ('internal_high', c.c_size_t),
                ('offset', c.c_uint32), ('offset_high', c.c_uint32), ('event', c.c_void_p)]


class Progress(c.Structure):
    _fields_ = [('status', c.c_uint32), ('current', c.c_uint64), ('completion', c.c_uint64)]


class WindowsVhdx:
    """No diskpart, existing-disk adoption, mount, resize or deletion operations.

    Polls provider completion and cancels on guard loss/deadline. If cancellation
    is unconfirmed, retains native buffers/handles instead of detaching/deleting
    or pretending worker exit established provider completion. Native proof is
    pending; the admitted host controller must supply a live permission callback.
    """
    pending_operations = []  # Keep OVERLAPPED storage alive on uncertain completion.

    def __init__(self, *, allowed, operation_seconds=180):
        if not callable(allowed) or operation_seconds not in (180, 1800):
            raise ValueError('ISOLATED_NATIVE_GUARD_REQUIRED')
        self.allowed, self.operation_seconds = allowed, operation_seconds
        if os.name != 'nt':
            raise ValueError('WINDOWS_VHDX_REQUIRED')
        self.api = c.WinDLL('virtdisk', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.api.CreateVirtualDisk.argtypes = [c.POINTER(StorageType), c.c_wchar_p, c.c_uint32,
            c.c_void_p, c.c_uint32, c.c_uint32, c.POINTER(CreateParameters), c.c_void_p, c.POINTER(c.c_void_p)]
        self.api.OpenVirtualDisk.argtypes = [c.POINTER(StorageType), c.c_wchar_p, c.c_uint32,
            c.c_uint32, c.POINTER(OpenParameters), c.POINTER(c.c_void_p)]
        self.api.GetVirtualDiskInformation.argtypes = [c.c_void_p, c.POINTER(c.c_uint32),
            c.POINTER(Info), c.POINTER(c.c_uint32)]
        self.api.GetVirtualDiskOperationProgress.argtypes = [c.c_void_p, c.POINTER(Overlapped), c.POINTER(Progress)]
        for name in ('CreateVirtualDisk', 'OpenVirtualDisk', 'GetVirtualDiskInformation',
                     'GetVirtualDiskOperationProgress'):
            getattr(self.api, name).restype = c.c_uint32
        self.kernel.CloseHandle.argtypes, self.kernel.CloseHandle.restype = [c.c_void_p], c.c_int
        self.kernel.CreateEventW.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_wchar_p]
        self.kernel.CreateEventW.restype = c.c_void_p
        self.kernel.WaitForSingleObject.argtypes, self.kernel.WaitForSingleObject.restype = [c.c_void_p, c.c_uint32], c.c_uint32
        self.kernel.ResetEvent.argtypes, self.kernel.ResetEvent.restype = [c.c_void_p], c.c_int
        self.kernel.CancelIoEx.argtypes, self.kernel.CancelIoEx.restype = [c.c_void_p, c.POINTER(Overlapped)], c.c_int
        self.storage = StorageType(3, GUID.from_uuid('ec984aec-a0f9-47e9-901f-71415a66345b'))

    @staticmethod
    def checked(status):
        if status:
            raise OSError(status, 'VHDX API operation failed')

    def create_fixed(self, path, logical_bytes, identifier):
        path = Path(path)
        tools.plain(path)
        if (path.name != 'store.vhdx' or path.exists() or
                logical_bytes not in (128 * MIB, 32 * GIB)):
            raise ValueError('ISOLATED_NATIVE_CREATE_INVALID')
        if self.pending_operations:
            raise ValueError('ISOLATED_PRIOR_PROVIDER_STOP_UNCONFIRMED')
        params = CreateParameters()
        params.version, params.v2.identifier = 2, GUID.from_uuid(identifier)
        params.v2.maximum, params.v2.sector, params.v2.physical_sector = logical_bytes, 512, 4096
        handle = c.c_void_p()
        operation, finished, completion = Overlapped(), False, {'confirmed': False}
        if self.allowed() is not True:
            raise ValueError('ISOLATED_NATIVE_GUARD_LOST')
        operation.event = self.kernel.CreateEventW(None, True, False, None)
        if not operation.event:
            raise OSError('VHDX completion event creation failed')
        try:
            status = self.api.CreateVirtualDisk(c.byref(self.storage), str(path), 0, None,
                1, 0, c.byref(params), c.byref(operation), c.byref(handle))
            if status not in (0, 997):
                finished = True
                self.checked(status)
            completion['confirmed'] = status == 0
            if not handle.value:
                raise ValueError('ISOLATED_NATIVE_HANDLE_INVALID')
            # Even a synchronous success is checked through provider progress.
            self.await_completion(handle, operation, completion=completion)
            finished = True
        finally:
            if finished or completion['confirmed']:
                if handle.value:
                    self.kernel.CloseHandle(handle)
                self.kernel.CloseHandle(operation.event)
            else:
                if handle.value:
                    try:
                        self.kernel.CancelIoEx(handle, c.byref(operation))
                    except Exception:
                        pass
                self.pending_operations.append((handle, operation))

    def await_completion(self, handle, operation, *, clock=time.monotonic, completion=None):
        started, cancelled, reason = clock(), None, None
        while True:
            progress = Progress()
            self.checked(self.api.GetVirtualDiskOperationProgress(handle, c.byref(operation), c.byref(progress)))
            now = clock()
            if progress.status != 997:
                if completion is not None:
                    completion['confirmed'] = True
                self.checked(progress.status)
                if reason:
                    raise ValueError(reason)
                if now < started or now - started >= self.operation_seconds or self.allowed() is not True:
                    raise ValueError('ISOLATED_VHDX_GUARD_OR_DEADLINE')
                return
            if cancelled is None:
                try:
                    permitted = self.allowed() is True
                except (ValueError, OSError, RuntimeError):
                    permitted = False
                if not permitted or now < started or now - started >= self.operation_seconds:
                    reason = 'ISOLATED_VHDX_GUARD_OR_DEADLINE'
                    cancelled = now
                    # Provider cancellation is a request, not a stopping proof.
                    self.kernel.CancelIoEx(handle, c.byref(operation))
            elif now < cancelled or now - cancelled >= 5:
                raise ValueError('ISOLATED_VHDX_PROVIDER_STOP_UNCONFIRMED')
            wait = self.kernel.WaitForSingleObject(operation.event, 100)
            if wait not in (0, 258):
                raise OSError('VHDX completion wait failed')
            if wait == 0 and not self.kernel.ResetEvent(operation.event):
                raise OSError('VHDX completion event reset failed')

    def properties(self, path):
        tools.plain(Path(path))
        handle = c.c_void_p()
        params = OpenParameters(1, 1)
        self.checked(self.api.OpenVirtualDisk(c.byref(self.storage), str(path), 0x80000,
            0, c.byref(params), c.byref(handle)))  # GET_INFO only
        try:
            def query(version):
                value, size, used = Info(), c.c_uint32(c.sizeof(Info)), c.c_uint32()
                value.version = version
                self.checked(self.api.GetVirtualDiskInformation(handle, c.byref(size), c.byref(value), c.byref(used)))
                return value.value
            size, identity, subtype = query(1), query(2), query(7)
            return {'virtualBytes': size.size.virtual, 'physicalBytes': size.size.physical,
                    'sectorBytes': size.size.sector, 'providerSubtype': subtype.subtype,
                    'identifier': str(uuid.UUID(bytes_le=bytes(identity.identifier.data)))}
        finally:
            if handle.value:
                self.kernel.CloseHandle(handle)
