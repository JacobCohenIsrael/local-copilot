"""Read-only preservation checks; never reset, move, delete or execute old evidence."""
import hashlib
import json
from pathlib import Path

import build_admission as build
import cpu_source_review as cpu
import image_download as download

REPO = Path(__file__).resolve().parents[2]
PROPOSAL = Path(__file__).with_name('image-stage-recovery.proposed.json')
PREVIOUS = REPO / '.runtime/guarded-image-stage'
PREVIOUS_REVIEW = '861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323'
NEXT = REPO / '.runtime/guarded-image-stage-recovery-1'


def file_tree(directory):
    download.tools.plain(directory)
    files = {}
    total = 0
    for count, path in enumerate(sorted(directory.rglob('*')), 1):
        if count > 1000:
            raise ValueError('Previous evidence entry budget exceeded')
        download.tools.plain(path)
        if path.is_file():
            total += path.stat().st_size
            if total > 4 * 1024**2:
                raise ValueError('Previous evidence byte budget exceeded')
            files[path.relative_to(directory).as_posix()] = {'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(cpu.bounded(path, 1024**2)).hexdigest()}
    return files


def binding():
    proposal = json.loads(cpu.bounded(PROPOSAL, 8192))
    if (type(proposal.get('version')) is not int or proposal['version'] != 1 or proposal.get('status') != 'recovery-proposal-not-approved' or
            proposal.get('previousReviewSha256') != PREVIOUS_REVIEW or
            proposal.get('previousNamespace') != '.runtime/guarded-image-stage' or
            proposal.get('newNamespace') != '.runtime/guarded-image-stage-recovery-1' or
            type(proposal.get('maximumNewAttempts')) is not int or proposal['maximumNewAttempts'] != 1 or
            any(proposal.get(key) is not False for key in ('resetPreviousAttempt', 'automaticRetry',
                   'imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('Recovery must preserve the failed attempt and remain disabled')
    if proposal.get('preservationDirectory') != '.runtime/image-recovery/8de46ce61487484694d473faf9f9bb29':
        raise ValueError('Unreviewed preservation directory')
    directory = REPO / proposal['preservationDirectory']
    raw = cpu.bounded(directory / 'preservation.json', 65536)
    if hashlib.sha256(raw).hexdigest() != proposal['preservationSha256']:
        raise ValueError('Preservation record changed')
    preserved = json.loads(raw)
    files = file_tree(PREVIOUS)
    if (files != preserved['failedFiles'] or build.sha(files) != proposal['previousTreeSha256'] or
            preserved['previousReviewSha256'] != PREVIOUS_REVIEW):
        raise ValueError('Failed attempt evidence changed')
    state = json.loads(cpu.bounded(PREVIOUS / 'state.json', 131072))
    claim = json.loads(cpu.bounded(PREVIOUS / 'attempt.json', 4096))
    if (state.get('phase') != 'FAULT' or state.get('workerFault') != 'HTTP_FRAMING_INVALID' or
            state.get('stopConfirmed') is not True or state.get('readerStopped') is not True or
            state.get('reviewSha256') != PREVIOUS_REVIEW or
            claim.get('reviewSha256') != PREVIOUS_REVIEW or claim.get('sessionId') != proposal['previousSessionId']):
        raise ValueError('Previous attempt is not the confirmed stopped failure')
    archived = json.loads(cpu.bounded(directory / 'previous-review.json', 131072))
    approval_raw = cpu.bounded(directory / 'previous-approval.json', 8192)
    current_approval = cpu.bounded(PROPOSAL.with_name('image-stage-approval.json'), 8192)
    if (build.sha(archived) != PREVIOUS_REVIEW or archived['helperSha256'] != preserved['previousHelperSha256'] or
            hashlib.sha256(approval_raw).hexdigest() != preserved['previousApprovalRawSha256'] or
            approval_raw != current_approval):
        raise ValueError('Previous review/approval archive changed')
    for rel, expected in preserved['previousHelperSha256'].items():
        path = Path(rel)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe preserved helper name')
        raw_helper = cpu.bounded(directory / 'previous-helpers' / path, 1024**2)
        if hashlib.sha256(raw_helper.replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('Preserved approved helper changed')
    diagnostic_raw = cpu.bounded(directory / 'auth-headers.json', 4096)
    if hashlib.sha256(diagnostic_raw).hexdigest() != proposal['authHeaderDiagnosticSha256']:
        raise ValueError('Auth framing diagnostic changed')
    observation = json.loads(diagnostic_raw)
    if (observation.get('status') != 200 or observation.get('httpVersion') != 11 or
            observation.get('contentLengthCount') != 0 or observation.get('transferEncoding') != ['chunked'] or
            observation.get('bodyReadCalled') is not False or observation.get('blobRequests') != 0):
        raise ValueError('Auth diagnostic is not the reviewed headers-only observation')
    check_raw = cpu.bounded(directory / 'auth-correction-check.json', 4096)
    if hashlib.sha256(check_raw).hexdigest() != proposal['authCorrectionCheckSha256']:
        raise ValueError('Auth-only correction check changed')
    check = json.loads(check_raw)
    if (check.get('status') != 'AUTH_ONLY_CORRECTION_CHECK_PASSED' or check.get('tokenSyntaxValid') is not True or
            check.get('tokenRetained') is not False or check.get('blobRequests') != 0 or
            type(check.get('authPayloadBytes')) is not int or not 0 < check['authPayloadBytes'] <= download.AUTH_BYTES or
            any(check.get(key) is not False for key in ('imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('Auth-only check is not a completed bounded correction check')
    return {'sessionId': claim['sessionId'], 'reviewSha256': PREVIOUS_REVIEW,
            'namespace': str(PREVIOUS), 'treeSha256': build.sha(files), 'fileCount': len(files),
            'phase': 'FAULT', 'workerFault': 'HTTP_FRAMING_INVALID',
            'stopConfirmed': True, 'readerStopped': True, 'resetPreviousAttempt': False,
            'archivedHelpers': len(preserved['previousHelperSha256']),
            'preservationFile': str(directory / 'preservation.json'),
            'preservationSha256': proposal['preservationSha256'],
            'authHeaderDiagnosticSha256': proposal['authHeaderDiagnosticSha256'],
            'authCorrectionCheckSha256': proposal['authCorrectionCheckSha256']}
