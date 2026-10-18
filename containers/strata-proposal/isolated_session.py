"""One-attempt isolation lifecycle and independent watchdog. Synthetic runner only.

The core exercises provision/validate/start/stop/detach ordering with injected
backends. Native VHDX/capsule adapters are not yet an admitted live workflow.
"""
import json
from pathlib import Path
import threading
import time
import uuid
import re

import stage_build_tools as tools

ROOT = tools.HERE.parents[1] / '.runtime/isolation-rehearsals'


class Session:
    def __init__(self, directory, backend, *, lease_seconds=3, operation_seconds=180, clock=time.monotonic):
        if backend.synthetic is not True:
            raise ValueError('ISOLATION_NATIVE_ADMISSION_NOT_WIRED')
        self.directory, self.backend, self.clock = Path(directory), backend, clock
        tools.plain(self.directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.started = self.last = clock()
        self.lease_seconds, self.operation_seconds = lease_seconds, operation_seconds
        self.fenced, self.closed = threading.Event(), threading.Event()
        self.lock = threading.RLock()
        self.fault = None
        self.stop_confirmed = self.detached = False
        self.store_qualified = False
        self.phase, self.monitor_fault = 'CLAIMED', None
        self.operation_error = None
        tools.base.atomic(self.directory / 'attempt.json', {'session': self.directory.name,
            'synthetic': True, 'maximumAttempts': 1, 'restartAllowed': False})

    def pulse(self):
        with self.lock:
            if self.fenced.is_set():
                raise ValueError('ISOLATION_FENCED')
            now = self.clock()
            if now < self.last:
                self.monitor_fault = 'CLOCK_INVALID'
            else:
                self.last = now

    def trip(self, reason):
        with self.lock:
            if self.fenced.is_set():
                return
            self.fault, self.phase = reason, 'FAULT'
            self.fenced.set()  # Fence before any stop or journal operation.
        # Backend stop must be bounded and independent of the main I/O path.
        try:
            result = self.backend.stop()
            self.stop_confirmed = result is True
        except Exception:
            self.stop_confirmed = False

    def checkpoint(self):
        if self.fenced.is_set():
            raise ValueError('ISOLATION_FENCED')

    def watch(self):
        while not self.closed.wait(.01):
            with self.lock:
                now, fault = self.clock(), self.monitor_fault
                if now < self.last:
                    fault = 'CLOCK_INVALID'
                elif now - self.started >= self.operation_seconds:
                    fault = 'ISOLATION_DEADLINE'
                elif now - self.last >= self.lease_seconds:
                    fault = 'CONTROLLER_LEASE_EXPIRED'
            if fault:
                self.trip(fault)
                return

    def execute(self):
        watchdog = threading.Thread(target=self.watch, name='isolated-session-watchdog', daemon=True)
        watchdog.start()
        try:
            self.checkpoint()
            self.backend.provision(self.fenced)
            self.checkpoint()
            self.phase = 'STORE_READY'
            self.backend.validate_store()
            self.store_qualified = True
            self.checkpoint()
            self.backend.start(self.fenced)
            self.checkpoint()
            self.backend.validate_engine()
            self.phase = 'ENGINE_READY'
            self.backend.exercise(self)
            self.checkpoint()
            with self.lock:
                self.checkpoint()
                self.phase = 'STOPPING'
                # Fence late asynchronous starts on success too.
                self.fenced.set()
            self.stop_confirmed = self.backend.stop() is True
            if not self.stop_confirmed:
                self.fault, self.phase = 'ENGINE_STOP_UNCONFIRMED', 'FAULT'
        except Exception as error:
            self.operation_error = {'category': type(error).__name__,
                'code': str(error) if re.fullmatch('[A-Z_]{1,80}', str(error)) else 'ISOLATION_BACKEND_ERROR',
                'osError': error.errno if isinstance(error, OSError) else None}
            if not self.fenced.is_set():
                self.trip('ISOLATION_OPERATION_FAILED')
            elif self.fault is None:
                self.fault = 'ENGINE_STOP_UNCONFIRMED'
        finally:
            # Also covers KeyboardInterrupt/SystemExit, unexpected backend
            # exceptions and failures before the first normal stop call.
            if not self.fenced.is_set():
                self.trip('ISOLATION_INTERRUPTED')
            self.closed.set()
            watchdog.join(timeout=1)
            if watchdog.is_alive():
                self.stop_confirmed = False
                self.fault = self.fault or 'WATCHDOG_STOP_UNCONFIRMED'
            if self.stop_confirmed and self.store_qualified:
                try:
                    self.detached = self.backend.detach() is True
                except Exception:
                    self.detached = False
                if not self.detached:
                    self.fault = self.fault or 'STORE_DETACH_UNCONFIRMED'
            if not self.stop_confirmed:
                self.fault = self.fault or 'ENGINE_STOP_UNCONFIRMED'
            self.phase = 'FAULT' if self.fault or not self.stop_confirmed or not self.detached else 'COMPLETE'
            result = {'phase': self.phase, 'fault': self.fault, 'synthetic': True,
                'operationError': self.operation_error,
                'stopConfirmed': self.stop_confirmed, 'storeDetached': self.detached,
                'storeRetained': True, 'restartAllowed': False,
                'imageDownloadEnabled': False, 'imageImportEnabled': False,
                'buildEnabled': False, 'modelLaunchEnabled': False}
            # Stop and detach decisions precede even this final journal write.
            tools.base.atomic(self.directory / 'state.json', result)
        return result


class FakeBackend:
    synthetic = True

    def __init__(self, case):
        self.case, self.events = case, []
        self.running = False
        self.release = threading.Event()

    def provision(self, fence):
        self.events.append('provision')
        if fence.is_set():
            raise ValueError('Already fenced')

    def validate_store(self):
        self.events.append('validate-store')
        if self.case in ('wrong-device', 'disk-over-cap'):
            raise ValueError('Rejected store proof')

    def start(self, fence):
        self.events.append('start')
        if fence.is_set():
            raise ValueError('Already fenced')
        self.running = True

    def validate_engine(self):
        self.events.append('validate-engine')
        if self.case in ('wrong-limits', 'extra-mount', 'shared-containerd'):
            raise ValueError('Rejected engine proof')

    def exercise(self, session):
        self.events.append('exercise')
        if self.case == 'cpu-hot':
            session.trip('CPU_HOT')
        elif self.case == 'disk-full':
            raise OSError('Synthetic full store')
        elif self.case == 'sensor-lost':
            session.trip('SENSOR_STALE')
        elif self.case == 'cancel':
            session.trip('CANCELLED')
        elif self.case in ('blocked-io', 'owner-loss', 'deadline'):
            # The watchdog must stop us while the main control path is blocked.
            if not self.release.wait(2):
                raise RuntimeError('Watchdog did not release the blocked operation')
        else:
            session.pulse()

    def stop(self):
        self.events.append('stop')
        self.running = False
        self.release.set()
        return self.case != 'stop-unconfirmed'

    def detach(self):
        self.events.append('detach')
        if self.running:
            raise AssertionError('Detach while engine still running')
        return self.case != 'detach-unconfirmed'


CASES = ('success', 'wrong-device', 'disk-over-cap', 'wrong-limits', 'extra-mount',
    'shared-containerd', 'cpu-hot', 'disk-full', 'sensor-lost', 'cancel', 'blocked-io',
    'owner-loss', 'deadline', 'stop-unconfirmed', 'detach-unconfirmed')


def rehearse():
    root = ROOT / uuid.uuid4().hex
    cases = []
    for case in CASES:
        backend = FakeBackend(case)
        session = Session(root / case, backend, lease_seconds=.1,
                          operation_seconds=.05 if case == 'deadline' else 3)
        result = session.execute()
        if ((case == 'success') != (result['phase'] == 'COMPLETE') or backend.running or
                ('detach' in backend.events and not result['stopConfirmed'])):
            raise AssertionError('Isolation rehearsal failed: ' + case)
        cases.append({'case': case, 'result': result, 'events': backend.events})
    result = {'status': 'PASS_SYNTHETIC_ISOLATION_CONTROLS', 'synthetic': True,
        'cases': cases, 'caseCount': len(cases), 'nativeDiskQuotaProven': False,
        'nativeEngineStopProven': False, 'imageImportEnabled': False,
        'buildEnabled': False, 'modelLaunchEnabled': False}
    tools.base.atomic(root / 'result.json', result)
    return {**result, 'resultFile': str(root / 'result.json')}
