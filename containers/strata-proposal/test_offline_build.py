import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_preflight
import offline_build_plan as offline


class OfflineBuildTests(unittest.TestCase):
    def test_proposed_profile_is_offline_bounded_and_not_executable(self):
        summary = build_preflight.offline_summary()
        self.assertEqual(summary['compilerNetwork'], 'none')
        self.assertTrue(summary['rootReadOnly'])
        self.assertEqual(summary['mutableFilesystems']['workBytes'], 2 * 1024**3)
        self.assertFalse(summary['buildEnabled'])
        self.assertFalse(summary['imageCompatibilityVerified'])
        self.assertTrue(summary['artifactExporterConnected'])
        self.assertTrue(summary['artifactCollector']['liveControllerConnected'])
        self.assertFalse(summary['controllerIntegration']['liveCpuFeedActive'])
        self.assertFalse(summary['artifactCollector']['startAuthority'])
        self.assertEqual(summary['controllerIntegration']['status'], 'IMPLEMENTED_APPROVAL_GATED')
        self.assertTrue(summary['controllerIntegration']['liveCpuFeedConnected'])
        self.assertFalse(summary['controllerIntegration']['startAuthority'])
        self.assertEqual(len(summary['controllerIntegration']['helperSha256']['controller_session.py']), 64)
        directory = Path(summary['directory'])
        plan = offline.checked_proposal(directory, summary['planSha256'])
        self.assertEqual(plan['cpuQuota'], 1)
        self.assertEqual(plan['ramBytes'], 4294967296)
        self.assertEqual(plan['gpuDevices'], [])
        script = (directory / 'input/compile_offline.sh').read_text()
        self.assertNotIn('apt-get', script)
        self.assertNotIn('pip install', script)

    def test_manifest_or_profile_edits_cannot_bypass_bounds(self):
        summary = build_preflight.offline_summary()
        directory = Path(summary['directory'])
        plan = offline.checked_proposal(directory, summary['planSha256'])
        with self.assertRaises(ValueError):
            offline.checked_proposal(directory, '0' * 64)
        plan['createArgs'][plan['createArgs'].index('--network') + 1] = 'bridge'
        # Simulate even a newly rehashed but unsafe candidate: profile checks
        # still reject the widened network before any workload is possible.
        encoded = json.dumps(plan)
        original = Path.read_text
        def altered(path, *args, **kwargs):
            return encoded if path == directory / 'offline-plan.json' else original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', altered), self.assertRaisesRegex(ValueError, 'profile changed'):
            offline.checked_proposal(directory, summary['planSha256'])

    def test_engine_fingerprint_changes_only_with_engine_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'CMakeLists.txt').write_text('project(strata VERSION 0.1.44.1)')
            (root / 'src').mkdir()
            (root / 'src/engine.cpp').write_text('synthetic engine source')
            (root / 'setup.py').write_text('raise RuntimeError("must not import")')
            baseline = offline.source_identity(root)
            (root / 'README.md').write_text('irrelevant documentation')
            self.assertEqual(offline.source_identity(root), baseline)
            (root / 'src/engine.cpp').write_text('changed engine source')
            self.assertNotEqual(offline.source_identity(root), baseline)


if __name__ == '__main__':
    unittest.main()
