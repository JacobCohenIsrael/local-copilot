"""Owned manual session controller and independent host watchdog."""
import base64
import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

import plan
import first_api as existing
import runtime_record_io as records
import startup_handoff
import cpu_feed
import controller_session as control
from protocol import LIMITS, request, terminal

guard = existing.guard
safety = existing.safety
# Process-local activation; never write the default/historical policy.
safety.POLICY = dict(plan.POLICY)
ENTRY = plan.HERE / 'chat.py'
TERMINAL = ('STOPPED', 'FAULT')


def save(state):
    records.publish(plan.LIVE, state)


def latest():
    return records.latest(plan.LIVE) if records.exists(plan.LIVE) else None


def claim():
    value = plan.read(plan.LIVE / 'attempt.json')
    if (not isinstance(value.get('sessionId'), str) or
            not plan.re.fullmatch('[0-9a-f]{32}', value['sessionId']) or
            not plan.re.fullmatch('[0-9a-f]{64}', value.get('reviewSha256', ''))):
        raise ValueError('MANUAL_CLAIM_IDENTITY')
    return value


def directory():
    return plan.LIVE / 'sessions' / claim()['sessionId']


def fault(state, code, docker, owned):
    state.update(phase='FAULT', fault=state.get('fault') or {'code': code})
    try:
        save(state)  # Latch before issuing the owned stop.
    finally:
        state.update(existing.stop(docker, owned))
        save(state)


