import unittest
import cpu_limits


class CpuLimitsTests(unittest.TestCase):
    def test_equal_limits_do_not_certify_no_hardware_throttling(self):
        result = cpu_limits.summarize([{'number': 0, 'maxMhz': 3000, 'currentMhz': 1000, 'limitMhz': 3000}])
        self.assertFalse(result['osReportedLimitBelowMax'])
        self.assertIsNone(result['cpuThermalThrottling'])
        self.assertFalse(result['validatedHardwareThrottleSource'])

    def test_reduced_os_limit_keeps_distinct_provenance(self):
        result = cpu_limits.summarize([{'number': 0, 'maxMhz': 3000, 'currentMhz': 3500, 'limitMhz': 2000}])
        self.assertTrue(result['osReportedLimitBelowMax'])
        self.assertIsNone(result['cpuThermalThrottling'])

    def test_empty_duplicate_and_unknown_limits_rejected(self):
        row = {'number': 0, 'maxMhz': 3000, 'currentMhz': 1000, 'limitMhz': 3000}
        for rows in ([], [row, row], [{**row, 'limitMhz': 0}], [{**row, 'number': True}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                cpu_limits.summarize(rows)


if __name__ == '__main__':
    unittest.main()
