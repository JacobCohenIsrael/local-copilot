"""Approval-gated pinned image acquisition/stream verification; never import/run.

Main process monitors the CPU reader while a job-owned child performs I/O.
Job owner death kills the child. A separate liveness thread terminates the job
if the main monitoring loop stalls, including while child I/O is blocked.
"""
import argparse
import contextlib
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import build_admission as build
import build_policy_review as policy
import controller_session as controller
import cpu_feed
import image_admission as admission
import image_download as download
import image_expand as expand
import probe_image_storage
import windows_job


class Gate(policy.CpuBuildReadinessGate):
    """Use exact image-scope proposed controls, not a borrowed build approval."""
    def __init__(self, packet, synthetic):
        policy.ThermalRehearsal.__init__(self, packet['thermalPolicy'])
        self.last_event = None
        self.expected_synthetic = synthetic
        self.source_fault = 'IMAGE_SENSOR_PROVENANCE'
        self.eligibility_state = 'ELIGIBLE_FOR_IMAGE_PREPARATION'


class Monitor:
    def __init__(self, feed, packet, *, clock=time.monotonic, unix=time.time):
        self.feed, self.clock, self.unix = feed, clock, unix
        self.started, self.last_frame = clock(), None
        self.gate = Gate(packet, feed.synthetic)
        self.last_error = None

    def poll(self, cancelled):
        elapsed = self.clock() - self.started
        phase = 'poll'
        try:
            frame = self.feed.poll()
            if cancelled:
                self.gate.trip('CANCELLED')
            elif frame is not None:
                phase = 'observe'
                self.last_frame = frame
                return self.gate.observe(frame, elapsed=elapsed, unix=self.unix())
            elif self.feed.sequence:
                phase = 'tick'
                return self.gate.tick(elapsed=elapsed, unix=self.unix(), controller_age=0)
            elif elapsed > 2.5:
                self.gate.trip('SENSOR_MISSING')
        except Exception as error:
            self.last_error = self.last_error or cpu_feed.error_record(self.feed, error, phase)
            self.gate.trip('SENSOR_FEED_ERROR')
        return self.gate.snapshot()


class LoopWatch:
    """No file I/O on the emergency path; only an already-owned process handle."""
    def __init__(self, seconds):
        self.seconds, self.last = seconds, time.monotonic()
        self.process = None
        self.fault = None
        self.fault_at = None
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def beat(self):
        now = time.monotonic()
        if now < self.last:
            self.fault = self.fault or 'CLOCK_INVALID'
            self.fault_at = self.fault_at or now
        self.last = now

    def _watch(self):
        while not self.done.wait(.05):
            if time.monotonic() - self.last > self.seconds:
                self.fault = 'MONITOR_LOOP_LOST'
                self.fault_at = time.monotonic()
                if self.process is not None:
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=1)
                    except BaseException:
                        pass  # Main cleanup/kill-on-close still runs; never success.
                return

    def close(self):
        self.done.set()
        self.thread.join(timeout=1)
        if self.thread.is_alive():
            self.fault = self.fault or 'MONITOR_WATCH_STOP_UNCONFIRMED'


