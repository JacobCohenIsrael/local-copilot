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


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def plan():
    manifest = json.loads((PACKAGE / 'build-manifest.json').read_text())
    if manifest['buildEnabled'] is not False or manifest['modelLaunchEnabled'] is not False:
        raise ValueError('Prepared package must remain disabled')
    args = manifest['createArgs']
    expected = ['create', '--name', 'copilot-strata-compile-1537f5ec',
                '--label', 'local-copilot.kind=strata-compile-proposal', '--platform', 'linux/amd64',
                '--pull=never', '--runtime', 'runc', '--cpus', '1', '--memory', '4g',
                '--memory-swap', '4g', '--pids-limit', '128', '--restart', 'no', '--network', 'bridge',
                '--security-opt', 'no-new-privileges', '--log-driver', 'json-file',
                '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
                '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--entrypoint', '/usr/bin/timeout',
                '--mount', f'type=bind,source={PACKAGE / "input"},target=/input,readonly',
                '--workdir', '/opt/strata',
                'nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c',
                '--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile.sh']
    if args != expected:
        raise ValueError('Prepared compiler command differs from the reviewed guard contract')
    for name, expected in manifest['inputHashes'].items():
        if name not in ('compile.sh', 'bounded_build.py') or digest(PACKAGE / 'input' / name) != expected:
            raise ValueError('Prepared build input changed')
    return {'version': 1, 'mode': 'compiler-guard-prepared-disabled', 'package': str(PACKAGE),
            'buildManifestSha256': digest(PACKAGE / 'build-manifest.json'),
            'compilerName': 'copilot-strata-compile-1537f5ec', 'image': manifest['baseImage'],
            'cpuQuota': 1, 'memoryBytes': 4294967296, 'swapBytes': 0, 'pids': 128,
            'buildEnabled': False, 'modelLaunchEnabled': False,
            'reader': str(Path(__file__).with_name('cpu_reader.ps1')),
            'readerSha256': digest(Path(__file__).with_name('cpu_reader.ps1')),
            'requiredChannels': ['cpuTemperatureC', 'cpuThermalThrottling'],
            'requiredChecks': ['valid source', 'fresh sequence and timestamp', 'bounded query',
                               'controller lease', 'exact container identity/isolation', 'approved live policy'],
            'livePolicy': None, 'rehearsalPolicy': TEST_POLICY,
            'sensorFeed': {'format': 'immutable JSON frames', 'frameBytes': 4096, 'maxFrames': 2048},
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
    def save():
        base.atomic(directory / 'guard-state.json', state)
    def fault(code):
        state['state'] = 'FAULT'
        state['fault'] = state['fault'] or {'code': code, 'at': base.utc()}
        save()
    with base.lock(directory / 'guard-lock'):
        if (directory / 'guard-state.json').exists():
            raise ValueError('Existing session state cannot be reset or restarted')
        if inspect_target(docker, spec) is None:
            raise ValueError('Target missing before admission')
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
        try:
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
            info = inspect_target(docker, spec)
            if info is not None:
                if info['State']['Running']:
                    try:
                        docker.call('stop', '--timeout', '1', info['Id'])
                    except Exception:
                        pass
                    info = inspect_target(docker, spec)
                    if info and info['State']['Running']:
                        docker.call('kill', '--signal', 'KILL', info['Id'])
                        info = inspect_target(docker, spec)
                if info is not None:
                    if info['State']['Running']:
                        raise RuntimeError('Target still running')
                    state['exitCode'] = info['State']['ExitCode']
                    docker.call('rm', info['Id'])
            if inspect_target(docker, spec) is not None:
                raise RuntimeError('Cleanup not verified')
            state['cleanupComplete'] = True
            save()
            base.atomic(directory / 'result.json', state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch-rehearsal')
    options = parser.parse_args()
    print(json.dumps(watch(options.watch_rehearsal) if options.watch_rehearsal else plan(), indent=2))
