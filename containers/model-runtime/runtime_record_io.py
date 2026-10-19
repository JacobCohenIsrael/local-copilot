"""Bounded immutable state journal; allow rename publication, never a writer.

This is host file I/O only. No retries, permissions changes, telemetry or Docker.
A complete older snapshot is valid while the next is published; leases still
bound observation age. An active writer or exclusive holder is an error.
"""
import ctypes as c
from ctypes import wintypes as w
import json
from itertools import islice
import os
from pathlib import Path
import re
import uuid

import sensor_frame_io as frame

MAXIMUM = 16384
MAX_RECORDS = 16


def records(namespace):
    directory=Path(namespace)/'states';frame.tools.plain(directory)
    if not directory.exists():return []
    files=sorted(islice(directory.iterdir(),MAX_RECORDS*2+1))
    if len(files)>MAX_RECORDS*2:raise ValueError('Runtime state entry budget')
    published=[]
    for path in files:
        frame.tools.plain(path)
        if re.fullmatch(r'state-[0-9]{4}\.json',path.name):published.append(path)
        elif not re.fullmatch(r'pending-[0-9a-f]{32}\.tmp',path.name):
            raise ValueError('Unexpected runtime state entry')
    if (len(published)>MAX_RECORDS or
            [p.name for p in published]!=[f'state-{n:04d}.json' for n in range(1,len(published)+1)]):
        raise ValueError('Runtime state sequence/budget')
    return published


def exists(namespace):return bool(records(namespace))


def latest(namespace):
    files=records(namespace)
    if not files:raise FileNotFoundError('No published runtime state')
    return read_json(files[-1])


def publish(namespace,value):
    """Caller holds the existing single-writer guard lock. Never replace a file."""
    raw=json.dumps(value,indent=2).encode('utf-8')
    if not isinstance(value,dict) or len(raw)>MAXIMUM:raise ValueError('Runtime state payload budget/type')
    files=records(namespace)
    if len(files)>=MAX_RECORDS:raise ValueError('Runtime state record budget')
    directory=Path(namespace)/'states';directory.mkdir(exist_ok=True)
    temporary=directory/('pending-'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    # Windows rename refuses any existing destination, even if accidentally
    # called by a second writer. A reader never blocks a later snapshot name.
    temporary.rename(directory/f'state-{len(files)+1:04d}.json')


def identity(kernel, handle):
    value = frame.FileInfo()
    frame.checked(kernel.GetFileInformationByHandle(handle, c.byref(value)))
    if kernel.GetFileType(handle) != 1 or value.attributes & (0x10 | 0x400) or value.links != 1:
        raise ValueError('Runtime record must be a plain single-link disk file')
    size = value.size_low | (value.size_high << 32)
    if size > MAXIMUM:
        raise ValueError('Runtime record exceeds budget')
    return (value.volume, value.index_low | (value.index_high << 32), size,
            value.written.dwLowDateTime, value.written.dwHighDateTime)


def read_json(path):
    path = Path(path)
    frame.tools.plain(path)
    if os.name != 'nt':  # Portable fixtures only; live supervisor requires Windows.
        with path.open('rb') as stream:
            raw = stream.read(MAXIMUM + 1)
    else:
        kernel = frame.api()
        handle = kernel.CreateFileW(str(path), 0x80000000, 5, None, 3, 0x00200000, None)
        if handle == c.c_void_p(-1).value:
            error = c.WinError(c.get_last_error())
            error.filename = str(path)
            raise error
        try:
            before = identity(kernel, handle)
            buffer, count = c.create_string_buffer(MAXIMUM + 1), w.DWORD()
            frame.checked(kernel.ReadFile(handle, buffer, MAXIMUM + 1, c.byref(count), None))
            if identity(kernel, handle) != before or count.value != before[2]:
                raise ValueError('Runtime record changed during read')
            # The opened immutable object must remain stable. Later snapshots
            # have different names and cannot invalidate an ongoing read.
            raw = buffer.raw[:count.value]
        finally:
            frame.checked(kernel.CloseHandle(handle))
    if len(raw) > MAXIMUM:
        raise ValueError('Runtime record exceeds budget')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Runtime record must be a JSON object')
    return value
