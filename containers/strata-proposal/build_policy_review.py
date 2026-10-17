"""Offline review of a disabled build policy. Only synthetic observations are accepted.

No Docker calls, sensor reads, approvals, build starts or policy writes exist here.
The simulation intentionally exercises a requested exception, not the live guard.
"""
import copy
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_draft():
    raw = (HERE / 'build-policy.draft.json').read_bytes().replace(b'\r\n', b'\n')
    draft = json.loads(raw)
    if (draft['status'] != 'draft-for-owner-review' or
            any(draft[key] is not False for key in ('approved', 'buildEnabled', 'modelLaunchEnabled')) or
            draft['throttleException']['status'] != 'requested-not-approved'):
        raise ValueError('Review accepts only a disabled, unapproved draft')
    return draft, hashlib.sha256(raw).hexdigest()


def load_approval(draft, sha):
    """Check the recorded human decision; never grant workload start authority."""
    approval = json.loads((HERE / 'build-policy-approval.json').read_text())
    if (approval.get('version') != 1 or approval.get('status') != 'owner-approved-controls-only' or
            approval.get('approvedDraftSha256') != sha or approval.get('scope') != draft['scope'] or
            any(approval.get(key) is not False for key in ('buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('Approval does not bind this disabled build-only policy')
    return approval


def load_thermal_revision():
    baseline, sha = load_draft()
    load_approval(baseline, sha)
    revision = json.loads((HERE / 'thermal-revision.proposed.json').read_text())
    if (type(revision.get('version')) is not int or revision['version'] != 1 or
            revision.get('status') != 'proposal-only-not-approved' or
            any(revision.get(key) is not False for key in ('approved', 'buildEnabled', 'modelLaunchEnabled')) or
            revision.get('basedOnApprovedDraftSha256') != sha or revision.get('scope') != baseline['scope']):
        raise ValueError('Thermal revision must remain a disabled proposal bound to the approved CPU-only policy')
    changes = revision.get('temperatureChanges')
    if (not isinstance(changes, dict) or set(changes) != {'startAtOrBelowC', 'stopAtOrAboveC'} or
            not all(finite(value) for value in changes.values()) or
            not 0 < changes['startAtOrBelowC'] < changes['stopAtOrAboveC'] < 100):
        raise ValueError('Revision may change only the two temperature controls below the documented 100 C limit')
    candidate = copy.deepcopy(baseline)
    candidate['temperature'].update(changes)
    return candidate, revision


def load_effective_controls():
    """Resolve the two recorded human decisions; retain disabled workload flags."""
    candidate, revision = load_thermal_revision()
    raw = (HERE / 'thermal-revision.proposed.json').read_bytes().replace(b'\r\n', b'\n')
    receipt = json.loads((HERE / 'thermal-revision-approval.json').read_text(encoding='utf-8'))
    if (type(receipt.get('version')) is not int or receipt['version'] != 1 or
            receipt.get('status') != 'owner-approved-controls-only' or
            receipt.get('approvedRevisionSha256') != hashlib.sha256(raw).hexdigest() or
            receipt.get('scope') != revision['scope'] or
            any(receipt.get(key) is not False for key in ('buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('Thermal approval does not bind this disabled CPU-only revision')
    return candidate


def coverage_error(sample, draft, *, age_seconds=0, baseline_pending=False):
    """Remaining reader lifetime required before a future controller starts work.

    This does not validate source/freshness or start anything. The real guard
    must also enforce those checks and monitor continuously through shutdown.
    """
    remaining = sample.get('readerRemainingSeconds') if isinstance(sample, dict) else None
    if not finite(remaining) or remaining < 0 or not finite(age_seconds) or age_seconds < 0:
        return 'READER_COVERAGE_MISSING'
    required = draft['resources']['deadlineSeconds'] + draft['stop']['confirmStoppedWithinSeconds']
    if baseline_pending:
        required += draft['temperature']['coolBaselineSeconds']
    if remaining - age_seconds < required:
        return 'READER_COVERAGE_INSUFFICIENT'
    return None


class ThermalRehearsal:
    """A deterministic thought experiment; ELIGIBLE is never build authority."""
    expected_synthetic = True
    source_fault = 'SYNTHETIC_ONLY'
    eligibility_state = 'ELIGIBLE_IN_SIMULATION_ONLY'
    def __init__(self, draft):
        self.draft = copy.deepcopy(draft)
        self.state = 'WAITING'
        self.fault = None
        self.sequence = 0
        self.last_tick = None
        self.last_stamp = None
        self.cool_since = None
        self.started = None
        self.throttle = None

    def trip(self, code):
        self.fault = self.fault or code
        self.state = 'FAULT'

    def observe(self, sample, *, elapsed, unix, controller_age=0, cancelled=False):
        if self.fault:
            return self.snapshot()
        p = self.draft['temperature']
        if (isinstance(sample, dict) and sample.get('synthetic') is self.expected_synthetic and
                type(sample.get('cpuThermalThrottling')) is bool):
            self.throttle = sample['cpuThermalThrottling']
        if not isinstance(sample, dict) or sample.get('synthetic') is not self.expected_synthetic:
            self.trip(self.source_fault)
        elif (not finite(elapsed) or elapsed < 0 or not finite(unix) or
              (self.last_tick is not None and elapsed <= self.last_tick)):
            self.trip('CLOCK_INVALID')
        elif self.last_tick is not None and elapsed - self.last_tick > p['maxSampleAgeSeconds']:
            self.trip('MONITOR_GAP')
        elif cancelled:
            self.trip('CANCELLED')
        elif not finite(controller_age) or not 0 <= controller_age <= p['maxControllerLeaseSeconds']:
            self.trip('CONTROLLER_LEASE_EXPIRED')
        elif (type(sample.get('version')) is not int or sample['version'] != 1 or sample.get('error') or
              sample.get('source') != p['source']):
            self.trip('SENSOR_SOURCE')
        elif type(sample.get('sequence')) is not int or sample['sequence'] <= self.sequence:
            self.trip('SENSOR_SEQUENCE')
        elif (not finite(sample.get('recordedAtUnix')) or
              not 0 <= unix - sample['recordedAtUnix'] <= p['maxSampleAgeSeconds'] or
              (self.last_stamp is not None and sample['recordedAtUnix'] <= self.last_stamp)):
            self.trip('SENSOR_STALE')
        elif not finite(sample.get('querySeconds')) or not 0 <= sample['querySeconds'] <= p['maxQuerySeconds']:
            self.trip('SENSOR_QUERY_TIMEOUT')
        elif sample.get('validatedCpuSensor') is not True:
            self.trip('CPU_SENSOR_UNVALIDATED')
        elif not finite(sample.get('cpuTemperatureC')) or not 0 < sample['cpuTemperatureC'] <= 125:
            self.trip('CPU_TEMPERATURE_MISSING')
        elif sample.get('cpuThermalThrottling') is not None and type(sample['cpuThermalThrottling']) is not bool:
            self.trip('CPU_THROTTLE_INVALID')
        elif (sample.get('cpuThermalThrottling') is None and
              self.draft['throttleException']['allowUnknownInSimulation'] is not True):
            self.trip('CPU_THROTTLE_MISSING')
        elif sample.get('cpuThermalThrottling') is True:
            self.trip('CPU_THROTTLING')
        elif sample['cpuTemperatureC'] >= p['stopAtOrAboveC']:
            self.trip('CPU_HOT')
        elif self.started is None and coverage_error(sample, self.draft,
                age_seconds=unix - sample['recordedAtUnix']):
            self.trip(coverage_error(sample, self.draft, age_seconds=unix - sample['recordedAtUnix']))
        elif self.started is not None and elapsed - self.started >= self.draft['resources']['deadlineSeconds']:
            self.trip('BUILD_DEADLINE')
        else:
            # Unknown is preserved even in the proposed exception's simulation.
            self.throttle = sample.get('cpuThermalThrottling')
            if self.started is None:
                if sample['cpuTemperatureC'] <= p['startAtOrBelowC']:
                    if self.cool_since is None:
                        self.cool_since = elapsed
                    if elapsed - self.cool_since >= p['coolBaselineSeconds']:
                        self.started = elapsed
                        self.state = self.eligibility_state
                else:
                    self.cool_since = None
            self.sequence = sample['sequence']
            self.last_stamp = sample['recordedAtUnix']
            self.last_tick = elapsed
        return self.snapshot()

    def snapshot(self):
        return {'state': self.state, 'fault': self.fault,
                'cpuThermalThrottling': self.throttle, 'simulationOnly': self.expected_synthetic,
                'buildEnabled': False, 'modelLaunchEnabled': False}


class CpuBuildReadinessGate(ThermalRehearsal):
    """Build-only telemetry gate, never process/start authority or a watchdog.

    Accepts newly received non-synthetic frames. An independent live caller
    must supply monotonic receipt time and invoke tick even when no frame arrives.
    Reader validation remains mandatory; current ASUS frames are unvalidated.
    """
    expected_synthetic = False
    source_fault = 'REAL_SOURCE_REQUIRED'
    eligibility_state = 'ELIGIBLE_FOR_BUILD_REVIEW'

    def __init__(self):
        super().__init__(load_effective_controls())
        self.last_event = None

    def observe(self, sample, *, elapsed, unix, controller_age=0, cancelled=False):
        if self.fault:
            return self.snapshot()
        if not finite(elapsed) or (self.last_event is not None and elapsed < self.last_event):
            self.trip('CLOCK_INVALID')
            return self.snapshot()
        self.last_event = elapsed
        return super().observe(sample, elapsed=elapsed, unix=unix,
                               controller_age=controller_age, cancelled=cancelled)

    def tick(self, *, elapsed, unix, controller_age):
        if self.fault:
            return self.snapshot()
        p = self.draft['temperature']
        if (not finite(elapsed) or not finite(unix) or not finite(controller_age) or
                elapsed < 0 or controller_age < 0 or (self.last_event is not None and elapsed < self.last_event)):
            self.trip('CLOCK_INVALID')
        elif controller_age > p['maxControllerLeaseSeconds']:
            self.trip('CONTROLLER_LEASE_EXPIRED')
        elif self.last_tick is None or self.last_stamp is None:
            self.trip('SENSOR_MISSING')
        elif (elapsed - self.last_tick > p['maxSampleAgeSeconds'] or
                not 0 <= unix - self.last_stamp <= p['maxSampleAgeSeconds']):
            self.trip('SENSOR_STALE')
        elif self.started is not None and elapsed - self.started >= self.draft['resources']['deadlineSeconds']:
            self.trip('BUILD_DEADLINE')
        self.last_event = elapsed
        return self.snapshot()


def synthetic(base_sequence, seconds, **changes):
    return {'version': 1, 'sequence': base_sequence, 'synthetic': True,
            'source': 'ASUS DSTS 0x00120094', 'error': None,
            'recordedAtUnix': 1000 + seconds, 'querySeconds': .02,
            'validatedCpuSensor': True, 'cpuTemperatureC': 65,
            'cpuThermalThrottling': None, 'readerRemainingSeconds': 1920 - seconds, **changes}


def report():
    import build_guard
    draft, sha = load_draft()
    approval = load_approval(draft, sha)
    controls = load_effective_controls()
    contract = build_guard.plan()  # Read-only hash/identity check; no Docker call.
    if draft['buildManifestSha256'] != contract['buildManifestSha256']:
        raise ValueError('Draft no longer binds the prepared build')
    cases = {}
    cool = ThermalRehearsal(controls)
    for second in range(11):
        cool.observe(synthetic(second + 1, second), elapsed=second, unix=1000 + second)
    cases['cool_baseline_unknown_throttle'] = cool.snapshot()
    cases['then_hot'] = cool.observe(synthetic(12, 11, cpuTemperatureC=97), elapsed=11, unix=1011)
    for name, changes, kwargs in [
        ('unvalidated_sensor', {'validatedCpuSensor': False}, {}),
        ('known_throttling', {'cpuThermalThrottling': True}, {}),
        ('stale_sensor', {'recordedAtUnix': 990}, {}),
        ('lost_controller', {}, {'controller_age': 3}),
        ('short_reader_probe', {'readerRemainingSeconds': 2}, {}),
        ('cancelled', {}, {'cancelled': True}),
        ('real_feed_rejected', {'synthetic': False}, {})
    ]:
        model = ThermalRehearsal(controls)
        cases[name] = model.observe(synthetic(1, 0, **changes), elapsed=0, unix=1000, **kwargs)
    return {'status': 'POLICY_APPROVED_BUILD_BLOCKED', 'draftSha256': sha,
            'policyApproval': approval['status'],
            'approvedTemperatureControls': controls['temperature'],
            'reviewedReaderSha256': draft['readerSha256'],
            'currentReaderSha256': contract['readerSha256'],
            'readerChangedSinceReview': draft['readerSha256'] != contract['readerSha256'],
            'readerRevalidationRequired': True,
            'buildEnabled': False, 'modelLaunchEnabled': False,
            'liveGuardChanged': False, 'remainingGates': draft['remainingGates'][1:],
            'syntheticCases': cases}


def thermal_revision_report():
    baseline, _ = load_draft()
    candidate, revision = load_thermal_revision()
    controls = load_effective_controls()
    model = ThermalRehearsal(candidate)
    for second in range(11):
        model.observe(synthetic(second + 1, second, cpuTemperatureC=92),
                      elapsed=second, unix=1000 + second)
    cases = {'start_at_92_after_ten_seconds': model.snapshot()}
    cases['running_at_95'] = model.observe(synthetic(12, 11, cpuTemperatureC=95), elapsed=11, unix=1011)
    cases['stop_at_97'] = model.observe(synthetic(13, 12, cpuTemperatureC=97), elapsed=12, unix=1012)
    warm = ThermalRehearsal(candidate)
    for second in range(11):
        warm.observe(synthetic(second + 1, second, cpuTemperatureC=95), elapsed=second, unix=1000 + second)
    cases['baseline_at_95_still_waits'] = warm.snapshot()
    keys = ('startAtOrBelowC', 'stopAtOrAboveC', 'coolBaselineSeconds')
    return {'status': 'THERMAL_CONTROLS_APPROVED_BUILD_BLOCKED',
            'requiresOwnerApproval': False, 'buildEnabled': False, 'modelLaunchEnabled': False,
            'originallyApproved': {key: baseline['temperature'][key] for key in keys},
            'currentlyApproved': {key: controls['temperature'][key] for key in keys},
            'proposed': {key: candidate['temperature'][key] for key in keys},
            'nonTemperatureControlsChanged': False, 'syntheticCases': cases,
            'limitations': revision['limitations']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--thermal-revision', action='store_true', help='Review the recorded CPU-only temperature revision')
    options = parser.parse_args()
    print(json.dumps(thermal_revision_report() if options.thermal_revision else report(), indent=2))