def watch():
    permit = plan.authorize()
    packet = permit.packet
    claimed = claim()
    if claimed['reviewSha256'] != permit.review_sha256:
        raise ValueError('MANUAL_WATCH_APPROVAL_CHANGED')
    folder = directory()
    target_record = plan.read(folder / 'target.json')
    owned = existing.target(packet, target_record['containerId'])
    docker = guard.base.Docker()
    state = dict(phase='WAITING_BASELINE', fault=None, containerId=owned.container_id,
                 reviewSha256=permit.review_sha256, sessionId=claimed['sessionId'],
                 stopConfirmed=False, readerExited=False)
    feed = cpu_feed.Feed(Path(target_record['readerDirectory']), source_permit=permit)
    gate = safety.Gate()
    handoff = startup_handoff.Handoff(owned.container_id, permit.review_sha256)
    started = time.monotonic()
    gpu = None
    next_gpu = next_pulse = 0
    gpu_sequence = 0
    with guard.base.lock(plan.LIVE / 'guard-lock'):
        if records.exists(plan.LIVE):
            raise ValueError('MANUAL_WATCH_STATE_EXISTS')
        try:
            owned.inspect(docker)
            feed.start_reader(samples=480)
            plan.write(folder / 'reader-process.json', dict(pid=feed.process.pid, watchdogPid=os.getpid()))
            lease = control.Pulse(plan.LIVE / 'control/controller.pulse', maximum=2048)
            save(state)
            while state['phase'] not in TERMINAL:
                now = time.monotonic()
                if now - started >= LIMITS['outerSeconds']:
                    fault(state, 'OUTER_DEADLINE', docker, owned)
                    break
                if (plan.LIVE / 'stop.request').exists():
                    state.update(existing.stop(docker, owned))
                    state['phase'] = 'STOPPED' if state['stopConfirmed'] else 'FAULT'
                    if state['phase'] == 'FAULT':
                        state['fault'] = {'code': 'STOP_UNCONFIRMED'}
                    save(state)
                    break
                if now >= next_gpu:
                    gpu = safety.snapshot()
                    next_gpu = time.monotonic() + 1
                    gpu_sequence += 1
                    if gpu_sequence > 512:
                        raise ValueError('GPU_SAMPLE_BUDGET')
                    plan.write(folder / f'gpu-{gpu_sequence:04d}.json', gpu)
                cpu = feed.poll()
                if cpu is None and gate.last_cpu is None and now - started <= 5:
                    time.sleep(.05)
                    continue
                eligible = gate.observe(cpu, gpu, now=time.monotonic(), unix=time.time(),
                    controller_age=lease.age(), cancelled=(plan.LIVE / 'cancel.request').exists())
                for _ in range(7):
                    if gate.fault:
                        break
                    cpu = feed.poll()
                    if cpu is None:
                        break
                    eligible = gate.observe(cpu, gpu, now=time.monotonic(), unix=time.time(), controller_age=lease.age())
                if gate.fault:
                    fault(state, gate.fault, docker, owned)
                    break
                if (plan.LIVE / 'api.failure').exists():
                    fault(state, 'MANUAL_API_FAILED', docker, owned)
                    break
                previous = state['phase']
                if previous == 'WAITING_BASELINE':
                    if now - started > 90:
                        fault(state, 'VALID_BASELINE_NOT_MET', docker, owned)
                        break
                    if eligible:
                        state.update(phase='ARMED', startupWarnings=dict(gate.startup_warnings))
                pending = False
                if previous == 'ARMED':
                    receipt = plan.LIVE / 'control/start-result.json'
                    pending = handoff.pending(time.monotonic(), records.read_json(receipt) if receipt.exists() else None)
                if not pending:
                    info = owned.inspect(guard.DeadlineDocker(docker, time.monotonic() + 1, time.monotonic))
                    if info is None:
                        raise ValueError('OWNED_CONTAINER_MISSING')
                    if info['State'].get('OOMKilled'):
                        raise ValueError('MODEL_OOM')
                    if info['State']['Running']:
                        if previous == 'WAITING_BASELINE':
                            raise ValueError('STARTED_BEFORE_ADMISSION')
                        if gate.model_started is None:
                            gate.model_started = handoff.granted_at
                            state.update(phase='RUNNING', grantedAtMonotonic=gate.model_started)
                    elif info['State'].get('Status') != 'created':
                        raise ValueError('UNEXPECTED_CONTAINER_EXIT')
                    elif previous == 'ARMED' and handoff.completed:
                        raise ValueError('START_RETURNED_NOT_RUNNING')
                if state['phase'] != previous:
                    if state['phase'] == 'ARMED':
                        handoff.grant(time.monotonic())
                        state['grantedAtMonotonic'] = handoff.granted_at
                    save(state)
                if time.monotonic() >= next_pulse:
                    control.pulse(plan.LIVE / 'control/guard.pulse', maximum=2048)
                    next_pulse = time.monotonic() + .5
                time.sleep(.1)
        except BaseException as error:
            state['watchError'] = existing.error_record(error, 'manual_watch')
            fault(state, str(error)[:100], docker, owned)
        finally:
            try:
                feed.close()
                state['readerExited'] = feed.process is None or feed.process.returncode is not None
                if not state['readerExited']:
                    raise ValueError('READER_EXIT_UNCONFIRMED')
            except BaseException as error:
                state.update(phase='FAULT', fault=state.get('fault') or {'code': 'READER_STOP_UNCONFIRMED'},
                             readerError=str(error)[:128])
            finally:
                save(state)
                plan.write(folder / 'guard-result.json', state)


def bridge(docker, owned, *args):
    raw = docker.call('exec', '--user', '65532:65532', owned.container_id,
        '/runtime/python/bin/python3.13', '-B', '/input/bridge.py', *args, timeout=1)
    if len(raw.encode()) > 131072:
        raise ValueError('BRIDGE_BYTES')
    return raw


def status():
    state = latest()
    return dict(recordedOnly=True, approvalExists=plan.APPROVAL.exists(),
                attemptConsumed=(plan.LIVE / 'attempt.json').exists(), state=state,
                modelLaunchEnabled=False)


