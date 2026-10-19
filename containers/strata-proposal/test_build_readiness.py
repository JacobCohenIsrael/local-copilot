import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import build_guard
import build_policy_review as policy
import build_preflight


class BuildReadinessTests(unittest.TestCase):
    def frame(self, second, **changes):
        # Mocked real-shaped data only; no hardware/provider validation occurs.
        return policy.synthetic(second + 1, second, **{'synthetic': False, 'cpuTemperatureC': 92, **changes})

    def test_approved_controls_preserve_resource_limits_and_runtime_disable(self):
        baseline, _ = policy.load_draft()
        controls = policy.load_effective_controls()
        self.assertEqual(controls['temperature']['startAtOrBelowC'], 92)
        self.assertEqual(controls['temperature']['stopAtOrAboveC'], 97)
        self.assertEqual(controls['resources'], baseline['resources'])
        self.assertFalse(controls['modelLaunchEnabled'])
        contract = build_guard.plan()
        self.assertEqual(contract['approvedBuildTemperatureControls'], controls['temperature'])
        self.assertFalse(contract['buildEnabled'])

    def test_approval_hash_and_scope_cannot_be_reused_after_changes(self):
        names = ('build-policy.draft.json', 'build-policy-approval.json',
                 'thermal-revision.proposed.json', 'thermal-revision-approval.json')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in names:
                shutil.copyfile(policy.HERE / name, root / name)
            with patch.object(policy, 'HERE', root):
                self.assertEqual(policy.load_effective_controls()['temperature']['stopAtOrAboveC'], 97)
                file = root / 'thermal-revision.proposed.json'
                original = file.read_text()
                revision = json.loads(original)
                revision['temperatureChanges']['stopAtOrAboveC'] = 99
                file.write_text(json.dumps(revision))
                with self.assertRaises(ValueError):
                    policy.load_effective_controls()
                file.write_text(original)
                receipt = json.loads((root / 'thermal-revision-approval.json').read_text(encoding='utf-8'))
                receipt['scope'] = 'model-runtime'
                (root / 'thermal-revision-approval.json').write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    policy.load_effective_controls()

    def test_real_shaped_frames_obey_baseline_hot_trip_and_unknown_preservation(self):
        gate = policy.CpuBuildReadinessGate()
        for second in range(11):
            result = gate.observe(self.frame(second), elapsed=second, unix=1000 + second)
        self.assertEqual(result['state'], 'ELIGIBLE_FOR_BUILD_REVIEW')
        self.assertIsNone(result['cpuThermalThrottling'])
        self.assertFalse(result['simulationOnly'])
        self.assertFalse(result['buildEnabled'])
        result = gate.observe(self.frame(11, cpuTemperatureC=97), elapsed=11, unix=1011)
        self.assertEqual(result['fault'], 'CPU_HOT')
        self.assertEqual(gate.tick(elapsed=12, unix=1012, controller_age=0)['fault'], 'CPU_HOT')

    def test_actual_unvalidated_reader_and_fake_frames_cannot_admit(self):
        for changes, expected in (({'validatedCpuSensor': False}, 'CPU_SENSOR_UNVALIDATED'),
                                  ({'synthetic': True}, 'REAL_SOURCE_REQUIRED')):
            gate = policy.CpuBuildReadinessGate()
            frame = self.frame(0)
            frame.update(changes)
            result = gate.observe(frame, elapsed=0, unix=1000)
            self.assertEqual(result['fault'], expected)

    def test_silent_feed_controller_loss_and_clock_regression_fault(self):
        for kwargs, expected in (({'elapsed': 3, 'unix': 1003, 'controller_age': 0}, 'SENSOR_STALE'),
                ({'elapsed': 1, 'unix': 1001, 'controller_age': 3}, 'CONTROLLER_LEASE_EXPIRED')):
            gate = policy.CpuBuildReadinessGate()
            gate.observe(self.frame(0), elapsed=0, unix=1000)
            self.assertEqual(gate.tick(**kwargs)['fault'], expected)
        gate = policy.CpuBuildReadinessGate()
        gate.observe(self.frame(0), elapsed=0, unix=1000)
        gate.tick(elapsed=1, unix=1001, controller_age=0)
        self.assertEqual(gate.observe(self.frame(1), elapsed=.5, unix=1001)['fault'], 'CLOCK_INVALID')

    def test_refreshed_preflight_verifies_helpers_and_never_enables_work(self):
        report = build_preflight.report()
        self.assertEqual(report['approvedCpuControls']['stopAtOrAboveC'], 97)
        self.assertNotIn('BUILD_PACKAGE_OUTDATED', report['blockers'])
        self.assertTrue(report['helpers']['bounded_build.py']['matches'])
        self.assertTrue(report['helpers']['compile.sh']['matches'])
        self.assertIn('FINAL_BUILD_WORKLOAD_NOT_APPROVED', report['blockers'])
        self.assertFalse(report['buildEnabled'])
        self.assertFalse(report['thermalGateIsStartAuthority'])
        contract = copy.deepcopy(build_guard.plan())
        contract['cpuQuota'] = 2
        with patch.object(build_guard, 'plan', return_value=contract), self.assertRaises(ValueError):
            build_preflight.report()

    def test_candidate_binding_rejects_manifest_changes_preserving_original(self):
        baseline, _ = policy.load_draft()
        self.assertEqual(build_guard.digest(build_guard.PACKAGE / 'build-manifest.json'),
                         baseline['buildManifestSha256'])
        with patch.object(build_guard, 'digest', return_value='0' * 64), self.assertRaises(ValueError):
            build_preflight.report()


if __name__ == '__main__':
    unittest.main()
