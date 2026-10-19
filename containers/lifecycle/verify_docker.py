"""Explicit opt-in real Docker checks, using sleeping CPU-only dummies."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import supervisor as s

TEST_ROOT = s.ROOT / '.runtime' / 'docker-dummy-tests'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise TimeoutError('Test observation deadline exceeded')


def child_run(directory, scenario):
    directory.resolve().relative_to(TEST_ROOT.resolve())
    return s.Supervisor(directory).run(scenario)


def verify():
    test_dir = TEST_ROOT / uuid.uuid4().hex
    test_dir.mkdir(parents=True)
    docker = s.Docker()
    docker.call('image', 'inspect', s.IMAGE)
    results = []
    fixture = None
    child = None
    current = None
    try:
        # A stopped, differently labelled fixture must survive all other sessions.
        fixture = 'copilot-foreign-fixture-' + uuid.uuid4().hex
        identity = {'runId': uuid.uuid4().hex, 'containerName': fixture}
        stage, control = test_dir / 'foreign-input', test_dir / 'foreign-control'
        stage.mkdir()
        control.mkdir()
        args = s.create_args(identity, stage, control, 'success')
        args[args.index('local-copilot.mode=' + s.MODE)] = 'local-copilot.mode=foreign-test-fixture'
        fixture_id = docker.call(*args).strip()

        for scenario in ('success', 'cancel', 'gpu-hot', 'sensor-lost', 'hang', 'ignore-stop', 'parent-death'):
            started = time.monotonic()
            directory = test_dir / scenario
            current = s.Supervisor(directory)
            worker_scenario = 'wait' if scenario in ('cancel', 'parent-death') else scenario
            if scenario in ('cancel', 'ignore-stop', 'parent-death'):
                child = subprocess.Popen([sys.executable, '-B', __file__, '--child', str(directory), worker_scenario],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                def active():
                    if not (directory / 'state.json').exists():
                        return None
                    state = s.load(directory)
                    return state if state['state'] == 'RUNNING' else None
                state = wait_for(active)
                # Verify the dummy actually spawned a descendant before testing stop.
                wait_for(lambda: '"event": "ready"' in docker.call('logs', '--tail', '10', state['containerName']))
                top = docker.call('top', state['containerName'], '-eo', 'pid,args')
                require('--child' in top, 'Expected a running dummy descendant')
                try:
                    current.run('success')
                    raise AssertionError('Concurrent run unexpectedly admitted')
                except s.Busy:
                    pass
                require(current.status()['busy'], 'Active session should report busy')
                if scenario == 'parent-death':
                    child.kill()  # Kill only the exact host test process we started.
                    child.communicate(timeout=5)
                    child = None
                    stopped = wait_for(lambda: (info if (info := docker.owned(state)) and not info['State']['Running'] else None), 6)
                    require(stopped['State']['ExitCode'] == 78, 'Worker did not exit on lease expiry')
                    observed = current.status()  # Reacquire OS lock, latch unclean exit, remove stopped dummy.
                    require(observed['fault']['code'] == 'UNCLEAN_EXIT', 'Missing unclean-exit latch')
                    require(observed['cleanupComplete'], 'Recovery did not clean up')
                    result = {'status': 'fault', 'fault': observed['fault'],
                              'cleanup': {'removed': True}, 'workerExitCode': stopped['State']['ExitCode']}
                else:
                    if scenario == 'cancel':
                        try:
                            current.cancel('wrong-run')
                            raise AssertionError('Wrong run cancellation accepted')
                        except s.Rejected:
                            pass
                    current.cancel(state['runId'])
                    stdout, stderr = child.communicate(timeout=15)
                    require(child.returncode == 0, 'Test child failed: ' + stderr)
                    child = None
                    result = json.loads(stdout)
            else:
                result = current.run(scenario)
            expected = {'success': None, 'cancel': None, 'gpu-hot': 'SYNTHETIC_GPU_HOT',
                        'sensor-lost': 'SYNTHETIC_SENSOR_LOST', 'hang': 'TASK_DEADLINE',
                        'ignore-stop': 'STOP_TIMEOUT', 'parent-death': 'UNCLEAN_EXIT'}[scenario]
            require((result['fault'] or {}).get('code') == expected, 'Unexpected result: ' + json.dumps(result))
            require(result['cleanup']['removed'], 'Owned container was not removed')
            if scenario == 'cancel':
                require(result['status'] == 'cancelled' and result['cleanup']['graceful'], 'Cancellation was not graceful')
            if scenario == 'success':
                require(result['status'] == 'succeeded', 'Success fixture failed')
            if expected:
                try:
                    current.run('success')
                    raise AssertionError('Latched fault admitted a new run')
                except s.Rejected:
                    pass
                # Dummy test domains only: audited reset proves recovery; no live policy is involved.
                current.reset('Reviewed expected dummy integration fault: ' + scenario, True)
                require(current.status()['state'] == 'OFF', 'Dummy reset failed')
            require(docker.inspect(fixture)['Id'] == fixture_id, 'Foreign fixture was changed')
            item = {'scenario': scenario, 'passed': True, 'result': result,
                    'seconds': round(time.monotonic() - started, 2)}
            results.append(item)
            print(json.dumps({'scenario': scenario, 'passed': True, 'seconds': item['seconds']}), flush=True)
        remaining = docker.call('ps', '-aq', '--filter', 'label=local-copilot.mode=' + s.MODE).split()
        # Other domains may exist; only this test's recorded identities must be gone.
        owned_ids = [s.load(test_dir / item['scenario'])['containerName'] for item in results]
        require(all(name is None or docker.inspect(name) is None for name in owned_ids), 'A test container remains')
        report = {'mode': s.MODE, 'passed': True, 'policyHash': s.POLICY_HASH,
                  'strataStarted': False, 'hardwareSensors': 'not queried',
                  'foreignFixturePreserved': True, 'results': results, 'otherDummyContainerIds': remaining}
        s.atomic(test_dir / 'verification.json', report)
        print('Evidence: ' + str(test_dir / 'verification.json'), flush=True)
    finally:
        if child is not None:
            child.kill()
            child.communicate(timeout=5)
        try:
            if current is not None:
                current.status()  # Lease/unclean exit recovery if a check failed mid-session.
        finally:
            if fixture is not None:
                info = docker.inspect(fixture)
                if info is not None:
                    require(info['Config']['Labels'].get('local-copilot.mode') == 'foreign-test-fixture',
                            'Refusing cleanup of mismatched foreign test fixture')
                    docker.call('rm', info['Id'])  # Test fixture was never started.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--child', nargs=2, metavar=('DIRECTORY', 'SCENARIO'))
    options = parser.parse_args()
    if options.child:
        print(json.dumps(child_run(Path(options.child[0]), options.child[1])))
    elif options.execute:
        verify()
    else:
        parser.error('Real Docker verification requires --execute; use test_supervisor.py for mocked tests')