def stop():
    """Stopping a claimed immutable ID never depends on a still-valid approval."""
    folder = directory()
    target_record = plan.read(folder / 'target.json')
    digest = claim()['reviewSha256']
    packet = plan.read(plan.ROOT / digest / 'review.json')
    owned = existing.target(packet, target_record['containerId'])
    (plan.LIVE / 'stop.request').touch(exist_ok=True)
    (plan.LIVE / 'control/finish.request').touch(exist_ok=True)
    result = existing.stop(guard.base.Docker(), owned)
    plan.write(folder / ('explicit-stop-' + uuid.uuid4().hex + '.json'), result)
    return result


def input_lines(inbox):
    try:
        while True:
            text = sys.stdin.readline(4097)
            if not text:
                inbox.put('/stop')
                return
            if len(text) > 4096:
                while text and not text.endswith('\n'):
                    text = sys.stdin.readline(4097)
                inbox.put('/input-too-long')
            else:
                inbox.put(text.rstrip('\r\n'))
    except BaseException:
        inbox.put('/stop')


def commands(line, history, output):
    """Pure terminal command handling, tested without Docker."""
    if line in ('/stop', '/quit', '/exit'):
        return 'stop', history, output, None
    if line == '/new':
        return 'new', [], output, None
    if line.startswith('/tokens '):
        maximum = int(line.split()[1])
        request([{'role': 'user', 'content': 'x'}], maximum)
        return 'tokens', history, maximum, None
    if line == '/help':
        return 'help', history, output, None
    if line.startswith('/'):
        raise ValueError('Unknown command; /help lists commands')
    if not line.strip():
        return 'empty', history, output, None
    return 'send', history, output, request(history + [{'role': 'user', 'content': line}], output)


def preflight(docker, folder):
    plan.base.build.image_ready(docker, {'image': plan.base.build.image_plan.metadata()})
    plan.base.build.vm_ready(docker, {'proposedVmEnvelope': {'logicalProcessors': 1,
                                                          'maximumReportedMemoryBytes': 6 * 1024**3}})
    gpu = safety.snapshot()
    if not str(gpu['driver']).split('.')[0].isdigit() or int(gpu['driver'].split('.')[0]) < 580:
        raise ValueError('CUDA_DRIVER_VERSION')
    import probe_image_storage
    probe = probe_image_storage.probe()
    plan.write(folder / 'capacity-probe.json', {'directory': str(probe)})
    capacity = plan.read(probe / 'result.json')
    if capacity.get('guestSwapTotalBytes') != 0 or not plan.base.build.image_plan.capacity(
            capacity, plan.base.build.image_plan.storage_budget(plan.base.build.image_plan.metadata()))['withinProposedBudgetAtProbe']:
        raise ValueError('DISK_CAPACITY_OR_SWAP')


