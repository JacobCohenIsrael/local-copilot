import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cpu_feed as cpu
import build_policy_review as policy


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / ('a' * 32)
        self.directory.mkdir()
        self.patched = patch.object(cpu, 'ROOT', self.root)
        self.patched.start()
        self.addCleanup(self.patched.stop)
        self.now = 100
        self.feed = cpu.Feed(self.directory, clock=lambda: self.now)
        self.monitor = cpu.Monitor(self.feed, unix=lambda: 1000 + self.now)

    def publish(self, sequence=1, **changes):
        frame = policy.synthetic(sequence, 0, synthetic=False, recordedAtUnix=1000 + self.now,
                                 **changes)
        (self.directory / f'sample-{sequence:08d}.json').write_text(json.dumps(frame), encoding='utf-8-sig')
        return frame

    def test_unvalidated_real_frame_stays_unvalidated_and_never_admits(self):
        self.publish(validatedCpuSensor=False)
        result = self.monitor.poll()
        self.assertEqual(result['fault'], 'CPU_SENSOR_UNVALIDATED')
        self.assertFalse(result['buildEnabled'])
        self.assertIsNone(result['cpuThermalThrottling'])
        self.assertEqual(self.feed.sequence, 1)

    def test_real_feed_rejects_synthetic_provenance(self):
        self.publish()
        path = self.directory / 'sample-00000001.json'
        frame = json.loads(path.read_text(encoding='utf-8-sig'))
        frame['synthetic'] = True
        path.write_text(json.dumps(frame))
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')

    def test_no_new_frame_ticks_and_faults_even_without_a_reader_reply(self):
        self.publish()
        self.assertIsNone(self.monitor.poll()['fault'])
        self.now += 3
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')

    def test_initial_missing_frame_and_controller_loss_are_bounded(self):
        self.now += 3
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_MISSING')
        self.monitor = cpu.Monitor(self.feed)
        self.assertEqual(self.monitor.poll(controller_age=3)['fault'], 'CONTROLLER_LEASE_EXPIRED')

    def test_unchanged_file_cannot_replay_a_sequence(self):
        frame = self.publish()
        self.assertEqual(self.feed.poll(), frame)
        self.assertIsNone(self.feed.poll())
        frame['recordedAtUnix'] += 1
        (self.directory / 'sample-00000001.json').write_text(json.dumps(frame))
        self.assertIsNone(self.feed.poll())
        self.assertEqual(self.feed.sequence, 1)

    def test_cancel_and_reader_exit_fault_in_monitor(self):
        self.assertEqual(self.monitor.poll(cancelled=True)['fault'], 'CANCELLED')
        self.monitor = cpu.Monitor(self.feed)
        self.feed.process = Mock()
        self.feed.process.poll.return_value = 1
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')

    def test_clock_regression_and_oversized_frame_fail_closed(self):
        self.now -= 1
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
        self.now = 100
        self.monitor = cpu.Monitor(self.feed)
        (self.directory / 'sample-00000001.json').write_bytes(b'x' * 4097)
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')

    def test_reader_hash_and_dirty_namespace_prevent_process_creation(self):
        with patch.object(cpu.windows_job, 'Process') as launch:
            with patch.object(cpu.tools, 'sha', return_value='wrong'):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    self.feed.start_reader()
            self.publish()
            with self.assertRaisesRegex(ValueError, 'empty'):
                self.feed.start_reader()
            launch.assert_not_called()

    def test_invalid_sample_counts_cannot_start_reader(self):
        for count in (0, 1921, True):
            with self.assertRaisesRegex(ValueError, 'sample budget'):
                self.feed.start_reader(samples=count)

    def test_partial_probe_cannot_cover_full_build(self):
        self.publish(readerRemainingSeconds=2)
        self.assertEqual(self.monitor.poll()['fault'], 'READER_COVERAGE_INSUFFICIENT')

    def test_rejected_qualification_does_not_commit_sequence_or_receipt(self):
        self.publish()
        self.feed.source_permit = Mock()
        self.feed.source_permit.qualify.side_effect = ValueError('sensitive arbitrary text')
        self.feed.process = Mock()
        self.feed.process.poll.return_value = None
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
        self.assertEqual(self.feed.sequence, 0)
        self.assertIsNone(self.feed.received)
        self.assertEqual(self.monitor.last_error['operation'], 'qualify')
        self.assertNotIn('sensitive', json.dumps(self.monitor.last_error))

    def test_buffered_frame_from_exited_reader_is_not_consumed_and_exit_is_retained(self):
        self.publish()
        self.feed.source_permit = Mock()
        self.feed.process = Mock()
        self.feed.process.poll.return_value = 0xC0000017
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
        self.assertEqual(self.feed.sequence, 0)
        self.assertEqual(self.monitor.last_error['reason'], 'READER_EXITED')
        self.assertEqual(self.monitor.last_error['readerExitCode'], 0xC0000017)
        self.feed.source_permit.qualify.assert_not_called()

    def test_malformed_or_wrong_shape_frame_stops_with_fixed_reason(self):
        for data, reason in [(b'{secret', 'READER_FRAME_JSON'), (b'[]', 'READER_FRAME_IDENTITY')]:
            (self.directory / 'sample-00000001.json').write_bytes(data)
            self.monitor = cpu.Monitor(self.feed)
            self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
            self.assertEqual(self.monitor.last_error['reason'], reason)
            self.assertEqual(self.feed.sequence, 0)

    def test_windows_read_error_is_redacted_and_never_retried(self):
        self.publish()
        error = PermissionError(13, 'secret path or credential')
        error.winerror = 32
        with patch.object(cpu.sensor_frame_io, 'read', side_effect=error) as opening:
            self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
            opening.assert_called_once()
        detail = self.monitor.last_error
        self.assertEqual(detail['osError'], 13)
        self.assertEqual(detail['windowsError'], 32)
        self.assertEqual(detail['operation'], 'read')
        self.assertNotIn('secret', json.dumps(detail))
        self.assertIsNone(self.feed.received)

    def test_missing_frame_reader_exit_and_coverage_are_distinct(self):
        self.feed.process = Mock()
        self.feed.process.poll.return_value = 7
        self.assertEqual(self.monitor.poll()['fault'], 'SENSOR_FEED_ERROR')
        self.assertEqual(self.monitor.last_error['reason'], 'READER_EXITED')
        self.assertEqual(self.monitor.last_error['readerExitCode'], 7)

    def test_original_262_frames_pass_without_touching_hardware(self):
        reader = Path(__file__).resolve().parents[2] / '.runtime/compiler-guard/746421aeb6f34c85b7dcd3a837cda5f7'
        frames = [json.loads(path.read_text(encoding='utf-8-sig')) for path in sorted(reader.glob('sample-????????.json'))]
        self.assertEqual(len(frames), 262)
        self.feed.source_permit = Mock()
        self.feed.source_permit.qualify.side_effect = lambda f: {**f, 'validatedCpuSensor': True}
        self.feed.process = Mock()
        self.feed.process.poll.return_value = None
        self.now = frames[0]['recordedAtUnix'] + .04
        self.monitor = cpu.Monitor(self.feed, unix=lambda: self.now)
        for frame in frames:
            self.now = frame['recordedAtUnix'] + .04
            (self.directory / f'sample-{frame["sequence"]:08d}.json').write_text(json.dumps(frame), encoding='utf-8-sig')
            self.assertIsNone(self.monitor.poll()['fault'])
        self.assertEqual(self.feed.sequence, 262)


if __name__ == '__main__':
    unittest.main()
