"""One bounded, read-only Windows RAM observation for an approved task only."""
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'safety'))
import telemetry

CONDITION = {'maximumHostUsedMiB': 18432, 'requiredHeadroomToEmergencyMiB': 10240,
             'emergencyStopMiB': 28672, 'observations': 1, 'querySeconds': 1,
             'helperSeconds': 1.5, 'helperStopSeconds': 1, 'freshSeconds': 2.5, 'automaticRetry': False,
             'startupTargetsRemainAdvisory': True}
SOURCE = 'Windows GlobalMemoryStatusEx/GetSystemPowerStatus'


def snapshot():
    started = time.monotonic()
    values = telemetry.native_windows()
    return {**values, 'source': SOURCE, 'synthetic': False,
            'querySeconds': time.monotonic() - started, 'recordedAtUnix': time.time()}


def evaluate(frame, *, unix):
    import math
    def finite(value): return type(value) in (int, float) and math.isfinite(value)
    if (not isinstance(frame, dict) or frame.get('source') != SOURCE or frame.get('synthetic') is not False or
            not all(finite(frame.get(key)) for key in ('ramUsedMiB', 'ramTotalMiB', 'querySeconds', 'recordedAtUnix')) or
            not finite(unix) or not 0 <= unix - frame['recordedAtUnix'] <= CONDITION['freshSeconds'] or
            not 0 <= frame['querySeconds'] <= CONDITION['querySeconds'] or
            not 0 <= frame['ramUsedMiB'] <= frame['ramTotalMiB'] or frame['ramTotalMiB'] <= 0):
        raise ValueError('HOST_RAM_READINESS_INVALID_OR_STALE')
    used = frame['ramUsedMiB']
    return {'ready': used <= CONDITION['maximumHostUsedMiB'],
            'reason': 'READY' if used <= CONDITION['maximumHostUsedMiB'] else 'TASK_HOST_RAM_HEADROOM_LOW',
            'ramUsedMiB': used, 'ramTotalMiB': frame['ramTotalMiB'],
            'availablePhysicalMiB': frame['ramTotalMiB'] - used,
            'headroomToEmergencyMiB': CONDITION['emergencyStopMiB'] - used,
            'condition': dict(CONDITION)}


def read_once(directory):
    # This one-shot child has no descendants. Its PID and exit are retained for
    # independent inspection, including a timeout before it can return a frame.
    process = subprocess.Popen([sys.executable, '-B', '-E', '-s', str(Path(__file__).resolve()), '--snapshot'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    def save(name, value):
        with (Path(directory) / name).open('x', encoding='utf-8') as out: json.dump(value, out, indent=2)
    try:
        save('query-process.json', {'pid': process.pid, 'startedAtUnix': time.time()})
        stdout, stderr = process.communicate(timeout=CONDITION['helperSeconds'])
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args, stdout, stderr)
        if len(stdout) > 4096 or len(stderr) > 4096:
            raise ValueError('HOST_RAM_READINESS_OUTPUT_BUDGET')
        return json.loads(stdout)
    finally:
        if process.poll() is None: process.kill()
        process.wait(timeout=CONDITION['helperStopSeconds'])
        for stream in (process.stdout, process.stderr):
            if stream is not None: stream.close()
        save('query-exit.json', {'pid': process.pid, 'exitCode': process.returncode,
                               'confirmedExited': process.poll() is not None})


if __name__ == '__main__':
    if sys.argv[1:] != ['--snapshot']: raise SystemExit('Explicit --snapshot required')
    print(json.dumps(snapshot()), flush=True)
