"""Disabled, cache-only verification recovery; preparation never reads blob bodies."""
import json
from pathlib import Path
import sys

import image_admission as image
import image_recovery as prior

build, cpu, tools = image.build, image.cpu, image.tools
HERE = image.HERE
REPO = HERE.parents[1]
ARCHIVE = REPO / '.runtime/verification-recovery/7ce23bea0a5848529330874891b08013'
PRESERVATION_SHA = 'e2a57b04d73a68991bdec3a3e2725e713577c2810a9e56a74918044c138ec6e9'
PREVIOUS = REPO / '.runtime/guarded-image-stage-recovery-1'
ROOT = REPO / '.runtime/verification-review'
PREVIOUS_VERIFICATION = REPO / '.runtime/guarded-image-verification-1'
PREVIOUS_VERIFICATION_APPROVAL = HERE / 'image-verification-approval.json'
PREVIOUS_VERIFICATION_REVIEW = REPO / '.runtime/verification-review/fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232/review.json'
VERIFICATION_PRESERVATION_SHA = '4fe1bc1ef8fe9eae8673d63a83001ffbf3f33f63230041188fa060f2cdff1ada'
ACCESS_RECOVERY = REPO / '.runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d'
LIVE = REPO / '.runtime/guarded-image-verification-2'
APPROVAL = HERE / 'image-verification-recovery-approval.json'
SCOPE = 'one-retained-image-cache-verification-no-download-no-import'


def metadata_tree(directory, *, skip_cache=False):
    """Small evidence only. Blob bodies are reserved for the approved worker."""
    result, total = {}, 0
    tools.plain(directory)
    for count, path in enumerate(sorted(directory.rglob('*')), 1):
        if count > 1000:
            raise ValueError('Preserved evidence entry budget')
        tools.plain(path)
        if skip_cache and path.relative_to(directory).parts[:2] == ('data', 'cache'):
            continue
        if path.is_file():
            size = path.stat().st_size
            total += size
            if size > 1024**2 or total > 4 * 1024**2:
                raise ValueError('Preserved metadata byte budget')
            result[path.relative_to(directory).as_posix()] = {'bytes': size, 'sha256': tools.sha(path)}
    return result


