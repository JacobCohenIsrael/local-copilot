"""Compiler guard contract and independent non-compiling rehearsal watchdog."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lifecycle'))
import supervisor as base

ROOT = base.ROOT / '.runtime/compiler-guard'
PACKAGE = base.ROOT / '.runtime/strata-build/1537f5ec'
TEST_POLICY = {'mode': 'rehearsal-only', 'cpuTripC': 85, 'sampleAgeSeconds': 1.5,
               'querySeconds': 1, 'controllerLeaseSeconds': 1.5, 'deadlineSeconds': 15}
# Owner-approved exit controls. Emergency stopping must not depend on reading
# mutable approval/configuration files after a worker has already been admitted.
STOP_GRACE_SECONDS = 1
STOP_CONFIRM_SECONDS = 5


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def plan(package=None):
    import build_policy_review as policy
    controls = policy.load_effective_controls()
    package = PACKAGE if package is None else Path(package).absolute()
    base.no_links(package)
    if package.parent != PACKAGE.parent or not re.fullmatch('[0-9a-f]{8}', package.name):
        raise ValueError('Build package must be a prepared source-only workspace package')
    compiler_name = 'copilot-strata-compile-' + package.name
    manifest = json.loads((package / 'build-manifest.json').read_text())
    if manifest['buildEnabled'] is not False or manifest['modelLaunchEnabled'] is not False:
        raise ValueError('Prepared package must remain disabled')
    args = manifest['createArgs']
    expected = ['create', '--name', compiler_name,
                '--label', 'local-copilot.kind=strata-compile-proposal', '--platform', 'linux/amd64',
                '--pull=never', '--runtime', 'runc', '--cpus', '1', '--memory', '4g',
                '--memory-swap', '4g', '--pids-limit', '128', '--restart', 'no', '--network', 'bridge',
                '--security-opt', 'no-new-privileges', '--log-driver', 'json-file',
                '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
                '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--entrypoint', '/usr/bin/timeout',
                '--mount', f'type=bind,source={package / "input"},target=/input,readonly',
                '--workdir', '/opt/strata',
                'nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c',
                '--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile.sh']
    if args != expected:
        raise ValueError('Prepared compiler command differs from the reviewed guard contract')
    if set(manifest['inputHashes']) != {'compile.sh', 'bounded_build.py'}:
        raise ValueError('Prepared compiler must bind both build helpers')
    for name, expected in manifest['inputHashes'].items():
        if name not in ('compile.sh', 'bounded_build.py') or digest(package / 'input' / name) != expected:
            raise ValueError('Prepared build input changed')
    return {'version': 1, 'mode': 'compiler-guard-prepared-disabled', 'package': str(package),
            'buildManifestSha256': digest(package / 'build-manifest.json'),
            'compilerName': compiler_name, 'image': manifest['baseImage'],
            'cpuQuota': 1, 'memoryBytes': 4294967296, 'swapBytes': 0, 'pids': 128,
            'buildEnabled': False, 'modelLaunchEnabled': False,
            'reader': str(Path(__file__).with_name('cpu_reader.ps1')),
            'readerSha256': digest(Path(__file__).with_name('cpu_reader.ps1')),
            'requiredChannels': ['cpuTemperatureC'], 'optionalChannels': ['cpuThermalThrottling'],
            'approvedBuildTemperatureControls': controls['temperature'],
            'unknownThrottleExceptionScope': 'cpu-only-build',
            'requiredChecks': ['valid source', 'fresh sequence and timestamp', 'bounded query',
                               'controller lease', 'exact container identity/isolation', 'approved live policy'],
            'livePolicy': None, 'rehearsalPolicy': TEST_POLICY,
            'sensorFeed': {'format': 'immutable JSON frames', 'frameBytes': 4096, 'maxFrames': 2048},
            'exitConfirmationSeconds': STOP_CONFIRM_SECONDS, 'cleanupConfirmationSeconds': 5,
            'stopOrder': ['latch first fault', 'recheck exact container', 'SIGTERM with 1 second rehearsal grace',
                          'kill on deadline', 'confirm exit', 'collect bounded evidence', 'remove owned rehearsal'],
            'note': 'No start/build/image pull is implemented. Rehearsal limits are not a live policy.'}


def reading_error(sample, now, previous_sequence=0, rehearsal=False, previous_stamp=None):
    if not isinstance(sample, dict) or sample.get('version') != 1:
        return 'SENSOR_INVALID'
    seq = sample.get('sequence')
    if type(seq) is not int or seq <= 0 or seq < previous_sequence:
        return 'SENSOR_SEQUENCE'
    if sample.get('synthetic') is not rehearsal or sample.get('error'):
        return 'SENSOR_SOURCE'
    stamp = sample.get('recordedAtUnix')
    if seq == previous_sequence and previous_stamp is not None and stamp != previous_stamp:
        return 'SENSOR_SEQUENCE'
    if type(stamp) not in (int, float) or not (-0.25 <= now - stamp <= TEST_POLICY['sampleAgeSeconds']):
        return 'SENSOR_STALE'
    duration = sample.get('querySeconds')
    if type(duration) not in (int, float) or not 0 <= duration <= TEST_POLICY['querySeconds']:
        return 'SENSOR_QUERY_TIMEOUT'
    temp = sample.get('cpuTemperatureC')
    if type(temp) not in (int, float) or not 0 < temp <= 125:
        return 'CPU_TEMPERATURE_MISSING'
    if sample.get('cpuThermalThrottling') is None:
        return 'CPU_THROTTLE_MISSING'
    if type(sample['cpuThermalThrottling']) is not bool:
        return 'SENSOR_INVALID'
    if not sample.get('validatedCpuSensor'):
        return 'CPU_SENSOR_UNVALIDATED'
    if sample['cpuThermalThrottling']:
        return 'CPU_THROTTLING'
    if rehearsal and temp >= TEST_POLICY['cpuTripC']:
        return 'CPU_HOT'
    return None


def inspect_target(docker, spec):
    info = docker.inspect(spec['name'])
    if info is None:
        return None
    config, host = info['Config'], info['HostConfig']
    compiler = spec.get('kind') == 'compiler-disabled'
    if compiler and spec != compiler_target():
        raise ValueError('Compiler target is not the prepared package')
    expected_mount = {(spec['input'].replace('\\', '/').lower(), '/input', False)}
    actual_mount = {(m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW']) for m in info['Mounts']}
    checks = [info['Name'] == '/' + spec['name'],
              config['Image'] == (plan()['image'] if compiler else base.IMAGE),
              config['Labels'].get('local-copilot.kind') == ('strata-compile-proposal' if compiler else 'compiler-guard-rehearsal'),
              compiler or config['Labels'].get('local-copilot.session') == spec['session'],
              compiler or config['Labels'].get('local-copilot.package') == spec['packageHash'],
              config['Entrypoint'] == (['/usr/bin/timeout'] if compiler else ['/usr/local/bin/python3']),
              config['Cmd'] == (['--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile.sh']
                                if compiler else ['-I', '-B', '/input/worker.py']),
              not compiler or config['WorkingDir'] == '/opt/strata',
              host['Memory'] == 4294967296, host['MemorySwap'] == 4294967296,
              host['NanoCpus'] == 1000000000, host['PidsLimit'] == 128,
              host['Runtime'] == 'runc', not host['Privileged'],
              not host.get('Devices'), not host.get('DeviceRequests'), not host.get('PortBindings'),
              host['NetworkMode'] == ('bridge' if compiler else 'none'), host['RestartPolicy']['Name'] == 'no',
              'no-new-privileges' in [s.split(':')[0] for s in host['SecurityOpt']], actual_mount == expected_mount]
    if not all(checks):
        raise ValueError('Rehearsal target identity/isolation mismatch; refusing control')
    return info


def compiler_target():
    contract = plan()
    return {'kind': 'compiler-disabled', 'name': contract['compilerName'],
            'input': str(PACKAGE / 'input'), 'packageHash': contract['buildManifestSha256']}


def read_sample(directory, current_sequence=None):
    if current_sequence is not None:
        sequence = current_sequence
        while (Path(directory) / f'sample-{sequence+1:08d}.json').exists():
            sequence += 1
            if sequence > 2048:
                raise ValueError('Sensor frame budget exceeded')
        path = Path(directory) / f'sample-{sequence:08d}.json'
        frames = [(sequence, path)]
    else:
        frames = []
        for path in Path(directory).glob('sample-*.json'):
            match = re.fullmatch(r'sample-(\d{8})\.json', path.name)
            if not match or path.is_symlink() or not 0 < int(match.group(1)) <= 2048:
                raise ValueError('Invalid sensor frame path')
            frames.append((int(match.group(1)), path))
            if len(frames) > 2048:
                raise ValueError('Sensor frame budget exceeded')
    if not frames:
        raise ValueError('Missing sensor frames or sensor frame budget exceeded')
    sequence, path = max(frames)
    if path.is_symlink():
        raise ValueError('Sensor frames must be regular files')
    with path.open('rb') as stream:
        data = stream.read(4097)
    if len(data) > 4096:
        raise ValueError('Sensor frame exceeds byte limit')
    sample = json.loads(data)
    if sample.get('sequence') != sequence:
        raise ValueError('Sensor frame identity mismatch')
    return sample


class DeadlineDocker:
    """Every Docker operation shares a deadline; failures never mean 'absent'."""
    def __init__(self, docker, deadline, clock):
        self.docker, self.deadline, self.clock = docker, deadline, clock

    def call(self, *args, timeout=1):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise TimeoutError('Docker confirmation deadline exhausted')
        result = self.docker.call(*args, timeout=min(timeout, remaining))
        if self.clock() > self.deadline:
            raise TimeoutError('Docker operation returned after confirmation deadline')
        return result

    def inspect(self, name):
        return base.Docker.inspect(self, name)


def stop_target(docker, spec, expected_id, *, started=None, clock=time.monotonic, matcher=None, remove=True):
    """Bound exit confirmation to approved controls, then separately bound cleanup.

    This cannot promise physical shutdown during a daemon/host failure. It
    returns explicit unresolved status and never authorizes a new workload.
    """
    started = clock() if started is None else started
    bounded = DeadlineDocker(docker, started + STOP_CONFIRM_SECONDS, clock)
    result = {'stopConfirmed': False, 'cleanupComplete': False, 'stopFault': None}

    def inspected(client):
        info = (matcher or inspect_target)(client, spec)
        if info is not None and info['Id'] != expected_id:
            raise ValueError('Container ID changed; refusing control of replacement')
        return info

    try:
        info = inspected(bounded)
        if info is not None and info['State']['Running']:
            try:
                bounded.call('stop', '--timeout', str(STOP_GRACE_SECONDS), expected_id, timeout=2)
            except Exception:
                pass  # A lost reply is not exit confirmation; re-inspect by identity.
            info = inspected(bounded)
            if info is not None and info['State']['Running']:
                bounded.call('kill', '--signal', 'KILL', expected_id)
                info = inspected(bounded)
        if info is not None and info['State']['Running']:
            raise RuntimeError('Target still running')
        result['stopConfirmed'] = True
        result['stopSeconds'] = clock() - started
        if info is None:
            result['cleanupComplete'] = True
            return result
        result['exitCode'] = info['State']['ExitCode']
    except Exception as error:
        result.update(stopFault='STOP_UNCONFIRMED', stopSeconds=clock() - started,
                      stopError=str(error)[:512])
        return result

    if not remove:
        result['retainedStoppedTarget'] = True
        return result

    # The five-second rule is for confirmed exit. Removal has its own bounded
    # phase; it must never turn a confirmed stop into falsely confirmed cleanup.
    cleanup = DeadlineDocker(docker, clock() + 5, clock)
    try:
        if inspected(cleanup) is not None:
            try:
                cleanup.call('rm', expected_id)
            except Exception:
                # Another owned stopper may have removed the same immutable ID.
                # A fresh confirmed absence resolves that race; an outage does not.
                if inspected(cleanup) is not None:
                    raise
        if inspected(cleanup) is not None:
            raise RuntimeError('Removal not confirmed')
        result['cleanupComplete'] = True
    except Exception as error:
        result.update(cleanupError=str(error)[:512])
    return result


def watch(directory, docker=None):
    directory = Path(directory).absolute()
    base.no_links(directory)
    if directory.parent != ROOT or len(directory.name) != 32 or any(c not in '0123456789abcdef' for c in directory.name):
        raise ValueError('Invalid rehearsal session directory')
    spec = json.loads((directory / 'target.json').read_text())
    compiler = spec.get('kind') == 'compiler-disabled'
    expected = compiler_target() if compiler else {'session': directory.name, 'name': 'copilot-compiler-test-' + directory.name,
                'input': str(directory / 'input'), 'packageHash': plan()['buildManifestSha256']}
    if spec != expected or (not compiler and digest(directory / 'input/worker.py') != digest(Path(__file__).parents[1] / 'safety/uncooperative.py')):
        raise ValueError('Rehearsal manifest/source changed')
    docker = docker or base.Docker()
    state = {'version': 1, 'mode': 'compiler-guard-disabled' if compiler else 'compiler-guard-rehearsal', 'state': 'ARMING',
             'fault': None, 'cleanupComplete': False, 'buildStarted': False, 'modelStarted': False}
    stop_started = None
    def save():
        base.atomic(directory / 'guard-state.json', state)
    def fault(code):
        nonlocal stop_started
        if state['fault'] is None:
            stop_started = time.monotonic()
        state['state'] = 'FAULT'
        state['fault'] = state['fault'] or {'code': code, 'at': base.utc()}
        save()
    with base.lock(directory / 'guard-lock'):
        if (directory / 'guard-state.json').exists():
            raise ValueError('Existing session state cannot be reset or restarted')
        target = inspect_target(docker, spec)
        if target is None:
            raise ValueError('Target missing before admission')
        state['containerId'] = target['Id']
        try:
            sample = read_sample(directory)
            error = 'BUILD_NOT_APPROVED' if compiler else reading_error(sample, time.time(), rehearsal=True)
            if error:
                fault(error)  # A failed preflight is never marked ARMED.
            else:
                state['state'] = 'ARMED'
                save()
            started = last_change = time.monotonic()
            lease = (directory / 'control/heartbeat').stat().st_size
            sequence = sample.get('sequence', 0)
            previous_stamp = sample.get('recordedAtUnix')
            while state['fault'] is None:
                sample = read_sample(directory, sequence)
                error = reading_error(sample, time.time(), sequence, rehearsal=True, previous_stamp=previous_stamp)
                sequence = sample.get('sequence', sequence)
                previous_stamp = sample.get('recordedAtUnix')
                if error:
                    fault(error)
                    break
                now = time.monotonic()
                size = (directory / 'control/heartbeat').stat().st_size
                if size < lease or not 0 < size <= 128:
                    fault('CONTROLLER_LEASE_INVALID')
                elif size != lease:
                    lease, last_change = size, now
                if state['fault'] is None and now - last_change >= TEST_POLICY['controllerLeaseSeconds']:
                    fault('CONTROLLER_LEASE_EXPIRED')
                if state['fault'] is None and now - started >= TEST_POLICY['deadlineSeconds']:
                    fault('SESSION_DEADLINE')
                if state['fault'] is None and (directory / 'cancel.request').exists():
                    fault('CANCELLED')
                if state['fault'] is None:
                    time.sleep(0.05)
        except BaseException as error:
            state['error'] = str(error)[:512]
            try:
                fault('GUARD_ERROR')
            except Exception:
                pass
        finally:
            state.update(stop_target(docker, spec, target['Id'], started=stop_started))
            save()
            base.atomic(directory / 'result.json', state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch-rehearsal')
    options = parser.parse_args()
    print(json.dumps(watch(options.watch_rehearsal) if options.watch_rehearsal else plan(), indent=2))
