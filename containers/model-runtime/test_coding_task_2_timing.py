"""Offline deadline wiring, immutable history and unchanged outer guards."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import coding_task_2_timing as timing
import container_test as base
import container_test_150 as guest
from test_runtime import answer


class TimingTests(unittest.TestCase):
    def test_timeout_history_and_spent_approval_are_verified_without_reset(self):
        proof = timing.timeout_proof(True)
        self.assertFalse(proof['previousAttemptReset'])
        self.assertFalse(proof['previousApprovalReused'])
        with patch.object(timing.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'TIMEOUT_MANIFEST_CHANGED'): timing.timeout_proof()

    def test_only_scoped_guest_changes_default_request_deadline(self):
        self.assertEqual(base.REQUEST_SECONDS, 90)
        fake = SimpleNamespace(REQUEST_SECONDS=90, main=Mock(return_value=0))
        with patch.dict(sys.modules, {'container_test_base':fake}):
            self.assertEqual(guest.main(), 0)
        self.assertEqual(fake.REQUEST_SECONDS, 150)
        fake.main.assert_called_once_with()
        self.assertEqual(base.REQUEST_SECONDS, 90)

    def guest_fixture(self, timeout=False):
        saved = {}
        class FakePath:
            def __init__(self, name): self.name = str(name)
            def __truediv__(self, name): return FakePath(self.name + '/' + name)
            def exists(self): return self.name in ('/input/request.json', '/control/finish.request')
            def stat(self): return SimpleNamespace(st_size=1)
            def read_bytes(self): return json.dumps({**timing.recovery.task.REQUEST}).encode()
            def write_bytes(self, data): saved[self.name] = data
            def rename(self, target): saved[str(target)] = saved.pop(self.name)
            def __str__(self): return self.name
        class Response:
            status = 200
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, maximum): return self.data[:maximum]
        thread = Mock()
        def thread_factory(**kwargs):
            thread.target = kwargs['target']
            return thread
        closed = Mock()
        closed.is_set.side_effect = [False, True]
        closed.wait.return_value = False
        gate = Mock(wraps=base.Leases(100))
        opener = Mock()
        def open_request(request, *, timeout):
            if isinstance(request, str): return Response(b'{}')
            self.assertEqual(timeout, 150)
            thread.target()  # One real lease-check iteration, against fake pulse files.
            if self.timeout_case: raise TimeoutError('offline timeout fixture')
            return Response(json.dumps(answer()).encode())
        self.timeout_case = timeout
        opener.open.side_effect = open_request
        process = Mock()
        process.poll.return_value = None
        with patch.object(base, 'REQUEST_SECONDS', 150), patch.object(base, 'Path', FakePath), \
             patch.object(base, 'qualify_environment', return_value={'offline':True}), \
             patch.object(base.subprocess, 'Popen', return_value=process) as popen, \
             patch.object(base.threading, 'Thread', side_effect=thread_factory), \
             patch.object(base.threading, 'Event', return_value=closed), \
             patch.object(base, 'Leases', return_value=gate), \
             patch.object(base.time, 'monotonic', return_value=100), \
             patch.object(base.signal, 'signal'), patch.object(base, 'shutdown') as shutdown, \
             patch.object(base.urllib.request, 'build_opener', return_value=opener):
            code = base.main()
        self.assertEqual(gate.check.call_args.args[2], 250)
        self.assertEqual([call.kwargs['timeout'] for call in opener.open.call_args_list], [.5, 150])
        popen.assert_called_once()
        shutdown.assert_called_once_with(process)
        result = json.loads(saved['/work/result.json'])
        self.assertEqual(result['requestsSubmitted'], 1)
        self.assertEqual(base.REQUEST_SECONDS, 90)
        return code, result

    def test_socket_and_independent_request_lease_share_150_second_deadline(self):
        code, result = self.guest_fixture()
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'REAL_STRATA_API_ANSWER')

    def test_request_timeout_faults_without_a_second_request(self):
        code, result = self.guest_fixture(timeout=True)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'FAULT')
        self.assertEqual(result['errorType'], 'TimeoutError')

    def test_longer_request_cannot_extend_container_or_lease_bounds(self):
        gate = base.Leases(0)
        gate.check(299, {'controller.pulse':1,'guard.pulse':1}, request_deadline=449)
        with self.assertRaisesRegex(TimeoutError, 'CONTAINER_DEADLINE'):
            gate.check(300, {'controller.pulse':2,'guard.pulse':2}, request_deadline=449)
        gate = base.Leases(0)
        gate.check(0, {'controller.pulse':1,'guard.pulse':1}, request_deadline=150)
        with self.assertRaisesRegex(TimeoutError, 'HOST_LEASE_EXPIRED'):
            gate.check(2.6, {'controller.pulse':1,'guard.pulse':1}, request_deadline=150)

    def test_only_request_deadline_delta_and_pinned_guest_inputs_are_allowed(self):
        root = timing.REPO / '.runtime/timing-offline-tests'
        root.mkdir(exist_ok=True)
        root.resolve().relative_to(timing.REPO.resolve())
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            Path(temporary).resolve().relative_to(root.resolve())
            inputs = Path(temporary) / 'input'
            inputs.mkdir()
            for name, source in timing.SCRIPTS.items():
                (inputs/name).write_bytes((timing.HERE/source).read_bytes().replace(b'\r\n', b'\n'))
            (inputs/'request.json').write_text('{}')
            (inputs/'strata.json').write_text('{}')
            packet = copy.deepcopy(timing.p.read(timing.TIMEOUT/'review.json', 131072))
            packet.update(packageDirectory=temporary, requestTimingChange=dict(timing.TIMING),
                          inputSha256={p.name:timing.p.build.tools.sha(p) for p in inputs.iterdir()})
            original = copy.deepcopy(packet)
            with patch.object(timing.recovery.task.coding, 'same_limits'), \
                 patch.object(timing.p, 'INPUT_SCRIPTS', dict(timing.SCRIPTS)):
                timing.same_limits(packet)
                self.assertEqual(packet, original)
                for area, key, value in [('requestTimingChange','hardRequestDeadlineSeconds',151),
                        ('requestTimingChange','to',80), ('policy','modelSeconds',301),
                        ('policy','outerSeconds',411), ('policy','cpuStopC',98),
                        ('request','max_tokens',33), ('configuration','engine_silence_s',80)]:
                    with self.subTest(area=area, key=key):
                        changed = copy.deepcopy(packet)
                        changed[area][key] = value
                        with self.assertRaises(ValueError): timing.same_limits(changed)
                (inputs/'container_test.py').write_bytes(b'other code')
                with self.assertRaisesRegex(ValueError, 'TIMED_GUEST_INPUT_CHANGED'): timing.same_limits(packet)

    def test_fresh_scope_refuses_missing_and_all_spent_approvals_before_docker(self):
        script = '''
import sys
from unittest.mock import patch
import coding_task_2_timing as t
t.activate()
assert t.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==150
assert t.p.config()['engine_silence_s']==75
assert t.p.safety.POLICY['modelSeconds']==300 and t.p.safety.POLICY['outerSeconds']==410
assert t.p.INPUT_SCRIPTS==t.SCRIPTS
assert t.p.APPROVAL.name=='coding-task-2-timing-approval.json'
assert t.p.LIVE==t.LIVE and t.recovery.task.coding.WORKER==t.WORKER
with patch.object(t.p,'APPROVAL',t.ROOT/'deliberately-missing.json'), \\
     patch.object(t.recovery.task.coding,'WORKER',t.ROOT/'deliberately-missing-worker'), \\
     patch.object(t.recovery.task.coding.first_api.guard.base,'Docker') as docker:
    try:t.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(t.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-timing']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    docker.assert_not_called()
old=t.p.read(t.TIMEOUT/'review.json',131072)
for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json']:
    with patch.object(t.p,'APPROVAL',t.HERE/name), patch.object(t.p,'review',return_value=('b'*64,old)):
        try:t.p.authorize()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
        else:raise AssertionError('spent approval reused')
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=timing.HERE,
                       capture_output=True, check=True, timeout=20)


if __name__ == '__main__': unittest.main()