def run():
    permit = plan.authorize()  # No live access before a fresh exact approval.
    if plan.LIVE.exists():
        raise ValueError('MANUAL_ATTEMPT_CONSUMED_NO_RETRY')
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('ADMINISTRATOR_REQUIRED_FOR_EXISTING_CPU_READER')
    packet = permit.packet
    plan.verify_inputs(packet)
    # mkdir is the exclusive single-attempt claim, even across two CLI launches.
    plan.LIVE.mkdir()
    folder = plan.LIVE / 'sessions' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    plan.write(plan.LIVE / 'attempt.json', dict(sessionId=folder.name, reviewSha256=permit.review_sha256,
                                             approvalSha256=permit.approval_sha256))
    (plan.LIVE / 'control').mkdir()
    owned = watchdog = None
    result = dict(status='FAULT', stopConfirmed=False)
    inbox = queue.Queue(maxsize=8)
    history, output, sequence, pending = [], LIMITS['outputTokens'], 0, None
    last_snapshot = None
    displayed, last_progress = '', None
    next_result = next_pulse = next_notice = 0
    docker = guard.base.Docker()
    try:
        preflight(docker, folder)
        container_id = docker.call(*packet['createArgs'], timeout=10).strip()
        owned = existing.target(packet, container_id)
        plan.write(folder / 'target.json', dict(containerId=container_id, readerDirectory=str(cpu_feed.ROOT / uuid.uuid4().hex)))
        plan.write(folder / 'created-container.json', owned.inspect(docker))
        control.pulse(plan.LIVE / 'control/controller.pulse', maximum=2048)
        with (folder / 'watch.log').open('xb') as log:
            watchdog = subprocess.Popen([sys.executable, '-B', '-E', '-s', str(ENTRY), '--watch'],
                stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        plan.write(folder / 'host-processes.json', dict(parentPid=os.getpid(), watchdogPid=watchdog.pid))
        lease = control.Pulse(plan.LIVE / 'control/guard.pulse', maximum=2048)
        end, started = time.monotonic() + LIMITS['outerSeconds'], False
        threading.Thread(target=input_lines, args=(inbox,), daemon=True).start()
        print('Manual Strata: /help, /new, /tokens N, /stop. Type a prompt once READY.\n'
              '16K context; 512 input tokens including history; output ceiling 4096.\n'
              '150 s per request; 300 s model lifetime includes startup and typing. No retries.', flush=True)
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= next_pulse:
                control.pulse(plan.LIVE / 'control/controller.pulse', maximum=2048)
                next_pulse = time.monotonic() + .5
            state = latest()
            if state and state['phase'] in TERMINAL:
                break
            if watchdog.poll() is not None:
                raise ValueError('MANUAL_WATCH_EXITED')
            if lease.path.exists() and lease.age() > 2.5:
                raise ValueError('GUARD_LEASE_LOST')
            if state and state['phase'] == 'ARMED' and not started:
                if not lease.changed or lease.age() > 2.5 or plan.authorize() != permit:
                    raise ValueError('START_PERMISSION_LOST')
                if latest()['phase'] != 'ARMED' or lease.age() > 2.5:
                    raise ValueError('START_PERMISSION_LOST')
                start = time.monotonic()
                docker.call('start', container_id, timeout=1.5)
                started = True
                plan.write(plan.LIVE / 'control/start-result.json',
                           startup_handoff.receipt(container_id, permit.review_sha256, time.monotonic() - start))
            if state and state['phase'] == 'RUNNING' and now >= next_result:
                last_snapshot = json.loads(bridge(docker, owned, 'snapshot'))
                next_result = time.monotonic() + 1
                snap = last_snapshot
                text = terminal(snap.get('text', ''))
                if text != displayed:
                    if text.startswith(displayed):
                        print(text[len(displayed):], end='', flush=True)
                    displayed = text
                if snap.get('progress') != last_progress:
                    last_progress = snap.get('progress')
                    if last_progress:
                        print(f"\n[prompt read {last_progress['processed']}/{last_progress['total']}]", flush=True)
                if snap['phase'] == 'FAULT':
                    print('\n[' + terminal(snap.get('apiError') or snap.get('error', 'API fault')) + ']', flush=True)
                    plan.write(folder / 'guest-fault.json', snap)
                    (plan.LIVE / 'api.failure').touch(exist_ok=True)
                if pending and snap['phase'] == 'READY' and snap['sequence'] == sequence:
                    plan.write(folder / f'reply-{sequence}.json', snap)
                    print(f"\n[{snap['finish']}; usage {snap['usage']}]", flush=True)
                    history = pending['messages'] + [{'role': 'assistant', 'content': snap['text']}]
                    pending = None
                    if sequence >= LIMITS['requests']:
                        (plan.LIVE / 'stop.request').touch(exist_ok=True)
                        break
            if state and state.get('grantedAtMonotonic') is not None:
                remaining = LIMITS['modelSeconds'] - (time.monotonic() - state['grantedAtMonotonic'])
                if remaining <= 5:
                    print('\n[session lifetime ending; stopping owned container]', flush=True)
                    (plan.LIVE / 'stop.request').touch(exist_ok=True)
                    break
            if now >= next_notice:
                phase = last_snapshot['phase'] if last_snapshot else state['phase'] if state else 'WAITING_FOR_GUARD'
                left = max(0, round(remaining)) if state and state.get('grantedAtMonotonic') is not None else None
                print(f'\n[{phase}; model seconds left: {left}; /stop available]', flush=True)
                next_notice = time.monotonic() + 5
            try:
                line = inbox.get_nowait()
            except queue.Empty:
                line = None
            if line is not None:
                try:
                    action, new_history, new_output, payload = commands(line, history, output)
                    if action == 'stop':
                        (plan.LIVE / 'stop.request').touch(exist_ok=True)
                        break
                    if action == 'help':
                        print('/new clears history; /tokens N sets 1..4096 output; /stop ends the session.\n'
                              'One line per prompt. Busy prompts are refused, never queued or resent.', flush=True)
                    elif action != 'empty':
                        if pending or not last_snapshot or last_snapshot['phase'] != 'READY':
                            print('[wait for READY; prompt/command was not submitted]', flush=True)
                        elif action == 'send':
                            if sequence >= LIMITS['requests']:
                                raise ValueError('REQUEST_COUNT')
                            sequence += 1
                            # Save the exact user input before the one delivery attempt.
                            plan.write(folder / f'request-{sequence}.json', payload)
                            encoded = base64.b64encode(json.dumps(payload).encode()).decode('ascii')
                            bridge(docker, owned, 'submit', str(sequence), encoded)
                            pending, displayed, last_progress = payload, '', None
                        else:
                            history, output = new_history, new_output
                            print(f'[{action}; output ceiling {output}]', flush=True)
                except (ValueError, IndexError) as error:
                    print(terminal(str(error)), flush=True)
            time.sleep(.1)
        else:
            raise TimeoutError('OUTER_DEADLINE')
    except BaseException as error:
        result['error'] = existing.error_record(error, 'manual_controller')
        (plan.LIVE / 'cancel.request').touch(exist_ok=True)
    finally:
        try:
            if not (plan.LIVE / 'cancel.request').exists():
                (plan.LIVE / 'stop.request').touch(exist_ok=True)
            (plan.LIVE / 'control/finish.request').touch(exist_ok=True)
        finally:
            # Evidence/signalling errors must never bypass the owned stopper.
            stopped = existing.stop(docker, owned) if owned else {'stopConfirmed': False, 'stopFault': 'CREATE_UNCONFIRMED'}
        result.update(stopped)
        if watchdog is not None:
            try:
                watchdog.wait(timeout=8)
            except subprocess.TimeoutExpired:
                watchdog.kill()
                watchdog.wait(timeout=2)
                result['watchdogForcedExit'] = True
        result['watchdogExited'] = watchdog is not None and watchdog.poll() is not None
        if last_snapshot is not None:
            plan.write(folder / 'last-snapshot.json', last_snapshot)
        state = latest()
        result['guardState'] = state
        if owned is not None:
            try:
                # Independent post-stop observation by exact immutable Docker ID.
                inspected = owned.stop_matcher(docker, {})
                plan.write(folder / 'post-stop-container.json', inspected or {'absent': True})
                result['independentStopConfirmed'] = inspected is not None and not inspected['State']['Running'] and inspected['State']['Pid'] == 0
                if result['independentStopConfirmed']:
                    existing.build_diagnostics.collect(folder, owned, docker)
            except Exception as error:
                result['postStopError'] = str(error)[:256]
        if (result.get('stopConfirmed') is True and result.get('independentStopConfirmed') is True and
                result['watchdogExited'] and not result.get('watchdogForcedExit') and
                state and state['phase'] == 'STOPPED' and state.get('readerExited') is True and 'error' not in result):
            result['status'] = 'MANUAL_SESSION_STOPPED_CONFIRMED'
        plan.write(folder / 'result.json', result)
    return result
