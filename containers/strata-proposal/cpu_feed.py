"""Supervised fixed ASUS reader and controller adapter; never certifies a sensor.

The same adapter reads real or explicitly synthetic frames. No driver/settings
changes, elevation, sensor-value substitution or workload start is implemented.
"""
import json
import os
from pathlib import Path
import re
import time
import uuid

import build_policy_review as policy
import controller_session as controller
import stage_build_tools as tools
import windows_job
import sensor_frame_io

ROOT = tools.HERE.parents[1] / '.runtime/compiler-guard'
READER = tools.HERE / 'cpu_reader.ps1'
READER_SHA = 'e8a3db7155b4ef177344d12bc1326f02f5da16ea9bab0a71066a97bb0c67b90d'


class FeedError(ValueError):
    """Fixed reason, never arbitrary exception text or a substituted reading."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def error_record(feed, error, phase='poll'):
    """In-memory bounded evidence; do not poll again or write before stopping."""
    codes = {'READER_CLOCK_INVALID', 'READER_EXITED', 'READER_FEED_LOST',
             'READER_FRAME_BUDGET', 'READER_FRAME_TOO_LARGE', 'READER_FRAME_IDENTITY',
             'READER_NOT_OWNED', 'READER_FRAME_JSON'}
    code = getattr(error, 'code', None)
    kind = ('os' if isinstance(error, OSError) else 'json' if isinstance(error, json.JSONDecodeError)
            else 'value' if isinstance(error, ValueError) else 'unexpected')
    return {'reason': code if code in codes else 'READER_OPERATION_FAILED',
            'exceptionCategory': kind,
            'phase': phase if phase in ('poll', 'observe', 'tick') else 'poll',
            'operation': getattr(feed, 'operation', 'unknown') if getattr(feed, 'operation', None) in
                ('clock', 'path', 'existence', 'liveness', 'read', 'decode', 'identity', 'qualify', 'commit') else 'unknown',
            'lastConsumedSequence': feed.sequence,
            'pendingSequence': feed.sequence + 1,
            'readerExitCode': getattr(feed, 'observed_exit_code', None) if type(getattr(feed, 'observed_exit_code', None)) is int else None,
            'osError': error.errno if isinstance(error, OSError) and type(error.errno) is int else None,
            'windowsError': getattr(error, 'winerror', None) if type(getattr(error, 'winerror', None)) is int else None}


def checked_directory(directory):
    directory = Path(directory).absolute()
    tools.plain(directory)
    if directory.parent != ROOT or not re.fullmatch('[0-9a-f]{32}', directory.name):
        raise ValueError('Expected a fixed reader namespace')
    return directory


class Feed:
    """Immutable frames plus local receipt age; an unchanged frame is not fresh."""
    def __init__(self, directory, *, synthetic=False, clock=time.monotonic, source_permit=None):
        if source_permit is not None and synthetic:
            raise ValueError('A source permit cannot qualify synthetic telemetry')
        if synthetic:
            directory = Path(directory).absolute()
            tools.plain(directory)
            rehearsal_root = tools.HERE.parents[1] / '.runtime/offline-controller-rehearsals'
            if (directory.parent.name != 'sessions' or directory.parents[3] != rehearsal_root or
                    not all(re.fullmatch('[0-9a-f]{32}', p.name)
                            for p in (directory, directory.parents[1], directory.parents[2]))):
                raise ValueError('Expected an owned controller rehearsal feed')
            self.directory = directory
        else:
            self.directory = checked_directory(directory)
        self.synthetic, self.clock = synthetic, clock
        self.source_permit = source_permit
        self.sequence, self.last, self.received = 0, clock(), None
        self.process = None
        self.reader_lock = None
        self.operation = 'clock'
        self.observed_exit_code = None

    def start_reader(self, *, samples=1920):
        if self.synthetic or self.process is not None or self.sequence:
            raise ValueError('Real reader requires a fresh non-synthetic feed')
        if type(samples) is not int or not 1 <= samples <= 1920:
            raise ValueError('Reader sample budget invalid')
        if tools.sha(READER) != READER_SHA:
            raise ValueError('Reviewed reader changed')
        self.directory.mkdir(parents=True, exist_ok=True)
        if any(self.directory.iterdir()):
            raise ValueError('Reader session must be empty before launch')
        self.reader_lock = tools.base.lock(ROOT / 'reader-control')
        self.reader_lock.__enter__()
        try:
            count = size = 0
            for path in ROOT.rglob('*'):
                tools.plain(path)
                count += 1
                if path.is_file():
                    size += path.stat().st_size
                if count + samples + 8 > 25000 or size + 2 * samples * 4096 + 65536 > 128 * 1024**2:
                    raise ValueError('Reader evidence namespace lacks session capacity')
            executable = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            env = {k: os.environ[k] for k in ('SystemRoot', 'TEMP', 'TMP') if k in os.environ}
            self.process = windows_job.Process([str(executable), '-NoProfile', '-NonInteractive', '-File', str(READER),
                               '-SessionDirectory', str(self.directory), '-Samples', str(samples)],
                               cwd=self.directory, env=env, memory_bytes=256 * 1024**2, processes=4)
        except BaseException:
            self.reader_lock.__exit__(None, None, None)
            self.reader_lock = None
            raise

    def poll(self):
        self.operation = 'clock'
        now = self.clock()
        if not policy.finite(now) or now < self.last:
            raise FeedError('READER_CLOCK_INVALID')
        self.last = now
        next_file = self.directory / f'sample-{self.sequence + 1:08d}.json'
        self.operation = 'path'
        tools.plain(next_file)
        self.operation = 'existence'
        if not next_file.exists():
            self.operation = 'liveness'
            if self.process is not None:
                self.observed_exit_code = self.process.poll()
                if self.observed_exit_code is not None:
                    raise FeedError('READER_EXITED')
            if self.received is not None and now - self.received > 2.5:
                raise FeedError('READER_FEED_LOST')
            return None
        if self.sequence >= 1920:
            raise FeedError('READER_FRAME_BUDGET')
        self.operation = 'read'
        raw = sensor_frame_io.read(next_file)
        if len(raw) > 4096:
            raise FeedError('READER_FRAME_TOO_LARGE')
        self.operation = 'decode'
        try:
            frame = json.loads(raw.decode('utf-8-sig'))
        except (ValueError, UnicodeError):
            raise FeedError('READER_FRAME_JSON') from None
        self.operation = 'identity'
        if (not isinstance(frame, dict) or frame.get('sequence') != self.sequence + 1 or type(frame.get('sequence')) is not int or
                frame.get('synthetic') is not self.synthetic):
            raise FeedError('READER_FRAME_IDENTITY')
        if self.source_permit is not None:
            self.operation = 'liveness'
            if self.process is None:
                raise FeedError('READER_NOT_OWNED')
            self.observed_exit_code = self.process.poll()
            if self.observed_exit_code is not None:
                raise FeedError('READER_EXITED')
            self.operation = 'qualify'
            frame = self.source_permit.qualify(frame)
        # Commit only a frame that has passed every check. Rejected frames must
        # not advance sequence/receipt time or appear as consumed evidence.
        self.operation = 'commit'
        self.sequence += 1
        self.received = now
        return frame  # Default remains unvalidated; raw on-disk frames never change.

    def close(self):
        try:
            if self.process is not None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                finally:
                    self.process.close()
        finally:
            if self.reader_lock is not None:
                self.reader_lock.__exit__(None, None, None)
                self.reader_lock = None


class Monitor:
    """Controller-facing safety feed; poll/tick never start a workload.

    Production uses the approved CPU-build gate. Synthetic mode is explicit,
    cannot be switched after construction, and is never live admission evidence.
    """
    def __init__(self, feed, *, unix=time.time):
        self.feed, self.unix = feed, unix
        self.gate = controller.RehearsalGate() if feed.synthetic else policy.CpuBuildReadinessGate()
        self.started = feed.clock()
        self.last_error = None

    def poll(self, *, controller_age=0, cancelled=False):
        elapsed = self.feed.clock() - self.started
        phase = 'poll'
        try:
            frame = self.feed.poll()
            if not policy.finite(controller_age) or controller_age < 0:
                self.gate.trip('CLOCK_INVALID')
            elif cancelled:
                self.gate.trip('CANCELLED')
            elif frame is not None:
                phase = 'observe'
                return self.gate.observe(frame, elapsed=elapsed, unix=self.unix(), controller_age=controller_age)
            elif self.feed.sequence:
                phase = 'tick'
                return self.gate.tick(elapsed=elapsed, unix=self.unix(), controller_age=controller_age)
            elif elapsed > 2.5 or controller_age > 2.5:
                self.gate.trip('SENSOR_MISSING' if elapsed > 2.5 else 'CONTROLLER_LEASE_EXPIRED')
        except Exception as error:
            self.last_error = self.last_error or error_record(self.feed, error, phase)
            self.gate.trip('SENSOR_FEED_ERROR')
        return self.gate.snapshot()


def probe():
    """Ten passive samples, independently bounded to 18 s; no self-elevation."""
    with tools.base.lock(ROOT / 'probe-control'):
        # Budget all retained frames/probe attempts, not only successful ones.
        count = size = 0
        for path in ROOT.rglob('*'):
            tools.plain(path)
            count += 1
            if path.is_file():
                size += path.stat().st_size
            if count > 25000 or size > 128 * 1024**2:
                raise ValueError('Reader evidence namespace full')
        directory = ROOT / uuid.uuid4().hex
        feed = Feed(directory)
        result = {'version': 1, 'status': 'OBSERVATION_ONLY', 'synthetic': False,
                  'readerSha256': READER_SHA, 'validatedCpuSensor': False,
                  'cpuThermalThrottling': None, 'workloadStarted': False, 'samples': [], 'readerStopped': False}
        try:
            feed.start_reader(samples=10)
            end = time.monotonic() + 18
            while time.monotonic() < end and len(result['samples']) < 10:
                frame = feed.poll()
                if frame is not None:
                    result['samples'].append(frame)
                    if frame.get('error') or frame.get('querySeconds', 2) > 1:
                        break
                time.sleep(.05)
            result['status'] = ('TEN_SAMPLES_OBSERVED_NOT_CERTIFIED' if len(result['samples']) == 10 and
                                all(not row.get('error') for row in result['samples']) else 'SOURCE_VALIDATION_BLOCKED')
        except Exception as error:
            result.update(status='SOURCE_VALIDATION_BLOCKED', error=type(error).__name__)
        finally:
            try:
                feed.close()
                result['readerStopped'] = True
            finally:
                directory.mkdir(exist_ok=True)
                tools.base.atomic(directory / 'probe-result.json', result)
                tools.base.atomic(ROOT / 'latest-probe.json', {
                    'sessionId': directory.name, 'sha256': tools.sha(directory / 'probe-result.json')})
        result['directory'] = str(directory)
        return result
