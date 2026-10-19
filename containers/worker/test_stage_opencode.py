import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import uuid

import stage_opencode as stage


class StageOpenCodeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / '.runtime/stage-opencode-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.folder.name)
        self.root.resolve().relative_to(root.resolve())
        self.addCleanup(self.folder.cleanup)

    def archive(self, extra=None, *, binary=None, version=stage.VERSION):
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        header[18:20] = b'\x3e\x00'
        data = {'package/package.json': json.dumps({'name': stage.PACKAGE, 'version': version,
                                                  'os': ['linux'], 'cpu': ['x64']}).encode(),
                'package/bin/opencode': bytes(header) if binary is None else binary}
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w:gz') as tar:
            for name, content in data.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
            if extra:
                member = tarfile.TarInfo(extra)
                member.type = tarfile.SYMTYPE if extra.endswith('link') else tarfile.REGTYPE
                member.linkname = '../outside'
                tar.addfile(member, io.BytesIO())
        path = self.root / (uuid.uuid4().hex + '.tgz')
        path.write_bytes(output.getvalue())
        return path

    def test_only_pinned_package_and_linux_elf_are_staged(self):
        target = self.root / 'valid'
        result = stage.unpack(self.archive(), target)
        self.assertEqual(result['binaryBytes'], 64)
        self.assertEqual(len(result['binarySha256']), 64)
        self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()},
                         {'package.json', 'staged/opencode'})
        with self.assertRaisesRegex(ValueError, 'NO_OVERWRITE'):
            stage.unpack(self.archive(), target)

    def test_paths_links_duplicates_and_identity_are_rejected(self):
        for index, name in enumerate(['package/../outside', '/absolute', 'package/bin/link',
                                       'package/bin/OPENCODE', 'package/bin/opencode']):
            with self.subTest(name=name), self.assertRaises(ValueError):
                stage.unpack(self.archive(name), self.root / str(index))
        with self.assertRaisesRegex(ValueError, 'PACKAGE_IDENTITY_MISMATCH'):
            stage.unpack(self.archive(version='latest'), self.root / 'wrong-version')
        with self.assertRaisesRegex(ValueError, 'NOT_LINUX_X64_ELF'):
            stage.unpack(self.archive(binary=b'not ELF'), self.root / 'bad-elf')
        self.assertFalse((self.root / 'outside').exists())

    def test_archive_integrity_and_fetch_allowlist(self):
        archive = self.root / 'tampered.tgz'
        archive.write_bytes(b'incorrect archive')
        with self.assertRaisesRegex(ValueError, 'PUBLISHED_SHA512_MISMATCH'):
            stage.verify_archive(archive)
        with self.assertRaisesRegex(ValueError, 'FIXED_URL_REQUIRED'):
            stage.fetch('https://example.com/arbitrary', self.root / 'download', 100)


if __name__ == '__main__':
    unittest.main()
