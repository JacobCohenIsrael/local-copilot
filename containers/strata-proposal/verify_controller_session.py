"""Rehearse independent guarding/export with fixed fake files and temperatures."""
import argparse
import json
import subprocess
import sys
import threading
import time
import uuid

import artifact_export as export
import build_guard as guard
import build_policy_review as policy
import controller_rehearsal as rehearsal
import controller_session as controller


def verify(*, cancelled=lambda: False):
    suite = rehearsal.ROOT / uuid.uuid4().hex
    suite.mkdir(parents=True)
    result = {'version': 1, 'passed': False, 'synthetic': True, 'compilerStarted': False,
              'modelStarted': False, 'imagePulled': False, 'cases': []}
    docker = guard.base.Docker()
    docker.call('image', 'inspect', guard.base.IMAGE)
    try:
        for scenario in ('success', 'cpu-hot-during-export', 'controller-lease-lost'):
            if cancelled():
                raise ValueError('CANCELLED')
            namespace = suite / uuid.uuid4().hex
            directory = namespace / 'sessions' / uuid.uuid4().hex
            inputs = directory / 'input'
            inputs.mkdir(parents=True)
            (inputs / 'fixture.py').write_bytes(rehearsal.fixture.FIXTURE.encode())
            (inputs / 'BUILD.json').write_bytes(rehearsal.fixture.META)
            row = {'scenario': scenario, 'session': str(directory), 'passed': False, 'cleanupComplete': False}
            result['cases'].append(row)
            owned_id = frozen = watchdog = exporter = None
            blocked, release = threading.Event(), threading.Event()
            exports, failures = [], []
            try:
                owned_id = docker.call(*rehearsal.create_args(directory)).strip()
                frozen = rehearsal.target(directory, owned_id)
                frozen.inspect(docker)
                guard.base.atomic(directory / 'target.json', {'containerId': owned_id})
                controller.pulse(directory / 'controller.pulse')
                sequence, next_frame = 0, 0
                def publish(temperature=92):
                    nonlocal sequence
                    sequence += 1
                    frame = policy.synthetic(sequence, 0, recordedAtUnix=time.time(),
                                             cpuTemperatureC=temperature, readerRemainingSeconds=1920)
                    guard.base.atomic(directory / f'sample-{sequence:08d}.json', frame)
                publish()
                with (directory / 'watch.log').open('xb') as log:
                    watchdog = subprocess.Popen([sys.executable, '-B', str(rehearsal.__file__),
                        '--watch-synthetic-only', str(directory)], stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    row['watchdogPid'] = watchdog.pid
                    lease = controller.Pulse(directory / 'guard.pulse')
                    end, started, requested, recorded = time.monotonic() + 32, False, False, False
                    while time.monotonic() < end:
                        if cancelled():
                            raise ValueError('CANCELLED')
                        now = time.monotonic()
                        if now >= next_frame:
                            publish(97 if scenario == 'cpu-hot-during-export' and blocked.is_set() else 92)
                            if not (scenario == 'controller-lease-lost' and blocked.is_set()):
                                controller.pulse(directory / 'controller.pulse')
                            next_frame = now + .5
                        if lease.path.exists():
                            lease.age()
                        file = namespace / 'state.json'
                        state = controller.read_json(file) if file.exists() else None
                        if state and state['phase'] == 'ARMED' and not started:
                            if watchdog.poll() is not None or not lease.changed or lease.age() > 2.5:
                                raise ValueError('Watchdog not independently alive before fake-worker start')
                            frozen.inspect(docker)
                            docker.call('start', owned_id)
                            started = True
                        if state and state['phase'] == 'RUNNING' and not requested:
                            if 'SYNTHETIC_OUTPUT_READY' in docker.call('logs', owned_id):
                                (directory / 'export.request').touch(exist_ok=False)
                                requested = True
                        if state and state['phase'] == 'EXPORTING' and exporter is None:
                            transport = controller.GuardedExport(namespace, frozen, docker, lease)
                            if scenario != 'success':
                                def blocked_copy(path, deadline):
                                    blocked.set()
                                    if not release.wait(timeout=min(8, export.check_deadline(deadline))):
                                        raise TimeoutError('Synthetic blocked export did not release')
                                    raise ValueError('Synthetic export interrupted by independent guard')
                                transport.copy = blocked_copy
                            def collect():
                                try:
                                    folder, receipt = export.collect(transport, container_id=owned_id,
                                        plan_sha256=frozen.plan_sha256, metadata_sha256=frozen.metadata_sha256,
                                        synthetic=True, deadline=time.monotonic() + 8)
                                    exports.append((folder, receipt))
                                except BaseException as error:
                                    failures.append(type(error).__name__)
                            exporter = threading.Thread(target=collect, daemon=True)
                            exporter.start()
                        if state and state['phase'] == 'FAULT' and blocked.is_set() and not release.is_set():
                            row['exportBlockedAtFault'] = exporter.is_alive()
                            release.set()
                        if exporter is not None and not exporter.is_alive() and not recorded:
                            if exports:
                                guard.base.atomic(directory / 'export.result.json', {'directory': str(exports[0][0])})
                            else:
                                (directory / 'export.failure').touch(exist_ok=False)
                            recorded = True
                        if watchdog.poll() is not None:
                            if not state or state['phase'] not in ('COMPLETE', 'FAULT'):
                                raise ValueError('Independent watchdog exited without a terminal receipt')
                            break
                        time.sleep(.05)
                    else:
                        raise TimeoutError('Synthetic controller suite deadline')
                terminal = controller.read_json(directory / 'result.json')
                row.update(phase=terminal['phase'], fault=terminal['fault'],
                           stopConfirmed=terminal['stopConfirmed'], cleanupComplete=terminal['cleanupComplete'],
                           stopSeconds=terminal.get('stopSeconds'))
                if scenario == 'success':
                    if terminal['phase'] != 'COMPLETE' or not exports or failures:
                        raise ValueError('Successful export did not complete through controller')
                    row['exportedBytes'] = sum(item['bytes'] for item in exports[0][1]['files'])
                else:
                    expected = 'CPU_HOT' if scenario == 'cpu-hot-during-export' else 'CONTROLLER_LEASE_EXPIRED'
                    if (terminal['phase'] != 'FAULT' or terminal['fault']['code'] != expected or
                            not row.get('exportBlockedAtFault') or exports or not failures):
                        raise ValueError('Independent safety fault/export interruption not confirmed')
                    try:
                        controller.Session(namespace, directory, frozen, docker)
                    except ValueError as error:
                        if 'Latched fault' not in str(error):
                            raise
                        row['restartRejected'] = True
                    else:
                        raise ValueError('Faulted namespace incorrectly allowed restart')
                if not terminal['stopConfirmed'] or not terminal['cleanupComplete'] or frozen.inspect(docker) is not None:
                    raise ValueError('Fake worker stop/removal not confirmed')
                row['passed'] = True
            finally:
                release.set()
                if exporter is not None:
                    exporter.join(timeout=2)
                if watchdog is not None and watchdog.poll() is None:
                    (directory / 'cancel.request').touch(exist_ok=True)
                    try:
                        watchdog.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        # Stop the owned fake target before terminating its stuck guard.
                        if frozen is not None:
                            row['fallbackStop'] = guard.stop_target(docker, {}, owned_id, matcher=frozen.matcher)
                        watchdog.kill()
                        watchdog.wait(timeout=2)
                if frozen is not None and frozen.inspect(docker) is not None:
                    row['fallbackStop'] = guard.stop_target(docker, {}, owned_id, matcher=frozen.matcher)
                if frozen is not None:
                    row['cleanupComplete'] = frozen.inspect(docker) is None
                # Immutable progress receipts avoid replacing the same Windows
                # file immediately before publishing the final suite result.
                guard.base.atomic(suite / ('case-' + str(len(result['cases'])) + '.json'), row)
            print(json.dumps(row), flush=True)
        result['passed'] = all(row['passed'] and row['cleanupComplete'] for row in result['cases'])
    finally:
        guard.base.atomic(suite / 'result.json', result)
    print(json.dumps({'directory': str(suite), 'passed': result['passed']}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-only', action='store_true', required=True)
    parser.parse_args()
    verify()
