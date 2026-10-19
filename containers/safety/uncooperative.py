"""Sleeping native-engine stand-in: ignores SIGTERM and reads no host lease."""
import json
import signal
import subprocess
import sys
import time

signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGINT, signal.SIG_IGN)
if '--child' not in sys.argv:
    subprocess.Popen([sys.executable, '-I', '-B', __file__, '--child'])
    print(json.dumps({'ready': True, 'cooperativeLease': False, 'descendant': True}), flush=True)
time.sleep(25)  # Harmless test fallback only; the external watchdog must stop it sooner.
