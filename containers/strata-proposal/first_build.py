"""One approved offline CPU compile: independent guard, owned target, bounded export.

No image pull/load/import or model command exists. run() rejects before any
process/container creation unless a human-approved exact review is present.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import artifact_export as export
import build_diagnostics
import build_admission as admission
import build_guard as guard
import controller_session as controller
import cpu_feed
import image_plan
import offline_build_plan as offline
import offline_target
import probe_image_storage


def _session(directory, *, admitter=admission):
    directory = Path(directory).absolute()
    export.tools.plain(directory)
    if (directory.parent != admitter.LIVE / 'sessions' or
            not guard.re.fullmatch('[0-9a-f]{32}', directory.name)):
        raise ValueError('First-build session outside fixed namespace')
    return directory


def watch(directory, *, admitter=admission):
    directory = _session(directory, admitter=admitter)
    permit = admitter.authorize()
    request = controller.read_json(directory / 'target.json')
    claim = controller.read_json(admitter.LIVE / 'attempt.json')
    if request['reviewSha256'] != permit.review_sha256 or claim != {
            'sessionId': directory.name, 'reviewSha256': permit.review_sha256}:
        raise ValueError('First-build claim/review mismatch')
    packet = permit.packet
    target = offline_target.from_proposal(packet['offlineDirectory'], packet['offlinePlanSha256'], request['containerId'])
    docker = guard.base.Docker()
    admitter.vm_ready(docker, packet)
    feed = cpu_feed.Feed(cpu_feed.checked_directory(Path(request['readerDirectory'])), source_permit=permit)
    with guard.base.lock(admitter.LIVE / 'guard-lock'):
        target.inspect(docker)
        session = None
        try:
            feed.start_reader(samples=1920)
            monitor = cpu_feed.Monitor(feed)
            session = controller.Session(admitter.LIVE, directory, target, docker, monitor=monitor, permit=permit)
            lease = controller.Pulse(directory / 'controller.pulse', maximum=4096)
            next_pulse = 0
            while session.state['phase'] not in ('FAULT', 'COMPLETE'):
                result = directory / 'export.result.json'
                exported = controller.read_json(result)['directory'] if result.exists() else None
                if (directory / 'export.failure').exists():
                    session.fail('EXPORT_FAILED')
                    break
                session.poll(controller_age=lease.age(), cancelled=(directory / 'cancel.request').exists(),
                             export_requested=(directory / 'export.request').exists(), export_directory=exported)
                if session.state['phase'] not in ('FAULT', 'COMPLETE') and time.monotonic() >= next_pulse:
                    controller.pulse(directory / 'guard.pulse', maximum=4096)
                    next_pulse = time.monotonic() + .5
                time.sleep(.1)
        except BaseException as error:
            if session is not None:
                session.state['watchError'] = type(error).__name__
                session.fail('BUILD_WATCHDOG_ERROR')
            else:
                state = {'phase': 'FAULT', 'fault': {'code': 'READER_OR_CONTROLLER_SETUP'},
                         'synthetic': False, 'modelLaunchEnabled': False,
                         **guard.stop_target(docker, {}, target.container_id, matcher=target.matcher, remove=False)}
                guard.base.atomic(admitter.LIVE / 'state.json', state)
        finally:
            try:
                if session is not None:
                    if session.state['phase'] not in ('FAULT', 'COMPLETE'):
                        session.fail('BUILD_WATCHDOG_INTERRUPTED')
                    guard.base.atomic(directory / 'result.json', session.state)
            finally:
                try:
                    feed.close()
                except Exception:
                    if session is not None:
                        session.fail('READER_STOP_UNCONFIRMED')
                        guard.base.atomic(directory / 'result.json', session.state)
                    raise


def _claim(directory, permit, *, admitter=admission):
    path = admitter.LIVE / 'attempt.json'
    if path.exists() or (admitter.LIVE / 'state.json').exists() or (admitter.LIVE / 'emergency.json').exists():
        raise ValueError('FIRST_BUILD_ATTEMPT_ALREADY_CONSUMED')
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'sessionId': directory.name, 'reviewSha256': permit.review_sha256}, stream)
        stream.flush()
        os.fsync(stream.fileno())


def _ready(docker, target, *, timeout=1):
    """Fixed bounded file read; no compiler stdout streaming or arbitrary exec."""
    try:
        raw = docker.call('exec', '--user', '65532:65532', '--workdir', '/work', target.container_id,
                          '/usr/bin/head', '-c', '4097', '/work/ready.json', timeout=timeout)
    except subprocess.CalledProcessError as error:
        if 'No such file or directory' in (error.stderr or ''):
            return False
        info = target.inspect(docker)
        if info is not None and not info['State']['Running']:
            return False  # Let the watchdog preserve the actual exit and logs.
        raise
    if len(raw.encode()) > 4096:
        raise ValueError('Build-ready record budget')
    if json.loads(raw) != {'state': 'BUILD_COMPLETE_AWAITING_EXPORT', 'modelStarted': False}:
        raise ValueError('Unexpected build-ready record')
    return True


def run(*, admitter=admission):
    permit = admitter.authorize()  # Before reader, Docker mutation or state claim.
    packet = permit.packet
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('ADMINISTRATOR_REQUIRED_FOR_FIXED_CPU_READER')
    _, _, plan = admitter.selected()
    if admitter.source_tree(plan) != packet['sourceTree']:
        raise ValueError('Full source tree changed since review')
    offline.verified_tools(plan['toolDirectory'])
    docker = guard.base.Docker()
    admitter.vm_ready(docker, packet)
    admitter.image_ready(docker, packet)  # inspect only; never pull an absent image.
    capacity_directory = probe_image_storage.probe()
    capacity = controller.read_json(capacity_directory / 'result.json')
    if not image_plan.capacity(capacity, image_plan.storage_budget(packet['image']))['withinProposedBudgetAtProbe']:
        raise ValueError('Insufficient fresh host/guest capacity')
    if (type(capacity.get('guestSwapTotalBytes')) is not int or
            capacity['guestSwapTotalBytes'] != packet['proposedVmEnvelope']['guestSwapBytes']):
        raise ValueError('REVIEWED_WSL_SWAP_SETTING_NOT_ACTIVE')
    with guard.base.lock(admitter.LIVE / 'controller-lock'):
        directory = admitter.LIVE / 'sessions' / uuid.uuid4().hex
        directory.mkdir(parents=True)
        _claim(directory, permit, admitter=admitter)
        owned_id = target = watchdog = exporter = None
        exported, errors = [], []
        reader = cpu_feed.ROOT / uuid.uuid4().hex
        failure_started, parent_error = None, None
        try:
            owned_id = docker.call(*packet['createArgs'], timeout=10).strip()
            target = offline_target.from_proposal(packet['offlineDirectory'], packet['offlinePlanSha256'], owned_id)
            target.inspect(docker)
            guard.base.atomic(directory / 'target.json', {'reviewSha256': permit.review_sha256,
                                   'containerId': owned_id, 'readerDirectory': str(reader)})
            controller.pulse(directory / 'controller.pulse', maximum=4096)
            with (directory / 'watch.log').open('xb') as log:
                watchdog = subprocess.Popen([sys.executable, '-B', '-E', '-s', str(Path(__file__).resolve()),
                            getattr(admitter, 'WATCH_FLAG', '--watch-approved'), str(directory)], stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                lease = controller.Pulse(directory / 'guard.pulse', maximum=4096)
                end, next_pulse, next_ready, started, requested = time.monotonic() + packet['outerSeconds'], 0, 0, False, False
                while time.monotonic() < end:
                    now = time.monotonic()
                    if now >= next_pulse:
                        controller.pulse(directory / 'controller.pulse', maximum=4096)
                        next_pulse = now + .5
                    state_path = admitter.LIVE / 'state.json'
                    state = controller.read_json(state_path) if state_path.exists() else None
                    if watchdog.poll() is not None:
                        state = controller.read_json(state_path) if state_path.exists() else None
                        if state is None or state['phase'] not in ('FAULT', 'COMPLETE'):
                            raise ValueError('Watchdog exited without terminal confirmation')
                        break
                    if lease.path.exists():
                        if lease.age() > 2.5:
                            raise ValueError('Independent build watchdog lost')
                    elif now + packet['outerSeconds'] - end > 5:
                        raise ValueError('Independent build watchdog startup timeout')
                    if state and state['phase'] == 'ARMED' and not started:
                        if not lease.changed or lease.age() > 2.5:
                            raise ValueError('No independently progressing watchdog before start')
                        target.inspect(guard.DeadlineDocker(docker, time.monotonic() + 1, time.monotonic))
                        # Last approval/helper check before the one allowed start.
                        if admitter.authorize() != permit:
                            raise ValueError('Admission changed before start')
                        docker.call('start', owned_id, timeout=1)
                        started = True
                    if state and state['phase'] == 'RUNNING' and now >= next_ready and not requested:
                        next_ready = now + 1
                        ready = (_ready(docker, target, timeout=packet['buildTiming']['readyQuerySeconds'])
                                 if 'buildTiming' in packet else _ready(docker, target))
                        if ready:
                            (directory / 'export.request').touch(exist_ok=False)
                            requested = True
                    if state and state['phase'] == 'EXPORTING' and exporter is None:
                        transport = controller.GuardedExport(admitter.LIVE, target, docker, lease, permit=permit)
                        def collect():
                            try:
                                folder, _ = export.collect(transport, container_id=owned_id,
                                    plan_sha256=target.plan_sha256, metadata_sha256=target.metadata_sha256,
                                    synthetic=False, deadline=time.monotonic() + 20)
                                exported.append(folder)
                            except BaseException as error:
                                errors.append(type(error).__name__)
                        exporter = threading.Thread(target=collect, daemon=True)
                        exporter.start()
                    if exporter is not None and not exporter.is_alive() and not (directory / 'export.result.json').exists():
                        if errors:
                            (directory / 'export.failure').touch(exist_ok=True)
                        else:
                            guard.base.atomic(directory / 'export.result.json', {'directory': str(exported[0])})
                    if state and state['phase'] in ('FAULT', 'COMPLETE'):
                        break
                    time.sleep(.1)
                else:
                    raise TimeoutError('First-build outer deadline')
        except BaseException as error:
            failure_started = time.monotonic()
            parent_error = error
            raise
        finally:
            # The parent never kills its guard before stopping the frozen target.
            try:
                (directory / 'cancel.request').touch(exist_ok=True)
            except OSError:
                pass  # A broken signal file cannot prevent emergency stopping.
            safe_to_end_guard = False
            if target is not None:
                stopped = guard.stop_target(docker, {}, target.container_id, matcher=target.matcher,
                                            started=failure_started, remove=False)
                safe_to_end_guard = stopped['stopConfirmed']
                if not stopped['stopConfirmed'] or (not stopped['cleanupComplete'] and not stopped.get('retainedStoppedTarget')):
                    guard.base.atomic(admitter.LIVE / 'emergency.json', {'fault': 'STOP_UNCONFIRMED', **stopped})
            else:
                guard.base.atomic(admitter.LIVE / 'emergency.json', {'fault': 'CREATE_OR_SETUP_UNCONFIRMED'})
            # Guard waiting/reaping is AFTER exit confirmation, so a hung guard
            # cannot consume eight seconds before the parent's emergency stop.
            if watchdog is not None and safe_to_end_guard:
                try:
                    watchdog.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    pass
            if watchdog is not None and watchdog.poll() is None and safe_to_end_guard:
                watchdog.kill()
                watchdog.wait(timeout=2)
            if exporter is not None:
                exporter.join(timeout=2)
            if target is not None and safe_to_end_guard and stopped.get('retainedStoppedTarget'):
                try:
                    build_diagnostics.collect(directory, target, docker)
                except Exception as error:
                    guard.base.atomic(directory / 'diagnostic-error.json', {'type': type(error).__name__,
                        'containerRetained': True, 'automaticRetry': False})
            if parent_error is not None:
                guard.base.atomic(directory / 'parent-error.json', parent_error_record(parent_error))
        state = controller.read_json(admitter.LIVE / 'state.json')
        if (state['phase'] != 'COMPLETE' or state.get('stopConfirmed') is not True or
                state.get('cleanupComplete') is not True or (admitter.LIVE / 'emergency.json').exists() or
                watchdog is None or watchdog.returncode != 0):
            raise ValueError('FIRST_BUILD_FAILED_OR_STOP_UNCONFIRMED')
        return state


def parent_error_record(error):
    record = {'type': type(error).__name__, 'stderr': str(getattr(error, 'stderr', ''))[:4096],
              'automaticRetry': False}
    if isinstance(error, subprocess.TimeoutExpired):
        record['timeoutSeconds'] = error.timeout
        command = error.cmd if isinstance(error.cmd, (list, tuple)) else [error.cmd]
        record['command'] = [str(part)[:256] for part in command[:24]]
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--watch-approved')
    choice.add_argument('--watch-recovery')
    choice.add_argument('--watch-timing')
    args = parser.parse_args()
    if args.watch_timing:
        import build_timing
        watch(args.watch_timing, admitter=build_timing)
    elif args.watch_recovery:
        import build_recovery
        watch(args.watch_recovery, admitter=build_recovery)
    else:
        watch(args.watch_approved)
