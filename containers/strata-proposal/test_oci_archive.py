from dataclasses import replace
import io
import tarfile
import unittest
from unittest.mock import Mock, patch

import import_rehearsal as rehearsal
import oci_archive as archive


class ArchiveTransportTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.blobs = rehearsal.fixture()
        self.exact = archive.archive_bytes(self.rows)

    def stream(self, sink=None, **kwargs):
        return archive.stream(self.rows, lambda sha: io.BytesIO(self.blobs[sha]),
            io.BytesIO() if sink is None else sink,
            guard=kwargs.get('guard', lambda: True), maximum_bytes=kwargs.get('maximum_bytes', self.exact))

    def test_archive_is_readable_and_contains_original_compressed_blobs(self):
        sink = io.BytesIO()
        result = self.stream(sink)
        self.assertEqual(result['archiveBytes'], self.exact)
        self.assertFalse(result['extracted'])
        with tarfile.open(fileobj=io.BytesIO(sink.getvalue()), mode='r:') as tar:
            self.assertEqual(tar.getnames(), [r.name for r in self.rows])
            for row in self.rows:
                self.assertEqual(tar.extractfile(row.name).read(), row.inline or self.blobs[row.sha256])
                self.assertEqual(tar.getmember(row.name).mtime, 0)
                self.assertTrue(tar.getmember(row.name).isfile())
        second = io.BytesIO()
        self.stream(second)
        self.assertEqual(sink.getvalue(), second.getvalue())

    def test_short_writes_do_not_lose_data_or_exceed_exact_ceiling(self):
        sink = rehearsal.Sink(capacity=self.exact, partial=1)
        self.stream(sink)
        expected = io.BytesIO()
        self.stream(expected)
        self.assertEqual(bytes(sink.data), expected.getvalue())

    def test_invalid_sink_counts_fail_without_spinning(self):
        for count in (None, 0, -1, True, 513):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'OCI_SINK_FAILED'):
                self.stream(Mock(write=Mock(return_value=count)))

    def test_output_limit_must_match_exact_metadata_before_any_read(self):
        for cap in (self.exact - 1, self.exact + 1, True):
            with self.subTest(cap=cap), self.assertRaisesRegex(ValueError, 'OCI_OUTPUT_LIMIT'):
                self.stream(maximum_bytes=cap)

    def test_guard_failure_prevents_even_the_first_byte(self):
        sink = io.BytesIO()
        with self.assertRaisesRegex(ValueError, 'OCI_GUARD_LOST'):
            self.stream(sink, guard=lambda: False)
        self.assertEqual(sink.getvalue(), b'')

    def test_link_and_path_traversal_cannot_be_declared(self):
        for name in ('../cache', '/root', 'blobs/sha256/../../x', 'blobs/sha256/' + 'A' * 64):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'OCI_MEMBER_INVALID'):
                archive.archive_bytes((*self.rows[:-1], replace(self.rows[-1], name=name)))

    def test_duplicate_member_digest_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'OCI_MEMBER_SET_INVALID'):
            archive.archive_bytes((*self.rows, self.rows[-1]))

    def test_changed_inline_metadata_rejected_before_output(self):
        rows = (replace(self.rows[0], inline=b'X' * self.rows[0].size), *self.rows[1:])
        with self.assertRaisesRegex(ValueError, 'OCI_MEMBER_INVALID'):
            archive.archive_bytes(rows)

    def test_blob_reads_are_bounded_and_no_read_after_guard_loss(self):
        opened = Mock(side_effect=AssertionError('Cache must remain unopened'))
        with self.assertRaisesRegex(ValueError, 'OCI_GUARD_LOST'):
            archive.stream(self.rows, opened, io.BytesIO(), guard=lambda: False, maximum_bytes=self.exact)
        opened.assert_not_called()

    def test_all_injected_transport_failures_are_rejected(self):
        result = rehearsal.exercise()
        self.assertEqual(result['caseCount'], 7)
        self.assertFalse(result['nativeDiskQuotaProven'])
        self.assertFalse(result['nativeDaemonShutdownProven'])
        self.assertTrue(all(r['result'] == 'REJECTED' for r in result['cases'][1:]))

    def test_blob_path_must_match_hash_contract(self):
        with self.assertRaisesRegex(ValueError, 'OCI_MEMBER_INVALID'):
            archive.archive_bytes((*self.rows[:-1], replace(self.rows[-1], sha256='0' * 64)))

    def test_oversized_or_nonbyte_source_reads_rejected(self):
        for raw in (b'X' * 65537, None, 'text'):
            source = Mock()
            source.__enter__ = Mock(return_value=source)
            source.__exit__ = Mock(return_value=False)
            source.read = Mock(return_value=raw)
            with self.subTest(raw=type(raw).__name__), self.assertRaisesRegex(ValueError, 'OCI_BLOB_SIZE_CHANGED'):
                archive.stream(self.rows, lambda sha: source, io.BytesIO(),
                               guard=lambda: True, maximum_bytes=self.exact)


if __name__ == '__main__':
    unittest.main()
