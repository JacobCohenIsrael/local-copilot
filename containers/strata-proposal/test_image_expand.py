import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import image_download as downloads
import image_expand as expand
import image_process_rehearsal as process


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.time = 100
        self.guard = lambda: True
        self.context = downloads.Context(downloads.Limits(1024**2, 1024**2, 0, 10, 3),
                                         lambda: self.guard(), lambda: self.time)

    def layer(self, raw=b'synthetic-stream' * 100, *, packed=None, expected=None):
        data = gzip.compress(raw, mtime=0) if packed is None else packed
        spec = expand.Layer(downloads.Blob('sha256:' + hashlib.sha256(data).hexdigest(), len(data)),
                            hashlib.sha256(raw).hexdigest() if expected is None else expected)
        (self.cache / spec.blob.digest[7:]).write_bytes(data)
        return spec

    def verify(self, specs, *, layer=200000, total=400000):
        return expand._verify(self.cache, specs, expand.Limits(layer, total), self.context)

    def test_exact_limits_verify_two_layers_without_writing_expanded_output(self):
        first, second = self.layer(b'a' * 1000), self.layer(b'b' * 2000)
        before = set(self.cache.iterdir())
        result = self.verify([first, second], layer=2000, total=3000)
        self.assertEqual(result['expandedBytes'], 3000)
        self.assertEqual([r['expandedBytes'] for r in result['layers']], [1000, 2000])
        self.assertEqual(set(self.cache.iterdir()), before)
        self.assertFalse(result['extracted'])
        self.assertFalse(result['dockerDiskUsageBounded'])

    def test_per_layer_overflow_stops_at_first_extra_byte(self):
        spec = self.layer(b'a' * 200000)
        with self.assertRaisesRegex(downloads.StageError, 'EXPANDED_BYTE_LIMIT'):
            self.verify([spec], layer=100, total=1000)

    def test_aggregate_overflow_in_second_layer(self):
        specs = [self.layer(b'a' * 1000), self.layer(b'b' * 1000)]
        with self.assertRaisesRegex(downloads.StageError, 'EXPANDED_BYTE_LIMIT'):
            self.verify(specs, layer=1000, total=1999)

    def test_full_output_buffers_are_drained_with_capped_inflate_calls(self):
        raw = b'a' * 262144
        spec = self.layer(raw)
        original = expand.zlib.decompressobj
        sizes = []
        class Capped:
            def __init__(self, *args):
                self.inner = original(*args)
            def __getattr__(self, key):
                return getattr(self.inner, key)
            def decompress(self, data, maximum):
                sizes.append(maximum)
                output = self.inner.decompress(data, maximum)
                self_test.assertLessEqual(len(output), maximum)
                return output
        self_test = self
        with patch.object(expand.zlib, 'decompressobj', Capped):
            result = self.verify([spec], layer=len(raw), total=len(raw))
        self.assertEqual(result['expandedBytes'], len(raw))
        self.assertTrue(all(0 < size <= downloads.CHUNK for size in sizes))
        self.assertGreater(len(sizes), 3)

    def test_wrong_diff_id_rejected(self):
        with self.assertRaisesRegex(downloads.StageError, 'DIFF_ID_MISMATCH'):
            self.verify([self.layer(expected='0' * 64)])

    def test_compressed_hash_is_rechecked_during_expansion(self):
        spec = self.layer(b'abc')
        changed = bytearray((self.cache / spec.blob.digest[7:]).read_bytes())
        changed[4] ^= 1  # Change only gzip mtime, keep expanded bytes/CRC valid.
        (self.cache / spec.blob.digest[7:]).write_bytes(changed)
        with self.assertRaisesRegex(downloads.StageError, 'CACHE_CHANGED'):
            self.verify([spec])

    def test_truncation_header_and_crc_corruption_rejected(self):
        packed = gzip.compress(b'abc', mtime=0)
        for data, code in ((packed[:-1], 'GZIP_TRUNCATED'),
                           (b'xx' + packed[2:], 'GZIP_INVALID'),
                           (packed[:-8] + b'\xff' * 4 + packed[-4:], 'GZIP_INVALID')):
            with self.subTest(code=code):
                with self.assertRaisesRegex(downloads.StageError, code):
                    self.verify([self.layer(b'abc', packed=data)])

    def test_trailing_data_and_concatenated_gzip_rejected(self):
        packed = gzip.compress(b'abc', mtime=0)
        for data in (packed + b'\x00', packed * 2):
            with self.assertRaisesRegex(downloads.StageError, 'GZIP_TRAILING_DATA'):
                self.verify([self.layer(b'abc', packed=data)])

    def test_trailing_member_in_next_input_chunk_rejected(self):
        spec = self.layer(b'abc', packed=gzip.compress(b'abc', mtime=0) * 2)
        with patch.object(downloads, 'CHUNK', len(gzip.compress(b'abc', mtime=0))):
            with self.assertRaisesRegex(downloads.StageError, 'GZIP_TRAILING_DATA'):
                self.verify([spec])

    def test_cancel_and_deadline_during_inflate(self):
        spec = self.layer()
        original = expand.zlib.decompressobj
        for event, code in (('cancel', 'GUARD_PERMISSION_LOST'), ('time', 'STAGING_DEADLINE')):
            self.guard, self.time = lambda: True, 100
            class Interrupted:
                def __init__(inner, *args):
                    inner.inner = original(*args)
                def __getattr__(inner, key):
                    return getattr(inner.inner, key)
                def decompress(inner, data, maximum):
                    output = inner.inner.decompress(data, maximum)
                    if event == 'cancel':
                        self.guard = lambda: False
                    else:
                        self.time = 105
                    return output
            with patch.object(expand.zlib, 'decompressobj', Interrupted):
                with self.assertRaisesRegex(downloads.StageError, code):
                    self.verify([spec])

    def test_changed_size_and_missing_cache_rejected(self):
        spec = self.layer()
        path = self.cache / spec.blob.digest[7:]
        path.write_bytes(b'x')
        with self.assertRaisesRegex(downloads.StageError, 'CACHE_CHANGED'):
            self.verify([spec])
        path.unlink()
        with self.assertRaisesRegex(downloads.StageError, 'CACHE_CHANGED'):
            self.verify([spec])

    def test_hardlinked_cache_rejected(self):
        spec = self.layer()
        (self.cache / 'alias').hardlink_to(self.cache / spec.blob.digest[7:])
        with self.assertRaisesRegex(ValueError, 'hard links'):
            self.verify([spec])

    def test_invalid_contracts_fail_before_read(self):
        spec = self.layer()
        for specs in ([], [spec] * 2, [None]):
            with self.assertRaisesRegex(downloads.StageError, 'LAYER_CONTRACT_INVALID'):
                self.verify(specs)
        for values in ((0, 1), (2, 1), (True, 100), (1, float('inf'))):
            with self.assertRaisesRegex(downloads.StageError, 'EXPANSION_LIMITS_INVALID'):
                expand.Limits(*values)


