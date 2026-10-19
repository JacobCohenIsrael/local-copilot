import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bundle_rehearsal as bridge
import task_bundle as bundle


class BundleRehearsalTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / '.runtime/bundle-bridge-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temporary.name)
        self.root.resolve().relative_to(root.resolve())
        self.addCleanup(self.temporary.cleanup)
        for module, value in [(bridge, self.root / 'runs'), (bundle, self.root / 'bundles')]:
            replacement = patch.object(module, 'ROOT', value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def worker(self, artifact, *, fake, scenario, bundle_id):
        self.assertTrue(fake)
        self.assertEqual(scenario, 'edit')
        self.bundle_id = bundle_id
        self.assertEqual(bundle.bounded_read(bundle.ROOT / bundle_id / 'workspace/example.py'), b'VALUE = 1\n')
        return {'cleanupConfirmed': True, 'containerExitCode': 0, 'oomKilled': False,
                'probe': {'compatibilityPassed': True, 'bundleInputUsed': True, 'timedOut': False,
                          'modelEnabled': False, 'strataContacted': False,
                          'outputFiles': {'example.py': base64.b64encode(b'VALUE = 2\n').decode()}}}

    def run_with(self, worker=None):
        with patch.object(bridge.verify_opencode, 'run', side_effect=worker or self.worker):
            return bridge.rehearse('fake-artifact-not-executed')

    def assert_copy_unchanged(self):
        self.assertEqual(bundle.bounded_read(bundle.ROOT / self.bundle_id / 'workspace/example.py'), b'VALUE = 1\n')

    def test_actual_bundle_collection_returns_valid_patch_without_touching_original(self):
        result = self.run_with()
        self.assertEqual(result['status'], 'PATCH_FOR_REVIEW')
        self.assertTrue(result['originalUnchanged'])
        self.assertTrue(result['cleanupConfirmed'])
        self.assertEqual(result['changedFiles'], ['example.py'])
        self.assertFalse(result['applied'])
        original = Path(result['runDirectory']) / 'original'
        self.assertEqual((original / 'example.py').read_bytes(), b'VALUE = 1\n')
        self.assertEqual({p.name for p in (bundle.ROOT / self.bundle_id / 'workspace').iterdir()}, {'example.py'})
        patch_path = self.root / 'result.patch'
        patch_path.write_bytes(result['patch'].encode())
        subprocess.run(['git', 'apply', '--check', str(patch_path)], cwd=original,
                       check=True, capture_output=True)
        saved = json.loads((Path(result['runDirectory']) / 'result.json').read_text())
        self.assertEqual(saved['patch'], result['patch'])

    def test_missing_cleanup_confirmation_blocks_import(self):
        def worker(*args, **kwargs):
            result = self.worker(*args, **kwargs)
            result['cleanupConfirmed'] = False
            return result
        result = self.run_with(worker)
        self.assertEqual(result['fault'], 'WORKER_CLEANUP_UNCONFIRMED')
        self.assertIsNone(result['patch'])
        self.assert_copy_unchanged()

    def test_unexpected_exported_paths_are_rejected_before_writing(self):
        def worker(*args, **kwargs):
            result = self.worker(*args, **kwargs)
            result['probe']['outputFiles']['../outside'] = 'eA=='
            return result
        result = self.run_with(worker)
        self.assertEqual(result['fault'], 'UNEXPECTED_EXPORTED_PATH')
        self.assertEqual(result['status'], 'FAULT')
        self.assert_copy_unchanged()

    def test_invalid_or_binary_or_oversized_exports_do_not_change_copy(self):
        for encoded in ['not-base64', base64.b64encode(b'a\x00b').decode(),
                        'x' * (4 * ((bundle.MAX_FILE_BYTES + 2) // 3) + 1)]:
            def worker(*args, **kwargs):
                result = self.worker(*args, **kwargs)
                result['probe']['outputFiles']['example.py'] = encoded
                return result
            result = self.run_with(worker)
            self.assertEqual(result['status'], 'FAULT')
            self.assertIsNone(result['patch'])
            self.assert_copy_unchanged()

    def test_baseline_change_during_worker_is_rejected_before_import(self):
        def worker(*args, **kwargs):
            result = self.worker(*args, **kwargs)
            (bundle.ROOT / self.bundle_id / 'baseline/example.py').write_bytes(b'tampered')
            return result
        result = self.run_with(worker)
        self.assertEqual(result['fault'], 'BASELINE_CHANGED')
        self.assert_copy_unchanged()

    def test_workspace_change_during_worker_is_rejected_before_import(self):
        def worker(*args, **kwargs):
            result = self.worker(*args, **kwargs)
            (bundle.ROOT / self.bundle_id / 'workspace/example.py').write_bytes(b'concurrent change')
            return result
        result = self.run_with(worker)
        self.assertEqual(result['fault'], 'PRISTINE_BUNDLE_REQUIRED')
        self.assertIsNone(result['patch'])
        self.assertEqual((bundle.ROOT / self.bundle_id / 'workspace/example.py').read_bytes(), b'concurrent change')

    def test_worker_without_bundle_proof_cannot_supply_output(self):
        def worker(*args, **kwargs):
            result = self.worker(*args, **kwargs)
            result['probe']['bundleInputUsed'] = False
            return result
        result = self.run_with(worker)
        self.assertEqual(result['fault'], 'FAKE_WORKER_FAILED')
        self.assert_copy_unchanged()

    def test_interrupt_saves_fault_without_returning_a_patch(self):
        def interrupted(*args, **kwargs):
            raise KeyboardInterrupt()
        result = self.run_with(interrupted)
        self.assertEqual(result['status'], 'FAULT')
        self.assertEqual(result['fault'], 'KeyboardInterrupt')
        self.assertIsNone(result['patch'])
        self.assertTrue(result['originalUnchanged'])


if __name__ == '__main__':
    unittest.main()
