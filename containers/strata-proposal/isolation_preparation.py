"""Exact owner approval for one empty native-engine isolation rehearsal."""
import hashlib
import json
from pathlib import Path
import sys

import import_plan as image
import image_admission
import isolated_engine as engine
import isolated_runtime as runtime
import isolated_store as store
import isolated_guest

ROOT = image.REPO / '.runtime/isolation-review'
LIVE = image.REPO / '.runtime/native-isolation-1'
APPROVAL = image.HERE / 'native-isolation-approval.json'
CANARY_SESSION = 'f1705ab385be4fedb419fb33921aec56'
SCOPE = isolated_guest.SCOPE
LIMITATION = ('Firmware refresh latency and calibration are not independently guaranteed; '
    'acceptance is only for one monitored 128-MiB empty native-engine canary, '
    'never image download/import, compilation, model execution, or an automatic retry.')


def material():
    directory, manifest, runtime_sha = runtime.review()
    helpers = image.build.helpers()
    if manifest['files']['launcher.py']['sha256'] != helpers['containers/strata-proposal/runtime_launcher.py']:
        raise ValueError('RUNTIME_LAUNCHER_STAGE_STALE')
    policy, source = image.build.policy.load_effective_controls(), image.cpu.report()
    thermal = {'scope': SCOPE, 'temperature': policy['temperature'],
        'resources': {'deadlineSeconds': 180, 'automaticRetry': False}, 'stop': policy['stop'],
        'throttleException': {'scope': SCOPE, 'status': 'proposed-native-canary-only',
            'allowUnknownInSimulation': True, 'assertNotThrottling': False, 'knownThrottlingStillFaults': True}}
    native_inputs = {name: hashlib.sha256((image.HERE / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                     for name in ('isolated_agent.py', 'isolated_guest.py', 'wsl_bridge.sh')}
    return {'version': 1, 'status': 'READY_FOR_NATIVE_REHEARSAL_APPROVAL', 'scope': SCOPE,
        'sessionId': CANARY_SESSION, 'liveNamespace': str(LIVE), 'helperSha256': helpers,
        'nativeInputSha256': native_inputs, 'preserved': image.binding(),
        'sourceEvidence': source, 'sourceEvidenceSha256': image.build.sha(source),
        'acceptSourceLimitation': LIMITATION, 'thermalPolicy': thermal,
        'runtime': {'directory': str(directory), 'manifestSha256': runtime_sha,
                    'bytes': manifest['bytes'], 'files': len(manifest['files']),
                    'status': manifest['status'], 'nativeCompatibilityProven': False},
        'interpreter': {'path': str(Path(sys.executable).resolve()), 'version': sys.version,
                        'executableSha256': image.tools.sha(Path(sys.executable))},
        'execution': {'argv': [str(Path(sys.executable).resolve()), '-B', str(image.REPO / 'local_worker.py'), 'run-isolation'],
                      'administratorRequired': True, 'selfElevates': False},
        'capsuleImageId': engine.build_guard.base.IMAGE.split('@')[1],
        'cachedCapsuleImage': engine.build_guard.base.IMAGE,
        'maximumAttempts': 1, 'readerSamples': 480, 'baselineWaitSeconds': 90,
        'outerSeconds': 300, 'workSeconds': 180, 'workerLeaseSeconds': 7.5,
        'controllerLeaseSeconds': 2.5, 'stopSeconds': 5,
        'hostJob': {'singleCpu': True, 'memoryBytes': 256 * store.MIB, 'processes': 4},
        'proposedVmEnvelope': {'logicalProcessors': 1, 'maximumReportedMemoryBytes': 6 * store.GIB,
            'guestSwapBytes': 0, 'proposalSha256': image.tools.sha(image.HERE / 'wsl-build-limits.proposed')},
        'capsulePrivileges': {'caps': list(engine.CAPS), 'apparmor': 'unconfined',
            'seccomp': 'Docker-default', 'privileged': False, 'sharedNamespaces': False,
            'rootReadonly': True, 'network': 'none', 'gpuDevices': False,
            'cpu': 1, 'memoryBytes': 4 * store.GIB, 'swapBytes': 0, 'pids': 128,
            'tmpfs': engine.TMPFS, 'dockerLogs': {'maxBytes': 131072, 'files': 2}},
        'proposedCanary': {'storePath': str(store.ROOT / CANARY_SESSION / 'store.vhdx'),
            'logicalBytes': 128 * store.MIB, 'maximumVhdxFileBytes': 384 * store.MIB,
            'hostReserveBytes': 20 * store.GIB, 'evidenceLimitBytes': 4 * store.MIB,
            'operationSeconds': 180, 'resizeAllowed': False,
            'nativeRuntimeCopyBytesLimit': 256 * store.MIB,
            'faultInjection': 'withhold-guest-pulse-after-READY-while-real-CPU-monitor-continues',
            'guestLeaseSeconds': 3, 'freshPulseGrowthBeforeWorkRequired': True,
            'requiresGlobalExclusiveBlockClaimBeforeDetach': True,
            'storeRetained': True, 'outerContainerRetained': True,
            'automaticRetry': False, 'globalDockerOrWslStopAllowed': False},
        'daemonConfiguration': engine.daemon_configuration(),
        'containerdConfiguration': engine.containerd_configuration(),
        'nativeRunEnabled': False, 'imageDownloadEnabled': False, 'imageImportEnabled': False,
        'buildEnabled': False, 'modelLaunchEnabled': False}


def prepare():
    if not (runtime.ROOT / 'candidate.json').exists():
        runtime.stage()
    packet = material()
    digest = image.build.sha(packet)
    image.tools.plain(ROOT)
    with image.tools.base.lock(ROOT / 'control'):
        directory = ROOT / digest
        directory.mkdir(exist_ok=True)
        path = directory / 'review.json'
        if path.exists():
            if json.loads(image.cpu.bounded(path, 131072)) != packet:
                raise ValueError('ISOLATION_REVIEW_COLLISION')
        else:
            image.tools.base.atomic(path, packet)
        image.tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return directory, packet


def review():
    pointer = json.loads(image.cpu.bounded(ROOT / 'candidate.json', 4096))
    digest = pointer['reviewSha256']
    if not image.build.guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('ISOLATION_REVIEW_INVALID')
    packet = json.loads(image.cpu.bounded(ROOT / digest / 'review.json', 131072))
    if image.build.sha(packet) != digest or packet != material():
        raise ValueError('ISOLATION_REVIEW_STALE')
    return digest, packet


class Permit(image_admission.Permit):
    @property
    def live_namespace(self):
        return LIVE

    def qualify(self, frame):
        if (frame.get('version') != 1 or type(frame.get('version')) is not int or
                frame.get('synthetic') is not False or frame.get('validatedCpuSensor') is not False or
                frame.get('cpuThermalThrottling') is not None or
                frame.get('source') != self.packet['thermalPolicy']['temperature']['source']):
            raise ValueError('NATIVE_SOURCE_QUALIFICATION_INVALID')
        return {**frame, 'rawValidatedCpuSensor': False, 'validatedCpuSensor': True,
                'sourceQualification': self.packet['sourceEvidenceSha256'], 'acceptanceScope': SCOPE}


def authorize():
    if not APPROVAL.exists():
        raise ValueError('ISOLATION_NOT_APPROVED')
    digest, packet = review()
    decision = json.loads(image.cpu.bounded(APPROVAL, 16384))
    if isolated_guest.approved(packet, decision) != digest:
        raise ValueError('NATIVE_APPROVAL_INVALID')
    return Permit(digest, image.build.encoded(packet).decode(), image.build.sha(decision))


def summary():
    try:
        digest, packet = review()
    except (ValueError, OSError, KeyError):
        return {'status': 'NOT_PREPARED_OR_STALE', 'nativeRunEnabled': False,
            'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    approved = False
    try:
        authorize(); approved = True
    except (ValueError, OSError, KeyError):
        pass
    consumed = (LIVE / 'attempt.json').exists() or (store.ROOT / CANARY_SESSION).exists()
    return {'status': 'ATTEMPT_CONSUMED' if consumed else 'APPROVED_REQUIRES_FRESH_ADMISSION' if approved else packet['status'],
        'reviewFile': str(ROOT / digest / 'review.json'), 'reviewSha256': digest,
        'approved': approved, 'attemptConsumed': consumed, 'nativeCompatibilityProven': False,
        'nativeRunEnabled': False, 'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}


def run():
    if not APPROVAL.exists():
        return {'status': 'ISOLATION_NOT_APPROVED', 'nativeRunEnabled': False,
            'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}
    permit = authorize()
    import isolation_native
    return isolation_native.run(permit)
