"""Capture a stopped build's bounded logs; never start, remove or reset it."""
import hashlib
from pathlib import Path
import subprocess
import time

import build_guard as guard
import stage_build_tools as tools

LOG_BYTES = 65536
CAPTURE_SECONDS = 2


def collect(directory, target, docker, *, capture=None):
    directory = Path(directory)
    receipt = directory / 'startup-diagnostics.json'
    if receipt.exists():
        raise ValueError('BUILD_DIAGNOSTICS_ALREADY_CAPTURED')
    info = target.inspect(guard.DeadlineDocker(docker, time.monotonic() + 1, time.monotonic))
    if info is None or info['Id'] != target.container_id or info['State']['Running']:
        raise ValueError('DIAGNOSTICS_REQUIRE_OWNED_STOPPED_CONTAINER')
    # The inspected profile limits daemon logs to two 1-MiB files. Only a
    # 64-KiB tail is retained locally; stdout and stderr must both be included.
    command = [guard.base.DOCKER, 'logs', '--timestamps', '--tail', '256', target.container_id]
    capture = subprocess.run if capture is None else capture
    status, code, raw = 'CAPTURED', None, b''
    try:
        result = capture(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=CAPTURE_SECONDS,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        raw, code = result.stdout or b'', result.returncode
        if code != 0:
            status = 'DOCKER_LOG_CAPTURE_FAILED'
    except subprocess.TimeoutExpired as error:
        raw, status = error.output or b'', 'DOCKER_LOG_CAPTURE_TIMEOUT'
    if not isinstance(raw, bytes):
        raise ValueError('BUILD_DIAGNOSTIC_CAPTURE_FORMAT')
    tail = raw[-LOG_BYTES:]
    path = directory / 'startup.log'
    with path.open('xb') as output:
        output.write(tail)
    state = info['State']
    record = {'version': 1, 'status': status, 'containerId': target.container_id,
        'exitCode': state.get('ExitCode'), 'oomKilled': state.get('OOMKilled'),
        'runtimeError': str(state.get('Error', ''))[:4096],
        'startedAt': state.get('StartedAt'), 'finishedAt': state.get('FinishedAt'),
        'logBytes': len(tail), 'truncated': len(raw) > len(tail),
        'logSha256': hashlib.sha256(tail).hexdigest(), 'dockerLogExitCode': code,
        'stderrIncluded': True, 'timeoutSeconds': CAPTURE_SECONDS,
        'containerRetainedStopped': True, 'modelLaunchEnabled': False}
    tools.base.atomic(receipt, record)
    return record
