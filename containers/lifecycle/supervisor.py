"""Docker dummy lifecycle CLI. No Strata, OpenCode, GPU, or model launch path."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / '.runtime' / 'docker-dummy-supervisor'
DOCKER = r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
IMAGE = 'docker.io/library/python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8'
MODE = 'docker-dummy-only'
SCENARIOS = ('success', 'wait', 'gpu-hot', 'sensor-lost', 'hang', 'ignore-stop')
POLICY = {'id': 'docker-dummy-v1', 'mode': MODE, 'image': IMAGE,
          'cpu': 0.5, 'memoryBytes': 268435456, 'swapBytes': 0, 'pids': 32,
          'taskSeconds': 4, 'sessionSeconds': 20, 'stopSeconds': 1,
          'leaseSeconds': 2.5, 'workerHardStopSeconds': 12,
          'sampleSeconds': 0.2, 'gpuTripC': 75, 'maxEventBytes': 131072}
POLICY_HASH = hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest()


class Rejected(Exception):
    pass


class Busy(Rejected):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def heartbeat(control):
    # Append-only and bounded: Windows bind mounts can deny replacement while a
    # Linux reader holds an existing file. The worker observes size via stat only.
    path = control / 'heartbeat'
    with path.open('ab') as stream:
        if stream.tell() >= 128:
            raise RuntimeError('Heartbeat byte budget exceeded')
        stream.write(b'.')
        stream.flush()
        os.fsync(stream.fileno())


def no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise Rejected('State directory must not contain links or junctions')


@contextmanager
def lock(directory):
    no_links(directory)
    directory.mkdir(parents=True, exist_ok=True)
    no_links(directory)
    stream = (directory / 'supervisor.lock').open('a+b')
    try:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise Busy('Another dummy session owns the supervisor') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def fresh():
    return {'version': 1, 'mode': MODE, 'policyHash': POLICY_HASH, 'state': 'OFF',
            'fault': None, 'runId': None, 'containerName': None, 'cleanupComplete': True, 'updatedAt': utc()}


def load(directory):
    path = directory / 'state.json'
    if not path.exists():
        return fresh()
    if path.stat().st_size > 16384:
        raise Rejected('State exceeds size limit; preserve it for investigation')
    state = json.loads(path.read_text())
    if (state.get('version') != 1 or state.get('mode') != MODE or
            state.get('policyHash') != POLICY_HASH or
            state.get('state') not in ('OFF', 'STARTING', 'RUNNING', 'STOPPING', 'FAULT') or
            (state['state'] == 'FAULT' and (not isinstance(state.get('fault'), dict) or
             not isinstance(state['fault'].get('code'), str))) or
            (state['state'] != 'FAULT' and state.get('fault') is not None) or
            not isinstance(state.get('cleanupComplete'), bool)):
        raise Rejected('Corrupt state or changed dummy policy; preserve evidence, no automatic reset')
    run_id = state.get('runId')
    if run_id is not None and (not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id)):
        raise Rejected('Invalid saved run identity')
    if state.get('containerName') != ('copilot-dummy-' + run_id if run_id else None):
        raise Rejected('Invalid saved container identity')
    if state['state'] != 'OFF' and run_id is None:
        raise Rejected('Active state lacks a run identity')
    return state


class Docker:
    def call(self, *args, timeout=5):
        return subprocess.run([DOCKER, *args], check=True, capture_output=True,
                              text=True, timeout=timeout).stdout

    def inspect(self, name):
        try:
            return json.loads(self.call('container', 'inspect', name))[0]
        except subprocess.CalledProcessError as error:
            if 'No such container' in error.stderr or 'No such object' in error.stderr:
                return None
            raise

    def owned(self, state):
        info = self.inspect(state['containerName'])
        if info is not None:
            labels = info['Config'].get('Labels', {})
            if (labels.get('local-copilot.mode') != MODE or
                    labels.get('local-copilot.run') != state['runId'] or
                    info['Name'] != '/' + state['containerName']):
                raise Rejected('Container identity mismatch; refusing to stop or remove it')
        return info


def create_args(state, stage, control, scenario):
    return ['create', '--name', state['containerName'], '--platform', 'linux/amd64',
            '--pull=never', '--runtime', 'runc', '--label', 'local-copilot.mode=' + MODE,
            '--label', 'local-copilot.run=' + state['runId'],
            '--cpus', '0.5', '--memory', '256m', '--memory-swap', '256m', '--pids-limit', '32',
            '--read-only', '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '65534:65534',
            '--restart', 'no', '--stop-signal', 'SIGTERM', '--stop-timeout', '1',
            '--log-driver', 'json-file', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
            '--env', 'NVIDIA_VISIBLE_DEVICES=void', '--entrypoint', '/usr/local/bin/python3',
            '--mount', f'type=bind,source={stage},target=/input,readonly',
            '--mount', f'type=bind,source={control},target=/control,readonly',
            IMAGE, '-I', '-B', '/input/worker.py', scenario]


def validate_container(info, state, stage, control, scenario):
    host = info['HostConfig']
    config = info['Config']
    expected = {(str(p).replace('\\', '/').lower(), t, False) for p, t in [(stage, '/input'), (control, '/control')]}
    actual = {(m['Source'].replace('\\', '/').lower(), m['Destination'], m['RW']) for m in info['Mounts']}
    checks = [host['Memory'] == POLICY['memoryBytes'], host['MemorySwap'] == POLICY['memoryBytes'],
              host['NanoCpus'] == 500000000, host['PidsLimit'] == 32, host['ReadonlyRootfs'],
              host['NetworkMode'] == 'none', host['Runtime'] == 'runc', not host['Privileged'],
              not host.get('Devices'), not host.get('DeviceRequests'), not host.get('PortBindings'),
              host['RestartPolicy']['Name'] == 'no', host['CapDrop'] == ['ALL'], not host.get('CapAdd'),
              'no-new-privileges' in [v.split(':')[0] for v in host['SecurityOpt']],
              config['User'] == '65534:65534', config['Entrypoint'] == ['/usr/local/bin/python3'],
              config['Cmd'] == ['-I', '-B', '/input/worker.py', scenario],
              config['Image'] == IMAGE, actual == expected,
              host['LogConfig'] == {'Type': 'json-file', 'Config': {'max-size': '64k', 'max-file': '1'}},
              config['Labels'].get('local-copilot.mode') == MODE,
              config['Labels'].get('local-copilot.run') == state['runId']]
    if not all(checks):
        raise Rejected('Container isolation mismatch; refusing startup')


class Supervisor:
    def __init__(self, directory=STATE_DIR, docker=None):
        self.directory = Path(directory)
        self.docker = docker or Docker()
        self.state = None
        self.events = None
        self.start_time = time.monotonic()
        self.signal_cancel = False

    def save(self):
        self.state['updatedAt'] = utc()
        atomic(self.directory / 'state.json', self.state)

    def event(self, kind, **fields):
        if self.events is None:
            return
        line = json.dumps({'at': utc(), 'elapsedSeconds': round(time.monotonic() - self.start_time, 3),
                           'mode': MODE, 'event': kind, **fields}) + '\n'
        if self.events.tell() + len(line.encode()) > POLICY['maxEventBytes']:
            raise RuntimeError('Event budget exceeded')
        self.events.write(line)
        self.events.flush()
        os.fsync(self.events.fileno())

    def trip(self, code):
        if self.state['fault'] is None:
            self.state.update(state='FAULT', fault={'code': code, 'at': utc(), 'syntheticSensors': True})
            self.save()  # Latch before any stop request.
            self.event('fault-latched', code=code)

    def cleanup(self):
        info = self.docker.owned(self.state)
        details = {'graceful': None, 'removed': False, 'exitCode': None}
        evidence_errors = []
        def record(kind, **fields):
            try:
                self.event(kind, **fields)
            except Exception as error:
                evidence_errors.append(str(error)[:256])
        if info is not None:
            if info['State']['Running']:
                record('stop-requested', target='dummy-worker')
                try:
                    self.docker.call('stop', '--timeout', '1', info['Id'], timeout=5)
                except Exception as error:
                    evidence_errors.append('Stop command failed: ' + str(error)[:256])
                    # Reverify ownership before a bounded fallback; never kill by name pattern.
                    remaining = self.docker.owned(self.state)
                    if remaining is not None and remaining['State']['Running']:
                        try:
                            self.trip('STOP_TIMEOUT')
                        except Exception as persistence_error:
                            evidence_errors.append('Fault persistence failed: ' + str(persistence_error)[:256])
                        self.docker.call('kill', '--signal', 'KILL', remaining['Id'])
                info = self.docker.owned(self.state)
            if info is None:
                raise RuntimeError('Owned container disappeared unexpectedly during cleanup')
            if info['State']['Running']:
                raise RuntimeError('Container remained running after stop')
            details['exitCode'] = info['State']['ExitCode']
            details['graceful'] = info['State']['ExitCode'] == 0
            try:
                if info['State']['ExitCode'] == 137:
                    self.trip('STOP_TIMEOUT')
                elif info['State']['ExitCode'] == 78:
                    self.trip('LEASE_EXPIRED')
                elif info['State']['ExitCode'] != 0:
                    self.trip('CLEANUP_EXIT')
                logs = self.docker.call('logs', '--tail', '30', info['Id'])
                if len(logs.encode()) > 16384:
                    raise RuntimeError('Dummy output exceeds budget')
                atomic(self.directory / self.state['runId'] / 'worker-log.json', {'stdout': logs})
            except Exception as error:
                evidence_errors.append('Evidence collection failed: ' + str(error)[:256])
            finally:
                # Missing/broken logs or fault persistence must not prevent removal.
                self.docker.call('rm', info['Id'])
        if self.docker.owned(self.state) is not None:
            raise RuntimeError('Container removal could not be verified')
        details['removed'] = True
        self.state['cleanupComplete'] = True
        self.save()
        record('cleanup-complete', **details)
        if evidence_errors:
            self.trip('CLEANUP_EVIDENCE_FAILURE')
            raise RuntimeError('; '.join(evidence_errors))
        return details

    def recover(self):
        if self.state['state'] not in ('OFF', 'FAULT'):
            self.trip('UNCLEAN_EXIT')
        if self.state['state'] == 'FAULT' and not self.state['cleanupComplete']:
            self.cleanup()

    def status(self):
        try:
            with lock(self.directory):
                self.state = load(self.directory)
                self.recover()
                return {**self.state, 'busy': False}
        except Busy:
            return {**load(self.directory), 'busy': True}

    def cancel(self, run_id):
        state = load(self.directory)
        if state['runId'] != run_id or state['state'] not in ('STARTING', 'RUNNING'):
            raise Rejected('Cancellation must name the current active dummy run')
        atomic(self.directory / run_id / 'cancel.json', {'runId': run_id, 'at': utc()})
        return {'mode': MODE, 'runId': run_id, 'cancellationRequested': True}

    def reset(self, reason, acknowledged):
        if not acknowledged or not 8 <= len(reason) <= 256:
            raise Rejected('Reset requires --acknowledge-dummy and a reason of 8–256 characters')
        with lock(self.directory):
            self.state = load(self.directory)
            self.recover()
            if self.state['state'] != 'FAULT' or not self.state['cleanupComplete']:
                raise Rejected('Reset requires a fault with verified cleanup')
            if self.docker.owned(self.state) is not None:
                raise Rejected('Reset blocked: a container still occupies the saved identity')
            atomic(self.directory / ('reset-' + uuid.uuid4().hex + '.json'),
                   {'at': utc(), 'mode': MODE, 'previousState': self.state, 'reason': reason})
            self.state = fresh()
            self.save()
            return self.state

    def run(self, scenario):
        if scenario not in SCENARIOS:
            raise Rejected('Unknown dummy scenario')
        with lock(self.directory):
            self.state = load(self.directory)
            self.recover()
            if self.state['state'] != 'OFF':
                raise Rejected('Dummy FAULT is latched; review evidence before an explicit dummy reset')
            # Require the already cached image; no hidden download/build on task startup.
            self.docker.call('image', 'inspect', IMAGE)
            run_id = uuid.uuid4().hex
            run_dir = self.directory / run_id
            stage, control = run_dir / 'input', run_dir / 'control'
            stage.mkdir(parents=True)
            control.mkdir()
            shutil.copyfile(Path(__file__).with_name('worker.py'), stage / 'worker.py')
            self.state.update(state='STARTING', runId=run_id, containerName='copilot-dummy-' + run_id,
                              cleanupComplete=False, pid=os.getpid())
            self.start_time = time.monotonic()
            self.save()  # Identity is durable before container creation.
            args = create_args(self.state, stage.resolve(), control.resolve(), scenario)
            atomic(run_dir / 'plan.json', {'mode': MODE, 'policy': POLICY, 'policyHash': POLICY_HASH,
                   'createArgs': args, 'workerSha256': hashlib.sha256((stage / 'worker.py').read_bytes()).hexdigest()})
            self.events = (run_dir / 'events.jsonl').open('x', encoding='utf-8')
            outcome = 'failed'
            stop_details = None
            error_text = None
            try:
                self.event('starting', scenario=scenario, sensors='synthetic', strataStarted=False)
                heartbeat(control)
                self.docker.call(*args)
                info = self.docker.owned(self.state)
                validate_container(info, self.state, stage.resolve(), control.resolve(), scenario)
                self.event('isolation-verified')
                heartbeat(control)
                self.docker.call('start', info['Id'])
                self.state['state'] = 'RUNNING'
                self.save()
                self.event('running')
                running_at = time.monotonic()
                while True:
                    now = time.monotonic()
                    elapsed = now - running_at
                    heartbeat(control)
                    self.event('metrics', synthetic=True,
                               gpuC=80 if scenario == 'gpu-hot' and elapsed >= 0.6 else 40,
                               sensorPresent=not (scenario == 'sensor-lost' and elapsed >= 0.6))
                    if now - self.start_time >= POLICY['sessionSeconds']:
                        self.trip('SESSION_DEADLINE')
                        break
                    if scenario == 'gpu-hot' and elapsed >= 0.6:
                        self.trip('SYNTHETIC_GPU_HOT')
                        break
                    if scenario == 'sensor-lost' and elapsed >= 0.6:
                        self.trip('SYNTHETIC_SENSOR_LOST')
                        break
                    if self.signal_cancel or (run_dir / 'cancel.json').exists():
                        outcome = 'cancelled'
                        self.event('cancelled')
                        break
                    info = self.docker.owned(self.state)
                    if info is None:
                        self.trip('CONTAINER_LOST')
                        break
                    if not info['State']['Running']:
                        if scenario == 'success' and info['State']['ExitCode'] == 0 and not info['State']['OOMKilled']:
                            outcome = 'succeeded'
                        else:
                            self.trip('WORKER_EXIT')
                        break
                    if elapsed >= POLICY['taskSeconds']:
                        self.trip('TASK_DEADLINE')
                        break
                    time.sleep(POLICY['sampleSeconds'])
            except BaseException as error:
                error_text = type(error).__name__ + ': ' + str(error)[:512]
                try:
                    self.trip('INTERNAL_ERROR')
                except Exception:
                    pass  # Cleanup is attempted even if evidence storage fails.
            finally:
                try:
                    if self.state['fault'] is None:
                        self.state['state'] = 'STOPPING'
                        try:
                            self.save()
                        except Exception as error:
                            error_text = 'Stop-state persistence failed: ' + str(error)[:512]
                            try:
                                self.trip('PERSISTENCE_FAILURE')
                            except Exception:
                                pass
                    stop_details = self.cleanup()
                except Exception as error:
                    error_text = (error_text or '') + ' Cleanup: ' + str(error)[:512]
                    try:
                        self.trip('CLEANUP_FAILED')
                    except Exception:
                        pass
                finally:
                    self.events.close()
                    self.events = None
            if self.state['fault'] or error_text:
                outcome = 'fault'
            result = {'version': 1, 'mode': MODE, 'runId': run_id, 'status': outcome,
                      'fault': self.state['fault'], 'error': error_text,
                      'sensors': 'synthetic', 'strataStarted': False, 'codingPerformed': False,
                      'cleanup': stop_details, 'policyHash': POLICY_HASH, 'artifacts': str(run_dir)}
            atomic(run_dir / 'result.json', result)
            if outcome != 'fault':
                self.state['state'] = 'OFF'
                self.save()
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run_parser = sub.add_parser('run')
    run_parser.add_argument('--scenario', choices=SCENARIOS, default='success')
    sub.add_parser('status')
    sub.add_parser('policy')
    sub.add_parser('plan')
    cancel_parser = sub.add_parser('cancel')
    cancel_parser.add_argument('--run-id', required=True)
    reset_parser = sub.add_parser('reset-fault')
    reset_parser.add_argument('--acknowledge-dummy', action='store_true')
    reset_parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    supervisor = Supervisor()
    def cancelled(_signal, _frame):
        supervisor.signal_cancel = True
    signal.signal(signal.SIGINT, cancelled)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, cancelled)
    try:
        if args.command == 'run':
            result = supervisor.run(args.scenario)
        elif args.command == 'status':
            result = supervisor.status()
        elif args.command == 'cancel':
            result = supervisor.cancel(args.run_id)
        elif args.command == 'reset-fault':
            result = supervisor.reset(args.reason, args.acknowledge_dummy)
        elif args.command == 'plan':
            identity = fresh()
            identity.update(runId='0' * 32, containerName='copilot-dummy-' + '0' * 32)
            folder = STATE_DIR / identity['runId']
            result = {'mode': MODE, 'policy': POLICY, 'policyHash': POLICY_HASH,
                      'exampleCreateArgs': create_args(identity, folder / 'input', folder / 'control', 'success'),
                      'note': 'Illustrative run identity; plan writes nothing and contacts no Docker service.'}
        else:
            result = {'mode': MODE, 'policy': POLICY, 'policyHash': POLICY_HASH}
        print(json.dumps(result, indent=2))
        return 3 if result.get('fault') else (2 if result.get('status') == 'cancelled' else 0)
    except Exception as error:
        print(json.dumps({'mode': MODE, 'error': type(error).__name__, 'detail': str(error)[:1024]}), file=sys.stderr)
        return 4 if isinstance(error, Busy) else 2


if __name__ == '__main__':
    sys.exit(main())
