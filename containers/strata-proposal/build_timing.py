"""One disabled CPU-build retry proposal; only query timing differs from policy."""
import contextlib
import hashlib
import io
from pathlib import Path
import sys

import build_recovery as recovery

base, tools, cpu, offline = recovery.base, recovery.tools, recovery.cpu, recovery.offline
REPO, HERE = recovery.REPO, recovery.HERE
ROOT = REPO / '.runtime/cpu-build-timing-review'
LIVE = REPO / '.runtime/cpu-build-timing-1'
APPROVAL = HERE / 'cpu-build-timing-approval.json'
SCOPE = 'one-cpu-build-timing-imported-image-no-download-import-or-model'
WATCH_FLAG = '--watch-timing'
PRIOR_SHA = 'b01b440e575209bb8c2fb629b18a0c4703301d5272acd950db2714b0f310ffc6'
PRIOR = recovery.ROOT / PRIOR_SHA
READER = HERE / 'cpu_build_reader.ps1'
READER_SHA = '4c449b37d835f7c8e03d09a1eb479770143f1ec56b0754865277ccc59c32ddd4'
TIMING = {'sensorQuerySeconds': 1.5, 'readyQuerySeconds': 1.5,
          'previousSensorQuerySeconds': 1, 'previousReadyQuerySeconds': 1,
          'appliesToModelRuntime': False}
read = recovery.read
source_tree, image_ready, vm_ready = base.source_tree, base.image_ready, base.vm_ready


def reader_contract():
    original = cpu.bounded(HERE / 'cpu_reader.ps1', 16384)
    variant = cpu.bounded(READER, 16384)
    expected = original.replace(b'# Fixed bounded ASUS reader.',
        b'# CPU-build-only timing variant; activation requires its exact one-attempt permit.').replace(
        b'$sample.querySeconds -gt 1)', b'$sample.querySeconds -gt 1.5)')
    if variant != expected or hashlib.sha256(variant).hexdigest() != READER_SHA:
        raise ValueError('BUILD_TIMING_READER_CHANGED')
    return {'path': str(READER), 'sha256': READER_SHA, 'originalSha256': cpu.READER_SHA,
            'onlyExecutableChange': 'querySeconds cutoff 1 -> 1.5; CIM timeout remains 2 seconds'}


def previous():
    earlier = recovery.previous()
    manifest = read(PRIOR / 'execution-preservation.json', 1048576)
    packet = read(PRIOR / 'review.json')
    if base.sha(packet) != PRIOR_SHA or manifest['reviewSha256'] != PRIOR_SHA:
        raise ValueError('PREVIOUS_TIMING_ATTEMPT_REVIEW_CHANGED')
    for key in ('attempt', 'reader', 'launcher', 'capacityProbe'):
        record = manifest[key]; directory = Path(record['directory'])
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('PREVIOUS_TIMING_EVIDENCE_FILE_SET_CHANGED')
        for relative, identity in record['files'].items():
            path = directory / relative; tools.plain(path)
            if path.stat().st_size != identity['bytes'] or tools.sha(path) != identity['sha256']:
                raise ValueError('PREVIOUS_TIMING_EVIDENCE_CHANGED')
    for name, identity in manifest['reviewEvidence'].items():
        path = PRIOR / name
        if path.stat().st_size != identity['bytes'] or tools.sha(path) != identity['sha256']:
            raise ValueError('PREVIOUS_TIMING_REVIEW_EVIDENCE_CHANGED')
    for relative, expected in packet['helperSha256'].items():
        raw = cpu.bounded(PRIOR / 'helpers' / relative, 131072).replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('PREVIOUS_TIMING_HELPER_CHANGED')
    result = read(PRIOR / 'execution-result.json')
    log = read(PRIOR / 'retained-container-log.json')
    if (result['status'] != 'CPU_BUILD_STOPPED_ON_SENSOR_FEED_FAULT' or
            result['attemptConsumed'] is not True or result['containerRetainedStopped'] is not True or
            result['modelRan'] is not False or tools.sha(PRIOR / 'retained-container.log') != log['sha256']):
        raise ValueError('PREVIOUS_TIMING_RESULT_CHANGED')
    return {'reviewSha256': PRIOR_SHA, 'earlier': earlier,
            'preservationSha256': tools.sha(PRIOR / 'execution-preservation.json'),
            'resultSha256': tools.sha(PRIOR / 'execution-result.json'),
            'failedContainerId': result['containerId'], 'previousAttemptsReset': False}


