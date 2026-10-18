"""Separate capped import design. Metadata-only preparation; live execution absent.

An owner preference chooses the architecture. It is not approval to provision a
disk, attach/mount/format it, start a daemon or import an image.
"""
import json
from pathlib import Path

import image_plan
import image_verification
import oci_archive
import verification_admission as prior

build, cpu, tools = prior.build, prior.cpu, prior.tools
REPO, HERE = prior.REPO, prior.HERE
ROOT = REPO / '.runtime/import-review'
SUCCESS = prior.ACCESS_RECOVERY
PRESERVATION_SHA = '23a48f19ab38b5b198ef9cc663f5457f57e7979a9ad87a4721ec0dcae2c7467f'
REVIEW_SHA = 'cd28c631f1e82edc58a4273ea9798009d566a5a46c36a942db260b860562254b'
READER = REPO / '.runtime/compiler-guard/2a5cc9fcdcb940ac94d5a8d452d3e67e'
GIB = 1024**3
BLOCKERS = (
    'Owned Windows-to-WSL bridge is wired but still needs the approved native rehearsal',
    'Installed runtime closure is staged and hashed; native compatibility is unproven',
    'Empty-engine bootstrap is wired; the retained-image import runner is not implemented',
    'Native creation/cancellation, disk/mount bounds and independent engine stop have no live proof',
    'OCI-load compatibility and post-import identity checks need a tiny synthetic native rehearsal',
    'No exact import-scope source/policy/workload approval exists',
)


def binding():
    previous = prior.binding()
    if tools.sha(SUCCESS / 'verification-code-preservation.json') != PRESERVATION_SHA:
        raise ValueError('IMPORT_SUCCESS_PRESERVATION_CHANGED')
    saved = json.loads(cpu.bounded(SUCCESS / 'verification-code-preservation.json', 131072))
    packet = json.loads(cpu.bounded(SUCCESS / 'verification-approved-review.json', 131072))
    if (build.sha(packet) != REVIEW_SHA or saved['reviewSha256'] != REVIEW_SHA or
            packet['helperSha256'] != saved['helperSha256'] or
            json.loads(cpu.bounded(prior.ROOT / REVIEW_SHA / 'review.json', 131072)) != packet or
            tools.sha(prior.APPROVAL) != saved['approvalRawSha256'] or
            tools.sha(SUCCESS / 'verification-approved-decision.json') != saved['approvalRawSha256']):
        raise ValueError('IMPORT_SUCCESS_REVIEW_CHANGED')
    for rel, expected in saved['helperSha256'].items():
        relative = Path(rel)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('IMPORT_UNSAFE_ARCHIVE_PATH')
        raw = cpu.bounded(SUCCESS / 'verification-approved-helpers' / relative, 1024**2)
        if build.hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('IMPORT_SUCCESS_HELPER_CHANGED')
    if (prior.metadata_tree(prior.LIVE) != saved['attemptFiles'] or
            prior.metadata_tree(READER) != saved['readerFiles']):
        raise ValueError('IMPORT_SUCCESS_EVIDENCE_CHANGED')
    state = json.loads(cpu.bounded(prior.LIVE / 'state.json', 131072))
    claim = json.loads(cpu.bounded(prior.LIVE / 'attempt.json', 4096))
    result = json.loads(cpu.bounded(prior.LIVE / 'worker-result.json', 131072))
    if (state.get('phase') != 'COMPLETE' or state.get('fault') is not None or
            state.get('readerStopped') is not True or state.get('stopConfirmed') is not True or
            claim.get('sessionId') != 'e21da7b06fdc4fab903af2efec885f54' or
            claim.get('reviewSha256') != REVIEW_SHA):
        raise ValueError('IMPORT_VERIFICATION_NOT_COMPLETE')
    image_verification.validate_result(result, packet, False)
    return {**previous, 'preservedAttemptCount': 4,
            'successfulSessionId': claim['sessionId'], 'successfulReviewSha256': REVIEW_SHA,
            'successPreservationSha256': PRESERVATION_SHA,
            'successMetadataSha256': build.sha(saved['attemptFiles']),
            'successReaderSha256': build.sha(saved['readerFiles']),
            'successArchivedHelpers': len(saved['helperSha256']),
            'verifiedExpandedBytes': result['streams']['expandedBytes']}


