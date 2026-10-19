"""Bounded immutable-frame read compatible with Windows rename publication.

No retry, permissions changes, creation, writes or sensor access. Sharing DELETE
permits the publisher's already-completed rename; sharing WRITE is NOT granted.
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path

import stage_build_tools as tools

MAXIMUM = 4096
SHARE = 0x1 | 0x4  # FILE_SHARE_READ | FILE_SHARE_DELETE; never FILE_SHARE_WRITE.


class FileInfo(c.Structure):
    _fields_ = [('attributes', w.DWORD), ('created', w.FILETIME), ('accessed', w.FILETIME),
                ('written', w.FILETIME), ('volume', w.DWORD), ('size_high', w.DWORD),
                ('size_low', w.DWORD), ('links', w.DWORD), ('index_high', w.DWORD), ('index_low', w.DWORD)]


def api():
    if os.name != 'nt':
        raise RuntimeError('Native Windows frame reader required')
    kernel = c.WinDLL('kernel32', use_last_error=True)
    for name, (args, result) in {
        'CreateFileW': ([w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
        'CloseHandle': ([w.HANDLE], w.BOOL),
        'ReadFile': ([w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p], w.BOOL),
        'GetFileInformationByHandle': ([w.HANDLE, c.POINTER(FileInfo)], w.BOOL),
        'GetFileType': ([w.HANDLE], w.DWORD),
    }.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def checked(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


def info(kernel, handle):
    value = FileInfo()
    checked(kernel.GetFileInformationByHandle(handle, c.byref(value)))
    if (kernel.GetFileType(handle) != 1 or value.attributes & (0x10 | 0x400) or value.links != 1):
        raise ValueError('Reader frame must be a plain single-link disk file')
    size = value.size_low | (value.size_high << 32)
    if size > MAXIMUM:
        raise ValueError('Reader frame exceeds budget')
    return (value.volume, value.index_low | (value.index_high << 32), size,
            value.written.dwLowDateTime, value.written.dwHighDateTime)


def read(path):
    """Exactly one read-only open; real sharing/access failures remain errors."""
    path = Path(path)
    tools.plain(path)
    if os.name != 'nt':  # Offline portable tests only; live supervisor requires Windows.
        with path.open('rb') as stream:
            return stream.read(MAXIMUM + 1)
    kernel = api()
    handle = kernel.CreateFileW(str(path), 0x80000000, SHARE, None, 3, 0x00200000, None)
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    try:
        before = info(kernel, handle)
        buffer, count = c.create_string_buffer(MAXIMUM + 1), w.DWORD()
        checked(kernel.ReadFile(handle, buffer, MAXIMUM + 1, c.byref(count), None))
        after = info(kernel, handle)
        tools.plain(path)
        named = path.stat(follow_symlinks=False)
        if (before != after or count.value != before[2] or
                named.st_ino != before[1] or named.st_size != before[2]):
            raise ValueError('Reader frame changed during bounded read')
        return buffer.raw[:count.value]
    finally:
        checked(kernel.CloseHandle(handle))
