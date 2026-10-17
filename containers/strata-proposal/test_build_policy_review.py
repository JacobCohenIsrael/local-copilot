import copy
import unittest
from unittest.mock import patch

import build_guard
import build_policy_review as review


class BuildPolicyReviewTests(unittest.TestCase):
    def setUp(self):
        self.draft, _ = review.load_draft()
        self.model = review.ThermalRehearsal(self.draft)

    def observe(self, second, **changes):
        return self.model.observe(review.synthetic(second + 1, second, **changes),
                                  elapsed=second, unix=1000 + second)

    def test_requires_continuous_cool_baseline_preserving_unknown(self):
        for second in range(10):
            self.assertEqual(self.observe(second)['state'], 'WAITING')
        result = self.observe(10)
        self.assertEqual(result['state'], 'ELIGIBLE_IN_SIMULATION_ONLY')
        self.assertIsNone(result['cpuThermalThrottling'])
        self.assertFalse(result['buildEnabled'])
        self.assertFalse(result['modelLaunchEnabled'])

    def test_warm_baseline_restarts_wait_but_hot_latches_fault(self):
        for second in range(10):
            self.observe(second, cpuTemperatureC=75)
        self.observe(10, cpuTemperatureC=76)
        for second in range(11, 21):
            self.assertEqual(self.observe(second)['state'], 'WAITING')
        self.assertEqual(self.observe(21)['state'], 'ELIGIBLE_IN_SIMULATION_ONLY')
        self.assertEqual(self.observe(22, cpuTemperatureC=80)['fault'], 'CPU_HOT')
        self.assertEqual(self.observe(23, cpuTemperatureC=60)['fault'], 'CPU_HOT')

    def test_historical_hot_values_cannot_admit(self):
        for value in (81, 83, 90, 94):
            with self.subTest(value=value):
                self.model = review.ThermalRehearsal(self.draft)
                self.assertEqual(self.observe(0, cpuTemperatureC=value)['fault'], 'CPU_HOT')

    def test_unvalidated_and_nonboolean_validity_fail(self):
        for value in (False, None, 'true', 1):
            with self.subTest(value=value):
                self.model = review.ThermalRehearsal(self.draft)
                self.assertEqual(self.observe(0, validatedCpuSensor=value)['fault'], 'CPU_SENSOR_UNVALIDATED')

    def test_unknown_is_only_simulated_exception_known_throttle_still_faults(self):
        self.assertIsNone(self.observe(0)['fault'])
        result = self.observe(1, cpuThermalThrottling=True)
        self.assertEqual(result['fault'], 'CPU_THROTTLING')
        self.assertIs(result['cpuThermalThrottling'], True)
        for value in (0, 'false'):
            self.model = review.ThermalRehearsal(self.draft)
            self.assertEqual(self.observe(0, cpuThermalThrottling=value)['fault'], 'CPU_THROTTLE_INVALID')
        # Existing real admission retains its mandatory channel unchanged.
        sample = review.synthetic(1, 0, synthetic=False)
        self.assertEqual(build_guard.reading_error(sample, 1000), 'CPU_THROTTLE_MISSING')
        self.assertFalse(build_guard.plan()['buildEnabled'])
        self.assertIsNone(build_guard.plan()['livePolicy'])
        strict = copy.deepcopy(self.draft)
        strict['throttleException']['allowUnknownInSimulation'] = False
        self.model = review.ThermalRehearsal(strict)
        self.assertEqual(self.observe(0)['fault'], 'CPU_THROTTLE_MISSING')

    def test_stale_replay_future_invalid_query_and_bad_values_fail(self):
        changes = [({'recordedAtUnix': 996}, 'SENSOR_STALE'),
                   ({'recordedAtUnix': 1001}, 'SENSOR_STALE'),
                   ({'sequence': True}, 'SENSOR_SEQUENCE'),
                   ({'querySeconds': float('nan')}, 'SENSOR_QUERY_TIMEOUT'),
                   ({'querySeconds': 1.01}, 'SENSOR_QUERY_TIMEOUT'),
                   ({'cpuTemperatureC': float('inf')}, 'CPU_TEMPERATURE_MISSING'),
                   ({'source': 'another provider'}, 'SENSOR_SOURCE'),
                   ({'error': 'denied'}, 'SENSOR_SOURCE'),
                   ({'synthetic': False}, 'SYNTHETIC_ONLY')]
        for fields, expected in changes:
            with self.subTest(fields=fields):
                self.model = review.ThermalRehearsal(self.draft)
                self.assertEqual(self.observe(0, **fields)['fault'], expected)
        self.model = review.ThermalRehearsal(self.draft)
        self.observe(0)
        self.assertEqual(self.observe(1, sequence=1)['fault'], 'SENSOR_SEQUENCE')

    def test_monitor_gap_lost_controller_clock_and_cancel_fault(self):
        self.observe(0)
        self.assertEqual(self.observe(3)['fault'], 'MONITOR_GAP')
        for kwargs, expected in [({'controller_age': 3}, 'CONTROLLER_LEASE_EXPIRED'),
                                 ({'cancelled': True}, 'CANCELLED'),
                                 ({'elapsed': float('nan')}, 'CLOCK_INVALID')]:
            self.model = review.ThermalRehearsal(self.draft)
            args = {'elapsed': 0, 'unix': 1000, **kwargs}
            result = self.model.observe(review.synthetic(1, 0), **args)
            self.assertEqual(result['fault'], expected)
            self.assertEqual(self.observe(1)['fault'], expected)

    def test_deadline_has_no_automatic_retry(self):
        for second in range(1810):
            self.assertIsNone(self.observe(second)['fault'])
        self.assertEqual(self.observe(1810)['fault'], 'BUILD_DEADLINE')
        self.assertEqual(self.observe(1811)['fault'], 'BUILD_DEADLINE')

    def test_report_bound_to_disabled_package_and_reader(self):
        result = review.report()
        self.assertEqual(result['status'], 'POLICY_APPROVED_BUILD_BLOCKED')
        self.assertEqual(result['policyApproval'], 'owner-approved-controls-only')
        self.assertTrue(result['readerRevalidationRequired'])
        self.assertTrue(result['readerChangedSinceReview'])
        self.assertFalse(result['buildEnabled'])
        self.assertFalse(result['liveGuardChanged'])
        contract = copy.deepcopy(build_guard.plan())
        contract['buildManifestSha256'] = '0' * 64
        with patch.object(build_guard, 'plan', return_value=contract), self.assertRaises(ValueError):
            review.report()

    def test_approval_cannot_transfer_to_changed_policy_or_runtime(self):
        draft, sha = review.load_draft()
        self.assertEqual(review.load_approval(draft, sha)['status'], 'owner-approved-controls-only')
        with self.assertRaises(ValueError):
            review.load_approval(draft, '0' * 64)
        draft['scope'] = 'model-runtime'
        with self.assertRaises(ValueError):
            review.load_approval(draft, sha)

    def test_reader_must_cover_build_shutdown_and_sample_age(self):
        for remaining, age, expected in [(2, 0, 'READER_COVERAGE_INSUFFICIENT'),
                (1805, 0, None), (1805, .1, 'READER_COVERAGE_INSUFFICIENT'),
                (1920, 0, None), (None, 0, 'READER_COVERAGE_MISSING')]:
            with self.subTest(remaining=remaining, age=age):
                self.assertEqual(review.coverage_error({'readerRemainingSeconds': remaining},
                    self.draft, age_seconds=age), expected)
        self.assertEqual(review.coverage_error({'readerRemainingSeconds': 1814}, self.draft,
            baseline_pending=True), 'READER_COVERAGE_INSUFFICIENT')
        self.assertEqual(self.observe(0, readerRemainingSeconds=2)['fault'], 'READER_COVERAGE_INSUFFICIENT')


if __name__ == '__main__':
    unittest.main()
