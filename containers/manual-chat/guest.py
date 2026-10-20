"""Finite interactive guest, reusing existing kernel qualification and leases."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import container_test as base
from protocol import LIMITS, Stream, validate_request

publication_lock = threading.Lock()


def publish(value):
    raw = json.dumps(value).encode()
    if len(raw) > 131072:
        raise ValueError('SNAPSHOT_BYTES')
    with publication_lock:
        path = Path('/work/chat.tmp')
        path.write_bytes(raw)
        path.replace('/work/chat.json')


def main():
    process = None
    closed = threading.Event()
    start = time.monotonic()
    leases = base.Leases(start)
    deadline = [None]
    state = dict(phase='STARTING', sequence=0, text='', requestsSubmitted=0)

    def monitor():
        try:
            while not closed.is_set():
                leases.check(time.monotonic(), {name: (Path('/control') / name).stat().st_size
                             for name in ('controller.pulse', 'guard.pulse')}, deadline[0])
                log = Path('/work/engine.log')
                if log.exists() and log.stat().st_size > 1048576:
                    raise ValueError('ENGINE_LOG_BUDGET')
                closed.wait(.1)
        except BaseException as error:
            # Preserve partial response before terminating a timed out request.
            try:
                publish({**state, 'phase': 'FAULT', 'error': str(error)[:128], 'partial': True})
                base.shutdown(process)
            finally:
                os._exit(70)

    def interrupted(*_):
        raise InterruptedError('HOST_STOP')

    signal.signal(signal.SIGTERM, interrupted)
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    exit_code = 70
    try:
        qualification = base.qualify_environment()
        print('RUNTIME_ENVIRONMENT_VERIFIED ' + json.dumps(qualification), flush=True)
        publish(state)
        process = subprocess.Popen([sys.executable, '-B', '/input/wrapper.py'], start_new_session=True)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        ready_end = time.monotonic() + LIMITS['startupSeconds']
        while True:
            if Path('/control/finish.request').exists():
                break
            if process.poll() is not None:
                raise ValueError('API_EXIT_BEFORE_READY')
            if time.monotonic() >= ready_end:
                raise TimeoutError('API_STARTUP_DEADLINE')
            try:
                with opener.open('http://127.0.0.1:8080/health', timeout=.5) as response:
                    if response.status == 200 and len(response.read(4097)) <= 4096:
                        state['phase'] = 'READY'
                        publish(state)
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(.2)
        while not Path('/control/finish.request').exists():
            if process.poll() is not None:
                raise ValueError('API_EXIT')
            sequence = state['sequence'] + 1
            if sequence > LIMITS['requests']:
                # Do not exit before the host has copied the final answer.
                time.sleep(.1)
                continue
            path = Path(f'/work/request-{sequence}.json')
            if not path.exists():
                time.sleep(.1)
                continue
            raw = path.read_bytes()
            if len(raw) > LIMITS['requestBytes']:
                raise ValueError('REQUEST_BYTES')
            request = validate_request(json.loads(raw))
            state.update(phase='GENERATING', sequence=sequence, text='', progress=None,
                         finish=None, usage=None, requestsSubmitted=sequence)
            publish(state)
            stream = Stream(request['max_tokens'])
            deadline[0] = time.monotonic() + LIMITS['requestSeconds']
            req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
                data=raw, headers={'Content-Type': 'application/json'}, method='POST')
            # Socket timeout is backed by the independent absolute guest timer.
            with opener.open(req, timeout=LIMITS['requestSeconds']) as response:
                if response.status != 200:
                    raise ValueError('API_STATUS')
                with Path(f'/work/stream-{sequence}.sse').open('xb') as evidence:
                    while True:
                        if Path('/control/finish.request').exists():
                            raise InterruptedError('USER_STOP_DURING_REQUEST')
                        line = response.readline(65537)
                        if not line:
                            break
                        stream.feed(line)
                        evidence.write(line)
                        evidence.flush()
                        state.update(text=stream.text, progress=stream.progress)
                        publish(state)
                        if stream.done:
                            break
            answer = stream.result()
            deadline[0] = None
            state.update(phase='READY', **answer)
            publish(state)
            # Retain all completed turns in tmpfs until host copies the evidence.
            Path(f'/work/reply-{sequence}.json').write_text(json.dumps(state))
        state.update(phase='STOPPED', reason='USER_OR_REQUEST_LIMIT')
        publish(state)
        exit_code = 0
    except BaseException as error:
        state.update(phase='FAULT', error=str(error)[:256], partial=True)
        if isinstance(error, urllib.error.HTTPError):
            # Token admission errors must reach the person typing the prompt.
            state['apiError'] = error.read(4097)[:4096].decode('utf-8', errors='replace')
        publish(state)
    finally:
        closed.set()
        base.shutdown(process)
        watcher.join(timeout=.5)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
