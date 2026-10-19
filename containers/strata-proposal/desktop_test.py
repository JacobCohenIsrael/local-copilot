"""One reviewed Desktop CUDA load followed by the existing guarded CPU build.

No private daemon, VHDX, model startup, GPU exposure or download route. Storage
selection alone is not workload approval. Shared-daemon cancellation is reported
as uncertain on faults; killing a client never proves daemon work has stopped.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

import build_admission as build
import cpu_source_review as cpu
import first_build
import image_admission
import image_plan as images
import image_stage as guarded
import import_plan as preserved_import
import oci_archive
import stage_build_tools as tools

REPO, HERE = preserved_import.REPO, preserved_import.HERE
ROOT = REPO / '.runtime/desktop-test-review'
LIVE = REPO / '.runtime/desktop-strata-test-1'
APPROVAL = HERE / 'desktop-test-approval.json'
STORAGE = HERE / 'desktop-storage-approval.json'
SCOPE = 'one-offline-desktop-cuda-import-and-cpu-strata-build-no-model'
LIMITATION = ('Firmware refresh latency and calibration are not independently guaranteed; '
    'acceptance is only for this one monitored image import and the pinned CPU build, never model runtime.')
CANCELLATION = ('Docker Desktop owns image unpacking outside the compiler cgroup. '
    'Stopping the owned import client does not prove the shared daemon stopped its background work. '
    'Do not stop global Docker/WSL automatically. A fault consumes the attempt and blocks compilation.')


def read(path, maximum=131072):
    return json.loads(cpu.bounded(path, maximum))


def rows():
    return oci_archive.members(images.read_metadata(HERE / 'cuda-base.manifest.json'),
        images.read_metadata(HERE / 'cuda-base.config.json'), expected_manifest=images.MANIFEST_SHA,
        image_name='docker.io/' + images.IMAGE)


def native_binding():
    """Preserve the failed native attempt without reauthorizing its stale code."""
    root = REPO / '.runtime/isolation-review/2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743'
    saved = read(root / 'native-execution-preservation.json', 1048576)
    for key in ('native', 'reader', 'launch'):
        record = saved[key]
        base = Path(record['directory'])
        actual = {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('PRIOR_NATIVE_FILE_SET_CHANGED')
        for relative, expected in record['files'].items():
            raw = cpu.bounded(base / relative, 131072)
            if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
                raise ValueError('PRIOR_NATIVE_EVIDENCE_CHANGED')
    disk = Path(saved['storeMetadata']['path'])
    tools.plain(disk)
    stat = disk.stat()
    if ([stat.st_dev, stat.st_ino] != saved['storeMetadata']['fileIdentity'] or
            stat.st_size != saved['storeMetadata']['bytes'] or
            tools.sha(disk.parent / 'owner.json') != saved['storeOwnerSha256']):
        raise ValueError('RETAINED_NATIVE_STORE_CHANGED')
    return {'preservationSha256': tools.sha(root / 'native-execution-preservation.json'),
            'resultSha256': tools.sha(root / 'native-execution-result.json'),
            'originalStateSha256': saved['native']['files']['state.json']['sha256'],
            'storeBodyRead': False, 'storeDetachedOrReused': False}


def material(build_sha, build_packet, *, preserved=None, native=None):
    selection = read(STORAGE, 8192)
    if (selection.get('status') != 'owner-approved-normal-desktop-storage-for-first-test' or
            selection.get('useNormalDesktopStorage') is not True or selection.get('modelLaunchEnabled') is not False):
        raise ValueError('NORMAL_DESKTOP_STORAGE_NOT_APPROVED')
    evidence = cpu.report()
    controls = build.policy.load_effective_controls()
    return {'version': 1, 'status': 'READY_FOR_DESKTOP_IMPORT_AND_BUILD_APPROVAL', 'scope': SCOPE,
        'storageApprovalSha256': tools.sha(STORAGE), 'storage': 'normal-Docker-Desktop-image-store',
        'preserved': preserved_import.binding() if preserved is None else preserved,
        'preservedNative': native_binding() if native is None else native,
        'image': images.metadata(), 'helperSha256': build.helpers(),
        'buildReviewSha256': build_sha, 'buildReviewFile': str(build.ROOT / build_sha / 'review.json'),
        'sourceEvidenceSha256': build.sha(evidence), 'acceptSourceLimitation': LIMITATION,
        'sharedDaemonCancellationLimitation': CANCELLATION,
        'thermalPolicy': {'scope': SCOPE, 'temperature': controls['temperature'],
            'resources': {'deadlineSeconds': 1800, 'automaticRetry': False}, 'stop': controls['stop'],
            'throttleException': {'allowUnknownInSimulation': True, 'assertNotThrottling': False,
                                  'knownThrottlingStillFaults': True}},
        'readerSamples': 1920, 'baselineWaitSeconds': 90, 'outerSeconds': 1910,
        'workSeconds': 1800, 'workerLeaseSeconds': 7.5, 'controllerLeaseSeconds': 2.5, 'stopSeconds': 5,
        'proposedVmEnvelope': build_packet['proposedVmEnvelope'],
        'archive': {'format': 'OCI-layout-tar', 'exactBytes': oci_archive.archive_bytes(rows()),
                    'fullArchiveRetained': True, 'hashWhileWriting': True, 'chunkBytes': oci_archive.CHUNK,
                    'imageName': 'docker.io/' + images.IMAGE},
        'disk': {'hostReserveBytes': 20 * images.GIB, 'guestReserveBytes': 4 * images.GIB,
                 'budget': images.storage_budget(images.metadata()), 'hardImportQuota': False,
                 'faultMayLeavePartialSharedDaemonContent': True},
        'hostJob': {'singleCpu': True, 'memoryBytes': 256 * 1024**2, 'processes': 4},
        'maximumImportAttempts': 1, 'maximumBuildAttempts': 1,
        'sequence': ['fresh-CPU-and-capacity-admission', 'write-and-rehash-owned-OCI-archive',
            'one-Docker-load-no-network', 'verify-pinned-manifest-platform-and-ordered-diff-ids',
            'fresh-CPU-admission-for-existing-offline-compiler', 'one-CPU-build-and-bounded-export'],
        'compiler': {'cpus': 1, 'memoryBytes': 4 * images.GIB, 'swapBytes': 0, 'pids': 128,
                     'jobs': 1, 'seconds': 1800, 'gpuDevices': [], 'network': 'none', 'architecture': 86},
        'modelLaunchEnabled': False, 'imageDownloadEnabled': False,
        'imageImportEnabled': False, 'buildEnabled': False}


def prepare():
    directory, build_packet = build.prepare()
    packet = material(directory.name, build_packet)
    digest = build.sha(packet)
    tools.plain(ROOT)
    destination = ROOT / digest
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / 'review.json'
    if path.exists() and read(path) != packet:
        raise ValueError('DESKTOP_REVIEW_COLLISION')
    if not path.exists():
        tools.base.atomic(path, packet)
    tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return destination, packet


def review():
    digest = read(ROOT / 'candidate.json', 4096)['reviewSha256']
    if not build.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('DESKTOP_REVIEW_INVALID')
    packet = read(ROOT / digest / 'review.json')
    bsha, bp = build.review()
    # Historical evidence is fully rechecked before starting the live monitor.
    # Replaying hundreds of old files inside its short lease adds unrelated I/O.
    if build.sha(packet) != digest or packet != material(bsha, bp,
            preserved=packet['preserved'], native=packet['preservedNative']):
        raise ValueError('DESKTOP_REVIEW_STALE')
    return digest, packet


class Permit(image_admission.Permit):
    @property
    def live_namespace(self):
        return LIVE

    def qualify(self, frame):
        qualified = super().qualify(frame)
        return {**qualified, 'acceptanceScope': SCOPE}


def authorize():
    if not APPROVAL.exists():
        raise ValueError('DESKTOP_IMPORT_AND_BUILD_NOT_APPROVED')
    digest, packet = review()
    decision = read(APPROVAL, 16384)
    if (type(decision.get('version')) is not int or decision['version'] != 1 or
            decision.get('status') != 'owner-approved-one-desktop-import-and-cpu-build' or
            decision.get('reviewSha256') != digest or decision.get('scope') != SCOPE or
            decision.get('buildReviewSha256') != packet['buildReviewSha256'] or
            decision.get('sourceEvidenceSha256') != packet['sourceEvidenceSha256'] or
            decision.get('acceptSourceLimitation') != LIMITATION or
            decision.get('acceptSharedDaemonCancellationLimitation') != CANCELLATION or
            decision.get('thermalPolicySha256') != build.sha(packet['thermalPolicy']) or
            decision.get('acceptUnknownThrottleForThisScope') is not True or
            decision.get('imageImportEnabled') is not True or decision.get('buildEnabled') is not True or
            decision.get('modelLaunchEnabled') is not False or decision.get('imageDownloadEnabled') is not False or
            decision.get('synthetic') is not False or type(decision.get('maximumAttempts')) is not int or
            decision['maximumAttempts'] != 1 or not isinstance(decision.get('ownerMessage'), str) or
            not decision['ownerMessage'].strip()):
        raise ValueError('DESKTOP_APPROVAL_SCOPE_OR_HASH_INVALID')
    return Permit(digest, build.encoded(packet).decode(), build.sha(decision))


def delegate_build(permit, import_state):
    """The combined owner's decision explicitly includes this exact build."""
    if (not isinstance(permit, Permit) or import_state.get('phase') != 'COMPLETE' or
            import_state.get('readerStopped') is not True or import_state.get('stopConfirmed') is not True or
            import_state.get('synthetic') is not False or import_state.get('reviewSha256') != permit.review_sha256):
        raise ValueError('COMPILATION_REQUIRES_SUCCESSFUL_GUARDED_IMPORT')
    validate_result(import_state.get('result', {}), permit.packet, False)
    if authorize() != permit:
        raise ValueError('DESKTOP_APPROVAL_CHANGED_BEFORE_COMPILATION')
    digest, packet = build.review()
    if digest != permit.packet['buildReviewSha256']:
        raise ValueError('CPU_BUILD_REVIEW_CHANGED')
    decision = {'version': 1, 'status': 'owner-approved-one-cpu-build', 'scope': packet['scope'],
        'reviewSha256': digest, 'acceptSourceQualificationSha256': packet['sourceReviewSha256'],
        'acceptSourceLimitation': cpu.LIMITATION, 'maximumAttempts': 1, 'synthetic': False,
        'buildEnabled': True, 'imageImportEnabled': False, 'imageDownloadEnabled': False,
        'modelLaunchEnabled': False, 'combinedReviewSha256': permit.review_sha256,
        'combinedApprovalSha256': permit.approval_sha256,
        'ownerMessage': read(APPROVAL, 16384)['ownerMessage']}
    with build.APPROVAL.open('x', encoding='utf-8') as stream:
        json.dump(decision, stream, indent=2)
    return build.authorize()


