"""Offline preservation, unchanged limits and approval boundaries for a fresh scope."""
import copy
import subprocess
import sys
import unittest
from unittest.mock import patch

import coding_task_2_recovery as recovery


class RecoveryTests(unittest.TestCase):
    def test_failed_attempt_and_spent_approval_are_bound_without_reset(self):
        proof = recovery.failed_proof(True)
        self.assertEqual(proof['reviewSha256'], recovery.FAILED_SHA)
        self.assertFalse(proof['previousAttemptReset'])
        self.assertFalse(proof['previousApprovalReused'])
        with patch.object(recovery.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'FAILED_CODING_MANIFEST_CHANGED'):
                recovery.failed_proof()

    def test_recovery_cannot_widen_resources_deadlines_output_or_task(self):
        original = recovery.p.read(recovery.FAILED / 'review.json', 131072)
        changes = [('policy', 'cpuStopC', 98), ('policy', 'modelSeconds', 301),
                   ('vmEnvelope', 'cpus', 2), ('request', 'max_tokens', 33),
                   ('codingTask', 'maximumGuardBytes', 129), ('codingTask', 'modelCalls', 2),
                   ('codingTask', 'task', 'another task')]
        with patch.object(recovery.task.coding, 'same_limits'):
            recovery.same_limits(copy.deepcopy(original))
            for area, key, value in changes:
                with self.subTest(area=area, key=key):
                    packet = copy.deepcopy(original)
                    packet[area][key] = value
                    with self.assertRaisesRegex(ValueError, 'RECOVERY_MUST_KEEP'):
                        recovery.same_limits(packet)

    def test_new_scope_refuses_missing_and_spent_approvals_before_docker_access(self):
        script = '''
import copy, sys
from unittest.mock import patch
import coding_task_2_recovery as r
r.activate()
assert r.p.APPROVAL.name == 'coding-task-2-recovery-approval.json'
assert r.p.LIVE == r.LIVE and r.task.coding.WORKER == r.WORKER
assert r.task.PREPARATION == r.PREPARATION
assert r.task.coding.first_api.WATCH_ENTRYPOINT.name == 'coding_task_2_recovery.py'
old_manifest=r.p.read(r.FAILED/'execution-preservation.json',1048576)
assert str(r.WORKER) != old_manifest['worker']['directory']
with patch.object(r.task.coding.first_api.guard.base,'Docker') as docker, \\
     patch.object(r.p,'APPROVAL',r.ROOT/'deliberately-missing-approval.json'), \\
     patch.object(r.task.coding,'WORKER',r.ROOT/'deliberately-missing-worker'):
    try:r.run()
    except ValueError as error:assert str(error)=='FIRST_MODEL_API_NOT_APPROVED',error
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(r.REPO))
    import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-recovery']):
        try:cli.main()
        except ValueError as error:assert str(error)=='FIRST_MODEL_API_NOT_APPROVED',error
        else:raise AssertionError('CLI bypassed approval')
    docker.assert_not_called()
old=r.p.read(r.FAILED/'review.json',131072)
with patch.object(r.p,'APPROVAL',r.HERE/'coding-task-2-approval.json'), \\
     patch.object(r.p,'review',return_value=('b'*64,old)), \\
     patch.object(r.task.coding.first_api.guard.base,'Docker') as docker:
    try:r.p.authorize()
    except ValueError as error:assert str(error)=='FIRST_MODEL_API_APPROVAL_INVALID',error
    else:raise AssertionError('spent approval reused')
    docker.assert_not_called()
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=recovery.HERE,
                       capture_output=True, check=True, timeout=20)


if __name__ == '__main__': unittest.main()