def stop_owned(process, seconds):
    """One finite budget, frozen owned handles, no policy/journal dependencies."""
    end = time.monotonic() + seconds
    try:
        if process.poll() is not None:
            return True
        try:
            process.wait(timeout=min(.2, max(0, end - time.monotonic())))
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=max(0, end - time.monotonic()))
        return process.poll() is not None
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_result(result, packet, synthetic):
    image = packet['image']
    expected = [(r['digest'], r['bytes'], r['expandedSha256']) for r in image['layers']]
    streams = result.get('streams', {})
    rows = streams.get('layers', [])
    staged = result.get('staged', {})
    blobs = [(image['configDigest'], image['configBytes'])] + [(r[0], r[1]) for r in expected]
    if (result.get('synthetic') is not synthetic or result.get('reviewSha256') != build.sha(packet) or
            result.get('scope') != packet['scope'] or streams.get('status') != 'STREAMS_VERIFIED_NOT_IMPORTED' or
            streams.get('extracted') is not False or streams.get('dockerDiskUsageBounded') is not False or
            staged.get('state') != 'STAGED_NOT_IMPORTED' or staged.get('fault') is not None or
            staged.get('synthetic') is not synthetic or staged.get('identitySha256') != build.sha(image) or
            any(staged.get(k) is not False for k in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled')) or
            [(r.get('digest'), r.get('bytes')) for r in staged.get('blobs', [])] != blobs or
            len(rows) != len(expected) or
            any(result.get(k) is not False for k in ('imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
        raise download.StageError('WORKER_RESULT_INVALID')
    total = 0
    for row, (digest, size, expanded_sha) in zip(rows, expected):
        count = row.get('expandedBytes')
        if (row.get('digest') != digest or row.get('compressedBytes') != size or
                row.get('expandedSha256') != expanded_sha or type(count) is not int or
                not 0 < count <= packet['budget']['expandedLayerBytes']):
            raise download.StageError('WORKER_RESULT_INVALID')
        total += count
    if (type(streams.get('expandedBytes')) is not int or total != streams['expandedBytes'] or
            total > packet['budget']['expandedTotalBytes']):
        raise download.StageError('WORKER_RESULT_INVALID')
    return result


def pipeline(directory, packet, source_factory, *, synthetic):
    """Shared real/fixture byte pipeline; caller owns exact admission and job."""
    image = packet['image']
    blobs = [download.Blob(image['configDigest'], image['configBytes'])] + [
        download.Blob(row['digest'], row['bytes']) for row in image['layers']]
    limits = download.Limits(packet['budget']['payloadBytes'],
        packet['budget']['namespaceBytes'] - packet['budget']['supervisorReserveBytes'],
        packet['budget']['freeReserveBytes'], packet['workSeconds'], packet['blobSeconds'])
    lease = controller.Pulse(directory / 'controller.pulse', maximum=4096)
    started, next_pulse = time.monotonic(), 0
    def guard():
        nonlocal next_pulse
        now = time.monotonic()
        if ((directory / 'cancel.request').exists() or lease.age() > packet['controllerLeaseSeconds'] or
                now - started >= packet['workSeconds']):
            return False
        if now >= next_pulse:
            controller.pulse(directory / 'worker.pulse', maximum=4096)
            next_pulse = now + .5
        return True
    if not guard():
        raise download.StageError('GUARD_PERMISSION_LOST')
    source = source_factory(blobs)  # Only after baseline, permit and child claim checks.
    _, staged = download._stage(directory / 'data', blobs, build.sha(image), source, limits,
                                guard=guard, synthetic=synthetic)
    # Total deadline spans BOTH phases, not another 30 minutes for expansion.
    remaining = packet['workSeconds'] - (time.monotonic() - started)
    if remaining <= 0:
        raise download.StageError('STAGING_DEADLINE')
    context = download.Context(download.Limits(limits.payload_bytes, limits.namespace_bytes,
                      limits.free_reserve_bytes, remaining, packet['blobSeconds']), guard)
    layers = [expand.Layer(download.Blob(r['digest'], r['bytes']), r['expandedSha256']) for r in image['layers']]
    with download.tools.base.lock(directory / 'data/control'):
        streams = expand._verify(directory / 'data/cache', layers,
            expand.Limits(packet['budget']['expandedLayerBytes'], packet['budget']['expandedTotalBytes']), context)
    result = {'synthetic': synthetic, 'reviewSha256': build.sha(packet), 'scope': packet['scope'],
              'staged': staged, 'streams': streams, 'imageImportEnabled': False,
              'buildEnabled': False, 'modelLaunchEnabled': False}
    validate_result(result, packet, synthetic)
    if not guard():
        raise download.StageError('GUARD_PERMISSION_LOST')
    download.tools.base.atomic(directory / 'worker-result.json', result)
    return result


def _execute(directory, packet, feed, launch, *, synthetic, permit=None, before_launch=lambda: None,
             clock=time.monotonic, unix=time.time, sleep=time.sleep, validate=validate_result,
             download_enabled=None, import_enabled=False, on_monitor_pass=lambda: None):
    """Connected lifecycle. Test injections are private; live CLI supplies none."""
    if not synthetic:
        if (not isinstance(permit, admission.Permit) or permit.packet != packet or
                directory != permit.live_namespace or feed.source_permit != permit):
            raise ValueError('REAL_IMAGE_STAGE_REQUIRES_EXACT_PERMIT')
    state_path = directory / 'state.json'
    if state_path.exists():
        raise download.StageError('IMAGE_STAGE_RESTART_REJECTED')
    state = {'version': 1, 'phase': 'WAITING_BASELINE', 'fault': None, 'synthetic': synthetic,
             'reviewSha256': build.sha(packet), 'scope': packet['scope'],
             'workerStarted': False, 'stopConfirmed': False, 'readerStopped': False,
             'imageDownloadEnabled': (not synthetic and packet.get('operation') != 'verify-retained-cache-only') if download_enabled is None else download_enabled,
             'imageImportEnabled': import_enabled,
             'buildEnabled': False, 'modelLaunchEnabled': False}
    process, watch, monitor, started, next_pulse, last_metric = None, None, None, clock(), 0, 0
    last_now = started
    def save():
        download.tools.base.atomic(state_path, state)
    try:
        save()  # Durable unfinished state before starting even the reader.
        feed.start_reader(samples=packet['readerSamples'])
        monitor = Monitor(feed, packet, clock=clock, unix=unix)
        watch = LoopWatch(packet['controllerLeaseSeconds'])
        worker_lease = controller.Pulse(directory / 'worker.pulse', maximum=4096, clock=clock)
        work_started = None
        while True:
            now = clock()
            if not policy.finite(now) or now < last_now or now - started > packet['outerSeconds']:
                raise download.StageError('IMAGE_STAGE_OUTER_DEADLINE_OR_CLOCK')
            last_now = now
            if watch.fault:
                raise download.StageError(watch.fault)
            observation = monitor.poll((directory / 'cancel.request').exists())
            if watch.fault:
                raise download.StageError(watch.fault)
            if observation['fault']:
                raise download.StageError(observation['fault'])
            watch.beat()  # Only a completed monitoring pass renews liveness.
            on_monitor_pass()
            if feed.sequence != last_metric:
                last_metric = feed.sequence
                state['readerSequence'] = last_metric
                frame = monitor.last_frame
                metric = {k: frame.get(k) for k in ('sequence', 'recordedAtUnix', 'cpuTemperatureC',
                                                    'querySeconds', 'cpuThermalThrottling')}
                raw = build.encoded(metric) + b'\n'
                if last_metric > 1920 or len(raw) > 512:
                    raise download.StageError('METRICS_BUDGET')
                with (directory / 'metrics.jsonl').open('ab') as stream:
                    stream.write(raw)
            if process is None:
                if now - started > packet['baselineWaitSeconds']:
                    raise download.StageError('BASELINE_WAIT_DEADLINE')
                if observation['state'] == 'ELIGIBLE_FOR_IMAGE_PREPARATION':
                    if now >= next_pulse:
                        controller.pulse(directory / 'controller.pulse', maximum=4096)
                        next_pulse = now + .5
                    before_launch()  # Last exact approval/hash check, still no socket.
                    fresh = monitor.poll((directory / 'cancel.request').exists())
                    if (fresh['fault'] or monitor.last_frame['cpuTemperatureC'] >
                            packet['thermalPolicy']['temperature']['startAtOrBelowC'] or watch.fault):
                        raise download.StageError(fresh['fault'] or watch.fault or 'BASELINE_LOST_BEFORE_START')
                    state['phase'] = 'RUNNING'
                    save()
                    process = launch()
                    watch.process = process
                    state['workerStarted'] = True
                    work_started = now
                    save()
            else:
                if now - work_started >= packet['workSeconds']:
                    raise download.StageError('IMAGE_WORK_DEADLINE')
                if now >= next_pulse:
                    controller.pulse(directory / 'controller.pulse', maximum=4096)
                    next_pulse = now + .5
                age = worker_lease.age() if worker_lease.path.exists() else now - work_started
                if age > packet['workerLeaseSeconds']:
                    raise download.StageError('WORKER_PROGRESS_LOST')
                if process.poll() is not None:
                    if process.returncode != 0:
                        try:
                            error = json.loads(admission.cpu.bounded(directory / 'worker-error.json', 4096))
                            code = error.get('code', '')
                            if isinstance(code, str) and build.guard.re.fullmatch('[A-Z_]{1,80}', code):
                                state['workerFault'] = code
                        except (OSError, ValueError, TypeError):
                            pass
                        raise download.StageError('IMAGE_WORKER_FAILED')
                    result = json.loads(admission.cpu.bounded(directory / 'worker-result.json', 131072))
                    state['result'] = validate(result, packet, synthetic)
                    state['phase'] = 'COMPLETE'
                    break
            sleep(.05)
    except BaseException as error:
        state.update(phase='FAULT', fault=error.code if isinstance(error, download.StageError) else 'IMAGE_SUPERVISOR_ERROR')
        state['errorType'] = type(error).__name__
    finally:
        # Latch in memory and stop before journal I/O: a full disk cannot delay
        # emergency termination. The durable claim/unfinished state denies retry.
        fault_at = time.monotonic()
        if watch is not None and watch.fault_at is not None:
            fault_at = min(fault_at, watch.fault_at)
        if process is not None:
            try:
                (directory / 'cancel.request').touch(exist_ok=True)
            except OSError:
                pass
            try:
                state['stopConfirmed'] = stop_owned(process, max(0, packet['stopSeconds'] - (time.monotonic() - fault_at)))
            except BaseException:
                state['stopConfirmed'] = False
            finally:
                state['workerStopElapsedSeconds'] = time.monotonic() - fault_at
                try:
                    if watch is not None:
                        try:
                            watch.close()
                        except BaseException:
                            state.update(phase='FAULT', fault=state['fault'] or 'MONITOR_WATCH_STOP_UNCONFIRMED')
                finally:
                    try:
                        process.close()  # Kill-on-close on exceptional/unconfirmed stop too.
                    except BaseException:
                        state.update(phase='FAULT', fault=state['fault'] or 'JOB_CLOSE_UNCONFIRMED')
            if not state['stopConfirmed']:
                state.update(phase='FAULT', fault=state['fault'] or 'STOP_UNCONFIRMED')
        else:
            state['stopConfirmed'] = True  # No staging worker was launched.
            if watch is not None:
                try:
                    watch.close()
                except BaseException:
                    state.update(phase='FAULT', fault=state['fault'] or 'MONITOR_WATCH_STOP_UNCONFIRMED')
        if watch is not None and watch.fault:
            state.update(phase='FAULT', fault=state['fault'] or watch.fault)
        try:
            feed.close()
            state['readerStopped'] = True
        except BaseException:
            state.update(phase='FAULT', fault=state['fault'] or 'READER_STOP_UNCONFIRMED')
        if state['phase'] != 'COMPLETE':
            state.pop('result', None)
        # The diagnostic is assembled in memory; persist only AFTER all stopping.
        if monitor is not None and monitor.last_error is not None:
            state['sensorFeedError'] = monitor.last_error
        save()
    return state


def child():
    permit = admission.authorize()
    directory = admission.LIVE
    claim = json.loads(admission.cpu.bounded(directory / 'attempt.json', 4096))
    request = json.loads(admission.cpu.bounded(directory / 'start.json', 4096))
    if (claim.get('reviewSha256') != permit.review_sha256 or claim.get('synthetic') is not False or
            not stage_session_id(claim.get('sessionId')) or request != {
                **claim, 'scope': admission.SCOPE}):
        raise download.StageError('IMAGE_CHILD_CLAIM_INVALID')
    try:
        ordinal = 0
        def headers(summary):
            nonlocal ordinal
            ordinal += 1
            if ordinal > len(permit.packet['image']['layers']) + 1:
                raise download.StageError('AUTH_OBSERVATION_LIMIT')
            download.tools.base.atomic(directory / ('auth-response-' + str(ordinal) + '.json'), summary)
        def source(blobs):
            return download.RegistrySource(blobs, on_auth_headers=headers)
        return pipeline(directory, permit.packet, source, synthetic=False)
    except BaseException as error:
        code = error.code if isinstance(error, download.StageError) else 'IMAGE_WORKER_ERROR'
        download.tools.base.atomic(directory / 'worker-error.json', {'code': code})
        raise


def stage_session_id(value):
    return isinstance(value, str) and build.guard.re.fullmatch('[0-9a-f]{32}', value) is not None


def run():
    permit = admission.authorize()  # Before ANY process, reader, transport or live namespace mutation.
    packet = permit.packet
    if any((admission.LIVE / name).exists() for name in ('attempt.json', 'state.json', 'data')):
        raise ValueError('IMAGE_STAGE_ATTEMPT_ALREADY_CONSUMED')
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('ADMINISTRATOR_CPU_READER_ACCESS_REQUIRED')
    configuration = Path.home() / '.wslconfig'
    if hashlib.sha256(admission.cpu.bounded(configuration, 4096)).hexdigest() != packet['proposedVmEnvelope']['proposalSha256']:
        raise ValueError('APPROVED_WSL_CONFIG_CHANGED')
    build.vm_ready(build.guard.base.Docker(), packet)
    # Small cached read-only fixture, not image transfer/import. Fresh swap proof.
    with contextlib.redirect_stdout(io.StringIO()):
        proof_dir = probe_image_storage.probe()
    proof = json.loads(admission.cpu.bounded(proof_dir / 'result.json', 16384))
    if type(proof.get('guestSwapTotalBytes')) is not int or proof['guestSwapTotalBytes'] != 0:
        raise ValueError('GUEST_SWAP_NOT_DISABLED')
    directory = admission.LIVE
    download.tools.plain(directory)
    with download.tools.base.lock(directory / 'control'):
        if any(p.name != 'control' for p in directory.iterdir()):
            raise ValueError('IMAGE_STAGE_ATTEMPT_ALREADY_CONSUMED')
        download.reserve_disk(directory, download.Limits(packet['budget']['payloadBytes'],
            packet['budget']['namespaceBytes'], packet['budget']['freeReserveBytes'], 1800, 600),
            packet['budget']['namespaceBytes'])
        claim = {'sessionId': uuid.uuid4().hex, 'reviewSha256': permit.review_sha256, 'synthetic': False}
        with (directory / 'attempt.json').open('x', encoding='utf-8') as stream:
            json.dump(claim, stream)
            stream.flush()
            os.fsync(stream.fileno())
        feed = cpu_feed.Feed(cpu_feed.ROOT / uuid.uuid4().hex, source_permit=permit)
        def launch():
            # Immutable handoff: the child never opens mutable state.json while
            # its owner publishes another state on Windows.
            with (directory / 'start.json').open('x', encoding='utf-8') as stream:
                json.dump({**claim, 'scope': admission.SCOPE}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            env = {k: os.environ[k] for k in ('SystemRoot', 'TEMP', 'TMP') if k in os.environ}
            return windows_job.Process([sys.executable, '-B', '-E', '-s', str(Path(__file__).resolve()), '--approved-child'],
                cwd=directory, env=env, memory_bytes=packet['job']['memoryBytes'],
                processes=packet['job']['processes'], single_cpu=True)
        def last_check():
            if admission.authorize() != permit:
                raise ValueError('Image approval changed before start')
        return _execute(directory, packet, feed, launch, synthetic=False, permit=permit, before_launch=last_check)


def cancel():
    directory = admission.LIVE
    download.tools.plain(directory)
    claim = json.loads(admission.cpu.bounded(directory / 'attempt.json', 4096))
    state = json.loads(admission.cpu.bounded(directory / 'state.json', 131072))
    if (state.get('reviewSha256') != claim.get('reviewSha256') or state.get('synthetic') is not False or
            state.get('phase') not in ('WAITING_BASELINE', 'RUNNING')):
        raise ValueError('No active owned image stage; no reset')
    (directory / 'cancel.request').touch(exist_ok=True)
    return {'status': 'CANCELLATION_REQUESTED', 'scope': admission.SCOPE}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-child', action='store_true', required=True)
    parser.parse_args()
    try:
        child()
    except BaseException:
        # Never log bearer tokens, registry/CDN URLs or untrusted exception text.
        raise SystemExit(3)