def write_archive(directory, packet, allowed):
    """Complete the hashed archive before sending any body to the daemon."""
    cache = Path(packet['preserved']['cache'])
    expected = {row.sha256: row.size for row in rows() if row.inline is None}
    def open_blob(digest):
        path = cache / digest
        tools.plain(path)
        if not path.is_file() or path.stat().st_size != expected[digest]:
            raise ValueError('DESKTOP_CACHE_CHANGED')
        return path.open('rb')
    output = directory / 'cuda-base.oci.tar'
    def check():
        return allowed() and shutil.disk_usage(directory).free >= packet['disk']['hostReserveBytes']
    with output.open('xb') as stream:
        receipt = oci_archive.stream(rows(), open_blob, stream, guard=check,
                                     maximum_bytes=packet['archive']['exactBytes'])
        stream.flush(); os.fsync(stream.fileno())
    stat = output.stat()
    return output, {**receipt, 'fileIdentity': [stat.st_dev, stat.st_ino], 'mtimeNs': stat.st_mtime_ns}


def load_archive(directory, archive, packet, allowed, *, popen=subprocess.Popen):
    tools.plain(archive)
    original = archive.stat()
    if original.st_size != packet['archive']['exactBytes']:
        raise ValueError('DESKTOP_ARCHIVE_SIZE_CHANGED')
    if allowed() is not True:
        raise ValueError('DESKTOP_IMPORT_GUARD_LOST')
    tools.base.atomic(directory / 'load-requested.json', {'image': packet['image']['image']})
    process = popen([build.guard.base.DOCKER, 'image', 'load', '--platform', 'linux/amd64', '--input', str(archive)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    output, overflow = bytearray(), threading.Event()
    def drain():
        while True:
            raw = process.stdout.read(4096)
            if not raw:
                return
            if len(output) + len(raw) > 131072:
                overflow.set(); return
            output.extend(raw)
    thread = threading.Thread(target=drain, daemon=True); thread.start()
    try:
        while process.poll() is None:
            if not allowed() or overflow.is_set():
                raise ValueError('DESKTOP_IMPORT_PERMISSION_OR_LOG_LIMIT')
            time.sleep(.1)
        thread.join(timeout=1)
        if (thread.is_alive() or overflow.is_set() or process.returncode != 0 or
                b'Error unpacking image' in output):
            raise ValueError('DESKTOP_IMAGE_LOAD_FAILED')
    finally:
        if process.poll() is None:
            process.kill()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: pass
        thread.join(timeout=.5)
        with (directory / 'load-output.txt').open('xb') as stream:
            stream.write(bytes(output))
        process.stdout.close()
    after = archive.stat()
    if any(getattr(original, k) != getattr(after, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')):
        raise ValueError('DESKTOP_ARCHIVE_CHANGED_DURING_LOAD')
    return {'clientExitCode': process.returncode, 'outputBytes': len(output)}


def child():
    permit = authorize(); packet = permit.packet
    claim = read(LIVE / 'attempt.json', 4096)
    if claim != {'reviewSha256': permit.review_sha256, 'scope': SCOPE, 'synthetic': False}:
        raise ValueError('DESKTOP_CHILD_CLAIM_INVALID')
    pulse = guarded.controller.Pulse(LIVE / 'controller.pulse', maximum=4096)
    started, done = time.monotonic(), threading.Event()
    def allowed():
        return (not done.is_set() and not (LIVE / 'cancel.request').exists() and pulse.age() <= 2.5 and
                time.monotonic() - started < packet['workSeconds'])
    def beat():
        while not done.wait(.25):
            if not allowed():return
            guarded.controller.pulse(LIVE / 'worker.pulse', maximum=4096)
    thread = threading.Thread(target=beat, daemon=True); thread.start()
    try:
        archive, receipt = write_archive(LIVE, packet, allowed)
        tools.base.atomic(LIVE / 'archive-result.json', receipt)
        loaded = load_archive(LIVE, archive, packet, allowed)
        if not allowed():raise ValueError('DESKTOP_IMPORT_GUARD_LOST')
        actual_id = build.image_ready(build.guard.base.Docker(), packet)
        result = {'scope': SCOPE, 'synthetic': False, 'reviewSha256': permit.review_sha256,
            'image': packet['image']['image'], 'imageId': actual_id, 'archive': receipt,
            'load': loaded, 'loadRequestCompleted': True, 'daemonStopClaimed': False,
            'imageDownloadEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
        tools.base.atomic(LIVE / 'worker-result.json', result)
    except BaseException as error:
        text = str(error)
        code = text if build.guard.re.fullmatch('[A-Z_]{1,80}', text) else 'DESKTOP_IMPORT_ERROR'
        tools.base.atomic(LIVE / 'worker-error.json', {'code': code, 'type': type(error).__name__})
        raise
    finally:
        done.set(); thread.join(timeout=1)


def validate_result(result, packet, synthetic):
    if (synthetic is not False or result.get('synthetic') is not False or result.get('scope') != SCOPE or
            result.get('reviewSha256') != build.sha(packet) or result.get('image') != packet['image']['image'] or
            result.get('imageId') not in (packet['image']['configDigest'], 'sha256:' + packet['image']['manifestSha256']) or
            result.get('archive', {}).get('archiveBytes') != packet['archive']['exactBytes'] or
            result.get('load', {}).get('clientExitCode') != 0 or result.get('loadRequestCompleted') is not True or
            result.get('daemonStopClaimed') is not False or
            any(result.get(k) is not False for k in ('imageDownloadEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('DESKTOP_IMPORT_RESULT_INVALID')
    return result


def run():
    permit = authorize(); packet = permit.packet
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('DESKTOP_ADMINISTRATOR_READER_ACCESS_REQUIRED')
    if LIVE.exists() and any(p.name != 'control' for p in LIVE.iterdir()):
        raise ValueError('DESKTOP_ATTEMPT_CONSUMED')
    if build.APPROVAL.exists() or any((build.LIVE / n).exists() for n in ('attempt.json', 'state.json', 'emergency.json')):
        raise ValueError('CPU_BUILD_AUTHORITY_OR_ATTEMPT_ALREADY_PRESENT')
    if tools.sha(Path.home() / '.wslconfig') != packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('APPROVED_WSL_POLICY_CHANGED')
    if preserved_import.binding() != packet['preserved'] or native_binding() != packet['preservedNative']:
        raise ValueError('PRIOR_EVIDENCE_CHANGED_BEFORE_DESKTOP_RUN')
    build.vm_ready(build.guard.base.Docker(), packet)
    proof_dir = guarded.probe_image_storage.probe()
    proof = read(proof_dir / 'result.json', 16384)
    if (proof.get('guestSwapTotalBytes') != 0 or
            not images.capacity(proof, packet['disk']['budget'])['withinProposedBudgetAtProbe']):
        raise ValueError('DESKTOP_CAPACITY_OR_SWAP_ADMISSION_FAILED')
    tools.plain(LIVE); LIVE.mkdir(parents=True, exist_ok=True)
    with tools.base.lock(LIVE / 'control'):
        if any(p.name != 'control' for p in LIVE.iterdir()):raise ValueError('DESKTOP_ATTEMPT_CONSUMED')
        if shutil.disk_usage(LIVE).free < packet['archive']['exactBytes'] + packet['disk']['hostReserveBytes']:
            raise ValueError('DESKTOP_ARCHIVE_CAPACITY_LOW')
        tools.base.atomic(LIVE / 'attempt.json', {'reviewSha256': permit.review_sha256, 'scope': SCOPE, 'synthetic': False})
        tools.base.atomic(LIVE / 'capacity-admission.json', {'proofDirectory': str(proof_dir), 'proof': proof})
        feed = guarded.cpu_feed.Feed(guarded.cpu_feed.ROOT / uuid.uuid4().hex, source_permit=permit)
        tools.base.atomic(LIVE / 'reader-binding.json', {'directory': str(feed.directory)})
        def fresh():
            if authorize() != permit:raise ValueError('DESKTOP_APPROVAL_CHANGED')
        def launch():
            fresh()
            # This trusted host importer needs the same local Docker context as
            # its parent. The sandboxed OpenCode worker has its own clean env.
            env = os.environ.copy()
            return guarded.windows_job.Process([sys.executable, '-B', '-E', '-s', str(Path(__file__).resolve()), '--approved-child'],
                cwd=REPO, env=env, memory_bytes=256 * 1024**2, processes=4, single_cpu=True)
        def reserve():
            if shutil.disk_usage(LIVE).free < packet['disk']['hostReserveBytes']:
                raise ValueError('DESKTOP_HOST_RESERVE_LOST')
        state = guarded._execute(LIVE, packet, feed, launch, synthetic=False, permit=permit,
            before_launch=fresh, validate=validate_result, download_enabled=False, import_enabled=True,
            on_monitor_pass=reserve)
        state['sharedDaemonCancellationUnconfirmed'] = state['phase'] != 'COMPLETE' and (LIVE / 'load-requested.json').exists()
        tools.base.atomic(LIVE / 'state.json', state)
        if state['phase'] != 'COMPLETE':return state
        try:
            delegate_build(permit, state)
            result = first_build.run()
            tools.base.atomic(LIVE / 'cpu-build-result.json', result)
            overall = {'scope': SCOPE, 'phase': 'COMPLETE', 'import': state,
                       'build': result, 'modelLaunchEnabled': False}
        except BaseException as error:
            tools.base.atomic(LIVE / 'cpu-build-error.json', {'type': type(error).__name__,
                'firstBuildState': str(build.LIVE / 'state.json'), 'automaticRetry': False})
            raise
        tools.base.atomic(LIVE / 'result.json', overall)
        return overall


def summary():
    try:
        digest, packet = review()
    except (OSError, ValueError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'modelLaunchEnabled': False}
    return {'status': 'ATTEMPT_CONSUMED' if (LIVE / 'attempt.json').exists() else packet['status'],
            'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
            'approvalExists': APPROVAL.exists(), 'modelLaunchEnabled': False}


if __name__ == '__main__':
    if sys.argv[1:] != ['--approved-child']:
        raise SystemExit('DESKTOP_INTERNAL_CHILD_ONLY')
    child()