def retained_binding():
    if tools.sha(ARCHIVE / 'preservation.json') != PRESERVATION_SHA:
        raise ValueError('Verification preservation record changed')
    saved = json.loads(cpu.bounded(ARCHIVE / 'preservation.json', 131072))
    if prior.binding() != saved['firstAttempt']:
        raise ValueError('First failed attempt changed')
    old = json.loads(cpu.bounded(ARCHIVE / 'previous-review.json', 131072))
    digest = build.sha(old)
    if (digest != saved['previousReviewSha256'] or
            tools.sha(ARCHIVE / 'previous-review.json') != saved['previousReviewRawSha256'] or
            tools.sha(image.ROOT / digest / 'review.json') != saved['previousReviewRawSha256'] or
            tools.sha(ARCHIVE / 'previous-approval.json') != saved['previousApprovalRawSha256'] or
            tools.sha(image.APPROVAL) != saved['previousApprovalRawSha256'] or
            old['helperSha256'] != saved['previousHelperSha256']):
        raise ValueError('Second review/approval archive changed')
    for rel, expected in saved['previousHelperSha256'].items():
        relative = Path(rel)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe archived helper path')
        raw = cpu.bounded(ARCHIVE / 'previous-helpers' / relative, 1024**2)
        if build.hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('Archived second-attempt helper changed')
    attempt = saved['secondAttempt']
    if attempt['namespace'] != str(PREVIOUS) or metadata_tree(PREVIOUS, skip_cache=True) != attempt['files']:
        raise ValueError('Second failed attempt metadata changed')
    state = json.loads(cpu.bounded(PREVIOUS / 'state.json', 131072))
    claim = json.loads(cpu.bounded(PREVIOUS / 'attempt.json', 4096))
    if (state.get('phase') != 'FAULT' or state.get('fault') != 'SENSOR_FEED_ERROR' or
            state.get('stopConfirmed') is not True or state.get('readerStopped') is not True or
            claim.get('sessionId') != attempt['sessionId'] or claim.get('reviewSha256') != digest):
        raise ValueError('Second predecessor is not the confirmed stopped fault')
    reader = REPO / '.runtime/compiler-guard/746421aeb6f34c85b7dcd3a837cda5f7'
    if saved['readerDirectory'] != str(reader) or metadata_tree(reader) != saved['readerFiles']:
        raise ValueError('Original reader evidence changed')
    cache = PREVIOUS / 'data/cache'
    actual = {}
    for index, path in enumerate(cache.iterdir(), 1):
        if index > 65:
            raise ValueError('Retained cache entry budget')
        tools.plain(path)
        if not path.is_file():
            raise ValueError('Unexpected cache entry')
        stat = path.stat()
        actual[path.name] = {'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns, 'fileId': stat.st_ino}
    expected = {old['image']['configDigest'][7:]: old['image']['configBytes']}
    expected.update({r['digest'][7:]: r['bytes'] for r in old['image']['layers']})
    if (actual != attempt['cache'] or set(actual) != set(expected) or
            any(actual[name]['bytes'] != size for name, size in expected.items())):
        raise ValueError('Retained cache metadata changed; no repair/download fallback')
    return {'firstAttempt': saved['firstAttempt'], 'secondSessionId': attempt['sessionId'],
            'secondReviewSha256': digest, 'secondMetadataSha256': build.sha(attempt['files']),
            'cache': str(cache), 'cacheMetadataSha256': build.sha(actual), 'blobCount': len(actual),
            'blobBytes': sum(expected.values()), 'cacheBodiesReadDuringPreparation': False,
            'archivedHelpers': len(saved['previousHelperSha256']),
            'preservationSha256': PRESERVATION_SHA, 'readerEvidenceSha256': build.sha(saved['readerFiles']),
            'resetPreviousAttempts': False}


def binding():
    retained = retained_binding()
    preservation = ARCHIVE / 'verification-code-preservation.json'
    if tools.sha(preservation) != VERIFICATION_PRESERVATION_SHA:
        raise ValueError('Third attempt preservation changed')
    saved = json.loads(cpu.bounded(preservation, 131072))
    old = json.loads(cpu.bounded(ARCHIVE / 'verification-approved-review.json', 131072))
    digest = build.sha(old)
    if (digest != 'fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232' or
            digest != saved['reviewSha256'] or old['helperSha256'] != saved['helperSha256'] or
            json.loads(cpu.bounded(PREVIOUS_VERIFICATION_REVIEW, 131072)) != old or
            tools.sha(PREVIOUS_VERIFICATION_APPROVAL) != saved['approvalRawSha256'] or
            tools.sha(ARCHIVE / 'verification-approved-decision.json') != saved['approvalRawSha256']):
        raise ValueError('Third approved review/code/decision changed')
    for rel, expected in saved['helperSha256'].items():
        relative = Path(rel)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe archived verification helper')
        raw = cpu.bounded(ARCHIVE / 'verification-approved-helpers' / relative, 1024**2)
        if build.hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('Archived third-attempt helper changed')
    reader = REPO / '.runtime/compiler-guard/278afc85eaec4534a0e41f091aa5e751'
    if (metadata_tree(PREVIOUS_VERIFICATION) != saved['attemptFiles'] or
            metadata_tree(reader) != saved['readerFiles']):
        raise ValueError('Third attempt or reader evidence changed')
    state = json.loads(cpu.bounded(PREVIOUS_VERIFICATION / 'state.json', 131072))
    claim = json.loads(cpu.bounded(PREVIOUS_VERIFICATION / 'attempt.json', 4096))
    error = state.get('sensorFeedError', {})
    if (state.get('phase') != 'FAULT' or state.get('fault') != 'SENSOR_FEED_ERROR' or
            state.get('stopConfirmed') is not True or state.get('readerStopped') is not True or
            claim.get('sessionId') != '429518fb72464042bbaa0e960de2000d' or claim.get('reviewSha256') != digest or
            error.get('osError') != 13 or error.get('operation') != 'read' or error.get('pendingSequence') != 71):
        raise ValueError('Third predecessor is not the confirmed stopped sample-read failure')
    return {**retained, 'verificationSessionId': claim['sessionId'], 'verificationReviewSha256': digest,
            'verificationPreservationSha256': VERIFICATION_PRESERVATION_SHA,
            'verificationMetadataSha256': build.sha(saved['attemptFiles']),
            'verificationReaderSha256': build.sha(saved['readerFiles']),
            'verificationArchivedHelpers': len(saved['helperSha256']), 'preservedAttemptCount': 3}


def material():
    preserved = binding()
    old = json.loads(cpu.bounded(ARCHIVE / 'previous-review.json', 131072))
    # Keep exactly the accepted source/thermal decision and numeric controls.
    return {**old, 'scope': SCOPE, 'helperSha256': build.helpers(),
            'interpreter': {'path': str(Path(sys.executable).resolve()), 'version': sys.version,
                            'executableSha256': tools.sha(Path(sys.executable))},
            'liveNamespace': str(LIVE), 'recoveryOf': preserved,
            'operation': 'verify-retained-cache-only', 'registry': None,
            'inputBytes': preserved['blobBytes'], 'cacheReadOnly': True,
            'verificationEnabled': False,
            'writeNamespaceBytes': 4 * 1024**2,
            'preparationReadsCacheBodies': False, 'downloadFallback': False,
            'sensorFeedCorrection': {'historicalCauseProven': False,
                'rejectBeforeSequenceCommit': True, 'persistReasonAndExitAfterStopping': True,
                'automaticReaderRestart': False, 'ignoreReadErrors': False,
                'savedFramesReplaySha256': tools.sha(ARCHIVE / 'offline-replay.json'),
                'injectedExitComparisonSha256': tools.sha(ARCHIVE / 'injected-exit-comparison.json')},
            'sampleReadCorrection': {'shareRead': True, 'shareDelete': True, 'shareWrite': False,
                'access': 'read-only-open-existing-no-reparse', 'maximumBytes': 4096,
                'oneOpenNoRetry': True, 'sameFileIdentityBeforeAfter': True,
                'firstHeartbeatPublication': 'complete-first-byte-before-visible',
                'publisherConflictReproduced': True,
                'legacyReproductionSha256': tools.sha(ACCESS_RECOVERY / 'legacy-reproduction.json'),
                'nativeFrameEvidenceSha256': tools.sha(REPO / '.runtime/frame-access-rehearsals/27497b1748de4c3bbb6b9a926d19ae99/result.json')},
            'imageDownloadEnabled': False, 'imageImportEnabled': False,
            'buildEnabled': False, 'modelLaunchEnabled': False}


def prepare():
    packet = material()
    digest = build.sha(packet)
    tools.plain(ROOT)
    with tools.base.lock(ROOT / 'control'):
        directory = ROOT / digest
        directory.mkdir(exist_ok=True)
        destination = directory / 'review.json'
        if destination.exists() and json.loads(cpu.bounded(destination, 131072)) != packet:
            raise ValueError('Verification review destination changed')
        tools.base.atomic(destination, packet)
        tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return directory, packet


def review():
    pointer = json.loads(cpu.bounded(ROOT / 'candidate.json', 4096))
    digest = pointer.get('reviewSha256', '')
    if not build.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid verification review')
    packet = json.loads(cpu.bounded(ROOT / digest / 'review.json', 131072))
    if build.sha(packet) != digest or packet != material():
        raise ValueError('Verification review stale')
    return digest, packet


class Permit(image.Permit):
    @property
    def live_namespace(self):
        return LIVE

    def qualify(self, frame):
        # The existing image-source decision is deliberately retained, not
        # silently broadened to import/build/runtime. The wrapper scope differs.
        return super().qualify(frame)


def authorize():
    if not APPROVAL.exists():
        raise ValueError('IMAGE_VERIFICATION_NOT_APPROVED')
    digest, packet = review()
    decision = json.loads(cpu.bounded(APPROVAL, 8192))
    if (type(decision.get('version')) is not int or decision['version'] != 1 or
            decision.get('status') != 'owner-approved-one-cache-verification' or
            decision.get('scope') != SCOPE or decision.get('reviewSha256') != digest or
            decision.get('recoveryOfFailedSession') != packet['recoveryOf']['verificationSessionId'] or
            decision.get('preservationSha256') != PRESERVATION_SHA or
            decision.get('verificationPreservationSha256') != VERIFICATION_PRESERVATION_SHA or
            decision.get('sourceEvidenceSha256') != packet['sourceEvidenceSha256'] or
            decision.get('acceptImageThermalPolicySha256') != build.sha(packet['thermalPolicy']) or
            decision.get('acceptSourceLimitation') != image.LIMITATION or
            decision.get('acceptUnknownThrottleForThisScope') is not True or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts'] != 1 or
            decision.get('verificationEnabled') is not True or decision.get('synthetic') is not False or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip() or
            any(decision.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('IMAGE_VERIFICATION_APPROVAL_SCOPE_OR_HASH_INVALID')
    return Permit(digest, build.encoded(packet).decode(), build.sha(decision))


def summary():
    try:
        digest, packet = review()
    except (ValueError, OSError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'verificationEnabled': False,
                'imageDownloadEnabled': False, 'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    try:
        authorize()
        approved = True
    except (ValueError, OSError, KeyError):
        approved = False
    consumed = any((LIVE / name).exists() for name in ('attempt.json', 'state.json'))
    state = None
    if consumed:
        try:
            state = json.loads(cpu.bounded(LIVE / 'state.json', 131072))
            state = {k: state.get(k) for k in ('phase', 'fault', 'stopConfirmed', 'readerStopped', 'sensorFeedError')}
        except (ValueError, OSError, KeyError):
            state = {'phase': 'UNCONFIRMED'}
    return {'status': 'ATTEMPT_CONSUMED' if consumed else 'APPROVED_REQUIRES_FRESH_ADMISSION' if approved else 'READY_FOR_OWNER_APPROVAL',
            'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
            'scope': SCOPE, 'approved': approved, 'attemptConsumed': consumed,
            'session': state, 'preservedAttempts': packet['recoveryOf'],
            'inputBytes': packet['inputBytes'], 'freshSafetyAdmissionRequired': True,
            'verificationEnabled': False, 'imageDownloadEnabled': False,
            'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
