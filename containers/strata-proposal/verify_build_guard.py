"""Execute only the compiler guard rehearsal; never launch a compiler or model."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import build_guard as g


def wait_for(callback, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = callback()
        if result:
            return result
        time.sleep(.05)
    raise TimeoutError('Rehearsal observation deadline')


def verify():
    plan = g.plan()
    g.ROOT.mkdir(parents=True, exist_ok=True)
    g.base.atomic(g.PACKAGE / 'guard-contract.json', plan)
    docker = g.base.Docker()
    docker.call('image', 'inspect', g.base.IMAGE)
    results = []
    with g.base.lock(g.ROOT / 'verification-lock'):
        for scenario, expected in [('hot', 'CPU_HOT'), ('stale', 'SENSOR_STALE'),
                                   ('controller-lost', 'CONTROLLER_LEASE_EXPIRED'), ('cancel', 'CANCELLED'),
                                   ('sensor-corrupt', 'GUARD_ERROR')]:
            directory = g.ROOT / uuid.uuid4().hex
            inputs = directory / 'input'
            inputs.mkdir(parents=True)
            (directory / 'control').mkdir()
            shutil.copyfile(Path(g.__file__).parents[1] / 'safety/uncooperative.py', inputs / 'worker.py')
            spec = {'session': directory.name, 'name': 'copilot-compiler-test-' + directory.name,
                    'input': str(inputs), 'packageHash': plan['buildManifestSha256']}
            g.base.atomic(directory / 'target.json', spec)
            def emit(seq, temp=60):
                g.base.atomic(directory / f'sample-{seq:08d}.json', {'version': 1, 'sequence': seq, 'synthetic': True,
                    'recordedAtUnix': time.time(), 'querySeconds': .01, 'cpuTemperatureC': temp,
                    'cpuThermalThrottling': False, 'validatedCpuSensor': True})
            emit(1)
            g.base.heartbeat(directory / 'control')
            args = ['create', '--name', spec['name'], '--label', 'local-copilot.kind=compiler-guard-rehearsal',
                    '--label', 'local-copilot.session=' + directory.name,
                    '--label', 'local-copilot.package=' + spec['packageHash'],
                    '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
                    '--cpus', '1', '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '128',
                    '--restart', 'no', '--network', 'none', '--security-opt', 'no-new-privileges',
                    '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
                    '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--entrypoint', '/usr/local/bin/python3',
                    '--mount', f'type=bind,source={inputs},target=/input,readonly',
                    g.base.IMAGE, '-I', '-B', '/input/worker.py']
            process = None
            try:
                docker.call(*args)
                process = subprocess.Popen([sys.executable, '-B', str(Path(g.__file__)), '--watch-rehearsal', str(directory)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                def armed():
                    file = directory / 'guard-state.json'
                    return file.exists() and json.loads(file.read_text())['state'] == 'ARMED'
                wait_for(armed)
                info = g.inspect_target(docker, spec)
                docker.call('start', info['Id'])
                started = time.monotonic()
                seq = 1
                # Controller and sensor freshness vary independently; guardian is a separate process.
                while process.poll() is None and time.monotonic() - started < 8:
                    elapsed = time.monotonic() - started
                    if scenario != 'controller-lost' or elapsed < .3:
                        g.base.heartbeat(directory / 'control')
                    if scenario != 'stale' or elapsed < .3:
                        seq += 1
                        emit(seq, 90 if scenario == 'hot' and elapsed > .4 else 60)
                        if scenario == 'sensor-corrupt' and elapsed > .4:
                            g.base.atomic(directory / f'sample-{seq:08d}.json', ['invalid frame'])
                    if scenario == 'cancel' and elapsed > .4:
                        (directory / 'cancel.request').write_text('test only')
                    time.sleep(.15)
                stdout, stderr = process.communicate(timeout=5)
                if process.returncode != 0:
                    raise RuntimeError(stderr)
                result = json.loads(stdout)
                if (result['fault']['code'] != expected or not result['cleanupComplete'] or
                        not result['stopConfirmed'] or result['stopSeconds'] > 5 or result['exitCode'] != 137):
                    raise AssertionError(result)
                if g.inspect_target(docker, spec) is not None:
                    raise AssertionError('Owned test container remains')
                results.append({'scenario': scenario, 'passed': True, 'result': result, 'session': str(directory)})
                print(json.dumps({'scenario': scenario, 'passed': True}), flush=True)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
                info = g.inspect_target(docker, spec)
                if info is not None:
                    docker.call('rm', '--force', info['Id'])
    report = {'passed': True, 'mode': 'compiler-guard-rehearsal', 'buildStarted': False,
              'modelStarted': False, 'packageHash': plan['buildManifestSha256'], 'cases': results}
    path = g.ROOT / ('verification-' + uuid.uuid4().hex + '.json')
    g.base.atomic(path, report)
    print('Evidence: ' + str(path), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.parse_args()
    verify()
