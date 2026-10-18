import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import image_recovery as recovery


class RecoveryPreservationTests(unittest.TestCase):
    def test_previous_fault_helpers_and_receipts_are_bound_without_resetting(self):
        before = recovery.file_tree(recovery.PREVIOUS)
        record = recovery.binding()
        self.assertEqual(record['treeSha256'], recovery.build.sha(before))
        self.assertEqual(record['phase'], 'FAULT')
        self.assertFalse(record['resetPreviousAttempt'])
        self.assertTrue(record['stopConfirmed'])
        self.assertEqual(recovery.file_tree(recovery.PREVIOUS), before)
        self.assertNotEqual(recovery.NEXT, recovery.PREVIOUS)

    def test_extra_missing_changed_or_linked_previous_evidence_denies_recovery(self):
        for mode in ('extra', 'missing', 'changed', 'linked'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for path in recovery.PREVIOUS.rglob('*'):
                    destination = root / path.relative_to(recovery.PREVIOUS)
                    if path.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(path.read_bytes())
                if mode == 'extra':
                    (root / 'unexpected').write_bytes(b'x')
                elif mode == 'missing':
                    (root / 'state.json').unlink()
                elif mode == 'changed':
                    (root / 'state.json').write_bytes(b'{}')
                else:
                    os.link(root / 'state.json', root / 'linked-state')
                with patch.object(recovery, 'PREVIOUS', root), self.assertRaises(ValueError):
                    recovery.binding()

    def test_proposal_cannot_reset_expand_attempt_count_or_enable_work(self):
        original = json.loads(recovery.PROPOSAL.read_bytes())
        for key, value in [('resetPreviousAttempt', True), ('automaticRetry', True), ('maximumNewAttempts', 2),
                           ('maximumNewAttempts', True), ('imageDownloadEnabled', True), ('imageImportEnabled', True),
                           ('buildEnabled', True), ('modelLaunchEnabled', True), ('version', True)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'proposal.json'
                path.write_text(json.dumps({**original, key: value}))
                with patch.object(recovery, 'PROPOSAL', path), self.assertRaises(ValueError):
                    recovery.binding()


if __name__ == '__main__':
    unittest.main()
