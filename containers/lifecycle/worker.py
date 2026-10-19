"""Sleeping dummy and descendant; never imports or starts an AI engine."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

scenario = sys.argv[1]
child = '--child' in sys.argv
stopping = False


def terminate(_signal, _frame):
    global stopping
    if scenario != 'ignore-stop':
        stopping = True


signal.signal(signal.SIGTERM, terminate)
signal.signal(signal.SIGINT, terminate)
started = time.monotonic()
last_change = started
last_sequence = None
if not child:
    subprocess.Popen([sys.executable, '-I', '-B', __file__, scenario, '--child'])
    print(json.dumps({'event': 'ready', 'descendantSpawned': True}), flush=True)
while True:
    now = time.monotonic()
    if stopping:
        print(json.dumps({'event': 'graceful-stop', 'child': child}), flush=True)
        sys.exit(0)
    try:
        # Metadata only avoids holding a Windows bind-mounted file open during updates.
        sequence = Path('/control/heartbeat').stat().st_size
        if not 0 < sequence <= 128:
            raise ValueError('Invalid heartbeat size')
        if sequence != last_sequence:
            last_sequence = sequence
            last_change = now
    except (OSError, ValueError, KeyError):
        print(json.dumps({'event': 'lease-invalid', 'child': child}), flush=True)
        sys.exit(78)
    if now - last_change >= 2.5 or now - started >= 12:
        print(json.dumps({'event': 'lease-expired', 'child': child}), flush=True)
        sys.exit(78)
    if not child and scenario == 'success' and now - started >= 1.2:
        print(json.dumps({'event': 'completed', 'codingPerformed': False}), flush=True)
        sys.exit(0)
    time.sleep(0.05)
