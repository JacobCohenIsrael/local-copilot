"""Controller/export connection, enabled only for fixed synthetic rehearsals.

No container creation/start command, hardware reader, reset or live-build CLI.
The separate watchdog process calls poll even while the exporter is blocked.
"""
import json
from pathlib import Path
import time

import artifact_export as export
import build_guard as guard
import build_policy_review as policy


def read_json(path):
    export.tools.plain(path)
    with path.open('rb') as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError('Controller record exceeds limit')
    return json.loads(raw)


class RehearsalGate(policy.CpuBuildReadinessGate):
    expected_synthetic = True
    source_fault = 'SYNTHETIC_ONLY'
    eligibility_state = 'ELIGIBLE_IN_REHEARSAL_ONLY'


class Pulse:
    """Monotonic receipt-time lease; filesystem modification time is not trusted."""
    def __init__(self, path, *, clock=time.monotonic):
        self.path, self.clock = path, clock
        self.size, self.changed, self.last = 0, False, clock()

    def age(self):
        export.tools.plain(self.path)
        size, now = self.path.stat().st_size, self.clock()
        if not 0 < size <= 1024 or size < self.size or now < self.last:
            raise ValueError('Controller pulse invalid/regressed')
        if self.size and size > self.size:
            self.changed = True
        if size > self.size:
            self.size, self.last = size, now
        return now - self.last


def pulse(path):
    export.tools.plain(path)
    with path.open('ab') as stream:
        if stream.tell() >= 1024:
            raise ValueError('Rehearsal heartbeat budget exceeded')
        stream.write(b'.')
        stream.flush()


