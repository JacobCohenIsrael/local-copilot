"""Cloud-orchestrator CLI for the bounded local worker. Real runtime stays blocked.

status is read-only. rehearse runs fixed synthetic staging, guarded fake-build
export, then real OpenCode against scripted replies; it never loads Strata.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / 'containers/strata-proposal'))
sys.path.insert(0, str(REPO / 'containers/worker'))
import build_preflight
import bundle_rehearsal
import cpu_feed
import image_download
import task_bundle
import verify_controller_session
import verify_opencode
import build_admission
import cpu_source_review
import first_build
import image_admission
import image_stage
import verify_image_stage
import verification_admission
import image_verification
import import_plan
import import_rehearsal
import isolation_preparation
import isolated_session
import desktop_test

ROOT = REPO / '.runtime/local-worker'
ARTIFACT = REPO / '.runtime/opencode-linux/2.0.26-musl-44f176ba'
WSL_CONFIG = Path.home() / '.wslconfig'


def record(path, maximum=128 * 1024):
    image_download.tools.plain(path)
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('Worker record budget exceeded')
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def namespace(run_id):
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('Owned run ID required')
    directory = ROOT / run_id
    image_download.tools.plain(directory)
    return directory


def latest():
    pointer = ROOT / 'latest.json'
    if not pointer.exists():
        return None
    candidate, _ = record(pointer)
    result, sha = record(namespace(candidate['runId']) / 'result.json')
    if (sha != candidate['sha256'] or result.get('runId') != candidate['runId'] or
            result.get('synthetic') is not True or result.get('modelStarted') is not False or
            result.get('compilerStarted') is not False):
        raise ValueError('Rehearsal evidence identity changed')
    return {'runId': candidate['runId'], 'status': result['status'], 'synthetic': True,
            'directory': str(namespace(candidate['runId'])), 'phases': result['phases'],
            'patch': result.get('patch'), 'originalUnchanged': result.get('originalUnchanged')}


def wsl_policy_status():
    """Report approved config and saved restart proof, never fresh VM authority."""
    try:
        directory = REPO / 'containers/strata-proposal'
        approval, approval_sha = record(directory / 'wsl-policy-approval.json')
        pointer, _ = record(directory / 'wsl-policy-observation.json')
        session = pointer.get('sessionId', '')
        if (approval.get('status') != 'owner-approved-temporary-wsl2-policy' or
                pointer.get('status') != 'observation-only-not-workload-approval' or
                not re.fullmatch('[0-9a-f]{32}', session)):
            raise ValueError('Invalid WSL policy record')
        evidence = REPO / '.runtime/wsl-policy' / session
        receipt, receipt_sha = record(evidence / 'verification.json')
        application, _ = record(evidence / 'application.json')
        image_download.tools.plain(WSL_CONFIG)
        with WSL_CONFIG.open('rb') as stream:
            config = stream.read(4097)
        expected = approval['proposalSha256']
        if (receipt_sha != pointer['verificationSha256'] or
                application.get('approvalSha256') != approval_sha or
                receipt.get('status') != 'APPLIED_RESTARTED_VERIFIED' or
                receipt.get('configSha256') != expected or len(config) > 4096 or
                hashlib.sha256(config).hexdigest() != expected or
                receipt.get('logicalProcessors') != 1 or receipt.get('guestSwapTotalBytes') != 0 or
                not 4 * 1024**3 < receipt.get('reportedMemoryBytes', 0) <= 6 * 1024**3):
            raise ValueError('WSL configuration or saved proof changed')
        return {'status': 'APPROVED_CONFIG_PRESENT_RESTART_VERIFIED',
                'recordedAtUtc': receipt['recordedAtUtc'],
                'logicalProcessorsObserved': receipt['logicalProcessors'],
                'memoryBytesObserved': receipt['reportedMemoryBytes'],
                'swapBytesObserved': receipt['guestSwapTotalBytes'],
                'freshRuntimeVerificationRequired': True, 'workloadApprovalGranted': False}
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'UNCONFIRMED_OR_CONFIG_CHANGED',
                'freshRuntimeVerificationRequired': True, 'workloadApprovalGranted': False}


def status():
    preflight = build_preflight.report()
    image = preflight['offlineSuccessorProposal']['cudaImagePreparation']
    return {'version': 1, 'status': 'REAL_RUNTIME_BLOCKED',
            'goal': 'One on-demand Docker Strata coding task supervised by Codex',
            'modelLaunchEnabled': False, 'buildEnabled': False,
            'wslPolicy': wsl_policy_status(),
            'imageStageAdmission': image_admission.summary(),
            'imageVerificationAdmission': verification_admission.summary(),
            'imageImportAdmission': import_plan.summary(),
            'isolationControls': isolation_preparation.summary(),
            'firstStrataBuild': desktop_test.summary(),
            'milestones': [
                {'name': 'Integrated rehearsal', 'status': 'AVAILABLE', 'command': 'python -B local_worker.py rehearse'},
                {'name': 'One capped CPU-only build', 'status': 'BLOCKED', 'blockers': [
                    'Explicit CPU-source acceptance and final workload approval',
                    'Reviewed image staging/import, disk limits and approved execution',
                    'Reviewed Docker/WSL envelope plus fresh safety admission']},
                {'name': 'First real local coding task', 'status': 'BLOCKED', 'blockers': [
                    'Successful build and reviewed model/runtime configuration',
                    'Real tokenizer, gate-only networking, GPU monitoring and runtime approval']}],
            'review': {'offlinePlanSha256': preflight['offlineSuccessorProposal']['planSha256'],
                       'readerSha256': preflight['readerSha256'],
                       'approvedCpuControls': preflight['approvedCpuControls'],
                       'image': image['identity']['image'], 'imageBlobBytes': image['identity']['lockedBlobBytes'],
                       'proposedStorageBudget': image['proposedStorageBudget'],
                       'buildOrModelPolicyActivated': False},
            'firstBuildAdmission': build_admission.summary(),
            'latestCpuObservation': latest_cpu(), 'latestRehearsal': latest()}


def latest_cpu():
    pointer = cpu_feed.ROOT / 'latest-probe.json'
    if not pointer.exists():
        return {'status': 'NO_CURRENT_ADAPTER_OBSERVATION'}
    candidate, _ = record(pointer)
    directory = cpu_feed.checked_directory(cpu_feed.ROOT / candidate['sessionId'])
    observation, sha = record(directory / 'probe-result.json')
    if (sha != candidate['sha256'] or observation.get('readerSha256') != cpu_feed.READER_SHA or
            observation.get('workloadStarted') is not False or observation.get('synthetic') is not False or
            observation.get('validatedCpuSensor') is not False):
        raise ValueError('Passive CPU observation changed or claims unexpected authority')
    samples = observation.get('samples', [])
    return {'status': observation['status'], 'samples': len(samples),
            'temperaturesC': [r.get('cpuTemperatureC') for r in samples],
            'error': next((r.get('error') for r in samples if r.get('error')), observation.get('error')),
            'readerStopped': observation['readerStopped'], 'sourceValidated': False,
            'directory': str(directory)}


def rehearse():
    image_download.tools.plain(ROOT)
    with image_download.tools.base.lock(ROOT / 'control'):
        entries, used = image_download.plain_usage(ROOT)
        if entries + 25 > 4096 or used + 1024**2 > 32 * 1024**2:
            raise ValueError('Worker rehearsal namespace full')
        # Recheck all prepared identities before starting even a fixed fixture.
        build_preflight.report()
        verify_opencode.artifact(ARTIFACT)
        directory = namespace(uuid.uuid4().hex)
        directory.mkdir()
        result = {'version': 1, 'runId': directory.name, 'status': 'RUNNING', 'synthetic': True,
                  'compilerStarted': False, 'modelStarted': False, 'strataContacted': False,
                  'realImageDownloaded': False, 'patchApplied': False, 'phases': [], 'fault': None}
        def cancelled():
            return (directory / 'cancel.request').exists()
        def save():
            image_download.tools.base.atomic(directory / 'result.json', result)
        def phase(name, function, validate):
            if cancelled():
                raise ValueError('CANCELLED')
            row = {'name': name, 'status': 'RUNNING'}
            result['phases'].append(row)
            save()
            print(json.dumps({'runId': directory.name, 'phase': name, 'status': 'RUNNING'}), flush=True)
            started = time.monotonic()
            # The existing helpers' bounded JSON is retained as evidence.
            with contextlib.redirect_stdout(io.StringIO()) as output:
                evidence = function()
            if len(output.getvalue()) > 128 * 1024 or validate(evidence) is not True:
                raise ValueError('REHEARSAL_PHASE_FAILED')
            image_download.tools.base.atomic(directory / (name + '.json'), evidence)
            row.update(status='PASSED', seconds=round(time.monotonic() - started, 3),
                       evidenceSha256=image_download.tools.sha(directory / (name + '.json')))
            save()
            return evidence
        save()
        try:
            phase('image-staging', lambda: verify_image_stage.verify(cancelled=cancelled), lambda r: r['passed'] is True)
            phase('guarded-build-export', lambda: verify_controller_session.verify(cancelled=cancelled),
                  lambda r: r['passed'] is True)
            task = phase('bounded-opencode-task', lambda: bundle_rehearsal.rehearse(ARTIFACT),
                         lambda r: r['status'] == 'PATCH_FOR_REVIEW' and r['cleanupConfirmed'] is True and
                                   r['originalUnchanged'] is True and r['strataContacted'] is False)
            if cancelled():
                raise ValueError('CANCELLED')
            result.update(status='PATCH_FOR_REVIEW_SYNTHETIC', patch=task['patch'],
                          originalUnchanged=task['originalUnchanged'], allWorkersStopped=True)
        except BaseException as error:
            result.update(status='FAULT', fault={'code': 'CANCELLED' if str(error) == 'CANCELLED' else 'REHEARSAL_FAILED',
                                               'type': type(error).__name__}, patch=None)
            if result['phases'] and result['phases'][-1]['status'] == 'RUNNING':
                result['phases'][-1]['status'] = 'FAULT'
            raise
        finally:
            save()
            image_download.tools.base.atomic(ROOT / 'latest.json', {
                'runId': directory.name, 'sha256': image_download.tools.sha(directory / 'result.json')})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('rehearse')
    commands.add_parser('probe-cpu')
    commands.add_parser('prepare-build')
    review_build = commands.add_parser('review-build')
    review_build.add_argument('--check-environment', action='store_true', help='Read-only pinned-image inspection')
    commands.add_parser('run-build')
    commands.add_parser('cancel-build')
    commands.add_parser('prepare-image')
    commands.add_parser('review-image')
    commands.add_parser('run-image')
    commands.add_parser('cancel-image')
    commands.add_parser('rehearse-image')
    commands.add_parser('prepare-verification')
    commands.add_parser('review-verification')
    commands.add_parser('run-verification')
    commands.add_parser('cancel-verification')
    commands.add_parser('prepare-import')
    commands.add_parser('review-import')
    commands.add_parser('rehearse-import')
    commands.add_parser('run-import')
    commands.add_parser('prepare-isolation')
    commands.add_parser('prepare-desktop-test')
    commands.add_parser('review-desktop-test')
    commands.add_parser('run-desktop-test')
    commands.add_parser('review-isolation')
    commands.add_parser('rehearse-isolation')
    commands.add_parser('run-isolation')
    prepare = commands.add_parser('prepare-task')
    prepare.add_argument('--request', required=True, help='Bounded JSON: sourceRoot, files, task')
    collect = commands.add_parser('collect')
    collect.add_argument('--run-id', required=True)
    cancel = commands.add_parser('cancel')
    cancel.add_argument('--run-id', required=True)
    commands.add_parser('run-task')  # Explicit blocked response, no enable/bypass flag.
    options = parser.parse_args()
    if options.command == 'status':
        result = status()
    elif options.command == 'rehearse':
        result = rehearse()
    elif options.command == 'probe-cpu':
        result = cpu_feed.probe()
    elif options.command == 'prepare-build':
        directory, packet = build_admission.prepare()
        result = {'status': 'PREPARED_NOT_APPROVED', 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'sourceTree': packet['sourceTree'],
                  'cpuSourceReview': packet['sourceReview']['status'],
                  'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'review-build':
        result = build_admission.summary(check_environment=options.check_environment)
    elif options.command == 'prepare-image':
        directory, packet = image_admission.prepare()
        result = {'status': 'PREPARED_NOT_APPROVED', 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'scope': packet['scope'],
                  'imageDownloadEnabled': False, 'imageImportEnabled': False,
                  'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'review-image':
        result = image_admission.summary()
    elif options.command == 'run-image':
        result = image_download.stage_pinned()
    elif options.command == 'prepare-verification':
        directory, packet = verification_admission.prepare()
        result = {'status': 'PREPARED_NOT_APPROVED', 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'scope': packet['scope'],
                  'verificationEnabled': False, 'imageDownloadEnabled': False,
                  'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'review-verification':
        result = verification_admission.summary()
    elif options.command == 'run-verification':
        result = image_verification.run()
    elif options.command == 'prepare-import':
        directory, packet = import_plan.prepare()
        result = {'status': packet['status'], 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'blockers': packet.get('blockers', []),
                  'imageDownloadEnabled': False, 'imageImportEnabled': False,
                  'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'review-import':
        result = import_plan.summary()
    elif options.command == 'rehearse-import':
        result = import_rehearsal.rehearse()
    elif options.command == 'run-import':
        result = import_plan.run()
    elif options.command == 'prepare-isolation':
        directory, packet = isolation_preparation.prepare()
        result = {'status': packet['status'], 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'blockers': packet.get('blockers', []),
                  'nativeRunEnabled': False, 'imageImportEnabled': False,
                  'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'prepare-desktop-test':
        directory, packet = desktop_test.prepare()
        result = {'status': packet['status'], 'reviewFile': str(directory / 'review.json'),
                  'reviewSha256': build_admission.sha(packet), 'buildReviewSha256': packet['buildReviewSha256'],
                  'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    elif options.command == 'review-desktop-test':
        result = desktop_test.summary()
    elif options.command == 'run-desktop-test':
        result = desktop_test.run()
    elif options.command == 'review-isolation':
        result = isolation_preparation.summary()
    elif options.command == 'rehearse-isolation':
        result = isolated_session.rehearse()
    elif options.command == 'run-isolation':
        result = isolation_preparation.run()
    elif options.command == 'cancel-verification':
        result = image_verification.cancel()
    elif options.command == 'cancel-image':
        result = image_stage.cancel()
    elif options.command == 'rehearse-image':
        with contextlib.redirect_stdout(io.StringIO()):
            result = verify_image_stage.verify()
    elif options.command == 'run-build':
        result = first_build.run()
    elif options.command == 'cancel-build':
        claim = record(build_admission.LIVE / 'attempt.json')[0]
        state = record(build_admission.LIVE / 'state.json')[0]
        if state.get('phase') in ('FAULT', 'COMPLETE'):
            raise ValueError('First-build session already terminal; no reset')
        directory = first_build._session(build_admission.LIVE / 'sessions' / claim['sessionId'])
        (directory / 'cancel.request').touch(exist_ok=True)
        result = {'status': 'CANCELLATION_REQUESTED', 'sessionId': claim['sessionId']}
    elif options.command == 'prepare-task':
        request, _ = record(Path(options.request).absolute(), 16384)
        result = task_bundle.prepare(request)
    elif options.command == 'collect':
        result = task_bundle.collect(options.run_id)
    elif options.command == 'cancel':
        directory = namespace(options.run_id)
        state, _ = record(directory / 'result.json')
        if state.get('synthetic') is not True or state.get('status') != 'RUNNING':
            raise ValueError('Only an active owned rehearsal can be cancelled')
        (directory / 'cancel.request').touch(exist_ok=True)
        result = {'status': 'CANCELLATION_REQUESTED', 'runId': options.run_id}
    else:
        result = {'status': 'REAL_RUNTIME_BLOCKED', 'reason': 'Complete the build and runtime approval gates',
                  'buildEnabled': False, 'modelLaunchEnabled': False}
    print(json.dumps(result, indent=2))
    if options.command in ('run-import', 'run-isolation'):
        return 3
    if options.command in ('run-image', 'run-verification', 'run-desktop-test') and result.get('phase') != 'COMPLETE':
        return 3
    return 3 if result.get('status') in ('REAL_RUNTIME_BLOCKED', 'SOURCE_VALIDATION_BLOCKED') and options.command != 'status' else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        code = str(error) if re.fullmatch('[A-Z_]{1,80}', str(error)) else 'INPUT_OR_ADMISSION_CHECK_FAILED'
        print(json.dumps({'status': 'FAULT', 'errorType': type(error).__name__,
                          'code': code,
                          'buildEnabled': False, 'modelLaunchEnabled': False}))
        raise SystemExit(3)