class ProcessControlTests(unittest.TestCase):
    def test_unconfirmed_stop_never_reports_success(self):
        child = Mock()
        child.wait.side_effect = process.subprocess.TimeoutExpired('fixed-fixture', .1)
        child.poll.return_value = None
        self.assertFalse(process.stop_child(child))
        child.terminate.assert_called_once_with()
        child.kill.assert_called_once_with()
        self.assertEqual(child.wait.call_count, 3)

    def test_successful_escalation_uses_owned_handle(self):
        child = Mock()
        child.wait.side_effect = [process.subprocess.TimeoutExpired('fixed-fixture', .1), 1]
        child.poll.return_value = 1
        self.assertTrue(process.stop_child(child))
        child.terminate.assert_called_once_with()
        child.kill.assert_not_called()

    def test_journal_failure_after_launch_still_stops_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / ('a' * 32) / 'success'
            directory.mkdir(parents=True)
            child = Mock(pid=123)
            child.poll.return_value = None
            with patch.object(process, 'ROOT', root), patch.object(process, 'launch', return_value=child), \
                    patch.object(process.downloads.tools.base, 'atomic', side_effect=[None, OSError('disk'),
                                                                                     OSError('disk'), OSError('disk')]), \
                    patch.object(process, 'stop_child', return_value=True) as stop:
                with self.assertRaises(OSError):
                    process.supervise(directory)
                self.assertTrue(stop.called)
                self.assertTrue(all(call.args == (child,) for call in stop.call_args_list))

    def test_lease_uses_observed_growth_not_modified_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pulse'
            lease = process.Lease(100)
            path.write_bytes(b'x')
            lease.observe(path, 100)
            path.touch()
            with self.assertRaisesRegex(downloads.StageError, 'CONTROLLER_LEASE_LOST'):
                lease.observe(path, 101)

    def test_lease_rejects_regression_and_oversized_counter(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pulse'
            lease = process.Lease(100)
            for now in (99, float('nan')):
                with self.assertRaisesRegex(downloads.StageError, 'CLOCK_INVALID'):
                    lease.observe(path, now)
            path.write_bytes(b'x' * 257)
            with self.assertRaisesRegex(downloads.StageError, 'CONTROLLER_LEASE_INVALID'):
                process.Lease(100).observe(path, 100)

    def test_child_cli_cannot_accept_arbitrary_namespace_or_command(self):
        for path in (process.ROOT / 'success', process.ROOT / ('a' * 32) / 'live',
                     Path('C:/arbitrary/success')):
            with self.assertRaisesRegex(downloads.StageError, 'SYNTHETIC_NAMESPACE_INVALID'):
                process.owned(path)

    def test_fault_state_rejects_restart_before_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / ('a' * 32) / 'read-deadline'
            directory.mkdir(parents=True)
            (directory / 'state.json').write_text(json.dumps({'state': 'FAULT'}))
            with patch.object(process, 'ROOT', root), patch.object(process, 'launch') as launch:
                with self.assertRaisesRegex(downloads.StageError, 'REHEARSAL_RESTART_REJECTED'):
                    process.supervise(directory)
                launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
