"""Container-only fixed --version check. No network, inference or arbitrary argv."""
import json
from pathlib import Path
import signal
import subprocess

signal.alarm(10)  # PID 1 exits even if the child/pipe handling does not return.
try:
    result = subprocess.run(['/input/opencode', '--version'], capture_output=True, timeout=6)
    print(json.dumps({'mode': 'version-only', 'exitCode': result.returncode,
                      'stdout': result.stdout[:4096].decode('utf-8', errors='replace'),
                      'stderr': result.stderr[:4096].decode('utf-8', errors='replace'),
                      'modelEnabled': False}))
except (OSError, subprocess.TimeoutExpired) as error:
    print(json.dumps({'mode': 'version-only', 'error': type(error).__name__,
                      'binaryExists': Path('/input/opencode').is_file(),
                      'glibcLoaderExists': Path('/lib64/ld-linux-x86-64.so.2').exists(),
                      'osRelease': Path('/etc/os-release').read_text()[:2048],
                      'modelEnabled': False}))
