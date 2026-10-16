from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import task_bundle as bundle


class TaskBundleTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / '.runtime' / 'bundle-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temporary.name)
        self.root.resolve().relative_to(root.resolve())
        self.addCleanup(self.temporary.cleanup)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.store = self.root / 'sessions'
        self.replacement = patch.object(bundle, 'ROOT', self.store)
        self.replacement.start()
        self.addCleanup(self.replacement.stop)
        (self.source / 'fix.py').write_bytes(b'answer = 1\n')

    def prepare(self, files=None, **extra):
        request = {'sourceRoot': str(self.source), 'files': files or ['fix.py'],
                   'task': 'Change answer to two.'}
        request.update(extra)
        return bundle.prepare(request)

    def test_patch_applies_and_original_is_unchanged(self):
        result = self.prepare()
        workspace = Path(result['workspace'])
        (workspace / 'fix.py').write_bytes(b'answer = 2\n')
        collected = bundle.collect(result['runId'])
        self.assertEqual(collected['changedFiles'], ['fix.py'])
        self.assertFalse(collected['applied'])
        self.assertFalse(result['executionEnabled'])
        patch_path = self.root / 'result.patch'
        patch_path.write_bytes(collected['patch'].encode('utf-8'))
        subprocess.run(['git', 'apply', '--check', str(patch_path)], cwd=self.source, check=True,
                       capture_output=True)
        self.assertEqual((self.source / 'fix.py').read_bytes(), b'answer = 1\n')

    def test_newline_space_unicode_and_empty_deletion_patches(self):
        name = 'small space é.py'
        for before, after in [(b'x=1', b'x=2'), (b'', None), (b'hello\r\n', None)]:
            (self.source / name).write_bytes(before)
            result = self.prepare(files=[name])
            target = Path(result['workspace']) / name
            if after is None:
                target.unlink()
            else:
                target.write_bytes(after)
            collected = bundle.collect(result['runId'])
            patch_path = self.root / 'result.patch'
            patch_path.write_bytes(collected['patch'].encode('utf-8'))
            subprocess.run(['git', 'apply', '--check', str(patch_path)], cwd=self.source,
                           check=True, capture_output=True)

    def test_reject_paths_aliases_and_unknown_fields_before_staging(self):
        for files in [['../secret'], ['C:/secret'], ['sub\\secret'], ['.git/config'],
                      ['NUL.txt'], ['fix.py', 'FIX.py'], ['fix.py/../fix.py']]:
            with self.assertRaises(ValueError):
                self.prepare(files=files)
        with self.assertRaises(ValueError):
            self.prepare(modelEnabled=True)
        self.assertFalse(self.store.exists())

    def test_input_and_task_budgets_and_binary_rejected(self):
        for data in [b'x' * (bundle.MAX_FILE_BYTES + 1), b'a\x00b', b'\xff']:
            (self.source / 'fix.py').write_bytes(data)
            with self.assertRaises(ValueError):
                self.prepare()
        with self.assertRaises(ValueError):
            self.prepare(task='x' * (bundle.MAX_TASK_CHARS + 1))
        self.assertFalse(self.store.exists())

    def test_output_growth_and_unapproved_path_rejected(self):
        result = self.prepare()
        workspace = Path(result['workspace'])
        (workspace / 'secret').write_text('unapproved')
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_OUTPUT_PATH'):
            bundle.collect(result['runId'])
        (workspace / 'secret').unlink()
        (workspace / 'fix.py').write_bytes(b'x' * (bundle.MAX_FILE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'FILE_BUDGET_EXCEEDED'):
            bundle.collect(result['runId'])

    def test_baseline_tampering_and_bad_run_id_rejected(self):
        result = self.prepare()
        (self.store / result['runId'] / 'baseline' / 'fix.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'BASELINE_CHANGED'):
            bundle.collect(result['runId'])
        with self.assertRaisesRegex(ValueError, 'INVALID_RUN_ID'):
            bundle.collect('../escape')

    def test_hard_link_input_and_output_rejected(self):
        alias = self.source / 'alias.py'
        alias.hardlink_to(self.source / 'fix.py')
        with self.assertRaisesRegex(ValueError, 'NOT_SINGLE_LINK_FILE'):
            self.prepare()
        alias.unlink()
        result = self.prepare()
        target = Path(result['workspace']) / 'fix.py'
        target.unlink()
        target.hardlink_to(self.source / 'fix.py')
        with self.assertRaisesRegex(ValueError, 'NOT_SINGLE_LINK_FILE'):
            bundle.collect(result['runId'])

    def test_total_and_patch_budgets(self):
        for name in ['one.py', 'two.py', 'three.py']:
            (self.source / name).write_bytes(b'x' * bundle.MAX_FILE_BYTES)
        with self.assertRaisesRegex(ValueError, 'TOTAL_BUDGET_EXCEEDED'):
            self.prepare(files=['one.py', 'two.py', 'three.py'])
        result = self.prepare(files=['one.py'])
        (Path(result['workspace']) / 'one.py').write_bytes(b'y' * bundle.MAX_FILE_BYTES)
        with self.assertRaisesRegex(ValueError, 'PATCH_BUDGET_EXCEEDED'):
            bundle.collect(result['runId'])


if __name__ == '__main__':
    unittest.main()
