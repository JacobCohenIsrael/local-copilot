"""Independent host-process watchdog for a fixed, non-GPU dummy container only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lifecycle'))
import supervisor as base

ROOT = base.ROOT / '.runtime' / 'independent-watchdog'
GUARD_TAG = 'independent-dummy-v1'
LEASE_SECONDS = 1.5
MAX_SECONDS = 12


def session(directory):
    directory = Path(directory).absolute()
    base.no_links(directory)
    run_id = directory.name
    if directory.parent != ROOT or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
        raise base.Rejected('Watchdog accepts only its fixed dummy test session directory')
    manifest = directory / 'manifest.json'
    if manifest.is_symlink() or manifest.stat().st_size > 4096:
        raise base.Rejected('Invalid watchdog manifest')
    data = json.loads(manifest.read_text())
    expected_hash = hashlib.sha256(Path(__file__).with_name('uncooperative.py').read_bytes()).hexdigest()
    if data != {'runId': run_id, 'workerSha256': expected_hash}:
        raise base.Rejected('Dummy manifest identity/source mismatch')
    if hashlib.sha256((directory / 'input/worker.py').read_bytes()).hexdigest() != expected_hash:
        raise base.Rejected('Staged dummy source mismatch')
    return directory, {'runId': run_id, 'containerName': 'copilot-dummy-' + run_id}


def owned(docker, identity, directory):
    info = docker.owned(identity)
    if info is not None:
        if info['Config']['Labels'].get('local-copilot.guard') != GUARD_TAG:
            raise base.Rejected('Refusing target without the independent dummy guard label')
        base.validate_container(info, identity, directory / 'input', directory / 'control', 'ignore-stop')
    return info


def heartbeat_size(directory):
    path = directory / 'control/heartbeat'
    size = path.stat().st_size
    if not 0 < size <= 128:
        raise ValueError('Invalid or missing supervisor heartbeat')
    return size


def supervise(directory, docker=None):
    directory, identity = session(directory)
    docker = docker or base.Docker()
    receipt = {'version': 1, 'mode': 'independent-watchdog-dummy-only', 'runId': identity['runId'],
               'phase': 'ARMING', 'fault': None, 'cleanupComplete': False, 'strataStarted': False,
               'cooperativeWorkerLease': False, 'startedAt': base.utc()}
    def save():
        base.atomic(directory / 'watchdog-state.json', receipt)
    def trip(code):
        receipt['phase'] = 'FAULT'
        if receipt['fault'] is None:
            receipt['fault'] = {'code': code, 'at': base.utc()}
        save()
    with base.lock(directory / 'guard-lock'):
        # Do not let another invocation clear a saved fault or restart a guard session.
        if (directory / 'watchdog-state.json').exists():
            raise base.Rejected('Watchdog session already has state; preserve it instead of restarting')
        info = owned(docker, identity, directory)
        if info is None:
            raise base.Rejected('No owned dummy container to guard')
        sequence = heartbeat_size(directory)
        receipt['phase'] = 'ARMED'
        save()  # Host must observe ARMED before starting the container.
        started = last_heartbeat = time.monotonic()
        reason = None
        try:
            while reason is None:
                now = time.monotonic()
                try:
                    size = heartbeat_size(directory)
                    if size < sequence:
                        reason = 'HEARTBEAT_REGRESSION'
                    elif size != sequence:
                        sequence, last_heartbeat = size, now
                except (OSError, ValueError):
                    reason = 'HEARTBEAT_INVALID'
                if reason is None and now - last_heartbeat >= LEASE_SECONDS:
                    reason = 'SUPERVISOR_LEASE_EXPIRED'
                if reason is None and now - started >= MAX_SECONDS:
                    reason = 'WATCHDOG_DEADLINE'
                if reason is None and (directory / 'stop.request').exists():
                    reason = 'EXPLICIT_TEST_STOP'
                if reason is None:
                    time.sleep(0.05)
            receipt['trigger'] = reason
            trip(reason)  # Persist fault before any Docker stop/kill.
        except BaseException as error:
            receipt['error'] = type(error).__name__ + ': ' + str(error)[:512]
            try:
                trip('WATCHDOG_ERROR')
            except Exception:
                pass
        finally:
            # Reinspect identity/isolation, independent of heartbeat producer and worker cooperation.
            info = owned(docker, identity, directory)
            if info is not None:
                if info['State']['Running']:
                    try:
                        docker.call('stop', '--timeout', '1', info['Id'], timeout=5)
                    except Exception as error:
                        receipt['stopError'] = str(error)[:512]
                    info = owned(docker, identity, directory)
                    if info is not None and info['State']['Running']:
                        docker.call('kill', '--signal', 'KILL', info['Id'])
                        info = owned(docker, identity, directory)
                if info is not None:
                    if info['State']['Running']:
                        raise RuntimeError('Owned dummy still running; cleanup is incomplete')
                    receipt['workerExitCode'] = info['State']['ExitCode']
                    try:
                        logs = docker.call('logs', '--tail', '10', info['Id'])
                        receipt['workerLog'] = logs[:4096]
                    except Exception as error:
                        receipt['logError'] = str(error)[:512]
                    finally:
                        docker.call('rm', info['Id'])
            if owned(docker, identity, directory) is not None:
                raise RuntimeError('Owned dummy removal not confirmed')
            receipt['cleanupComplete'] = True
            receipt['finishedAt'] = base.utc()
            receipt['elapsedSeconds'] = round(time.monotonic() - started, 3)
            save()
            base.atomic(directory / 'watchdog-result.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    options = parser.parse_args()
    print(json.dumps(supervise(Path(options.session)), indent=2))
