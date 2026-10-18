"""Exact, disabled image-staging review and owner-approval admission; no transport."""
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import sys

import build_admission as build
import build_policy_review as policy
import cpu_source_review as cpu
import image_plan as images
import image_download as download
import image_recovery
import stage_build_tools as tools

HERE = images.HERE
ROOT = HERE.parents[1] / '.runtime/guarded-image-review'
LIVE = image_recovery.NEXT
APPROVAL = HERE / 'image-stage-recovery-approval.json'  # Fresh approval; never reuse the spent receipt.
SCOPE = 'one-pinned-image-acquisition-and-stream-verification-no-import'
LIMITATION = ('Firmware refresh latency and calibration are not independently guaranteed; '
              'acceptance is for one monitored image download/stream-verification attempt, never import, compilation or model runtime.')


def material():
    evidence = cpu.report()  # Reuse observations, never the build-only acceptance.
    base = policy.load_effective_controls()
    thermal = {'scope': SCOPE, 'temperature': base['temperature'],
               'resources': {'deadlineSeconds': 1800, 'automaticRetry': False},
               'stop': base['stop'],
               'throttleException': {'scope': SCOPE, 'status': 'proposed-image-scope-not-approved',
                    'allowUnknownInSimulation': True, 'assertNotThrottling': False,
                    'knownThrottlingStillFaults': True}}
    image = images.metadata()
    return {'version': 1, 'status': 'REVIEW_ONLY_NOT_APPROVED', 'scope': SCOPE,
            'image': image, 'sourceEvidence': evidence, 'sourceEvidenceSha256': build.sha(evidence),
            'acceptSourceLimitation': LIMITATION, 'thermalPolicy': thermal,
            'helperSha256': build.helpers(), 'liveNamespace': str(LIVE),
            'recoveryOf': image_recovery.binding(),
            'interpreter': {'path': str(Path(sys.executable).resolve()), 'version': sys.version,
                            'executableSha256': tools.sha(Path(sys.executable))},
            'maximumAttempts': 1, 'readerSamples': 1920, 'baselineWaitSeconds': 90,
            'outerSeconds': 1910, 'workSeconds': 1800, 'blobSeconds': 600,
            'workerLeaseSeconds': 7.5, 'controllerLeaseSeconds': 2.5, 'stopSeconds': 5,
            'job': {'singleLogicalProcessor': True, 'memoryBytes': 128 * 1024**2, 'processes': 1},
            'budget': {'payloadBytes': images.DOWNLOAD_LIMIT,
                       'namespaceBytes': images.storage_budget(image)['hostStageBytes'],
                       'supervisorReserveBytes': 4 * 1024**2, 'freeReserveBytes': images.HOST_RESERVE,
                       'expandedLayerBytes': images.EXPANDED_LIMIT, 'expandedTotalBytes': images.EXPANDED_LIMIT},
            'proposedVmEnvelope': {'logicalProcessors': 1, 'maximumReportedMemoryBytes': 6 * images.GIB,
                                   'guestSwapBytes': 0, 'proposalSha256': tools.sha(HERE / 'wsl-build-limits.proposed')},
            'registry': {'repository': 'nvidia/cuda', 'anonymousOnly': True, 'automaticRetries': False,
                         'authFraming': ['exact-content-length', 'http11-chunked-without-content-length'],
                         'authRetainedBytes': download.AUTH_BYTES, 'authOverflowProbeBytes': 1,
                         'blobFraming': 'exact-content-length-only', 'redactedAuthObservations': True,
                         'serviceHosts': ['auth.docker.io', 'registry-1.docker.io'],
                         'cdnHosts': sorted(download.CDN_HOSTS)},
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
            raise ValueError('Image review destination changed')
        tools.base.atomic(destination, packet)
        tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return directory, packet


def review():
    pointer = json.loads(cpu.bounded(ROOT / 'candidate.json', 4096))
    digest = pointer.get('reviewSha256', '')
    if not build.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid image review pointer')
    packet = json.loads(cpu.bounded(ROOT / digest / 'review.json', 131072))
    if build.sha(packet) != digest or packet != material():
        raise ValueError('Image review changed; prepare a new exact packet')
    return digest, packet


@dataclass(frozen=True)
class Permit:
    review_sha256: str
    packet_json: str
    approval_sha256: str

    @property
    def packet(self):
        return json.loads(self.packet_json)

    @property
    def live_namespace(self):
        return LIVE

    def qualify(self, frame):
        if (type(frame.get('version')) is not int or frame['version'] != 1 or frame.get('synthetic') is not False or
                frame.get('validatedCpuSensor') is not False or frame.get('cpuThermalThrottling') is not None or
                frame.get('source') != self.packet['thermalPolicy']['temperature']['source']):
            raise ValueError('Image permit cannot qualify another source or synthetic frame')
        return {**frame, 'rawValidatedCpuSensor': False, 'validatedCpuSensor': True,
                'sourceQualification': self.packet['sourceEvidenceSha256'], 'acceptanceScope': SCOPE}


def authorize():
    # No directory creation, CPU reader, subprocess or RegistrySource before this.
    if not APPROVAL.exists():
        raise ValueError('IMAGE_STAGING_NOT_APPROVED')
    digest, packet = review()
    raw = cpu.bounded(APPROVAL, 8192)
    decision = json.loads(raw)
    if (type(decision.get('version')) is not int or decision['version'] != 1 or decision.get('status') != 'owner-approved-one-image-stage' or
            decision.get('scope') != SCOPE or decision.get('reviewSha256') != digest or
            decision.get('recoveryOfFailedSession') != packet['recoveryOf']['sessionId'] or
            decision.get('sourceEvidenceSha256') != packet['sourceEvidenceSha256'] or
            decision.get('acceptSourceLimitation') != LIMITATION or
            decision.get('acceptImageThermalPolicySha256') != build.sha(packet['thermalPolicy']) or
            decision.get('acceptUnknownThrottleForThisScope') is not True or
            decision.get('imageDownloadEnabled') is not True or decision.get('synthetic') is not False or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts'] != 1 or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip() or
            any(decision.get(k) is not False for k in ('imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('IMAGE_STAGE_APPROVAL_SCOPE_OR_HASH_INVALID')
    return Permit(digest, build.encoded(packet).decode(), build.sha(decision))


def summary():
    try:
        digest, packet = review()
    except (ValueError, OSError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'imageDownloadEnabled': False,
                'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    try:
        authorize()
        approved = True
    except (ValueError, OSError, KeyError):
        approved = False
    consumed = any((LIVE / name).exists() for name in ('attempt.json', 'state.json'))
    active = None
    if consumed:
        try:
            state = json.loads(cpu.bounded(LIVE / 'state.json', 131072))
            active = {'phase': state['phase'] if state.get('phase') in ('WAITING_BASELINE', 'RUNNING', 'FAULT', 'COMPLETE') else 'UNCONFIRMED',
                      'fault': state.get('fault'), 'stopConfirmed': state.get('stopConfirmed') is True,
                      'readerStopped': state.get('readerStopped') is True}
        except (OSError, ValueError, KeyError):
            active = {'phase': 'UNCONFIRMED', 'stopConfirmed': False, 'readerStopped': False}
    return {'status': 'ATTEMPT_CONSUMED' if consumed else 'APPROVED_REQUIRES_FRESH_ADMISSION' if approved else 'READY_FOR_OWNER_APPROVAL',
            'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
            'operationScope': SCOPE, 'approved': approved, 'attemptConsumed': consumed,
            'previousAttempt': packet['recoveryOf'],
            'session': active,
            'lockedBlobBytes': packet['image']['lockedBlobBytes'], 'freshSafetyAdmissionRequired': True,
            'hostFreeBytesObserved': shutil.disk_usage(HERE).free,
            'imageDownloadEnabled': False, 'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
