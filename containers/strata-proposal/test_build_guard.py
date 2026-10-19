import time
import unittest
import copy
import tempfile

import build_guard as g


class GuardTests(unittest.TestCase):
    def sample(self):
        return {'version': 1, 'sequence': 1, 'synthetic': True, 'recordedAtUnix': time.time(),
                'querySeconds': .01, 'cpuTemperatureC': 60, 'cpuThermalThrottling': False,
                'validatedCpuSensor': True}

    def test_valid_rehearsal_and_hot_trip(self):
        sample = self.sample()
        self.assertIsNone(g.reading_error(sample, time.time(), rehearsal=True))
        sample['cpuTemperatureC'] = 90
        self.assertEqual(g.reading_error(sample, time.time(), rehearsal=True), 'CPU_HOT')

    def test_missing_throttle_and_unvalidated_cpu_block_admission(self):
        for change, code in [({'cpuThermalThrottling': None}, 'CPU_THROTTLE_MISSING'),
                             ({'validatedCpuSensor': False}, 'CPU_SENSOR_UNVALIDATED'),
                             ({'cpuThermalThrottling': True}, 'CPU_THROTTLING')]:
            sample = {**self.sample(), **change}
            self.assertEqual(g.reading_error(sample, time.time(), rehearsal=True), code)

    def test_stale_future_regressed_and_replayed_samples_fail(self):
        sample = self.sample()
        for stamp in (time.time()-5, time.time()+5, float('nan')):
            self.assertEqual(g.reading_error({**sample, 'recordedAtUnix': stamp}, time.time(), rehearsal=True), 'SENSOR_STALE')
        self.assertEqual(g.reading_error(sample, time.time(), 2, rehearsal=True), 'SENSOR_SEQUENCE')
        self.assertEqual(g.reading_error(sample, time.time(), 1, rehearsal=True, previous_stamp=sample['recordedAtUnix']-.1), 'SENSOR_SEQUENCE')

    def test_invalid_duration_and_source_fail(self):
        sample = self.sample()
        self.assertEqual(g.reading_error({**sample, 'querySeconds': 3}, time.time(), rehearsal=True), 'SENSOR_QUERY_TIMEOUT')
        self.assertEqual(g.reading_error(sample, time.time(), rehearsal=False), 'SENSOR_SOURCE')

    def test_real_reader_missing_flag_does_not_become_healthy(self):
        sample = {**self.sample(), 'synthetic': False, 'cpuThermalThrottling': None,
                  'validatedCpuSensor': False}
        self.assertEqual(g.reading_error(sample, time.time()), 'CPU_THROTTLE_MISSING')

    def test_package_contract_never_enables_compilation(self):
        plan = g.plan()
        self.assertFalse(plan['buildEnabled'])
        self.assertFalse(plan['modelLaunchEnabled'])
        self.assertIsNone(plan['livePolicy'])

    def test_actual_compiler_matcher_rejects_gpu_or_foreign_identity(self):
        spec = g.compiler_target()
        info = {'Name': '/' + spec['name'], 'Config': {
            'Image': g.plan()['image'], 'Labels': {'local-copilot.kind': 'strata-compile-proposal'},
            'Entrypoint': ['/usr/bin/timeout'],
            'Cmd': ['--signal=TERM', '--kill-after=2s', '1800s', '/bin/bash', '/input/compile.sh'],
            'WorkingDir': '/opt/strata'},
            'HostConfig': {'Memory': 4294967296, 'MemorySwap': 4294967296, 'NanoCpus': 1000000000,
            'PidsLimit': 128, 'Runtime': 'runc', 'Privileged': False, 'NetworkMode': 'bridge',
            'RestartPolicy': {'Name': 'no'}, 'SecurityOpt': ['no-new-privileges']},
            'Mounts': [{'Source': spec['input'], 'Destination': '/input', 'RW': False}]}
        class Docker:
            def inspect(self, _name):
                return info
        self.assertIsNotNone(g.inspect_target(Docker(), spec))
        original = copy.deepcopy(info)
        for change in ('gpu', 'name', 'image', 'mount'):
            info = copy.deepcopy(original)
            if change == 'gpu':
                info['HostConfig']['DeviceRequests'] = [{'Capabilities': [['gpu']]}]
            elif change == 'name':
                info['Name'] = '/foreign'
            elif change == 'image':
                info['Config']['Image'] = 'unreviewed-image'
            else:
                info['Mounts'][0]['RW'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                g.inspect_target(Docker(), spec)

    def test_immutable_frames_advance_and_reject_filename_mismatch(self):
        root = g.base.ROOT / '.runtime/guard-frame-unit'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            folder = g.Path(folder)
            folder.resolve().relative_to(root.resolve())
            sample = self.sample()
            g.base.atomic(folder / 'sample-00000001.json', sample)
            self.assertEqual(g.read_sample(folder)['sequence'], 1)
            g.base.atomic(folder / 'sample-00000002.json', {**sample, 'sequence': 2})
            self.assertEqual(g.read_sample(folder, 1)['sequence'], 2)
            g.base.atomic(folder / 'sample-00000003.json', {**sample, 'sequence': 9})
            with self.assertRaises(ValueError):
                g.read_sample(folder, 2)


if __name__ == '__main__':
    unittest.main()
