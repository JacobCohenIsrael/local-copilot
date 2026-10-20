"""Offline RAM accounting, one-shot readiness and consumed-approval containment."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import coding_task_2_ram as scope
import host_ram_readiness as readiness
from test_runtime import cpu


def frame(used=18000, **changes):
    return {'source': readiness.SOURCE, 'synthetic': False, 'ramUsedMiB': used,
            'ramTotalMiB': 32388.67578125, 'recordedAtUnix': 100, 'querySeconds': .01, **changes}


class RamTests(unittest.TestCase):
    def test_saved_crossing_reproduces_existing_emergency_without_attribution(self):
        result = scope.p.read(scope.REJECTED / 'execution-result.json', 131072)
        manifest = scope.p.read(scope.REJECTED / 'execution-preservation.json', 1048576)
        attempt = Path(manifest['attempt']['directory'])
        claim = scope.p.read(attempt / 'attempt.json')
        saved = sorted((attempt / 'sessions' / claim['sessionId']).glob('gpu-*.json'))
        last = scope.p.read(saved[-1])
        gate = scope.p.safety.Gate()
        self.assertFalse(gate.observe(cpu(stamp=last['recordedAtUnix'], cpuTemperatureC=96), last,
                                     now=0, unix=last['recordedAtUnix'], controller_age=0))
        self.assertEqual(gate.fault, 'HOST_RAM_HIGH')
        self.assertEqual(last['ramUsedMiB'], 29090.76953125)
        self.assertEqual(result['modelState']['fault']['code'], gate.fault)

    def test_readiness_boundary_reserves_ten_gib_below_unchanged_stop(self):
        condition = readiness.CONDITION
        self.assertEqual(condition['emergencyStopMiB'], scope.p.safety.POLICY['ramStopMiB'])
        self.assertEqual(condition['maximumHostUsedMiB'] + condition['requiredHeadroomToEmergencyMiB'], 28672)
        self.assertTrue(readiness.evaluate(frame(18432), unix=100)['ready'])
        self.assertFalse(readiness.evaluate(frame(18432.01), unix=100)['ready'])
        self.assertFalse(readiness.evaluate(frame(24921.6015625), unix=100)['ready'])
        self.assertTrue(scope.p.safety.POLICY['startupTargetsWarningsOnly'])

    def test_invalid_stale_future_and_slow_frames_cannot_admit(self):
        for changes in ({'ramUsedMiB': float('nan')}, {'ramUsedMiB': True}, {'ramUsedMiB': -1},
                        {'ramUsedMiB': 40000}, {'querySeconds': 1.01}, {'recordedAtUnix': 97},
                        {'recordedAtUnix': 101}, {'synthetic': True}, {'source': 'fixture'}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'READINESS_INVALID_OR_STALE'):
                readiness.evaluate(frame(**changes), unix=100)

    def test_read_helper_timeout_kills_reaps_and_preserves_pid_without_retry(self):
        root = scope.REPO / '.runtime/ram-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            child = Mock(pid=123, returncode=-9)
            child.communicate.side_effect = subprocess.TimeoutExpired('fake', 1.5)
            child.poll.side_effect = [None, -9]
            with patch.object(readiness.subprocess, 'Popen', return_value=child) as popen:
                with self.assertRaises(subprocess.TimeoutExpired): readiness.read_once(Path(temporary))
            popen.assert_called_once()
            child.kill.assert_called_once()
            child.wait.assert_called_once_with(timeout=1)
            self.assertEqual(json.loads((Path(temporary) / 'query-process.json').read_text())['pid'], 123)
            self.assertTrue(json.loads((Path(temporary) / 'query-exit.json').read_text())['confirmedExited'])

    def test_low_readiness_consumes_scope_before_worker_and_never_retries(self):
        self.exercise_run(used=24921)

    def test_read_error_consumes_scope_before_worker_and_never_retries(self):
        self.exercise_run(error=TimeoutError('offline helper timeout'))

    def test_ready_frame_enters_existing_coding_runner_once(self):
        self.exercise_run(used=18000)

    def exercise_run(self, used=18000, error=None):
        root = scope.REPO / '.runtime/ram-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            directory = Path(temporary)
            permit = SimpleNamespace(review_sha256='b' * 64, approval_sha256='c' * 64)
            with patch.object(scope, 'activate'), patch.object(scope, 'RAM_GATE', directory / 'readiness'), \
                 patch.object(scope, 'WORKER', directory / 'worker'), patch.object(scope, 'LIVE', directory / 'model'), \
                 patch.object(scope, '_owner_authorize', Mock(return_value=permit), create=True), \
                 patch.object(scope.time, 'time', return_value=100), \
                 patch.object(readiness, 'read_once', return_value=frame(used), side_effect=error) as read, \
                 patch.object(scope.task.coding, 'run', return_value={'status': 'OFFLINE_CODING_STUB'}) as run:
                if error or used > 18432:
                    with self.assertRaisesRegex(ValueError, 'TASK_HOST_RAM_HEADROOM_NOT_READY'): scope.run()
                    run.assert_not_called()
                else:
                    self.assertEqual(scope.run()['status'], 'OFFLINE_CODING_STUB')
                    run.assert_called_once()
                read.assert_called_once()
                result = json.loads((directory / 'readiness/result.json').read_text())
                self.assertTrue(result['operationApprovalConsumed'])
                self.assertFalse(result['automaticRetry'])
                with self.assertRaisesRegex(ValueError, 'RAM_SCOPE_ATTEMPT_CONSUMED'): scope.run()
                read.assert_called_once()

    def test_full_ram_fault_inventory_and_spent_approval_stay_immutable(self):
        proof = scope.ram_fault_proof(True)
        self.assertFalse(proof['previousAttemptReset'])
        self.assertFalse(proof['previousApprovalReused'])
        with patch.object(scope.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'REJECTED_MANIFEST_CHANGED'): scope.ram_fault_proof()

    def test_new_condition_is_bound_and_no_existing_limit_request_or_config_changes(self):
        base = scope.p.read(scope.REJECTED / 'review.json', 131072)
        root = scope.REPO / '.runtime/ram-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs = Path(temporary) / 'input'
            inputs.mkdir()
            for path in (Path(base['packageDirectory']) / 'input').iterdir():
                (inputs / path.name).write_bytes(path.read_bytes())
            packet = {**base, 'packageDirectory': temporary, 'hostRamReadiness': dict(readiness.CONDITION)}
            with patch.object(scope.p, 'INPUT_SCRIPTS', dict(scope.timing.SCRIPTS)), \
                 patch.object(scope.task, 'WORKER_HELPERS', dict(scope.HELPERS)), patch.object(scope.task, 'check_task'):
                scope.same_limits(packet)
                for area, key, value in [('hostRamReadiness', 'maximumHostUsedMiB', 18433),
                        ('policy', 'ramStopMiB', 28673), ('policy', 'cpuStopC', 98),
                        ('policy', 'startupTargetsWarningsOnly', False),
                        ('requestTimingChange', 'hardRequestDeadlineSeconds', 151),
                        ('configuration', 'engine_silence_s', 76), ('request', 'max_tokens', 33),
                        ('request', 'messages', []), ('codingTask', 'modelCalls', 2)]:
                    changed = copy.deepcopy(packet)
                    changed[area][key] = value
                    with self.subTest(area=area, key=key), self.assertRaises(ValueError): scope.same_limits(changed)

    def test_missing_and_spent_decisions_refuse_before_any_readiness_or_docker_access(self):
        script = '''
import sys
from unittest.mock import patch
import coding_task_2_ram as s
s.activate()
assert s.p.APPROVAL.name=='coding-task-2-ram-approval.json'
assert s.p.config()['engine_silence_s']==75
assert s.p.REQUEST==s.prior.REQUEST
assert s.p.safety.POLICY['startupTargetsWarningsOnly'] is True
with patch.object(s.readiness,'read_once') as read, patch.object(s.task.coding.first_api.guard.base,'Docker') as docker:
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-ram']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    read.assert_not_called();docker.assert_not_called()
for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json']:
    with patch.object(s.p,'APPROVAL',s.HERE/name), patch.object(s.p,'review',return_value=('b'*64,{})):
        try:s._owner_authorize()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
        else:raise AssertionError('spent approval reused')
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=scope.HERE,
                       capture_output=True, check=True, timeout=20)

    def test_extra_owner_acceptance_and_complete_readiness_receipts_are_required(self):
        script = '''
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import coding_task_2_ram as s
s.prior.activate()
permit=SimpleNamespace(review_sha256='b'*64,approval_sha256='c'*64)
root=s.REPO/'.runtime/ram-offline-tests';root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root) as temporary, patch.object(s.p,'authorize',return_value=permit):
    s.activate()
    directory=Path(temporary);decision=directory/'decision.json'
    with patch.object(s.p,'APPROVAL',decision),patch.object(s,'RAM_GATE',directory):
        decision.write_text('{}')
        try:s._owner_authorize()
        except ValueError as e:assert str(e)=='HOST_RAM_READINESS_NOT_APPROVED',e
        else:raise AssertionError('additional condition not approved')
        decision.write_text(json.dumps({'acceptHostRamReadiness':s.readiness.CONDITION}))
        assert s._owner_authorize()==permit
        try:s.p.authorize()
        except OSError:pass
        else:raise AssertionError('no readiness receipt admitted')
        observation={'source':s.readiness.SOURCE,'synthetic':False,'ramUsedMiB':18000,'ramTotalMiB':32388,'recordedAtUnix':100,'querySeconds':.01}
        ready=s.readiness.evaluate(observation,unix=100)
        record={'status':'READY_FOR_SINGLE_WORKLOAD','reviewSha256':permit.review_sha256,'approvalSha256':permit.approval_sha256,'observationSha256':s.p.sha(observation),'readiness':ready}
        for name,value in [('observation.json',observation),('query-process.json',{'pid':123}),('query-exit.json',{'pid':123,'exitCode':0,'confirmedExited':True}),('result.json',record)]:
            (directory/name).write_text(json.dumps(value))
        assert s.p.authorize()==permit
        record['readiness']['headroomToEmergencyMiB']=99999
        (directory/'result.json').write_text(json.dumps(record))
        try:s.p.authorize()
        except ValueError as e:assert str(e)=='HOST_RAM_JOB_NOT_READY',e
        else:raise AssertionError('altered readiness admitted')
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=scope.HERE,
                       capture_output=True, check=True, timeout=20)


if __name__ == '__main__': unittest.main()
