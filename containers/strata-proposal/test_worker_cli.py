import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import local_worker as worker
import windows_job


class WorkerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = patch.object(worker, 'ROOT', self.root)
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def test_latest_rehearsal_is_hash_bound_and_never_real_admission(self):
        directory = self.root / ('a' * 32)
        directory.mkdir()
        result = {'runId': directory.name, 'synthetic': True, 'compilerStarted': False,
                  'modelStarted': False, 'status': 'PATCH_FOR_REVIEW_SYNTHETIC', 'phases': []}
        raw = json.dumps(result).encode()
        (directory / 'result.json').write_bytes(raw)
        (self.root / 'latest.json').write_text(json.dumps({'runId': directory.name,
                                                          'sha256': hashlib.sha256(raw).hexdigest()}))
        self.assertTrue(worker.latest()['synthetic'])
        (directory / 'result.json').write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'changed'):
            worker.latest()

    def test_rehearsal_does_not_hide_a_failed_phase_or_run_coding_after_failure(self):
        with patch.object(worker.build_preflight, 'report'), patch.object(worker.verify_opencode, 'artifact'), \
                patch.object(worker.verify_image_stage, 'verify', return_value={'passed': False}), \
                patch.object(worker.bundle_rehearsal, 'rehearse') as coding:
            with self.assertRaisesRegex(ValueError, 'PHASE_FAILED'):
                worker.rehearse()
            coding.assert_not_called()
        result = worker.latest()
        self.assertEqual(result['status'], 'FAULT')
        self.assertEqual(result['phases'][0]['status'], 'FAULT')
        self.assertIsNone(result['patch'])

    def test_real_run_task_rejects_before_any_process_or_docker_operation(self):
        with patch.object(sys, 'argv', ['local_worker.py', 'run-task']), \
                patch.object(worker, 'rehearse') as rehearsal, patch.object(worker.cpu_feed, 'probe') as probe:
            self.assertEqual(worker.main(), 3)
            rehearsal.assert_not_called()
            probe.assert_not_called()

    def test_image_fault_is_a_failed_cli_result_and_never_cleared_by_exit_zero(self):
        with patch.object(sys, 'argv', ['local_worker.py', 'run-image']), \
                patch.object(worker.image_download, 'stage_pinned', return_value={
                    'phase': 'FAULT', 'fault': 'CPU_HOT', 'stopConfirmed': True}):
            self.assertEqual(worker.main(), 3)

    def test_read_only_status_cannot_promote_synthetic_proofs_to_authority(self):
        with patch.object(worker, 'latest_cpu', return_value={}), patch.object(worker, 'latest', return_value={
                'status': 'PATCH_FOR_REVIEW_SYNTHETIC'}):
            result = worker.status()
        self.assertEqual(result['status'], 'REAL_RUNTIME_BLOCKED')
        self.assertFalse(result['buildEnabled'])
        self.assertFalse(result['modelLaunchEnabled'])
        self.assertEqual(len(result['milestones']), 3)

    def test_cancel_rejects_a_finished_or_foreign_run(self):
        directory = self.root / ('a' * 32)
        directory.mkdir()
        for state in ({'synthetic': False, 'status': 'RUNNING'},
                      {'synthetic': True, 'status': 'PATCH_FOR_REVIEW_SYNTHETIC'}):
            (directory / 'result.json').write_text(json.dumps(state))
            with patch.object(sys, 'argv', ['local_worker.py', 'cancel', '--run-id', directory.name]):
                with self.assertRaisesRegex(ValueError, 'Only an active'):
                    worker.main()
            self.assertFalse((directory / 'cancel.request').exists())

    def test_wsl_observation_never_grants_workload_authority_and_detects_changes(self):
        config = self.root / '.wslconfig'
        config.write_bytes(b'[wsl2]\nprocessors=1\nmemory=6GB\nswap=0\n')
        expected = hashlib.sha256(config.read_bytes()).hexdigest()
        approval = {'status': 'owner-approved-temporary-wsl2-policy', 'proposalSha256': expected}
        pointer = {'status': 'observation-only-not-workload-approval', 'sessionId': 'a' * 32,
                   'verificationSha256': 'receipt-sha'}
        receipt = {'status': 'APPLIED_RESTARTED_VERIFIED', 'configSha256': expected,
                   'logicalProcessors': 1, 'reportedMemoryBytes': 6 * 1024**3 - 1024**2,
                   'guestSwapTotalBytes': 0, 'recordedAtUtc': 'test-time'}
        def records(path):
            return {'wsl-policy-approval.json': (approval, 'approval-sha'),
                    'wsl-policy-observation.json': (pointer, ''),
                    'verification.json': (receipt, 'receipt-sha'),
                    'application.json': ({'approvalSha256': 'approval-sha'}, '')}[path.name]
        with patch.object(worker, 'WSL_CONFIG', config), patch.object(worker, 'record', side_effect=records):
            good = worker.wsl_policy_status()
            self.assertEqual(good['status'], 'APPROVED_CONFIG_PRESENT_RESTART_VERIFIED')
            self.assertFalse(good['workloadApprovalGranted'])
            self.assertTrue(good['freshRuntimeVerificationRequired'])
            config.write_bytes(config.read_bytes() + b'# owner edit\n')
            self.assertEqual(worker.wsl_policy_status()['status'], 'UNCONFIRMED_OR_CONFIG_CHANGED')
            config.write_bytes(b'[wsl2]\nprocessors=1\nmemory=6GB\nswap=0\n')
            receipt['guestSwapTotalBytes'] = 1024
            self.assertEqual(worker.wsl_policy_status()['status'], 'UNCONFIRMED_OR_CONFIG_CHANGED')

    def test_request_record_is_bounded_before_task_preparation(self):
        path = self.root / 'request.json'
        path.write_bytes(b' ' * 16385)
        with patch.object(sys, 'argv', ['local_worker.py', 'prepare-task', '--request', str(path)]), \
                patch.object(worker.task_bundle, 'prepare') as prepare:
            with self.assertRaisesRegex(ValueError, 'budget'):
                worker.main()
            prepare.assert_not_called()


