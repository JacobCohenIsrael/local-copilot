"""One approved native empty-engine rehearsal; no image/model/build route."""
import contextlib
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

import image_stage as guarded
import isolated_bridge as bridge
import isolated_engine as engine
import isolated_store as store
import isolation_preparation as admission


def load(path, maximum=131072):
    return json.loads(admission.image.cpu.bounded(path, maximum))


def emit(path, value):
    if len(guarded.build.encoded(value)) > 131072:
        raise ValueError('NATIVE_RECORD_LIMIT')
    if path.exists():
        raise ValueError('NATIVE_RECORD_ALREADY_EXISTS')
    guarded.download.tools.base.atomic(path, value)


def copy_inputs(permit, directory, disk, mapping):
    packet = permit.packet
    guest = directory / 'guest'
    if set(p.name for p in guest.iterdir()) - {'owner.pulse', 'owner.pulse.initial'}:
        raise ValueError('NATIVE_GUEST_INPUT_NOT_FRESH')
    for name in ('isolated_agent.py', 'isolated_guest.py', 'wsl_bridge.sh'):
        source = admission.image.HERE / name
        raw = source.read_bytes().replace(b'\r\n', b'\n')
        expected = packet['nativeInputSha256'][name]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('NATIVE_GUEST_INPUT_CHANGED')
        (guest / name).write_bytes(raw)
    (guest / 'empty-cdi').mkdir()
    emit(guest / 'review.json', packet)
    emit(guest / 'approval.json', load(admission.APPROVAL, 16384))
    raw = (Path(packet['runtime']['directory']) / 'runtime.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != packet['runtime']['manifestSha256']:
        raise ValueError('NATIVE_RUNTIME_MANIFEST_CHANGED')
    (guest / 'runtime.json').write_bytes(raw)
    emit(guest / 'dockerd.json', packet['daemonConfiguration'])
    (guest / 'containerd.toml').write_bytes(packet['containerdConfiguration'].encode())
    emit(guest / 'launch.json', {'version': 1, 'reviewSha256': permit.review_sha256,
        'sessionId': packet['sessionId'], 'markerHex': disk.marker.hex(),
        'logicalBytes': disk.spec.logical_bytes, 'deviceToken': mapping['deviceToken'],
        'diskSequence': mapping['diskSequence'], 'majorMinor': mapping['majorMinor']})


def parse_logs(raw):
    if len(raw.encode()) > 262144:
        raise ValueError('NATIVE_GUEST_LOG_LIMIT')
    rows = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get('event') in ('READY', 'STOPPED'):
            rows.append(value)
    return rows


def validate_ready(ready, token):
    if (ready.get('deviceToken') != token or
            ready.get('engine', {}).get('Images') != 0 or ready.get('engine', {}).get('Containers') != 0 or
            ready.get('engine', {}).get('DockerRootDir') != '/store/docker' or
            ready.get('engine', {}).get('containerdSocket') != '/run/copilot/containerd.sock'):
        raise ValueError('NATIVE_GUEST_READY_INVALID')
    engine.validate_cgroup(ready['limits'])


def validate_guest(ready, stopped, token):
    validate_ready(ready, token)
    if (stopped.get('deviceToken') != token or
            stopped.get('fault') != 'OWNER_LEASE_EXPIRED' or stopped.get('ready') is not True or
            any(stopped.get(k) is not True for k in ('enginesStopped', 'unmounted', 'exclusiveDeviceClaim')) or
            any(stopped.get(k) is not False for k in ('imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('NATIVE_GUEST_STOP_OR_IDENTITY_INVALID')


def operation(permit, directory, allowed, *, disk_factory=store.Store,
              backend_factory=store.WindowsVhdx, bridge_factory=bridge.WslBridge,
              docker_factory=guarded.build.guard.base.Docker):
    packet, target, detached = permit.packet, None, False
    docker = docker_factory()
    disk = disk_factory(store.Spec(packet['sessionId'], logical_bytes=128 * store.MIB))
    backend = backend_factory(allowed=allowed, operation_seconds=180)
    transport = bridge_factory(disk, backend, directory / 'wsl_bridge.sh')
    try:
        if not allowed():
            raise ValueError('NATIVE_PERMISSION_LOST')
        created = disk.create(backend)
        emit(directory / 'native-created.json', created)
        mapping = transport.attach()
        emit(directory / 'bridge-proof.json', mapping)
        copy_inputs(permit, directory, disk, mapping)
        spec = engine.Spec(packet['sessionId'], packet['capsuleImageId'], str(directory / 'guest'),
                           packet['runtime']['directory'], mapping['device'], permit.review_sha256)
        if not allowed():
            raise ValueError('NATIVE_PERMISSION_LOST')
        container_id = docker.call(*engine.create_args(spec), timeout=10).strip()
        target = engine.Capsule(spec, container_id, docker)
        emit(directory / 'capsule-owned.json', {'id': container_id, 'device': mapping['device']})
        target.start()
        started, ready = time.monotonic(), None
        while True:
            if not allowed() or time.monotonic() - started >= 120:
                raise ValueError('NATIVE_PERMISSION_OR_START_DEADLINE')
            row = target.inspect()
            events = parse_logs(docker.call('logs', '--tail', '10', target.id, timeout=3))
            for event in events:
                if event['event'] == 'READY' and ready is None:
                    ready = event
                    validate_ready(ready, mapping['deviceToken'])
                    emit(directory / 'guest-ready.json', ready)
                    # This is the one reviewed fault injection. The Windows CPU
                    # monitor stays active; only the guest lease stops advancing.
                    (directory / 'withhold.request').touch(exist_ok=False)
            if engine.Capsule.stopped(row):
                stopped = [r for r in events if r['event'] == 'STOPPED']
                if ready is None or len(stopped) != 1 or row['State'].get('ExitCode') != 0 or row['State'].get('OOMKilled'):
                    emit(directory / 'guest-failed-events.json', {'events': events})
                    raise ValueError('NATIVE_CANARY_FAILED')
                validate_guest(ready, stopped[0], mapping['deviceToken'])
                emit(directory / 'guest-stopped.json', stopped[0])
                detached = transport.detach(guest=stopped[0], capsule_stopped=True)
                if detached is not True:
                    raise ValueError('NATIVE_STORE_DETACH_UNCONFIRMED')
                return {'scope': admission.SCOPE, 'reviewSha256': permit.review_sha256, 'synthetic': False,
                    'sessionId': packet['sessionId'], 'ownerLeaseFaultObserved': True,
                    'engineStopConfirmed': True, 'storeDetached': True, 'runtimeManifestSha256': packet['runtime']['manifestSha256'],
                    'logicalBytes': 134217728, 'imageDownloadEnabled': False, 'imageImportEnabled': False,
                    'buildEnabled': False, 'modelLaunchEnabled': False}
            time.sleep(.5)
    finally:
        if target is not None:
            cleanup = target.stop()
            emit(directory / 'native-stop.json', {**cleanup, 'storeDetached': detached})
            if cleanup['stopConfirmed'] is not True:
                raise ValueError('NATIVE_ENGINE_STOP_UNCONFIRMED')


def child():
    permit = admission.authorize()
    directory = admission.LIVE
    claim = load(directory / 'attempt.json', 4096)
    if claim['reviewSha256'] != permit.review_sha256 or claim.get('synthetic') is not False:
        raise ValueError('NATIVE_CHILD_CLAIM_INVALID')
    pulse = guarded.controller.Pulse(directory / 'controller.pulse', maximum=4096)
    started, done = time.monotonic(), threading.Event()
    def allowed():
        return (not done.is_set() and not (directory / 'cancel.request').exists() and
                pulse.age() <= permit.packet['controllerLeaseSeconds'] and time.monotonic() - started < 180)
    def heartbeat():
        while not done.wait(.25):
            try:
                if not allowed():
                    return
                guarded.controller.pulse(directory / 'worker.pulse', maximum=4096)
            except Exception:
                return
    beat = threading.Thread(target=heartbeat, daemon=True)
    beat.start()
    try:
        result = operation(permit, directory, allowed)
        emit(directory / 'worker-result.json', result)
    except BaseException as error:
        code = str(error) if re.fullmatch('[A-Z_]{1,80}', str(error)) else 'NATIVE_OPERATION_ERROR'
        emit(directory / 'worker-error.json', {'code': code, 'type': type(error).__name__,
             'osError': error.errno if isinstance(error, OSError) else None})
        raise
    finally:
        done.set(); beat.join(timeout=1)


def validate_result(result, packet, synthetic):
    if (synthetic is not False or result.get('synthetic') is not False or
            result.get('scope') != admission.SCOPE or result.get('sessionId') != packet['sessionId'] or
            result.get('reviewSha256') != guarded.build.sha(packet) or result.get('logicalBytes') != 134217728 or
            result.get('runtimeManifestSha256') != packet['runtime']['manifestSha256'] or
            any(result.get(k) is not True for k in ('ownerLeaseFaultObserved', 'engineStopConfirmed', 'storeDetached')) or
            any(result.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('NATIVE_WORKER_RESULT_INVALID')
    return result


def run(permit):
    if not isinstance(permit, admission.Permit) or admission.authorize() != permit:
        raise ValueError('NATIVE_EXACT_PERMIT_REQUIRED')
    packet = permit.packet
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('NATIVE_ADMINISTRATOR_ACCESS_REQUIRED')
    if admission.LIVE.exists() and any(p.name != 'control' for p in admission.LIVE.iterdir()):
        raise ValueError('NATIVE_CANARY_ATTEMPT_CONSUMED')
    if (store.ROOT / packet['sessionId']).exists():
        raise ValueError('NATIVE_STORE_ATTEMPT_CONSUMED')
    if hashlib.sha256(admission.image.cpu.bounded(Path.home() / '.wslconfig', 4096)).hexdigest() != packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('NATIVE_WSL_POLICY_CHANGED')
    guarded.build.vm_ready(guarded.build.guard.base.Docker(), packet)
    directory = admission.LIVE
    guarded.download.tools.plain(directory)
    with guarded.download.tools.base.lock(directory / 'control'):
        if any(p.name != 'control' for p in directory.iterdir()):
            raise ValueError('NATIVE_CANARY_ATTEMPT_CONSUMED')
        emit(directory / 'attempt.json', {'sessionId': packet['sessionId'], 'reviewSha256': permit.review_sha256,
                                         'synthetic': False, 'scope': admission.SCOPE})
        (directory / 'guest').mkdir()
        raw = (admission.image.HERE / 'wsl_bridge.sh').read_bytes().replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != packet['nativeInputSha256']['wsl_bridge.sh']:
            raise ValueError('NATIVE_BRIDGE_SCRIPT_CHANGED')
        (directory / 'wsl_bridge.sh').write_bytes(raw)
        feed = guarded.cpu_feed.Feed(guarded.cpu_feed.ROOT / uuid.uuid4().hex, source_permit=permit)
        last_owner_pulse = 0
        def owner_pulse():
            nonlocal last_owner_pulse
            now = time.monotonic()
            if now - last_owner_pulse >= .5 and not (directory / 'withhold.request').exists():
                guarded.controller.pulse(directory / 'guest/owner.pulse', maximum=4096)
                last_owner_pulse = now
        def launch():
            if admission.authorize() != permit:
                raise ValueError('NATIVE_APPROVAL_CHANGED')
            return guarded.windows_job.Process([sys.executable, '-B', str(Path(__file__).resolve()), '--child'],
                cwd=admission.image.REPO, env=os.environ.copy(), memory_bytes=256 * 1024**2, processes=4, single_cpu=True)
        state = guarded._execute(directory, packet, feed, launch, synthetic=False, permit=permit,
            validate=validate_result, download_enabled=False, on_monitor_pass=owner_pulse)
        state['helperStopConfirmed'] = state['stopConfirmed']
        state['engineStopConfirmed'] = state.get('result', {}).get('engineStopConfirmed', False)
        state['storeDetached'] = state.get('result', {}).get('storeDetached', False)
        if not state['engineStopConfirmed'] and (directory / 'capsule-owned.json').exists():
            try:
                owned = load(directory / 'capsule-owned.json', 4096)
                target = engine.Capsule(engine.Spec(packet['sessionId'], packet['capsuleImageId'], str(directory / 'guest'),
                    packet['runtime']['directory'], owned['device'], permit.review_sha256), owned['id'], guarded.build.guard.base.Docker())
                state['engineStopConfirmed'] = target.stop()['stopConfirmed']
            except Exception:
                state['engineStopConfirmed'] = False
        guarded.download.tools.base.atomic(directory / 'state.json', state)
        return state


if __name__ == '__main__':
    if sys.argv[1:] != ['--child']:
        raise SystemExit('NATIVE_INTERNAL_CHILD_ONLY')
    child()
