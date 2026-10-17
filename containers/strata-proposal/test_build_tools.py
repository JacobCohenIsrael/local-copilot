import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import stage_build_tools as tools


class BuildToolTests(unittest.TestCase):
    def payload(self, data):
        return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def test_exact_payload_and_truncation_overrun_hash_failure(self):
        data = b'bounded tool payload'
        output = io.BytesIO()
        tools.copy_payload(io.BytesIO(data), output, self.payload(data))
        self.assertEqual(output.getvalue(), data)
        for body in (data[:-1], data + b'x', b'X' * len(data)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                tools.copy_payload(io.BytesIO(body), io.BytesIO(), self.payload(data))

    def test_payload_deadline_stops_before_writing_late_bytes(self):
        clock = iter((0, 0, 121))
        output = io.BytesIO()
        with self.assertRaises(TimeoutError):
            tools.copy_payload(io.BytesIO(b'x'), output, self.payload(b'x'), clock=lambda: next(clock))
        self.assertEqual(output.getvalue(), b'')

    def archives(self, root, unsafe=None):
        rows = []
        elf = b'\x7fELF\x02\x01' + b'\0' * 12 + b'\x3e\x00' + b'synthetic, not executable'
        for name in ('cmake', 'ninja'):
            path = root / (name + '.whl')
            with zipfile.ZipFile(path, 'w') as archive:
                binary_path = f'{name}/data/bin/{name}' if name == 'cmake' else 'ninja-1.13.2.data/scripts/ninja'
                archive.writestr(binary_path, elf)
                archive.writestr(f'{name}/__init__.py', 'raise RuntimeError("must never import")')
                archive.writestr(f'{name}-1.dist-info/licenses/LICENSE', 'synthetic license')
                if unsafe and name == 'ninja':
                    archive.writestr(unsafe, 'bad')
            rows.append((name, path))
        return rows

    def test_extracts_native_data_and_licenses_without_python_wrappers(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(tools, 'reserve'):
            root = Path(folder)
            records = tools.unpack(self.archives(root), root / 'staged')
            self.assertTrue((root / 'staged/cmake/bin/cmake').is_file())
            self.assertFalse(any('__init__.py' in r['path'] for r in records))
            self.assertTrue(any(r['path'].startswith('licenses/') for r in records))

    def test_unsafe_archives_and_expansion_limit_fail_before_any_extraction(self):
        for path in ('../escape', '/absolute', 'ninja/data/bin/CON', 'ninja/data/bin/ninja'):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                with self.assertRaises(ValueError):
                    tools.unpack(self.archives(root, path), root / 'out')
                self.assertFalse((root / 'out').exists())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                tools.unpack(self.archives(root), root / 'out', expanded_limit=1)
            self.assertFalse((root / 'out').exists())

    def test_reserved_disk_space_and_redirects_are_enforced(self):
        with patch.object(tools.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 0})()):
            with self.assertRaises(ValueError):
                tools.reserve(Path('.'))
        with self.assertRaises(ValueError):
            tools.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere/')

    def test_lock_rejects_unapproved_download_host_and_total_budget(self):
        original = json.loads((tools.HERE / 'build-tools.lock.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original['tools'][0]['url'] = original['tools'][0]['url'].replace('files.pythonhosted.org', 'elsewhere.example')
            (root / 'build-tools.lock.json').write_text(json.dumps(original))
            with patch.object(tools, 'HERE', root), self.assertRaises(ValueError):
                tools.lock()

    def test_repeated_staging_cannot_grow_past_combined_budget(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(tools, 'ROOT', Path(folder)):
            with patch.object(tools, 'root_usage', return_value=tools.ROOT_BYTES_LIMIT), patch.object(tools, 'download') as download:
                with self.assertRaises(ValueError):
                    tools.stage(fetch=True)
                download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
