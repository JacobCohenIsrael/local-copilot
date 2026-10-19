import copy
import unittest

import build_guard
import build_policy_review as review


class ThermalRevisionTests(unittest.TestCase):
    def setUp(self):
        self.candidate, _ = review.load_thermal_revision()

    def test_only_temperature_pair_changes_without_transferring_approval(self):
        baseline, sha = review.load_draft()
        restored = copy.deepcopy(self.candidate)
        restored['temperature'].update(startAtOrBelowC=75, stopAtOrAboveC=80)
        self.assertEqual(restored, baseline)
        self.assertEqual(review.load_approval(baseline, sha)['status'], 'owner-approved-controls-only')
        result = review.thermal_revision_report()
        self.assertFalse(result['requiresOwnerApproval'])
        self.assertEqual(result['originallyApproved']['stopAtOrAboveC'], 80)
        self.assertEqual(result['currentlyApproved']['stopAtOrAboveC'], 97)
        self.assertFalse(result['buildEnabled'])
        self.assertFalse(build_guard.plan()['buildEnabled'])

    def test_loaded_cpu_temperatures_allowed_after_cool_baseline_then_hot_latched(self):
        model = review.ThermalRehearsal(self.candidate)
        for second in range(11):
            result = model.observe(review.synthetic(second + 1, second, cpuTemperatureC=92),
                                   elapsed=second, unix=1000 + second)
        self.assertEqual(result['state'], 'ELIGIBLE_IN_SIMULATION_ONLY')
        for second, temp in ((11, 94), (12, 95), (13, 96)):
            result = model.observe(review.synthetic(second + 1, second, cpuTemperatureC=temp),
                                   elapsed=second, unix=1000 + second)
            self.assertIsNone(result['fault'])
            self.assertIsNone(result['cpuThermalThrottling'])
        result = model.observe(review.synthetic(15, 14, cpuTemperatureC=97), elapsed=14, unix=1014)
        self.assertEqual(result['fault'], 'CPU_HOT')
        self.assertEqual(model.observe(review.synthetic(16, 15), elapsed=15, unix=1015)['fault'], 'CPU_HOT')

    def test_current_hot_baseline_cannot_start_and_boundary_trip_is_immediate(self):
        for temp, expected in ((93, 'WAITING'), (95, 'WAITING'), (97, 'FAULT'), (100, 'FAULT')):
            model = review.ThermalRehearsal(self.candidate)
            for second in range(11):
                result = model.observe(review.synthetic(second + 1, second, cpuTemperatureC=temp),
                                       elapsed=second, unix=1000 + second)
            with self.subTest(temp=temp):
                self.assertEqual(result['state'], expected)

    def test_missing_or_stale_monitoring_and_known_throttle_still_fault(self):
        for changes, expected in (({'validatedCpuSensor': False}, 'CPU_SENSOR_UNVALIDATED'),
                ({'recordedAtUnix': 990}, 'SENSOR_STALE'),
                ({'cpuThermalThrottling': True}, 'CPU_THROTTLING'),
                ({'readerRemainingSeconds': 2}, 'READER_COVERAGE_INSUFFICIENT'),
                ({'synthetic': False}, 'SYNTHETIC_ONLY')):
            model = review.ThermalRehearsal(self.candidate)
            result = model.observe(review.synthetic(1, 0, **changes), elapsed=0, unix=1000)
            with self.subTest(changes=changes):
                self.assertEqual(result['fault'], expected)


if __name__ == '__main__':
    unittest.main()
