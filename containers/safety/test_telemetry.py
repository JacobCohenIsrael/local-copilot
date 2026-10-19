import unittest
import telemetry as t


class TelemetryTests(unittest.TestCase):
    def test_missing_invalid_and_nonfinite_are_not_zero(self):
        for value in (None, 'N/A', '[Not Supported]', 'NaN', 'inf', '-1'):
            self.assertIsNone(t.number(value))
        self.assertEqual(t.number('15.25 W'), 15.25)

    def test_unknown_thermal_status_does_not_become_false(self):
        xml = '<nvidia_smi_log><gpu><temperature><gpu_temp>44 C</gpu_temp></temperature></gpu></nvidia_smi_log>'
        gpu = t.parse_gpu(xml)
        self.assertEqual(gpu['values']['gpuTemperatureC'], 44)
        self.assertIsNone(gpu['values']['gpuPowerW'])
        self.assertIsNone(gpu['values']['gpuThermalThrottling'])

    def test_known_thermal_trip_wins_even_if_other_channel_missing(self):
        xml = '<nvidia_smi_log><gpu><clocks_event_reasons><clocks_event_reason_hw_thermal_slowdown>Active</clocks_event_reason_hw_thermal_slowdown></clocks_event_reasons></gpu></nvidia_smi_log>'
        self.assertTrue(t.parse_gpu(xml)['values']['gpuThermalThrottling'])

    def test_cpu_sensor_is_not_inferred_from_gpu_or_acpi(self):
        providers = [{'available': True, 'namespace': 'test', 'sensors': [
            {'Identifier': '/nvidiagpu/0/temperature/0', 'Name': 'GPU', 'Value': 30},
            {'Identifier': '/acpi/temperature', 'Name': 'Thermal Zone', 'Value': 25},
            {'Identifier': '/intelcpu/0/temperature/0', 'Name': 'CPU Package', 'Value': 62},
            {'Identifier': '/intelcpu/0/temperature/1', 'Name': 'CPU Core', 'Value': 65}]}]
        self.assertEqual(t.cpu_temperature(providers)['value'], 65)
        self.assertIsNone(t.cpu_temperature(providers[0:0]))

    def test_missing_channels_block_coverage(self):
        self.assertEqual(t.availability({}), list(t.REQUIRED))
        self.assertIn('cpuTemperatureC', t.availability({'gpuTemperatureC': {'value': 40}}))


if __name__ == '__main__':
    unittest.main()
