import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

import artifact_export as export

META = b'{"source":"synthetic-only"}'
SHA = hashlib.sha256(META).hexdigest()


def elf(kind=2):
    data = bytearray(64)
    data[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI', data, 16, kind, 62, 1)
    struct.pack_into('<H', data, 52, 64)
    return bytes(data)


def archive(rows=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, payload, kind in rows if rows is not None else [
                ('engine', b'', tarfile.DIRTYPE), ('engine/strata', elf(), tarfile.REGTYPE),
                ('engine/libstrata_kq.so', elf(3), tarfile.REGTYPE), ('engine/BUILD.json', META, tarfile.REGTYPE)]:
            info = tarfile.TarInfo(name)
            info.type, info.size = kind, len(payload)
            info.mode = 0o7777
            tar.addfile(info, io.BytesIO(payload))
    return data.getvalue()


class Transport:
    def __init__(self, data, fail_verify=None, fail_ack=False):
        self.data, self.fail_verify, self.fail_ack = data, fail_verify, fail_ack
        self.calls = []
        self.checks = 0

    def verify(self):
        self.calls.append('verify')
        self.checks += 1
        return self.checks != self.fail_verify

    def copy(self, path, deadline):
        self.calls.append('copy')
        path.write_bytes(self.data)

    def acknowledge(self, deadline):
        self.calls.append('ack')
        if self.fail_ack:
            raise TimeoutError('simulated ack outage')


class ArtifactExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reserve = patch.object(export.tools, 'reserve')
        self.reserve.start()
        self.namespace = patch.object(export, 'ROOT', self.root / 'exports')
        self.namespace.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.reserve.stop)
        self.addCleanup(self.namespace.stop)

    def unpack(self, data):
        path = self.root / 'sample.tar'
        path.write_bytes(data)
        return export.unpack_archive(path, self.root / 'files', SHA, time.monotonic() + 3)

    def collect(self, transport, **kwargs):
        return export.collect(transport, container_id='a' * 64, plan_sha256='b' * 64,
                              metadata_sha256=SHA, synthetic=True, **kwargs)

    def receipt(self):
        return json.loads(next(export.ROOT.glob('*/result.json')).read_text())

    def test_success_hashes_before_ack_and_provenance(self):
        transport = Transport(archive())
        folder, receipt = self.collect(transport)
        self.assertEqual(transport.calls, ['verify', 'copy', 'verify', 'verify', 'ack'])
        self.assertEqual(receipt['state'], 'ARTIFACTS_SAVED_ACK_SENT')
        self.assertTrue(receipt['synthetic'])
        self.assertFalse(receipt['buildEnabled'])
        self.assertEqual({r['path'] for r in receipt['files']}, set(export.LIMITS))
        for row in receipt['files']:
            self.assertEqual(hashlib.sha256((folder / 'files' / row['path']).read_bytes()).hexdigest(), row['sha256'])

    def test_optional_library_not_required(self):
        rows = [('engine/strata', elf(), tarfile.REGTYPE), ('engine/BUILD.json', META, tarfile.REGTYPE)]
        self.assertEqual(len(self.unpack(archive(rows))), 2)

    def test_paths_and_entry_types_fail_closed(self):
        bad = [('engine/../strata', tarfile.REGTYPE), ('engine/STRATA', tarfile.REGTYPE),
               ('/engine/strata', tarfile.REGTYPE), ('engine/a/b', tarfile.REGTYPE),
               ('engine/strata:alternate', tarfile.REGTYPE), ('engine/strata', tarfile.SYMTYPE),
               ('engine/strata', tarfile.LNKTYPE), ('engine/strata', tarfile.FIFOTYPE),
               ('engine/strata', tarfile.XHDTYPE), ('engine/strata', tarfile.GNUTYPE_LONGNAME),
               ('engine/strata', tarfile.GNUTYPE_SPARSE)]
        for name, kind in bad:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / 'sample.tar'
                path.write_bytes(archive([(name, b'', kind)]))
                with self.assertRaises(ValueError):
                    export.unpack_archive(path, root / 'files', SHA, time.monotonic() + 3)

    def test_duplicate_or_missing_files_rejected(self):
        for rows in [[('engine/strata', elf(), tarfile.REGTYPE)] * 2, []]:
            transport = Transport(archive(rows))
            with self.assertRaises(ValueError):
                self.collect(transport)
            self.assertNotIn('ack', transport.calls)

    def test_wrong_metadata_or_elf_never_acknowledged(self):
        for payload, meta in [(b'not an engine', META), (elf(), b'{}')]:
            transport = Transport(archive([('engine/strata', payload, tarfile.REGTYPE),
                                           ('engine/BUILD.json', meta, tarfile.REGTYPE)]))
            with self.assertRaises(ValueError):
                self.collect(transport)
            self.assertNotIn('ack', transport.calls)
            self.assertEqual(self.receipt()['state'], 'EXPORT_FAULT')

    def test_identity_or_lease_loss_at_each_boundary(self):
        for check in (1, 2, 3):
            transport = Transport(archive(), fail_verify=check)
            with self.assertRaises(ValueError):
                self.collect(transport)
            self.assertNotIn('ack', transport.calls)
            if check == 1:
                self.assertNotIn('copy', transport.calls)

    def test_ack_failure_preserves_files_with_unconfirmed_status(self):
        transport = Transport(archive(), fail_ack=True)
        with self.assertRaises(TimeoutError):
            self.collect(transport)
        receipt = self.receipt()
        self.assertFalse(receipt['acknowledged'])
        self.assertTrue(receipt['acknowledgementAttempted'])
        self.assertEqual(len(receipt['files']), 3)
        self.assertEqual(receipt['state'], 'EXPORT_FAULT')

    def test_oversize_header_rejected_before_payload_read(self):
        info = tarfile.TarInfo('engine/strata')
        info.size = export.LIMITS['strata'] + 1
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.unpack(info.tobuf(format=tarfile.USTAR_FORMAT))
        self.assertFalse((self.root / 'files/strata').exists())

    def test_wire_limit_checked_before_extraction(self):
        with patch.object(export, 'WIRE_LIMIT', 512), self.assertRaisesRegex(ValueError, 'size/alignment'):
            self.unpack(archive())
        self.assertFalse((self.root / 'files').exists())

    def test_truncation_bad_checksum_and_trailing_data_rejected(self):
        data = archive()
        for damaged in (data[:700], b'x' + data[1:], data[:-512] + b'x' * 512, data[:1024]):
            transport = Transport(damaged)
            with self.assertRaises((ValueError, tarfile.HeaderError)):
                self.collect(transport)
            self.assertNotIn('ack', transport.calls)

    def test_deadline_expiry_never_acknowledged(self):
        transport = Transport(archive())
        with self.assertRaises(TimeoutError):
            self.collect(transport, deadline=0)
        self.assertNotIn('copy', transport.calls)
        self.assertNotIn('ack', transport.calls)

    def test_aggregate_reservation_counts_failed_attempts(self):
        with patch.object(export, 'ROOT_LIMIT', export.SESSION_RESERVATION - 1):
            with self.assertRaisesRegex(ValueError, 'capacity'):
                self.collect(Transport(archive()))

    def test_existing_destination_not_overwritten(self):
        (self.root / 'files').mkdir()
        with self.assertRaises(FileExistsError):
            self.unpack(archive())

    def test_expired_copy_cannot_launch_tar(self):
        with patch.object(export.subprocess, 'Popen') as popen, self.assertRaises(TimeoutError):
            export.capture_archive('a' * 64, self.root / 'out', 0)
        popen.assert_not_called()
        self.assertFalse((self.root / 'out').exists())

    def test_invalid_container_identity_rejected_before_process(self):
        with patch.object(export.subprocess, 'Popen') as popen, self.assertRaises(ValueError):
            export.capture_archive('mutable-name', self.root / 'out', time.monotonic() + 1)
        popen.assert_not_called()

    def test_binary_transport_caps_stdout_without_large_memory_buffer(self):
        original = subprocess.Popen
        def start(*args, **kwargs):
            return original([sys.executable, '-I', '-B', '-c', 'import sys; sys.stdout.buffer.write(b"x" * 4096)'], **kwargs)
        output = self.root / 'out'
        with patch.object(export, 'WIRE_LIMIT', 512), patch.object(export.subprocess, 'Popen', side_effect=start):
            with self.assertRaisesRegex(ValueError, 'wire limit'):
                export.capture_archive('a' * 64, output, time.monotonic() + 3)
        self.assertLessEqual(output.stat().st_size, 512)

    def test_docker_diagnostic_is_capped(self):
        original = subprocess.Popen
        def start(*args, **kwargs):
            return original([sys.executable, '-I', '-B', '-c', 'import sys; sys.stderr.buffer.write(b"x" * 8192)'], **kwargs)
        with patch.object(export.subprocess, 'Popen', side_effect=start):
            with self.assertRaisesRegex(ValueError, 'diagnostic exceeds'):
                export.capture_archive('a' * 64, self.root / 'out', time.monotonic() + 3)

    def test_only_fixed_non_root_tar_and_touch_commands_allowed(self):
        original = subprocess.Popen
        def start(command, **kwargs):
            self.assertEqual(command, [export.build_guard.base.DOCKER, 'exec', '--user', '65532:65532',
                '--workdir', '/work', 'a' * 64, '/bin/tar', '-cf', '-', 'engine'])
            return original([sys.executable, '-I', '-B', '-c', 'pass'], **kwargs)
        with patch.object(export.subprocess, 'Popen', side_effect=start):
            export.capture_archive('a' * 64, self.root / 'out', time.monotonic() + 3)
        with patch.object(export.subprocess, 'run') as run:
            export.acknowledge_export('a' * 64, time.monotonic() + 3)
            self.assertEqual(run.call_args.args[0], [export.build_guard.base.DOCKER, 'exec', '--user',
                '65532:65532', 'a' * 64, '/bin/touch', '/work/export.complete'])
            with self.assertRaises(ValueError):
                export.acknowledge_export('mutable-name', time.monotonic() + 3)
            self.assertEqual(run.call_count, 1)

    def test_silent_copy_timeout_is_failure(self):
        original = subprocess.Popen
        def start(*args, **kwargs):
            return original([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(5)'], **kwargs)
        with patch.object(export.subprocess, 'Popen', side_effect=start):
            with self.assertRaises((TimeoutError, subprocess.TimeoutExpired)):
                export.capture_archive('a' * 64, self.root / 'out', time.monotonic() + 0.2)


if __name__ == '__main__':
    unittest.main()