class Session:
    """Single-writer kernel; caller holds namespace/guard-lock for its lifetime."""
    def __init__(self, namespace, directory, target, docker, *, clock=time.monotonic, unix=time.time):
        if not target.synthetic:
            raise ValueError('Live build controller remains disabled')
        self.namespace, self.directory = Path(namespace), Path(directory)
        self.target, self.docker, self.clock, self.unix = target, docker, clock, unix
        self.file = self.namespace / 'state.json'
        export.tools.plain(self.namespace)
        if self.file.exists():
            previous = read_json(self.file)
            if (previous.get('version') != 1 or previous.get('mode') != 'synthetic-controller-only' or
                    previous.get('synthetic') is not True or previous.get('buildEnabled') is not False or
                    previous.get('modelLaunchEnabled') is not False or
                    previous.get('phase') != 'COMPLETE' or previous.get('fault') is not None or
                    previous.get('cleanupComplete') is not True or previous.get('stopConfirmed') is not True):
                raise ValueError('Latched fault or unresolved session: no automatic restart/reset')
        self.gate, self.started = RehearsalGate(), clock()
        self.last_clocks = (self.started, unix())
        self.state = {'version': 1, 'mode': 'synthetic-controller-only', 'sessionId': directory.name,
                      'phase': 'WAITING_BASELINE', 'fault': None, 'containerId': target.container_id,
                      'planSha256': target.plan_sha256, 'metadataSha256': target.metadata_sha256,
                      'synthetic': True, 'buildEnabled': False, 'modelLaunchEnabled': False,
                      'stopConfirmed': False, 'cleanupComplete': False}
        self._save()

    def _save(self):
        guard.base.atomic(self.file, self.state)

    def _stop(self, started=None):
        return guard.stop_target(self.docker, {}, self.target.container_id, started=started,
                                 clock=self.clock, matcher=self.target.matcher)

    def fail(self, code):
        if self.state['fault'] is not None:
            return self.state
        stop_started = self.clock()  # Includes journal time in the stop budget.
        self.state.update(phase='FAULT', fault={'code': code})
        try:
            self._save()  # A durable fault is attempted before any Docker mutation.
        except Exception as error:
            self.state['journalError'] = type(error).__name__
        finally:
            self.state.update(self._stop(stop_started))
        try:
            self._save()
        except Exception as error:
            self.state['journalError'] = type(error).__name__
        return self.state

    def _receipt(self, directory):
        directory = Path(directory).absolute()
        export.tools.plain(directory)
        if directory.parent != export.ROOT or not guard.re.fullmatch('[0-9a-f]{32}', directory.name):
            raise ValueError('Export receipt outside owned namespace')
        receipt = read_json(directory / 'result.json')
        if (receipt.get('state') != 'ARTIFACTS_SAVED_ACK_SENT' or receipt.get('acknowledged') is not True or
                receipt.get('synthetic') is not True or receipt.get('containerId') != self.target.container_id or
                receipt.get('planSha256') != self.target.plan_sha256 or
                receipt.get('metadataSha256') != self.target.metadata_sha256 or
                receipt.get('buildEnabled') is not False or receipt.get('modelLaunchEnabled') is not False):
            raise ValueError('Export receipt identity/completion mismatch')
        return str(directory)

    def poll(self, sample=None, *, controller_age=0, cancelled=False, export_requested=False, export_directory=None):
        if self.state['phase'] in ('FAULT', 'COMPLETE'):
            return self.state
        try:
            now, unix = self.clock(), self.unix()
            elapsed = now - self.started
            previous_mono, previous_unix = self.last_clocks
            if (not policy.finite(now) or not policy.finite(unix) or now < previous_mono or
                    unix < previous_unix or abs((unix - previous_unix) - (now - previous_mono)) >
                    self.gate.draft['temperature']['maxSampleAgeSeconds']):
                return self.fail('CLOCK_DISCONTINUITY')
            self.last_clocks = (now, unix)
            if sample is not None:
                observation = self.gate.observe(sample, elapsed=elapsed, unix=unix,
                                                controller_age=controller_age, cancelled=cancelled)
            elif cancelled:
                return self.fail('CANCELLED')
            else:
                observation = self.gate.tick(elapsed=elapsed, unix=unix, controller_age=controller_age)
            if observation['fault']:
                return self.fail(observation['fault'])
            if elapsed > 35:  # Rehearsal-only outer cap, never the real build budget.
                return self.fail('REHEARSAL_DEADLINE')
            info = self.target.inspect(guard.DeadlineDocker(self.docker, self.clock() + 1, self.clock))
            if info is None:
                return self.fail('WORKER_MISSING')
            if info['State'].get('OOMKilled'):
                return self.fail('WORKER_OOM')
            phase = self.state['phase']
            if phase == 'WAITING_BASELINE' and observation['state'] == self.gate.eligibility_state:
                self.state['phase'] = 'ARMED'
            if info['State']['Running']:
                if self.state['phase'] == 'WAITING_BASELINE':
                    return self.fail('WORKER_STARTED_BEFORE_BASELINE')
                if self.state['phase'] == 'ARMED':
                    self.state['phase'] = 'RUNNING'
                if export_requested:
                    self.state['phase'] = 'EXPORTING'
            elif info['State'].get('Status') != 'created':
                # ACK may let the worker exit before the host publishes its receipt.
                # Keep monitoring the feed/lease while waiting for that receipt.
                if phase != 'EXPORTING':
                    return self.fail('UNEXPECTED_WORKER_EXIT')
                if info['State']['ExitCode'] != 0:
                    return self.fail('WORKER_EXIT_ERROR')
                if export_directory is not None:
                    self.state['exportDirectory'] = self._receipt(export_directory)
                    self.state.update(self._stop())
                    if not self.state['stopConfirmed'] or not self.state['cleanupComplete']:
                        return self.fail('CLEANUP_UNCONFIRMED')
                    self.state['phase'] = 'COMPLETE'
            if self.state['phase'] != phase:
                self._save()
            return self.state
        except Exception as error:
            self.state['error'] = type(error).__name__
            return self.fail('CONTROLLER_ERROR')


class GuardedExport:
    """The collector can proceed only with a fresh independent watchdog lease."""
    def __init__(self, namespace, target, docker, lease):
        if not target.synthetic:
            raise ValueError('Live export remains disabled')
        self.namespace, self.target, self.docker, self.lease = Path(namespace), target, docker, lease

    def verify(self):
        state = read_json(self.namespace / 'state.json')
        if (state.get('phase') != 'EXPORTING' or state.get('fault') is not None or
                state.get('containerId') != self.target.container_id or
                state.get('planSha256') != self.target.plan_sha256 or
                state.get('synthetic') is not True or state.get('buildEnabled') is not False or
                state.get('modelLaunchEnabled') is not False or
                self.lease.age() > 2.5 or not self.lease.changed):
            raise ValueError('Independent watchdog is faulted, stale or not exporting')
        info = self.target.inspect(guard.DeadlineDocker(self.docker, self.lease.clock() + 1, self.lease.clock))
        # The inspect RPC may have taken time while the guard tripped/died.
        after = read_json(self.namespace / 'state.json')
        if after != state or self.lease.age() > 2.5:
            raise ValueError('Independent watchdog permission changed during inspect')
        return info is not None and info['State']['Running'] and not info['State'].get('OOMKilled')

    def copy(self, path, deadline):
        export.capture_archive(self.target.container_id, path, deadline)

    def acknowledge(self, deadline):
        if self.verify() is not True:
            raise ValueError('Export acknowledgement lost watchdog permission')
        export.acknowledge_export(self.target.container_id, deadline)
