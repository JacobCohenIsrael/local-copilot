"""One approval-gated verification of retained blobs. No registry/downloader path."""
import argparse
import contextlib
import ctypes
import io
import json
import os
from pathlib import Path
import sys
import time
import uuid

import image_stage as stage
import verification_admission as admission

download = stage.download


def cache_identity(cache, packet):
    expected = {packet['image']['configDigest'][7:]: packet['image']['configBytes']}
    expected.update({r['digest'][7:]: r['bytes'] for r in packet['image']['layers']})
    if not 2 <= len(expected) <= 65:
        raise download.StageError('CACHE_CONTRACT_INVALID')
    result = {}
    download.tools.plain(Path(cache))
    for index, path in enumerate(Path(cache).iterdir(), 1):
        if index > len(expected):
            raise download.StageError('CACHE_CHANGED')
        download.tools.plain(path)
        if path.name not in expected or not path.is_file():
            raise download.StageError('CACHE_CHANGED')
        stat = path.stat()
        if stat.st_size != expected[path.name]:
            raise download.StageError('CACHE_CHANGED')
        result[path.name] = {'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns, 'fileId': stat.st_ino}
    if set(result) != set(expected):
        raise download.StageError('CACHE_CHANGED')
    expected_sha = packet.get('recoveryOf', {}).get('cacheMetadataSha256')
    if expected_sha is not None and stage.build.sha(result) != expected_sha:
        raise download.StageError('CACHE_CHANGED')
    return result


def validate_result(result, packet, synthetic):
    streams = result.get('streams', {})
    image = packet['image']
    expected = [(r['digest'], r['bytes'], r['expandedSha256']) for r in image['layers']]
    rows = streams.get('layers', [])
    if (result.get('synthetic') is not synthetic or result.get('reviewSha256') != stage.build.sha(packet) or
            result.get('scope') != packet['scope'] or result.get('operation') != 'verify-retained-cache-only' or
            result.get('configVerified') is not True or result.get('verifiedInputBytes') != packet['inputBytes'] or
            result.get('inputCacheChanged') is not False or type(result.get('networkRequests')) is not int or result['networkRequests'] != 0 or
            streams.get('status') != 'STREAMS_VERIFIED_NOT_IMPORTED' or streams.get('extracted') is not False or
            streams.get('dockerDiskUsageBounded') is not False or len(rows) != len(expected) or
            any(result.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise download.StageError('VERIFICATION_RESULT_INVALID')
    total = 0
    for row, (digest, size, expanded_sha) in zip(rows, expected):
        count = row.get('expandedBytes')
        if (row.get('digest') != digest or row.get('compressedBytes') != size or
                row.get('expandedSha256') != expanded_sha or type(count) is not int or
                not 0 < count <= packet['budget']['expandedLayerBytes']):
            raise download.StageError('VERIFICATION_RESULT_INVALID')
        total += count
    if (type(streams.get('expandedBytes')) is not int or streams['expandedBytes'] != total or
            total > packet['budget']['expandedTotalBytes']):
        raise download.StageError('VERIFICATION_RESULT_INVALID')
    return result


def pipeline(directory, packet, cache, *, synthetic):
    """Rehash config + compressed layers and verify diff IDs; never modify cache."""
    pulse = stage.controller.Pulse(directory / 'controller.pulse', maximum=4096)
    started, next_pulse = time.monotonic(), 0
    def guard():
        nonlocal next_pulse
        now = time.monotonic()
        if ((directory / 'cancel.request').exists() or pulse.age() > packet['controllerLeaseSeconds'] or
                now - started >= packet['workSeconds']):
            return False
        if now >= next_pulse:
            stage.controller.pulse(directory / 'worker.pulse', maximum=4096)
            next_pulse = now + .5
        return True
    limits = download.Limits(packet['inputBytes'] + 1, packet['writeNamespaceBytes'],
                             packet['budget']['freeReserveBytes'], packet['workSeconds'], packet['blobSeconds'])
    context = download.Context(limits, guard)
    context.check()
    before = cache_identity(cache, packet)
    image = packet['image']
    path = Path(cache) / image['configDigest'][7:]
    download.tools.plain(path)
    if not path.is_file() or path.stat().st_size != image['configBytes'] or image['configBytes'] > 1024**2:
        raise download.StageError('CACHE_CHANGED')
    context.begin_blob()
    data = bytearray()
    with path.open('rb') as source:
        while True:
            chunk = download.read_chunk(source, min(download.CHUNK, image['configBytes'] - len(data) + 1), context)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > image['configBytes']:
                raise download.StageError('CACHE_CHANGED')
    if (len(data) != image['configBytes'] or
            'sha256:' + stage.hashlib.sha256(data).hexdigest() != image['configDigest']):
        raise download.StageError('CACHE_CHANGED')
    layers = [stage.expand.Layer(download.Blob(r['digest'], r['bytes']), r['expandedSha256']) for r in image['layers']]
    streams = stage.expand._verify(cache, layers,
                  stage.expand.Limits(packet['budget']['expandedLayerBytes'], packet['budget']['expandedTotalBytes']), context)
    context.check()
    if cache_identity(cache, packet) != before:
        raise download.StageError('CACHE_CHANGED')
    result = {'synthetic': synthetic, 'reviewSha256': stage.build.sha(packet), 'scope': packet['scope'],
              'operation': 'verify-retained-cache-only', 'configVerified': True,
              'verifiedInputBytes': len(data) + sum(r['compressedBytes'] for r in streams['layers']),
              'inputCacheChanged': False, 'networkRequests': 0, 'streams': streams,
              'imageDownloadEnabled': False, 'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    validate_result(result, packet, synthetic)
    if len(stage.build.encoded(result)) > 128 * 1024:
        raise download.StageError('VERIFICATION_RESULT_BUDGET')
    download.tools.base.atomic(directory / 'worker-result.json', result)
    return result


def child():
    permit = admission.authorize()
    directory, packet = admission.LIVE, permit.packet
    claim = json.loads(admission.cpu.bounded(directory / 'attempt.json', 4096))
    start = json.loads(admission.cpu.bounded(directory / 'start.json', 4096))
    if (claim.get('reviewSha256') != permit.review_sha256 or claim.get('synthetic') is not False or
            not stage.stage_session_id(claim.get('sessionId')) or start != {**claim, 'scope': admission.SCOPE}):
        raise download.StageError('VERIFICATION_CHILD_CLAIM_INVALID')
    try:
        return pipeline(directory, packet, Path(packet['recoveryOf']['cache']), synthetic=False)
    except BaseException as error:
        download.tools.base.atomic(directory / 'worker-error.json',
               {'code': error.code if isinstance(error, download.StageError) else 'VERIFICATION_WORKER_ERROR'})
        raise


def run():
    permit = admission.authorize()  # No reader, process, cache read or directory before approval.
    packet = permit.packet
    if any((admission.LIVE / name).exists() for name in ('attempt.json', 'state.json')):
        raise ValueError('IMAGE_VERIFICATION_ATTEMPT_ALREADY_CONSUMED')
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('ADMINISTRATOR_CPU_READER_ACCESS_REQUIRED')
    configuration = Path.home() / '.wslconfig'
    if stage.hashlib.sha256(admission.cpu.bounded(configuration, 4096)).hexdigest() != packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('APPROVED_WSL_CONFIG_CHANGED')
    stage.build.vm_ready(stage.build.guard.base.Docker(), packet)
    with contextlib.redirect_stdout(io.StringIO()):
        proof_dir = stage.probe_image_storage.probe()
    proof = json.loads(admission.cpu.bounded(proof_dir / 'result.json', 16384))
    if type(proof.get('guestSwapTotalBytes')) is not int or proof['guestSwapTotalBytes'] != 0:
        raise ValueError('GUEST_SWAP_NOT_DISABLED')
    directory = admission.LIVE
    download.tools.plain(directory)
    with download.tools.base.lock(directory / 'control'):
        if any(p.name != 'control' for p in directory.iterdir()):
            raise ValueError('IMAGE_VERIFICATION_ATTEMPT_ALREADY_CONSUMED')
        download.reserve_disk(directory, download.Limits(1, packet['writeNamespaceBytes'],
            packet['budget']['freeReserveBytes'], packet['workSeconds'], packet['blobSeconds']), packet['writeNamespaceBytes'])
        claim = {'sessionId': uuid.uuid4().hex, 'reviewSha256': permit.review_sha256, 'synthetic': False}
        with (directory / 'attempt.json').open('x', encoding='utf-8') as stream:
            json.dump(claim, stream)
            stream.flush()
            os.fsync(stream.fileno())
        feed = stage.cpu_feed.Feed(stage.cpu_feed.ROOT / uuid.uuid4().hex, source_permit=permit)
        def launch():
            with (directory / 'start.json').open('x', encoding='utf-8') as stream:
                json.dump({**claim, 'scope': admission.SCOPE}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            env = {k: os.environ[k] for k in ('SystemRoot', 'TEMP', 'TMP') if k in os.environ}
            return stage.windows_job.Process([sys.executable, '-B', '-E', '-s', str(Path(__file__).resolve()), '--approved-child'],
                 cwd=directory, env=env, memory_bytes=packet['job']['memoryBytes'],
                 processes=packet['job']['processes'], single_cpu=True)
        def last_check():
            if admission.authorize() != permit:
                raise ValueError('Verification approval changed before start')
        return stage._execute(directory, packet, feed, launch, synthetic=False, permit=permit,
                              before_launch=last_check, validate=validate_result)


def cancel():
    directory = admission.LIVE
    download.tools.plain(directory)
    state = json.loads(admission.cpu.bounded(directory / 'state.json', 131072))
    claim = json.loads(admission.cpu.bounded(directory / 'attempt.json', 4096))
    if (state.get('phase') not in ('WAITING_BASELINE', 'RUNNING') or state.get('synthetic') is not False or
            state.get('scope') != admission.SCOPE or state.get('reviewSha256') != claim.get('reviewSha256')):
        raise ValueError('No active owned verification; no reset')
    (directory / 'cancel.request').touch(exist_ok=True)
    return {'status': 'CANCELLATION_REQUESTED', 'scope': admission.SCOPE}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-child', action='store_true', required=True)
    parser.parse_args()
    try:
        child()
    except BaseException:
        raise SystemExit(3)
