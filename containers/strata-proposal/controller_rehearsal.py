"""Independent watchdog for fixed fake-output workers. No live build entry point."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

import artifact_export as export
import build_guard as guard
import build_preflight
import controller_session as controller
import cpu_feed
import offline_target
import verify_artifact_export as fixture

ROOT = guard.base.ROOT / '.runtime/offline-controller-rehearsals'


def session_path(directory):
    directory = Path(directory).absolute()
    export.tools.plain(directory)
    if (directory.parent.name != 'sessions' or directory.parents[3] != ROOT or
            not all(re.fullmatch('[0-9a-f]{32}', p.name)
                    for p in (directory, directory.parents[1], directory.parents[2]))):
        raise ValueError('Expected an owned synthetic controller session')
    return directory


def target(directory, container_id):
    directory = session_path(directory)
    for name, expected in [('fixture.py', fixture.FIXTURE.encode()), ('BUILD.json', fixture.META)]:
        path = directory / 'input' / name
        export.tools.plain(path)
        if path.stat().st_size != len(expected) or path.read_bytes() != expected:
            raise ValueError('Synthetic fixture source/metadata changed')
    summary = build_preflight.offline_summary()  # Still disabled, no image/tool execution.
    contract = {'name': 'copilot-controller-test-' + directory.name,
                'image': guard.base.IMAGE, 'entrypoint': ['/usr/local/bin/python3'],
                'command': ['-I', '-B', '/input/fixture.py', 'success'],
                'labels': {'local-copilot.kind': 'offline-controller-rehearsal',
                           'local-copilot.session': directory.name},
                'host': offline_target.host_profile(fixture=True),
                'binds': offline_target.binds([(directory / 'input', '/input')])}
    return offline_target.Target(container_id, json.dumps(contract, sort_keys=True), summary['planSha256'],
                                 hashlib.sha256(fixture.META).hexdigest(), synthetic=True)


def create_args(directory):
    directory = session_path(directory)
    return ['create', '--name', 'copilot-controller-test-' + directory.name,
            '--label', 'local-copilot.kind=offline-controller-rehearsal',
            '--label', 'local-copilot.session=' + directory.name,
            '--platform', 'linux/amd64', '--pull=never', '--runtime', 'runc',
            '--network', 'none', '--read-only', '--cpus', '0.5', '--memory', '64m',
            '--memory-swap', '64m', '--pids-limit', '16', '--user', '65532:65532',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--restart', 'no',
            '--shm-size', str(offline_target.offline.SHM_BYTES),
            '--log-driver', 'json-file', '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1',
            '--env', 'NVIDIA_VISIBLE_DEVICES=void',
            '--tmpfs', '/work:rw,noexec,nosuid,nodev,size=65536,mode=1777',
            '--mount', f'type=bind,source={directory / "input"},target=/input,readonly',
            '--workdir', '/work', '--entrypoint', '/usr/local/bin/python3', guard.base.IMAGE,
            '-I', '-B', '/input/fixture.py', 'success']


def watch(directory):
    directory = session_path(directory)
    namespace = directory.parents[1]
    identity = controller.read_json(directory / 'target.json')
    if set(identity) != {'containerId'}:
        raise ValueError('Unexpected synthetic target manifest')
    frozen = target(directory, identity['containerId'])
    docker = guard.base.Docker()
    with guard.base.lock(namespace / 'guard-lock'):
        if frozen.inspect(docker) is None:
            raise ValueError('Synthetic worker missing before admission')
        monitor = cpu_feed.Monitor(cpu_feed.Feed(directory, synthetic=True))
        session = controller.Session(namespace, directory, frozen, docker, monitor=monitor)
        lease = controller.Pulse(directory / 'controller.pulse')
        try:
            while session.state['phase'] not in ('FAULT', 'COMPLETE'):
                done = directory / 'export.result.json'
                exported = controller.read_json(done)['directory'] if done.exists() else None
                if (directory / 'export.failure').exists():
                    session.fail('EXPORT_FAILED')
                    break
                session.poll(controller_age=lease.age(),
                             cancelled=(directory / 'cancel.request').exists(),
                             export_requested=(directory / 'export.request').exists(), export_directory=exported)
                if session.state['phase'] not in ('FAULT', 'COMPLETE'):
                    controller.pulse(directory / 'guard.pulse')
                    time.sleep(.1)
        except BaseException as error:
            session.state['watchError'] = type(error).__name__
            session.fail('WATCHDOG_ERROR')
        finally:
            if session.state['phase'] not in ('FAULT', 'COMPLETE'):
                session.fail('WATCHDOG_INTERRUPTED')
            guard.base.atomic(directory / 'result.json', session.state)
        return session.state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch-synthetic-only', required=True)
    print(json.dumps(watch(parser.parse_args().watch_synthetic_only), indent=2))
