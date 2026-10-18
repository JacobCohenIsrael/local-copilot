"""Read-only, disabled CUDA image staging proposal. No network/Docker/pull API."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import stage_build_tools as tools

HERE = Path(__file__).resolve().parent
MANIFEST_SHA = '435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c'
IMAGE = 'nvidia/cuda@sha256:' + MANIFEST_SHA
GIB = 1024**3
METADATA_LIMIT = 256 * 1024
DOWNLOAD_LIMIT = 5 * GIB
EXPANDED_LIMIT = 16 * GIB  # Proposed ceiling, NOT a measured expanded image size.
HOST_RESERVE = 20 * GIB
GUEST_RESERVE = 4 * GIB
IMPORT_SCRATCH = 2 * GIB
STORAGE_ROOT = HERE.parents[1] / '.runtime/image-storage'


def read_metadata(path):
    tools.plain(path)
    with path.open('rb') as stream:
        raw = stream.read(METADATA_LIMIT + 1)
    if len(raw) > METADATA_LIMIT:
        raise ValueError('Image metadata exceeds limit')
    # Reconstruct the upstream LF bytes after a normal Windows Git checkout.
    return raw.replace(b'\r\n', b'\n')


def descriptor(row, expected_type, limit):
    if (not isinstance(row, dict) or set(row) != {'mediaType', 'size', 'digest'} or
            row['mediaType'] != expected_type or type(row['size']) is not int or
            not 0 < row['size'] <= limit or not isinstance(row['digest'], str) or
            not re.fullmatch('sha256:[0-9a-f]{64}', row['digest'])):
        raise ValueError('Invalid/foreign image descriptor')
    return row


def metadata(manifest_raw=None, config_raw=None, *, expected_sha=MANIFEST_SHA):
    manifest_raw = read_metadata(HERE / 'cuda-base.manifest.json') if manifest_raw is None else manifest_raw
    config_raw = read_metadata(HERE / 'cuda-base.config.json') if config_raw is None else config_raw
    if (len(manifest_raw) > METADATA_LIMIT or len(config_raw) > METADATA_LIMIT or
            hashlib.sha256(manifest_raw).hexdigest() != expected_sha):
        raise ValueError('Pinned image manifest changed')
    manifest = json.loads(manifest_raw)
    if (type(manifest.get('schemaVersion')) is not int or manifest['schemaVersion'] != 2 or
            manifest.get('mediaType') != 'application/vnd.docker.distribution.manifest.v2+json'):
        raise ValueError('Expected the pinned single-platform Docker v2 manifest')
    config_ref = descriptor(manifest['config'], 'application/vnd.docker.container.image.v1+json', METADATA_LIMIT)
    if (len(config_raw) != config_ref['size'] or
            'sha256:' + hashlib.sha256(config_raw).hexdigest() != config_ref['digest']):
        raise ValueError('Pinned image configuration changed')
    config = json.loads(config_raw)
    if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
        raise ValueError('Expected Linux amd64 image configuration')
    layers = manifest.get('layers')
    diff_ids = config.get('rootfs', {}).get('diff_ids')
    if (not isinstance(layers, list) or not 1 <= len(layers) <= 64 or
            config.get('rootfs', {}).get('type') != 'layers' or not isinstance(diff_ids, list) or
            len(diff_ids) != len(layers) or
            not all(isinstance(d, str) and re.fullmatch('sha256:[0-9a-f]{64}', d) for d in diff_ids)):
        raise ValueError('Image layer/diff-ID coverage invalid')
    rows = []
    for row, diff_id in zip(layers, diff_ids):
        descriptor(row, 'application/vnd.docker.image.rootfs.diff.tar.gzip', 3 * GIB)
        rows.append({'digest': row['digest'], 'bytes': row['size'], 'expandedSha256': diff_id[7:]})
    total = sum(row['bytes'] for row in rows) + config_ref['size']
    if total > DOWNLOAD_LIMIT:
        raise ValueError('Image locked payload exceeds proposed 5 GiB ceiling')
    return {'image': IMAGE, 'manifestSha256': expected_sha,
            'manifestBytes': len(manifest_raw), 'configDigest': config_ref['digest'],
            'configBytes': config_ref['size'], 'platform': 'linux/amd64',
            'layers': rows, 'layerBytes': total - config_ref['size'], 'lockedBlobBytes': total}


def storage_budget(identity):
    # No shared-layer savings assumed. Source blobs + a possible import archive
    # live on Windows; containerd retains compressed content and expanded data.
    host_stage = 2 * identity['lockedBlobBytes'] + 16 * 1024**2
    guest_growth = identity['lockedBlobBytes'] + EXPANDED_LIMIT + IMPORT_SCRATCH
    return {'hostStageBytes': host_stage, 'guestGrowthBytes': guest_growth,
            'guestAvailableRequiredBytes': guest_growth + GUEST_RESERVE,
            'sameHostVolumeAvailableRequiredBytes': host_stage + guest_growth + HOST_RESERVE,
            'separateStageVolumeRequiredBytes': host_stage + HOST_RESERVE,
            'separateDockerVolumeRequiredBytes': guest_growth + HOST_RESERVE,
            'expandedLimitBytesProposed': EXPANDED_LIMIT, 'expandedSizeMeasured': False,
            'daemonHardDiskQuotaEnforced': False,
            'note': 'Planning headroom, not a reservation or an enforced Docker import quota.'}


def capacity(observation, budget):
    if (not isinstance(observation, dict) or observation.get('version') != 1 or
            observation.get('mode') != 'read-only-image-storage-probe' or observation.get('image') != IMAGE or
            observation.get('cleanupComplete') is not True or observation.get('stopConfirmed') is not True or
            observation.get('probeExitCode') != 0 or type(observation.get('recordedAtUnix')) not in (int, float) or
            not math.isfinite(observation['recordedAtUnix']) or observation['recordedAtUnix'] < 0):
        raise ValueError('Expected a completed read-only storage probe')
    for key in ('stageVolumeFreeBytes', 'dockerCandidateVolumeFreeBytes', 'guestRootAvailableBytes'):
        if type(observation.get(key)) is not int or observation[key] < 0:
            raise ValueError('Missing/invalid measured storage capacity')
    same = observation.get('sameHostVolume')
    if type(same) is not bool:
        raise ValueError('Storage-volume relationship is unknown')
    stage_required = budget['sameHostVolumeAvailableRequiredBytes'] if same else budget['separateStageVolumeRequiredBytes']
    docker_required = budget['sameHostVolumeAvailableRequiredBytes'] if same else budget['separateDockerVolumeRequiredBytes']
    enough = (observation['stageVolumeFreeBytes'] >= stage_required and
              observation['dockerCandidateVolumeFreeBytes'] >= docker_required and
              observation['guestRootAvailableBytes'] >= budget['guestAvailableRequiredBytes'])
    return {'status': 'OBSERVED_HEADROOM' if enough else 'INSUFFICIENT_HEADROOM',
            'withinProposedBudgetAtProbe': enough,
            'recordedAtUnix': observation['recordedAtUnix'],
            'dockerBackingPathConfirmed': observation.get('dockerBackingPathConfirmed') is True,
            'guestProbeScope': 'current container root filesystem; not an independent host-mount audit',
            'recheckImmediatelyBeforeAnyStagingRequired': True,
            'capacityIsReservationOrApproval': False}


def selected_observation():
    pointer = HERE / 'image-storage-observation.json'
    if not pointer.exists():
        return None
    candidate = json.loads(read_metadata(pointer))
    if (candidate.get('version') != 1 or candidate.get('status') != 'observation-only-not-approval' or
            not isinstance(candidate.get('sessionId'), str) or not re.fullmatch('[0-9a-f]{32}', candidate['sessionId']) or
            any(candidate.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled'))):
        raise ValueError('Storage observation pointer is not a disabled observation')
    path = STORAGE_ROOT / candidate['sessionId'] / 'result.json'
    raw = read_metadata(path)
    if hashlib.sha256(raw).hexdigest() != candidate.get('receiptSha256'):
        raise ValueError('Storage observation changed')
    observation = json.loads(raw)
    return observation


def report(observation=None):
    import image_download
    identity = metadata()
    budget = storage_budget(identity)
    observation = selected_observation() if observation is None else observation
    return {'version': 1, 'status': 'IMAGE_STAGING_PROPOSAL_NOT_APPROVED',
            'imageDownloadEnabled': False, 'imageImportEnabled': False,
            'buildEnabled': False, 'modelLaunchEnabled': False,
            'identity': identity, 'proposedStorageBudget': budget,
            'downloadImplementation': image_download.prepared_contract(identity),
            'capacity': capacity(observation, budget) if observation is not None else {'status': 'NOT_MEASURED'},
            'remainingGates': [
                'Review and approve the exact image-staging operation and budgets',
                'Accept image-scope source/thermal/unknown-throttle limitations; the approval-gated live bridge is connected',
                'Recheck live VM/swap, host disk and reader baseline through the connected guard before staging',
                'Confirm Docker backing-volume mapping and fresh host/guest capacity before the separate import step',
                'Verify actual pinned layer streams/diff IDs with reviewed expansion limits before any Docker import',
                'Review daemon import resource/disk limits and cancellation confirmation separately'],
            'note': 'Only public manifest/config metadata was read. No real image layer downloaded, decompressed, imported or run.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capacity', help='Owned .runtime/image-storage/<32hex>/result.json observation')
    options = parser.parse_args()
    observation = None
    if options.capacity:
        path = Path(options.capacity).absolute()
        if (path.name != 'result.json' or path.parent.parent != STORAGE_ROOT or
                not re.fullmatch('[0-9a-f]{32}', path.parent.name)):
            raise ValueError('Capacity record outside owned probe namespace')
        observation = json.loads(read_metadata(path))
    print(json.dumps(report(observation), indent=2))
