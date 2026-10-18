import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import import_plan as plan


class ImportAdmissionTests(unittest.TestCase):
    def test_no_live_runner_can_be_unblocked_by_old_approval_or_preparation(self):
        with patch.object(plan, 'binding', side_effect=AssertionError('No evidence reads allowed')), \
                patch.object(plan, 'material', side_effect=AssertionError('No preparation allowed')):
            result = plan.run()
        self.assertEqual(result['status'], 'IMPORT_EXECUTION_NOT_IMPLEMENTED')
        self.assertFalse(result['imageImportEnabled'])
        self.assertFalse(result['buildEnabled'])
        self.assertFalse(result['modelLaunchEnabled'])

    def test_design_pins_separate_storage_and_allocation_scope(self):
        with patch.object(plan, 'binding', return_value={'preservedAttemptCount': 4}):
            packet = plan.material()
        self.assertEqual(packet['proposedStore']['logicalBytes'], 32 * 1024**3)
        self.assertFalse(packet['proposedStore']['resizeAllowed'])
        self.assertTrue(packet['proposedStore']['daemonDataContainerdContentSnapshotsTmpAndLogsInsideStore'])
        self.assertFalse(packet['proposedStore']['implementationAndPhysicalAllocationBoundProven'])
        self.assertFalse(packet['proposedEngine']['shareDesktopContainerd'])
        self.assertFalse(packet['proposedEngine']['sharedStorageFallback'])
        self.assertFalse(packet['proposedGuard']['clientExitIsDaemonStopProof'])
        self.assertEqual(packet['archive']['members'], 15)
        self.assertGreater(packet['archive']['exactBytes'], packet['image']['lockedBlobBytes'])
        self.assertFalse(packet['liveRunnerImplemented'])

    def test_prepare_and_summary_are_metadata_only_and_design_never_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(plan, 'ROOT', Path(temp) / 'review'), \
                    patch.object(plan, 'binding', return_value={'preservedAttemptCount': 4, 'blobBytes': 3951095908}):
                directory, packet = plan.prepare()
                result = plan.summary()
                self.assertEqual(result['status'], 'DESIGN_REVIEW_ONLY_NOT_EXECUTABLE')
                self.assertEqual(result['reviewSha256'], plan.build.sha(packet))
                self.assertFalse(result['imageImportEnabled'])
                # Packet mutation does not acquire authority and is detectable.
                changed = dict(packet, imageImportEnabled=True)
                (directory / 'review.json').write_text(json.dumps(changed))
                self.assertEqual(plan.summary()['status'], 'NOT_PREPARED_OR_STALE')

    def test_bad_success_preservation_rejects_before_reading_success_or_cache(self):
        with patch.object(plan.prior, 'binding', return_value={}), \
                patch.object(plan.tools, 'sha', return_value='0' * 64), \
                patch.object(plan.cpu, 'bounded') as read:
            with self.assertRaisesRegex(ValueError, 'IMPORT_SUCCESS_PRESERVATION_CHANGED'):
                plan.binding()
            read.assert_not_called()

    def test_cli_live_refusal_does_not_read_state_start_sensor_or_spawn(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import local_worker as worker
        with patch.object(sys, 'argv', ['local_worker.py', 'run-import']), \
                patch.object(worker.cpu_feed, 'probe') as sensor, \
                patch.object(worker.subprocess, 'Popen') as process, \
                patch.object(plan, 'material') as material, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(worker.main(), 3)
        self.assertEqual(json.loads(output.getvalue())['status'], 'IMPORT_EXECUTION_NOT_IMPLEMENTED')
        sensor.assert_not_called()
        process.assert_not_called()
        material.assert_not_called()


if __name__ == '__main__':
    unittest.main()