@unittest.skipUnless(sys.platform == 'win32', 'Windows process jobs required')
class JobAdmissionTests(unittest.TestCase):
    def kernel(self):
        kernel = Mock()
        kernel.CreateJobObjectW.return_value = 11
        kernel.SetInformationJobObject.return_value = 1
        def initialize(_buffer, _count, _flags, size):
            size._obj.value = 64
            return 1
        kernel.InitializeProcThreadAttributeList.side_effect = initialize
        kernel.UpdateProcThreadAttribute.return_value = 1
        def create(*args):
            info = args[-1]._obj
            info.process, info.thread, info.pid = 22, 33, 44
            return 1
        kernel.CreateProcessW.side_effect = create
        return kernel

    def test_job_assignment_failure_never_resumes_the_child(self):
        kernel = self.kernel()
        kernel.UpdateProcThreadAttribute.return_value = 0
        with patch.object(windows_job, 'api', return_value=kernel):
            with self.assertRaises(OSError):
                windows_job.Process([sys.executable, '-B', 'fixed.py'], cwd='C:/', env={})
        kernel.ResumeThread.assert_not_called()
        kernel.CreateProcessW.assert_not_called()
        kernel.TerminateProcess.assert_not_called()
        closed = {call.args[0] for call in kernel.CloseHandle.call_args_list}
        self.assertEqual(closed, {11})

    def test_resume_failure_terminates_suspended_child_and_closes_job(self):
        kernel = self.kernel()
        kernel.ResumeThread.return_value = 0xffffffff
        with patch.object(windows_job, 'api', return_value=kernel):
            with self.assertRaises(OSError):
                windows_job.Process([sys.executable, '-B', 'fixed.py'], cwd='C:/', env={})
        kernel.TerminateProcess.assert_called_once_with(22, 125)
        self.assertEqual({call.args[0] for call in kernel.CloseHandle.call_args_list}, {11, 22, 33})

    def test_exit_witness_has_no_termination_capability(self):
        kernel = self.kernel()
        with patch.object(windows_job, 'api', return_value=kernel):
            witness = windows_job.Witness(123)
            with self.assertRaisesRegex(RuntimeError, 'no termination'):
                witness.kill()
        kernel.TerminateProcess.assert_not_called()
        kernel.TerminateJobObject.assert_not_called()

    def test_single_cpu_job_is_verified_before_any_child_instruction(self):
        kernel = self.kernel()
        kernel.GetActiveProcessorGroupCount.return_value = 1
        def affinity(_process, allowed, system):
            allowed._obj.value, system._obj.value = 0b10110, 0b11111
            return 1
        kernel.GetProcessAffinityMask.side_effect = affinity
        captured = {}
        def set_limits(_job, _kind, info, _size):
            captured['flags'] = info._obj.basic.flags
            captured['affinity'] = info._obj.basic.affinity
            captured['memory'] = info._obj.job_memory
            captured['processes'] = info._obj.basic.active_processes
            return 1
        def query(_job, _kind, info, _size, _length):
            info._obj.basic.flags = captured['flags']
            info._obj.basic.affinity = captured['affinity']
            info._obj.job_memory = captured['memory']
            info._obj.basic.active_processes = captured['processes']
            return 1
        kernel.SetInformationJobObject.side_effect = set_limits
        kernel.QueryInformationJobObject.side_effect = query
        with patch.object(windows_job, 'api', return_value=kernel):
            process = windows_job.Process([sys.executable, '-B', 'fixed.py'], cwd='C:/', env={}, single_cpu=True)
            process.close()
        self.assertEqual(captured['affinity'], 0b10)
        self.assertTrue(captured['flags'] & 0x10)
        order = [call[0] for call in kernel.mock_calls]
        self.assertLess(order.index('QueryInformationJobObject'), order.index('CreateProcessW'))
        self.assertLess(order.index('CreateProcessW'), order.index('ResumeThread'))

    def test_unsupported_or_unconfirmed_cpu_limits_never_create_a_child(self):
        for groups in (2, 1):
            kernel = self.kernel()
            kernel.GetActiveProcessorGroupCount.return_value = groups
            def affinity(_process, allowed, system):
                allowed._obj.value, system._obj.value = 1, 1
                return 1
            kernel.GetProcessAffinityMask.side_effect = affinity
            kernel.QueryInformationJobObject.return_value = 1  # Observed limits stay zero: reject.
            with patch.object(windows_job, 'api', return_value=kernel):
                with self.assertRaises(RuntimeError):
                    windows_job.Process([sys.executable, '-B', 'fixed.py'], cwd='C:/', env={}, single_cpu=True)
            kernel.CreateProcessW.assert_not_called()
            kernel.ResumeThread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
