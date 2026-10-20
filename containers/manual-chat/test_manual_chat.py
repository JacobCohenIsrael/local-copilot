"""Offline only: fake APIs/Docker/telemetry; never exercise real readers."""
import base64
from contextlib import ExitStack, contextmanager
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import plan
import protocol as p
import manual_supervisor as host
import bridge
import wrapper
import chat


@contextmanager
def scratch():
    root = plan.REPO / '.runtime/manual-chat-offline-tests'
    root.mkdir(parents=True, exist_ok=True)
    # Keep offline fixtures, including failures, in this task's own namespace.
    yield tempfile.mkdtemp(dir=root)


def line(text='', finish=None, usage=None, **extra):
    value = dict(choices=[dict(delta={'content': text}, finish_reason=finish)], **extra)
    if usage is not None:
        value['usage'] = usage
    return b'data: ' + json.dumps(value).encode() + b'\n'


class ProtocolTests(unittest.TestCase):
    def test_unicode_request_and_no_tools(self):
        r = p.request([dict(role='user', content='שלום 🙂')])
        self.assertEqual(p.validate_request(r), r)
        for key, value in [('tools', []), ('temperature', .5), ('stream', False), ('model', 'other')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.validate_request({**r, key: value})

    def test_output_and_message_bounds(self):
        for output in [True, 0, 4097, -1, 1.5]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                p.request([dict(role='user', content='x')], output)
        for messages in [[], [dict(role='system', content='x')], [dict(role='user', content='')],
                         [dict(role='user', content=['image'])], [dict(role='user', content='x' * 8193)]]:
            with self.subTest(messages=str(messages)[:30]), self.assertRaises(ValueError):
                p.request(messages)

    def test_exact_token_budget_includes_template_history(self):
        p.admit_prompt([1] * 512, 4096)
        for size in [0, 513, 16384]:
            with self.subTest(size=size), self.assertRaises(ValueError):
                p.admit_prompt([1] * size, 4096)

    def test_stream_text_prompt_progress_and_finish(self):
        s = p.Stream(64)
        s.feed(b': still waiting\n')
        self.assertIsNone(s.progress)
        s.feed(line(prompt_progress=dict(processed=16, total=23)))
        self.assertEqual(s.progress, dict(processed=16, total=23))
        s.feed(line('שלום'))
        s.feed(line(' 🙂'))
        s.feed(line(finish='stop', usage=dict(prompt_tokens=23, completion_tokens=3, total_tokens=26)))
        s.feed(b'data: [DONE]\n')
        self.assertEqual(s.result()['text'], 'שלום 🙂')
        self.assertFalse(s.result()['truncated'])

    def test_length_is_visible_not_misreported_complete(self):
        s = p.Stream(1)
        s.feed(line('hello', 'length', dict(prompt_tokens=1, completion_tokens=1, total_tokens=2)))
        s.feed(b'data: [DONE]\n')
        self.assertTrue(s.result()['truncated'])

    def test_broken_streams_fail_closed(self):
        for raw in [line('partial'), b'data: [DONE]\n', b'data: {"error":"bad"}\n',
                    line('a', 'stop', dict(prompt_tokens=513, completion_tokens=1, total_tokens=514)),
                    line('a', 'stop', dict(prompt_tokens=1, completion_tokens=2, total_tokens=3))]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                s = p.Stream(1)
                s.feed(raw)
                s.result()

    def test_stream_byte_and_progress_limits(self):
        for raw in [b'data:' + b'x' * 65536, line(prompt_progress=dict(processed=99, total=23))]:
            with self.assertRaises(ValueError):
                p.Stream(64).feed(raw)
        s = p.Stream(64)
        s.bytes = p.LIMITS['streamBytes']
        with self.assertRaises(ValueError):
            s.feed(b'\n')

    def test_terminal_controls_removed(self):
        self.assertNotIn('\x1b', p.terminal('\x1b]52;secret\x07שלום\n'))
        self.assertIn('שלום\n', p.terminal('\x1b]52;secret\x07שלום\n'))

    def test_commands_and_history(self):
        history = [dict(role='user', content='hello'), dict(role='assistant', content='hi')]
        self.assertEqual(host.commands('/new', history, 64)[1], [])
        self.assertEqual(host.commands('/stop', history, 64)[0], 'stop')
        self.assertEqual(host.commands('/tokens 4096', history, 64)[2], 4096)
        self.assertEqual(host.commands('next', history, 64)[3]['messages'][:-1], history)
        for command in ['/tokens -1', '/tokens nope', '/unknown']:
            with self.assertRaises(ValueError):
                host.commands(command, history, 64)


class WrapperTests(unittest.TestCase):
    def service(self, count):
        class Service:
            def encode_prompt(self, *args):
                return [1] * count
            def prepare(self, *args):
                return [1] * count, False, args[3]
        fake = types.SimpleNamespace(Service=Service)
        wrapper.install(fake)
        return Service()

    def test_admission_before_original_prepare_or_inference(self):
        self.assertEqual(len(self.service(512).prepare([], [], {'enable_thinking': False}, 4096)[0]), 512)
        with self.assertRaisesRegex(ValueError, 'TOKEN_BUDGET'):
            self.service(513).prepare([], [], {'enable_thinking': False}, 4096)

    def test_reject_tools_and_reasoning(self):
        for tools, kwargs in [(['tool'], {'enable_thinking': False}), ([], {})]:
            with self.assertRaises(ValueError):
                self.service(12).prepare([], tools, kwargs, 64)


class MailboxTests(unittest.TestCase):
    def test_single_delivery_and_budget(self):
        with scratch() as td, patch.object(bridge, 'WORK', Path(td)):
            folder = Path(td)
            (folder / 'chat.json').write_text('{"phase":"READY","sequence":0}')
            r = p.request([dict(role='user', content='test')], 64)
            data = base64.b64encode(json.dumps(r).encode()).decode()
            bridge.submit(1, data)
            self.assertEqual(json.loads((folder / 'request-1.json').read_text()), r)
            with self.assertRaises(FileExistsError):
                bridge.submit(1, data)
            with self.assertRaises(ValueError):
                bridge.submit(2, data)
            (folder / 'chat.json').write_text('{"phase":"GENERATING","sequence":0}')
            with self.assertRaises(ValueError):
                bridge.submit(1, data)


class ReviewTests(unittest.TestCase):
    def test_frozen_json_contract_roundtrip_and_staged_input_mutation(self):
        with scratch() as td, patch.object(plan, 'ROOT', Path(td) / 'review'), \
                patch.object(plan, 'LIVE', Path(td) / 'not-started'), patch.object(plan, 'verify_inputs'):
            prepared = plan.prepare()
            digest, packet = plan.review()
            self.assertEqual(prepared['reviewSha256'], digest)
            self.assertFalse(packet['modelLaunchEnabled'])
            inputs = Path(packet['packageDirectory']) / 'input'
            (inputs / 'protocol.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'INPUT_CHANGED'):
                plan.review()


class CliTests(unittest.TestCase):
    def test_missing_approval_is_clear_without_traceback_or_live_access(self):
        with patch.object(chat, 'main', side_effect=ValueError('MANUAL_CHAT_NOT_APPROVED')), \
                patch('sys.stderr', new_callable=io.StringIO) as output, \
                patch.object(host.guard.base, 'Docker') as docker:
            self.assertEqual(chat.cli(), 2)
            self.assertIn('No Docker or model operation was started', output.getvalue())
            self.assertNotIn('Traceback', output.getvalue())
            docker.assert_not_called()

    def test_other_errors_keep_their_diagnostics(self):
        with patch.object(chat, 'main', side_effect=ValueError('OTHER_FAILURE')):
            with self.assertRaisesRegex(ValueError, 'OTHER_FAILURE'):
                chat.cli()


class SafetyIntegrationTests(unittest.TestCase):
    def test_manual_approval_cannot_reuse_old_scope_or_enable_worker(self):
        packet = dict(sourceLimitation='source limitation', limitations=['known limitation'])
        decision = dict(version=1, status='owner-approved-one-manual-chat-session', scope=plan.SCOPE,
            reviewSha256='a' * 64, maximumAttempts=1, acceptPolicySha256=plan.base.sha(plan.POLICY),
            acceptLimits=p.LIMITS, acceptSourceLimitation=packet['sourceLimitation'],
            acceptLimitations=packet['limitations'], modelLaunchEnabled=True,
            workerLaunchEnabled=False, synthetic=False, ownerMessage='offline synthetic fixture only')
        with scratch() as td, patch.object(plan, 'APPROVAL', Path(td) / 'approval.json'), \
                patch.object(plan, 'review', return_value=('a' * 64, packet)):
            plan.APPROVAL.write_text(json.dumps(decision))
            self.assertEqual(plan.authorize().review_sha256, 'a' * 64)
            for changes in [dict(scope='old-coding-scope'), dict(workerLaunchEnabled=True),
                            dict(acceptLimits={**p.LIMITS, 'requestSeconds': 900}),
                            dict(maximumAttempts=2), dict(version=True), dict(ownerMessage='')]:
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    plan.APPROVAL.write_text(json.dumps({**decision, **changes}))
                    plan.authorize()

    def test_run_without_approval_has_no_live_access(self):
        with scratch() as td, patch.object(plan, 'APPROVAL', Path(td) / 'absent'), \
                patch.object(host.guard.base, 'Docker') as docker, patch.object(host.safety, 'snapshot') as gpu, \
                patch.object(host.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, 'NOT_APPROVED'):
                host.run()
            docker.assert_not_called()
            gpu.assert_not_called()
            process.assert_not_called()

    def test_policy_exactly_preserves_requested_emergency_stops(self):
        self.assertEqual({k: plan.POLICY[k] for k in ['cpuStopC', 'gpuStopC', 'gpuStopPowerW',
                         'gpuStopVramMiB', 'ramStopMiB']}, dict(cpuStopC=97, gpuStopC=75,
                         gpuStopPowerW=100, gpuStopVramMiB=14336, ramStopMiB=30720))
        self.assertTrue(plan.POLICY['startupTargetsWarningsOnly'])
        self.assertEqual((plan.POLICY['modelSeconds'], plan.POLICY['outerSeconds']), (300, 410))

    def test_existing_gate_hot_cpu_and_ram_latch(self):
        def cpu(temp=95):
            return dict(version=1, synthetic=False, validatedCpuSensor=False, sequence=1,
                source='ASUS DSTS 0x00120094', cpuTemperatureC=temp, cpuThermalThrottling=None,
                recordedAtUnix=100, querySeconds=.2, readerRemainingSeconds=480)
        def gpu(ram=20000):
            return dict(gpuUuid=host.safety.GPU_UUID, gpuTemperatureC=65, gpuPowerW=50,
                vramUsedMiB=5000, vramTotalMiB=16384, ramUsedMiB=ram, ramTotalMiB=32768,
                acConnected=True, gpuThermalThrottling=False, recordedAtUnix=100, querySeconds=.1)
        for frame, sample, code in [(cpu(97), gpu(), 'CPU_HOT'), (cpu(), gpu(30720), 'HOST_RAM_HIGH')]:
            gate = host.safety.Gate()
            gate.observe(frame, sample, now=0, unix=100, controller_age=0)
            self.assertEqual(gate.fault, code)
            gate.observe(None, gpu(), now=.1, unix=100.1, controller_age=0)
            self.assertEqual(gate.fault, code)

    def test_existing_guest_leases_and_absolute_deadlines(self):
        from container_test import Leases
        for now, sizes, deadline, code in [(3, {'controller.pulse': 1, 'guard.pulse': 1}, None, 'LEASE_EXPIRED'),
                                           (150, {'controller.pulse': 2, 'guard.pulse': 2}, 150, 'REQUEST_DEADLINE'),
                                           (300, {'controller.pulse': 2, 'guard.pulse': 2}, None, 'CONTAINER_DEADLINE')]:
            lease = Leases(0)
            lease.check(0, {'controller.pulse': 1, 'guard.pulse': 1})
            with self.assertRaisesRegex(TimeoutError, code):
                lease.check(now, sizes, deadline)

    def test_stop_does_not_require_new_authorization_or_global_docker(self):
        with scratch() as td, ExitStack() as stack:
            live = Path(td)
            folder = live / 'sessions' / ('a' * 32)
            folder.mkdir(parents=True)
            (live / 'control').mkdir()
            stack.enter_context(patch.object(plan, 'LIVE', live))
            stack.enter_context(patch.object(host, 'directory', return_value=folder))
            stack.enter_context(patch.object(host, 'claim', return_value=dict(reviewSha256='b' * 64)))
            stack.enter_context(patch.object(plan, 'read', side_effect=[{'containerId': 'c' * 64}, {}]))
            stack.enter_context(patch.object(host.existing, 'target', return_value='owned'))
            stopped = stack.enter_context(patch.object(host.existing, 'stop', return_value={'stopConfirmed': True}))
            stack.enter_context(patch.object(host.guard.base, 'Docker', return_value='docker'))
            authority = stack.enter_context(patch.object(plan, 'authorize', side_effect=AssertionError('not needed')))
            self.assertTrue(host.stop()['stopConfirmed'])
            stopped.assert_called_once_with('docker', 'owned')
            authority.assert_not_called()
            self.assertTrue((live / 'stop.request').exists())


class ConnectedSimulationTests(unittest.TestCase):
    """Drive the real controller loop; every external dependency is a fake."""
    def run_controller(self, mode='answer'):
        with scratch() as td, ExitStack() as stack:
            root = Path(td)
            live = root / 'session'
            now = [0.0]
            submitted = []
            inbox = []
            docker = Mock()
            watchdog = Mock(returncode=None, pid=123)
            watchdog.poll.side_effect = lambda: watchdog.returncode
            watchdog.wait.side_effect = lambda timeout: setattr(watchdog, 'returncode', 0)
            owned = Mock(container_id='c' * 64)
            stopped = dict(Id='c' * 64, State=dict(Running=False, Pid=0, ExitCode=0))
            owned.inspect.return_value = stopped
            owned.stop_matcher.return_value = stopped
            started = [False]

            def thread(*, target, args, daemon):
                inbox.append(args[0])
                return types.SimpleNamespace(start=lambda: None)

            def state():
                return dict(phase='STOPPED' if (live / 'stop.request').exists() else
                            'RUNNING' if started[0] else 'ARMED', fault=None,
                            grantedAtMonotonic=0, readerExited=True)

            def call(*args, **kwargs):
                if args[0] == 'create':
                    return 'c' * 64
                if args[0] == 'start':
                    started[0] = True
                    return ''
                if args[0] == 'exec':
                    operation = args[7]
                    if operation == 'submit':
                        submitted.append(args)
                        if mode == 'delivery-error':
                            raise subprocess.CalledProcessError(1, 'fake-delivery')
                        return ''
                    if not submitted:
                        inbox[0].put('hello')  # Person types only once READY.
                        return json.dumps(dict(phase='READY', sequence=0, text=''))
                    if mode == 'guest-fault':
                        return json.dumps(dict(phase='FAULT', sequence=1, text='partial', error='REQUEST_DEADLINE'))
                    inbox[0].put('/stop')
                    return json.dumps(dict(phase='READY', sequence=1, text='hello back', finish='stop',
                                           usage=dict(prompt_tokens=12, completion_tokens=2, total_tokens=14)))
                raise AssertionError(args)

            docker.call.side_effect = call
            packet = dict(createArgs=['create'], limits=p.LIMITS)
            permit = types.SimpleNamespace(packet=packet, review_sha256='b' * 64, approval_sha256='a' * 64)
            capacity = root / 'capacity'
            capacity.mkdir()
            (capacity / 'result.json').write_text('{"guestSwapTotalBytes":0}')
            fake_probe = types.SimpleNamespace(probe=lambda: capacity)
            stack.enter_context(patch.dict('sys.modules', probe_image_storage=fake_probe))
            stack.enter_context(patch.object(plan, 'LIVE', live))
            stack.enter_context(patch.object(plan, 'authorize', return_value=permit))
            stack.enter_context(patch.object(plan, 'verify_inputs'))
            stack.enter_context(patch.object(host, 'latest', side_effect=state))
            stack.enter_context(patch.object(host, 'bridge', side_effect=lambda d, o, *a: call('exec', '--user', 'uid', 'id', 'python', '-B', 'bridge', *a)))
            stack.enter_context(patch.object(host.guard.base, 'Docker', return_value=docker))
            stack.enter_context(patch.object(host.existing, 'target', return_value=owned))
            stop_call = stack.enter_context(patch.object(host.existing, 'stop', return_value={'stopConfirmed': True}))
            stack.enter_context(patch.object(host.existing.build_diagnostics, 'collect'))
            stack.enter_context(patch.object(host.safety, 'snapshot', return_value={'driver': '617.14'}))
            stack.enter_context(patch.object(host.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=True))
            stack.enter_context(patch.object(host.threading, 'Thread', side_effect=thread))
            stack.enter_context(patch.object(host.subprocess, 'Popen', return_value=watchdog))
            stack.enter_context(patch.object(host.time, 'monotonic', side_effect=lambda: now[0]))
            stack.enter_context(patch.object(host.time, 'sleep', side_effect=lambda n: now.__setitem__(0, now[0] + n)))
            stack.enter_context(patch.object(host.control, 'Pulse', return_value=types.SimpleNamespace(
                path=types.SimpleNamespace(exists=lambda: True), changed=True, age=lambda: 0)))
            for name in ('image_ready', 'vm_ready'):
                fake = stack.enter_context(patch.object(plan.base.build, name))
                if name == 'image_ready' and mode == 'preflight-error':
                    fake.side_effect = ValueError('IMAGE_PREFLIGHT_FAILURE')
            stack.enter_context(patch.object(plan.base.build.image_plan, 'metadata', return_value={}))
            stack.enter_context(patch.object(plan.base.build.image_plan, 'storage_budget', return_value={}))
            stack.enter_context(patch.object(plan.base.build.image_plan, 'capacity', return_value={'withinProposedBudgetAtProbe': True}))
            output = stack.enter_context(patch('sys.stdout', new_callable=io.StringIO))
            if mode == 'guest-fault':
                # Simulate the independent watchdog's fault reaction to the marker.
                def fault_state():
                    if (live / 'api.failure').exists():
                        return dict(phase='FAULT', fault={'code': 'MANUAL_API_FAILED'}, readerExited=True)
                    return state()
                host.latest.side_effect = fault_state
            result = host.run()
            self.assertEqual(stop_call.called, mode != 'preflight-error')
            self.assertEqual(len(submitted), 0 if mode == 'preflight-error' else 1)
            self.assertTrue((live / 'attempt.json').exists())
            self.assertFalse(any(c.args[0] in ('restart', 'rm', 'system') for c in docker.call.call_args_list))
            return result, output.getvalue()

    def test_one_manual_prompt_reply_and_confirmed_owned_stop(self):
        result, output = self.run_controller()
        self.assertEqual(result['status'], 'MANUAL_SESSION_STOPPED_CONFIRMED')
        self.assertIn('hello back', output)
        self.assertTrue(result['independentStopConfirmed'])

    def test_uncertain_delivery_ends_session_without_resend(self):
        result, _ = self.run_controller('delivery-error')
        self.assertEqual(result['status'], 'FAULT')
        self.assertTrue(result['stopConfirmed'])

    def test_live_preflight_failure_consumes_the_operation_without_model_start(self):
        result, _ = self.run_controller('preflight-error')
        self.assertEqual(result['status'], 'FAULT')
        self.assertEqual(result['error']['reason'], 'IMAGE_PREFLIGHT_FAILURE')

    def test_api_timeout_partial_reply_keeps_fault_and_stops(self):
        result, output = self.run_controller('guest-fault')
        self.assertEqual(result['status'], 'FAULT')
        self.assertEqual(result['guardState']['fault']['code'], 'MANUAL_API_FAILED')
        self.assertIn('partial', output)


class WatchdogSimulationTests(unittest.TestCase):
    def watch(self, mode):
        with scratch() as td, ExitStack() as stack:
            live = Path(td)
            folder = live / 'sessions' / ('a' * 32)
            folder.mkdir(parents=True)
            (live / 'control').mkdir()
            (live / 'control/controller.pulse').write_bytes(b'.')
            now, seq = [0.0], [0]
            owned = Mock(container_id='c' * 64)
            owned.inspect.return_value = {'State': {'Running': False, 'Status': 'created'}}
            feed = Mock(process=types.SimpleNamespace(pid=123, returncode=None))
            feed.close.side_effect = lambda: setattr(feed.process, 'returncode', 0)

            def cpu():
                seq[0] += 1
                return dict(version=1, synthetic=False, validatedCpuSensor=False, sequence=seq[0],
                    source='ASUS DSTS 0x00120094', cpuTemperatureC=97 if mode == 'hot' else 95,
                    cpuThermalThrottling=None, recordedAtUnix=1000 + now[0], querySeconds=.02,
                    readerRemainingSeconds=480)

            def gpu():
                return dict(gpuUuid=host.safety.GPU_UUID, gpuTemperatureC=65, gpuPowerW=50,
                    vramUsedMiB=5000, vramTotalMiB=16384, ramUsedMiB=20000, ramTotalMiB=32768,
                    acConnected=True, gpuThermalThrottling=False, recordedAtUnix=1000 + now[0], querySeconds=.1)

            def sleep(n):
                now[0] += n
                state = host.latest()
                if state and state['phase'] == 'ARMED':
                    (live / 'stop.request').touch()

            feed.poll.side_effect = cpu
            permit = types.SimpleNamespace(packet={}, review_sha256='b' * 64)
            stack.enter_context(patch.object(plan, 'LIVE', live))
            stack.enter_context(patch.object(plan, 'authorize', return_value=permit))
            stack.enter_context(patch.object(host, 'claim', return_value={'reviewSha256': 'b' * 64, 'sessionId': 'a' * 32}))
            stack.enter_context(patch.object(host, 'directory', return_value=folder))
            stack.enter_context(patch.object(plan, 'read', return_value={'containerId': 'c' * 64, 'readerDirectory': str(live / 'reader')}))
            stack.enter_context(patch.object(host.existing, 'target', return_value=owned))
            stopper = stack.enter_context(patch.object(host.existing, 'stop', return_value={'stopConfirmed': True}))
            stack.enter_context(patch.object(host.guard.base, 'Docker', return_value=Mock()))
            stack.enter_context(patch.object(host.cpu_feed, 'Feed', return_value=feed))
            stack.enter_context(patch.object(host.safety, 'snapshot', side_effect=gpu))
            stack.enter_context(patch.object(host.time, 'monotonic', side_effect=lambda: now[0]))
            stack.enter_context(patch.object(host.time, 'time', side_effect=lambda: 1000 + now[0]))
            stack.enter_context(patch.object(host.time, 'sleep', side_effect=sleep))
            stack.enter_context(patch.object(host.control, 'Pulse', return_value=types.SimpleNamespace(age=lambda: 3 if mode == 'lease' else 0)))
            host.watch()
            state = host.latest()
            feed.close.assert_called_once()
            self.assertTrue(stopper.called)
            self.assertTrue(state['readerExited'])
            return state

    def test_hot_reading_latches_before_start_and_stops(self):
        state = self.watch('hot')
        self.assertEqual(state['phase'], 'FAULT')
        self.assertEqual(state['fault']['code'], 'CPU_HOT')

    def test_controller_lease_expiry_stops_and_latches(self):
        self.assertEqual(self.watch('lease')['fault']['code'], 'CONTROLLER_LEASE_EXPIRED')

    def test_advisory_exceedances_allow_valid_baseline_then_explicit_stop(self):
        state = self.watch('valid')
        self.assertEqual(state['phase'], 'STOPPED')
        self.assertEqual(state['startupWarnings']['cpuTemperatureC']['observed'], 95)
        self.assertIsNone(state['fault'])


if __name__ == '__main__':
    unittest.main()
