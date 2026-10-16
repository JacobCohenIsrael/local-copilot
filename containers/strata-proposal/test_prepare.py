import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import prepare


class ArchiveTests(unittest.TestCase):
    def test_rejects_archive_escape_alias_and_symlink_before_writing(self):
        root = prepare.ROOT / '.runtime/source-preparation-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            folder = Path(folder)
            folder.resolve().relative_to(root.resolve())  # Validate cleanup scope before recursive removal.
            for index, names in enumerate([['repo/../escape'], ['repo/C:/escape'], ['repo/x', 'repo/X'], ['other/x'], ['repo/NUL.txt']]):
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, 'w') as output:
                    for name in names:
                        output.writestr(name, 'data')
                archive.seek(0)
                target = folder / str(index)
                with self.assertRaises(ValueError):
                    prepare.extract(archive, target, 'repo')
                self.assertFalse(target.exists())
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as output:
                entry = zipfile.ZipInfo('repo/link')
                entry.external_attr = 0o120777 << 16
                output.writestr(entry, '../secret')
            archive.seek(0)
            with self.assertRaises(ValueError):
                prepare.extract(archive, folder / 'link-case', 'repo')


if __name__ == '__main__':
    unittest.main()
