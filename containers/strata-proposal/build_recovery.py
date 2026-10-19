"""Prepare one new CPU build from the imported image; spent attempts stay frozen."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys

import build_admission as base
import cpu_source_review as cpu
import first_build
import offline_build_plan as offline
import stage_build_tools as tools

REPO, HERE = base.HERE.parents[1], base.HERE
ROOT = REPO / '.runtime/cpu-build-recovery-review'
LIVE = REPO / '.runtime/cpu-build-recovery-1'
APPROVAL = HERE / 'cpu-build-recovery-approval.json'
SCOPE = 'one-cpu-build-recovery-imported-image-no-download-import-or-model'
WATCH_FLAG = '--watch-recovery'
PRIOR_SHA = '35f7e4b766ef0fd25c99de44428ab49bcca1a4a53254c4f384b96a6485163e78'
PRIOR = REPO / '.runtime/desktop-test-review' / PRIOR_SHA
NINJA_VERSION = b'1.13.2.git.kitware.jobserver-pipe-1'
source_tree, image_ready, vm_ready = base.source_tree, base.image_ready, base.vm_ready


def read(path, maximum=131072):
    return json.loads(cpu.bounded(Path(path), maximum))


def previous():
    """Validate old state, readers, archive metadata and exact approved code."""
    manifest = read(PRIOR / 'execution-preservation.json', 1048576)
    prior = read(PRIOR / 'review.json')
    if base.sha(prior) != PRIOR_SHA or manifest['reviewSha256'] != PRIOR_SHA:
        raise ValueError('PRIOR_BUILD_REVIEW_CHANGED')
    for key in ('importAttempt', 'buildAttempt', 'importReader', 'buildReader', 'launcher'):
        record = manifest[key]; directory = Path(record['directory'])
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('PRIOR_BUILD_EVIDENCE_FILE_SET_CHANGED')
        for relative, expected in record['files'].items():
            path = directory / relative; tools.plain(path); stat = path.stat()
            if stat.st_size != expected['bytes']:
                raise ValueError('PRIOR_BUILD_EVIDENCE_SIZE_CHANGED')
            if 'sha256' in expected:
                if tools.sha(path) != expected['sha256']:
                    raise ValueError('PRIOR_BUILD_EVIDENCE_CHANGED')
            elif ([stat.st_dev, stat.st_ino] != expected['fileIdentity'] or stat.st_mtime_ns != expected['mtimeNs']):
                raise ValueError('RETAINED_OCI_ARCHIVE_CHANGED')
    for name, record in manifest['reviewEvidence'].items():
        path = PRIOR / name
        if path.stat().st_size != record['bytes'] or tools.sha(path) != record['sha256']:
            raise ValueError('PRIOR_EXECUTION_REVIEW_EVIDENCE_CHANGED')
    for relative, expected in prior['helperSha256'].items():
        raw = cpu.bounded(PRIOR / 'helpers' / relative, 131072).replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('PRIOR_APPROVED_HELPER_CHANGED')
    result = read(PRIOR / 'execution-result.json')
    if (result['status'] != 'IMPORT_COMPLETE_BUILD_FAULT' or result['imageImportComplete'] is not True or
            result['attemptConsumed'] is not True or result['modelRan'] is not False):
        raise ValueError('PRIOR_EXECUTION_STATUS_INVALID')
    return {'reviewSha256': PRIOR_SHA, 'preservationSha256': tools.sha(PRIOR / 'execution-preservation.json'),
        'resultSha256': tools.sha(PRIOR / 'execution-result.json'), 'priorHelpers': len(prior['helperSha256']),
        'failedNamespace': manifest['buildAttempt']['directory'], 'imageAlreadyImported': True,
        'archiveBodyRehashed': False, 'previousAttemptsReset': False}


def version_evidence(plan):
    path = Path(plan['toolDirectory']) / 'tools/ninja/bin/ninja'
    raw = cpu.bounded(path, 1048576)
    if not raw.startswith(b'\x7fELF') or raw.count(NINJA_VERSION + b'\0') != 1:
        raise ValueError('PINNED_NINJA_VERSION_LITERAL_CHANGED')
    return {'binarySha256': hashlib.sha256(raw).hexdigest(), 'embeddedVersion': NINJA_VERSION.decode(),
        'formerScriptExpected': '1.13.2', 'literalMismatchConfirmed': True,
        'historicalFailingLineUnrecorded': True, 'binaryExecutedDuringPreparation': False}


def prepare():
    preservation = previous()
    _, _, old = base.selected()
    # A new immutable input package; never edit the spent c47d... package/pointer.
    with contextlib.redirect_stdout(io.StringIO()):
        directory = offline.prepare(old['toolDirectory'])
    plan_sha = tools.sha(directory / 'offline-plan.json')
    plan = offline.checked_proposal(directory, plan_sha)
    packet = base.material(selection=(directory, plan_sha, plan), live_namespace=LIVE, scope=SCOPE)
    packet.update(status='CPU_BUILD_RECOVERY_READY_FOR_APPROVAL', recoveryOf=preservation,
        startupDiagnosis=version_evidence(plan),
        diagnostics={'retainedLogBytes': 65536, 'captureSeconds': 2, 'stderrIncluded': True,
            'failedContainerRetainedStopped': True, 'daemonLogMaximumBytes': 2 * 1024**2,
            'stopBeforeLogCapture': True}, imageImportEnabled=False, imageDownloadEnabled=False,
        imagePreparationLimitation='Uses the already-imported pinned image; no download, load, import or image build command.')
    digest = base.sha(packet); destination = ROOT / digest
    tools.plain(ROOT); destination.mkdir(parents=True, exist_ok=False)
    tools.base.atomic(destination / 'review.json', packet)
    tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return destination, packet


def review():
    digest = read(ROOT / 'candidate.json', 4096)['reviewSha256']
    if not base.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('CPU_RECOVERY_REVIEW_INVALID')
    packet = read(ROOT / digest / 'review.json')
    controls = base.policy.load_effective_controls()
    plan = offline.checked_proposal(packet['offlineDirectory'], packet['offlinePlanSha256'])
    if (base.sha(packet) != digest or packet['scope'] != SCOPE or
            packet['status'] != 'CPU_BUILD_RECOVERY_READY_FOR_APPROVAL' or packet['liveNamespace'] != str(LIVE) or
            packet['helperSha256'] != base.helpers() or packet['sourceReviewSha256'] != base.sha(cpu.report()) or
            packet['controls'] != controls['temperature'] or packet['resources'] != controls['resources'] or
            packet['stop'] != controls['stop'] or packet['createArgs'] != plan['createArgs'] or
            packet['mutableFilesystems'] != plan['mutableFilesystems'] or
            packet['image'] != base.image_plan.metadata() or
            packet['startupDiagnosis'] != version_evidence(plan) or
            packet['proposedVmEnvelope']['proposalSha256'] != tools.sha(HERE / 'wsl-build-limits.proposed') or
            any(packet[k] is not False for k in ('buildEnabled','modelLaunchEnabled','imageImportEnabled','imageDownloadEnabled'))):
        raise ValueError('CPU_RECOVERY_REVIEW_STALE')
    return digest, packet


class Permit(base.Permit):
    @property
    def live_namespace(self):
        return LIVE


def authorize():
    if not APPROVAL.exists():
        raise ValueError('CPU_BUILD_RECOVERY_NOT_APPROVED')
    digest, packet = review(); decision = read(APPROVAL, 16384)
    if (type(decision.get('version')) is not int or decision['version'] != 1 or
            decision.get('status') != 'owner-approved-one-cpu-build-recovery' or
            decision.get('scope') != SCOPE or decision.get('reviewSha256') != digest or
            decision.get('acceptSourceQualificationSha256') != packet['sourceReviewSha256'] or
            decision.get('acceptSourceLimitation') != cpu.LIMITATION or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts'] != 1 or
            decision.get('synthetic') is not False or decision.get('buildEnabled') is not True or
            decision.get('acceptStoppedFailureContainerRetention') is not True or
            any(decision.get(k) is not False for k in ('imageDownloadEnabled','imageImportEnabled','modelLaunchEnabled')) or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip()):
        raise ValueError('CPU_RECOVERY_APPROVAL_SCOPE_OR_HASH_INVALID')
    return Permit(digest, base.encoded(packet).decode(), base.sha(decision))


def selected():
    _, packet = review()
    directory = Path(packet['offlineDirectory'])
    return directory, packet['offlinePlanSha256'], offline.checked_proposal(directory, packet['offlinePlanSha256'])


def run():
    permit = authorize()
    if LIVE.exists() and any(p.name != 'controller-lock' for p in LIVE.iterdir()):
        raise ValueError('CPU_RECOVERY_ATTEMPT_CONSUMED')
    if previous() != permit.packet['recoveryOf']:
        raise ValueError('PRIOR_EVIDENCE_CHANGED_BEFORE_CPU_RECOVERY')
    if tools.sha(Path.home() / '.wslconfig') != permit.packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('APPROVED_WSL_POLICY_CHANGED')
    return first_build.run(admitter=sys.modules[__name__])


def summary():
    try:
        digest, packet = review()
    except (OSError, ValueError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'modelLaunchEnabled': False}
    return {'status': 'ATTEMPT_CONSUMED' if (LIVE / 'attempt.json').exists() else packet['status'],
        'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
        'approvalExists': APPROVAL.exists(), 'modelLaunchEnabled': False,
        'imageDownloadEnabled': False, 'imageImportEnabled': False}