def prepare():
    preservation = previous()
    old = read(PRIOR / 'review.json')
    old_plan = offline.checked_proposal(old['offlineDirectory'], old['offlinePlanSha256'])
    with contextlib.redirect_stdout(io.StringIO()):
        directory = offline.prepare(old_plan['toolDirectory'])
    plan_sha = tools.sha(directory / 'offline-plan.json')
    plan = offline.checked_proposal(directory, plan_sha)
    packet = base.material(selection=(directory, plan_sha, plan), live_namespace=LIVE, scope=SCOPE)
    packet.update(status='CPU_BUILD_TIMING_READY_FOR_APPROVAL', recoveryOf=preservation,
                  buildTiming=TIMING, buildReader=reader_contract())
    packet['controls']['maxQuerySeconds'] = TIMING['sensorQuerySeconds']
    digest = base.sha(packet); destination = ROOT / digest
    tools.plain(ROOT); destination.mkdir(parents=True, exist_ok=False)
    tools.base.atomic(destination / 'review.json', packet)
    tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return destination, packet


def review():
    digest = read(ROOT / 'candidate.json', 4096)['reviewSha256']
    if not base.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('BUILD_TIMING_REVIEW_INVALID')
    packet = read(ROOT / digest / 'review.json')
    effective = base.policy.load_effective_controls()
    effective['temperature']['maxQuerySeconds'] = TIMING['sensorQuerySeconds']
    plan = offline.checked_proposal(packet['offlineDirectory'], packet['offlinePlanSha256'])
    if (base.sha(packet) != digest or packet['scope'] != SCOPE or packet['liveNamespace'] != str(LIVE) or
            packet['status'] != 'CPU_BUILD_TIMING_READY_FOR_APPROVAL' or packet['buildTiming'] != TIMING or
            packet['buildReader'] != reader_contract() or packet['helperSha256'] != base.helpers() or
            packet['sourceReviewSha256'] != base.sha(cpu.report()) or packet['controls'] != effective['temperature'] or
            packet['resources'] != effective['resources'] or packet['stop'] != effective['stop'] or
            packet['createArgs'] != plan['createArgs'] or packet['mutableFilesystems'] != plan['mutableFilesystems'] or
            packet['image'] != base.image_plan.metadata() or
            packet['proposedVmEnvelope']['proposalSha256'] != tools.sha(HERE / 'wsl-build-limits.proposed') or
            any(packet[k] is not False for k in ('buildEnabled', 'modelLaunchEnabled', 'imageImportEnabled', 'imageDownloadEnabled'))):
        raise ValueError('BUILD_TIMING_REVIEW_STALE')
    return digest, packet


class Permit(base.Permit):
    @property
    def live_namespace(self): return LIVE

    @property
    def reader_contract(self): return READER, READER_SHA

    @property
    def query_budget(self): return TIMING['sensorQuerySeconds']


def authorize():
    if not APPROVAL.exists():
        raise ValueError('CPU_BUILD_TIMING_NOT_APPROVED')
    digest, packet = review(); decision = read(APPROVAL, 16384)
    if (type(decision.get('version')) is not int or decision['version'] != 1 or
            decision.get('status') != 'owner-approved-one-cpu-build-timing' or decision.get('scope') != SCOPE or
            decision.get('reviewSha256') != digest or decision.get('acceptBuildTiming') != TIMING or
            decision.get('acceptSourceQualificationSha256') != packet['sourceReviewSha256'] or
            decision.get('acceptSourceLimitation') != cpu.LIMITATION or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts'] != 1 or
            decision.get('synthetic') is not False or decision.get('buildEnabled') is not True or
            decision.get('acceptStoppedFailureContainerRetention') is not True or
            any(decision.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'modelLaunchEnabled')) or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip()):
        raise ValueError('CPU_BUILD_TIMING_APPROVAL_INVALID')
    return Permit(digest, base.encoded(packet).decode(), base.sha(decision))


def selected():
    _, packet = review()
    return Path(packet['offlineDirectory']), packet['offlinePlanSha256'], offline.checked_proposal(
        packet['offlineDirectory'], packet['offlinePlanSha256'])


def run():
    permit = authorize()
    if LIVE.exists() and any(p.name != 'controller-lock' for p in LIVE.iterdir()):
        raise ValueError('CPU_BUILD_TIMING_ATTEMPT_CONSUMED')
    if previous() != permit.packet['recoveryOf']:
        raise ValueError('PREVIOUS_TIMING_EVIDENCE_CHANGED')
    if tools.sha(Path.home() / '.wslconfig') != permit.packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('APPROVED_WSL_POLICY_CHANGED')
    return recovery.first_build.run(admitter=sys.modules[__name__])


def summary():
    try:
        digest, packet = review()
    except (OSError, ValueError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'modelLaunchEnabled': False}
    return {'status': 'ATTEMPT_CONSUMED' if (LIVE / 'attempt.json').exists() else packet['status'],
            'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
            'approvalExists': APPROVAL.exists(), 'buildTiming': TIMING, 'modelLaunchEnabled': False,
            'imageDownloadEnabled': False, 'imageImportEnabled': False}