def material():
    preserved = binding()
    image = image_plan.metadata()
    rows = oci_archive.members(image_plan.read_metadata(HERE / 'cuda-base.manifest.json'),
                               image_plan.read_metadata(HERE / 'cuda-base.config.json'),
                               expected_manifest=image_plan.MANIFEST_SHA)
    return {'version': 1, 'status': 'DESIGN_REVIEW_ONLY_NOT_EXECUTABLE',
        'scope': 'one-offline-import-to-new-separate-capped-engine',
        'selection': 'owner-selected-separate-store-with-enforced-disk-cap',
        'preserved': preserved, 'image': image, 'helperSha256': build.helpers(),
        'archive': {'format': 'OCI-layout-tar', 'members': len(rows),
                    'exactBytes': oci_archive.archive_bytes(rows), 'chunkBytes': oci_archive.CHUNK,
                    'fullArchiveFile': False, 'originalManifestPreserved': True,
                    'rehashWhileStreaming': True, 'networkRequests': 0},
        'proposedStore': {
            'kind': 'new-fixed-capacity-block-device-ext4',
            'windowsPath': str(REPO / '.runtime/isolated-import-1/store.vhdx'),
            'logicalBytes': 32 * GIB, 'resizeAllowed': False,
            'containerFileAllowanceBytes': 256 * 1024**2,
            'hostReserveBytes': 20 * GIB, 'hostEvidenceLimitBytes': 4 * 1024**2,
            'freeHostBytesRequiredBeforeCreation': 52 * GIB + 260 * 1024**2,
            'daemonDataContainerdContentSnapshotsTmpAndLogsInsideStore': True,
            'reserveInsideStoreStopBytes': 4 * GIB,
            'separateRuntimeTmpfsBytes': 64 * 1024**2,
            'formatOnlyNewOwnedDeviceAfterIdentityCheck': True,
            'existingDesktopDataVhdModified': False,
            'implementationAndPhysicalAllocationBoundProven': False},
        'proposedEngine': {
            'endpoint': 'private-unix-socket-via-fixed-WSL-adapter',
            'changeDefaultDockerContext': False, 'shareDesktopContainerd': False,
            'sharedStorageFallback': False, 'networkNamespace': 'isolated-no-egress',
            'bridge': 'none', 'iptables': False, 'ipForward': False, 'gpuDevices': False,
            'cpuMax': '100000 100000', 'memoryMaxBytes': 4 * GIB,
            'memorySwapMaxBytes': 0, 'pidsMax': 128,
            'requireDelegatedOwnedCgroup': True,
            'globalWslPolicy': {'processors': 1, 'memoryBytes': 6 * GIB, 'swapBytes': 0},
            'startDesktopOrChangeItsConfig': False,
            'engineRuntimeSource': 'staged-installed-ELF-closure-native-compatibility-unproven-no-download-fallback',
            'proposedResourceEnforcement': 'restricted-outer-Docker-capsule',
            'modifySharedCgroupControllers': False,
            'capsuleCapSysAdminAndAppArmorExceptionRequireApproval': True},
        'proposedGuard': {'baselineMaxC': 92, 'baselineSeconds': 10,
            'stopAtC': 97, 'maximumAttempts': 1, 'operationSeconds': 1800,
            'controllerLeaseSeconds': 3, 'gracefulStopSeconds': 5,
            'forceStopConfirmationSeconds': 5, 'unknownThrottleRemainsNull': True,
            'sourceAcceptanceRequiredForImportScope': True,
            'sensorMissingOrStale': 'stop-owned-engine-latch-fault',
            'ownerDeath': 'independent-guest-lease-stops-owned-cgroup',
            'clientExitIsDaemonStopProof': False,
            'unconfirmedStop': 'latched-fault-keep-mounted-no-detach-or-delete',
            'stopDesktopOrGlobalWslAllowed': False},
        'sequence': ['verify-preserved-cache-metadata-and-exact-approval',
            'fresh-source-baseline-host-reserve-and-WSL-admission',
            'create-new-owned-capped-device-verify-identity-format-mount',
            'prove-all-writes-contained-and-start-owned-cgroup-watchdog',
            'start-private-offline-daemon-and-check-effective-limits',
            'stream-once-with-rehash-no-download-no-archive-copy',
            'inspect-config-id-linux-amd64-and-ordered-diff-ids',
            'stop-entire-owned-engine-confirm-empty-cgroup-and-reader-stop',
            'unmount-detach-new-device-retain-store-and-all-receipts'],
        'successIdentity': {'configId': image['configDigest'], 'platform': image['platform'],
            'orderedDiffIds': ['sha256:' + r['expandedSha256'] for r in image['layers']],
            'repositoryDigestMayBeAbsentAfterLoad': True,
            'noImageContainerMayBeStarted': True},
        'controlPrimitivesImplemented': True,
        'nativeBootstrapWired': False, 'emptyEngineCanaryBootstrapWired': True,
        'blockers': list(BLOCKERS), 'liveRunnerImplemented': False,
        'nativeStoreProof': None, 'nativeDaemonStopProof': None,
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
            raise ValueError('IMPORT_REVIEW_COLLISION')
        if not destination.exists():
            tools.base.atomic(destination, packet)
        tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return directory, packet


def summary():
    try:
        pointer = json.loads(cpu.bounded(ROOT / 'candidate.json', 4096))
        digest = pointer['reviewSha256']
        if not build.guard.re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('IMPORT_REVIEW_INVALID')
        packet = json.loads(cpu.bounded(ROOT / digest / 'review.json', 131072))
        if build.sha(packet) != digest or packet != material():
            raise ValueError('IMPORT_REVIEW_STALE')
    except (ValueError, OSError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'imageImportEnabled': False,
                'imageDownloadEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    return {'status': packet['status'], 'reviewSha256': digest,
            'reviewFile': str(ROOT / digest / 'review.json'),
            'preservedAttempts': 4, 'blobBytes': packet['preserved']['blobBytes'],
            'blockers': packet['blockers'], 'imageImportEnabled': False,
            'imageDownloadEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}


def run():
    # Refuse BEFORE any file, process, daemon, sensor, cache body or WSL access.
    # There is deliberately no approval reader or bypass option yet.
    return {'status': 'IMPORT_EXECUTION_NOT_IMPLEMENTED', 'imageImportEnabled': False,
            'imageDownloadEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False,
            'blockers': list(BLOCKERS)}
