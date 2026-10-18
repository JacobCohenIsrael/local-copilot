"""Offline native reproduction of publication sharing, using generated frames only."""
import contextlib
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import time
import uuid
from unittest.mock import patch

import cpu_feed
import sensor_frame_io as frame_io

ROOT = cpu_feed.tools.HERE.parents[1] / '.runtime/frame-access-rehearsals'


def api():
    kernel = frame_io.api()
    kernel.MoveFileExW.argtypes, kernel.MoveFileExW.restype = [w.LPCWSTR, w.LPCWSTR, w.DWORD], w.BOOL
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], w.HANDLE
    kernel.GetProcessHandleCount.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    kernel.GetProcessHandleCount.restype = w.BOOL
    return kernel


@contextlib.contextmanager
def published_frame(directory, sequence, data):
    """Hold the publisher's DELETE access across visibility of a complete rename."""
    directory = Path(directory).resolve()
    cpu_feed.tools.plain(directory)
    temporary = directory / f'generated-{sequence}.tmp'
    target = directory / f'sample-{sequence:08d}.json'
    if len(data) > 4097:
        raise ValueError('Tiny frame fixture budget')
    with temporary.open('xb') as stream:
        stream.write(data)
    kernel = api()
    handle = kernel.CreateFileW(str(temporary), 0x10000, 7, None, 3, 0x80, None)
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    try:
        frame_io.checked(kernel.MoveFileExW(str(temporary), str(target), 0))
        yield target
    finally:
        frame_io.checked(kernel.CloseHandle(handle))


def generated(sequence, seconds):
    return {'version': 1, 'sequence': sequence, 'synthetic': True,
            'source': 'ASUS DSTS 0x00120094', 'error': None, 'validatedCpuSensor': True,
            'cpuTemperatureC': 65, 'cpuThermalThrottling': None, 'recordedAtUnix': 1000 + seconds,
            'querySeconds': .01, 'readerRemainingSeconds': 1920 - seconds}


def handle_count(kernel):
    count = w.DWORD()
    frame_io.checked(kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count)))
    return count.value


def rehearse():
    directory = ROOT / uuid.uuid4().hex
    directory.mkdir(parents=True)
    session = directory / uuid.uuid4().hex
    session.mkdir()
    now = [100.]
    with patch.object(cpu_feed, 'ROOT', directory):
        feed = cpu_feed.Feed(session, clock=lambda: now[0])
    feed.synthetic = True  # All bytes are generated; start_reader must stay disabled.
    monitor = cpu_feed.Monitor(feed, unix=lambda: 1000 + now[0] - 100)
    kernel = api()
    before = handle_count(kernel)
    denied = 0
    for sequence in range(1, 65):  # 64 bounded frames; no busy workload or hardware probe.
        seconds = (sequence - 1) * .25
        now[0] = 100 + seconds
        expected = generated(sequence, seconds)
        raw = json.dumps(expected).encode()
        with published_frame(session, sequence, raw) as target:
            try:
                target.read_bytes()
            except PermissionError as error:
                assert error.errno == 13
                denied += 1
            else:
                raise AssertionError('Legacy publisher conflict not reproduced')
            assert frame_io.read(target) == raw
            assert monitor.poll()['fault'] is None
            assert feed.sequence == sequence
    after = handle_count(kernel)
    assert after == before, (before, after)
    assert denied == 64
    failures = {}
    target = session / 'sample-00000064.json'
    for label, access, share in [('exclusive', 0x80000000, 0), ('active-writer', 0x40000000, 7)]:
        handle = kernel.CreateFileW(str(target), access, share, None, 3, 0x80, None)
        if handle == c.c_void_p(-1).value:
            raise c.WinError(c.get_last_error())
        try:
            try:
                frame_io.read(target)
            except OSError as error:
                assert error.winerror == 32
                failures[label] = {'rejected': True, 'windowsError': error.winerror, 'osError': error.errno}
            else:
                raise AssertionError('Real sharing conflict was ignored')
        finally:
            frame_io.checked(kernel.CloseHandle(handle))
    result = {'version':1, 'status':'PASSED', 'synthetic':True,
              'legacyDenied':denied, 'correctedFeedFrames':feed.sequence,
              'heldRenameHandleCompatible':True, 'readOnlyNoWriteSharing':True,
              'realConflicts':failures, 'handleCountBefore':before, 'handleCountAfter':after,
              'automaticRetries':0, 'realSensorReads':0, 'realBlobReads':0,
              'imageDownloadEnabled':False, 'imageImportEnabled':False,'buildEnabled':False,'modelLaunchEnabled':False}
    cpu_feed.tools.base.atomic(directory / 'result.json', result)
    return {'directory':str(directory), **result}


if __name__ == '__main__':
    print(json.dumps(rehearse(), indent=2))
