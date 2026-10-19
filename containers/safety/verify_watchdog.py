"""Real CPU-only verification; deliberately kill only a test heartbeat producer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import watchdog as w

base = w.base


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise TimeoutError('Watchdog verification observation deadline exceeded')


def producer(directory, stall):
    directory, _ = w.session(directory)
    log = (directory / 'watchdog-host.log').open('w')
    guardian = subprocess.Popen([sys.executable, '-B', str(Path(__file__).with_name('watchdog.py')),
                                 '--session', str(directory)], close_fds=True,
                                stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    base.atomic(directory / 'producer.json', {'producerPid': os.getpid(), 'watchdogPid': guardian.pid})
    started = time.monotonic()
    while guardian.poll() is None and time.monotonic() - started < 16:
        if not stall or time.monotonic() - started < 1:
            base.heartbeat(directory / 'control')
        time.sleep(0.1)
    if guardian.poll() is None:
        raise RuntimeError('Guardian did not finish within the test producer deadline')
    if guardian.returncode != 0:
        raise RuntimeError('Guardian failed; preserve watchdog-host.log')


def verify():
    docker = base.Docker()
    docker.call('image', 'inspect', base.IMAGE)
    w.ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    with base.lock(w.ROOT / 'verification-lock'):
        for scenario in ('explicit-stop', 'heartbeat-stall', 'producer-killed'):
            run_id = uuid.uuid4().hex
            directory = w.ROOT / run_id
            stage, control = directory / 'input', directory / 'control'
            stage.mkdir(parents=True)
            control.mkdir()
            source = Path(__file__).with_name('uncooperative.py')
            shutil.copyfile(source, stage / 'worker.py')
            base.atomic(directory / 'manifest.json', {'runId': run_id,
                        'workerSha256': hashlib.sha256(source.read_bytes()).hexdigest()})
            base.heartbeat(control)
            identity = {'runId': run_id, 'containerName': 'copilot-dummy-' + run_id}
            args = base.create_args(identity, stage, control, 'ignore-stop')
            args[1:1] = ['--label', 'local-copilot.guard=' + w.GUARD_TAG]
            base.atomic(directory / 'plan.json', {'mode': 'independent-watchdog-dummy-only', 'args': args})
            process = None
            try:
                docker.call(*args)
                process = subprocess.Popen([sys.executable, '-B', __file__, '--producer', str(directory)] +
                                           (['--stall'] if scenario == 'heartbeat-stall' else []),
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                def armed():
                    path = directory / 'watchdog-state.json'
                    return path.exists() and json.loads(path.read_text())['phase'] == 'ARMED'
                wait_for(armed)
                info = w.owned(docker, identity, directory)
                if process.poll() is not None:
                    raise RuntimeError('Heartbeat producer ended before startup')
                docker.call('start', info['Id'])
                wait_for(lambda: '"ready": true' in docker.call('logs', '--tail', '5', info['Id']))
                top = docker.call('top', info['Id'], '-eo', 'pid,args')
                if '--child' not in top:
                    raise AssertionError('Uncooperative descendant was not running')
                if scenario == 'producer-killed':
                    process.kill()
                    process.communicate(timeout=5)
                elif scenario == 'explicit-stop':
                    (directory / 'stop.request').write_text('fixed dummy test stop')
                wait_for(lambda: (directory / 'watchdog-result.json').exists(), timeout=12)
                result = json.loads((directory / 'watchdog-result.json').read_text())
                if result['workerExitCode'] != 137 or not result['cleanupComplete']:
                    raise AssertionError('External watchdog did not terminate/remove the uncooperative dummy')
                expected = 'EXPLICIT_TEST_STOP' if scenario == 'explicit-stop' else 'SUPERVISOR_LEASE_EXPIRED'
                if result['fault']['code'] != expected:
                    raise AssertionError('Unexpected watchdog fault: ' + json.dumps(result))
                if result['elapsedSeconds'] >= 10:
                    raise AssertionError('Watchdog did not act well before the dummy fallback exit')
                if process.poll() is None:
                    stdout, stderr = process.communicate(timeout=5)
                    if process.returncode != 0:
                        raise RuntimeError(stderr)
                results.append({'scenario': scenario, 'passed': True, 'session': str(directory), 'result': result})
                print(json.dumps({'scenario': scenario, 'passed': True, 'seconds': result['elapsedSeconds']}), flush=True)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                # Emergency test cleanup only, rechecking both identity and exact isolation.
                info = w.owned(docker, identity, directory)
                if info is not None:
                    docker.call('rm', '--force', info['Id'])
        report = {'version': 1, 'mode': 'independent-watchdog-dummy-only', 'passed': True,
                  'strataStarted': False, 'realSensorsUsed': False, 'results': results}
        target = w.ROOT / ('verification-' + uuid.uuid4().hex + '.json')
        base.atomic(target, report)
        print('Evidence: ' + str(target), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--producer')
    parser.add_argument('--stall', action='store_true')
    options = parser.parse_args()
    if options.producer:
        producer(Path(options.producer), options.stall)
    elif options.execute:
        verify()
    else:
        parser.error('Use --execute for real non-GPU Docker tests')
