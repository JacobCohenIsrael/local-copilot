import copy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import stage_opencode_runtime as runtime
import verify_opencode as verify


class VerifyOpenCodeTests(unittest.TestCase):
    def test_changed_container_identity_gpu_network_and_quota_are_rejected(self):
        source = Path('C:/test/input')
        info = {'Name': '/owned', 'Config': {'Labels': {'local-copilot.kind': 'opencode-version-only'},
                'Image': verify.IMAGE, 'User': '65532:65532', 'Entrypoint': ['python'],
                'Cmd': ['-B', '/input/probe.py']},
                'Mounts': [{'Source': str(source), 'Destination': '/input', 'RW': False}],
                'HostConfig': {'NanoCpus': 500000000, 'Memory': 536870912, 'MemorySwap': 536870912,
                    'PidsLimit': 64, 'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Runtime': 'runc',
                    'Privileged': False, 'CapDrop': ['ALL'], 'RestartPolicy': {'Name': 'no'},
                    'SecurityOpt': ['no-new-privileges'], 'Tmpfs': {'/tmp': 'rw,noexec,nosuid,size=64m'}}}
        verify.validate(info, 'owned', source)
        for field, value in [('DeviceRequests', [{'Count': -1, 'Capabilities': [['gpu']]}]),
                             ('NetworkMode', 'bridge'), ('ReadonlyRootfs', False),
                             ('NanoCpus', 1000000000), ('Privileged', True)]:
            changed = copy.deepcopy(info)
            changed['HostConfig'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify.validate(changed, 'owned', source)
        with self.assertRaises(ValueError):
            verify.validate(info, 'different-container', source)
        changed = copy.deepcopy(info)
        changed['Mounts'][0]['RW'] = True
        with self.assertRaises(ValueError):
            verify.validate(changed, 'owned', source)

    def test_runtime_copies_only_pinned_regular_library_and_rejects_tampering(self):
        root = Path(__file__).resolve().parents[2] / '.runtime/runtime-library-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            folder = Path(folder)
            folder.resolve().relative_to(root.resolve())
            package = folder / 'fixture.apk'
            library = b'\x7fELF\x02\x01' + b'fixture'
            with tarfile.open(package, 'w:gz') as archive:
                # An unrelated installer member must never be written/executed.
                for name, data in [('.post-install', b'not executable'), ('usr/lib/fixture.so.1', library)]:
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            expected = hashlib.sha256(package.read_bytes()).hexdigest()
            packages = [('fixture.apk', expected, 'usr/lib/fixture.so.1', 'fixture.so.1')]
            with patch.object(runtime, 'ROOT', folder), patch.object(runtime, 'PACKAGES', packages):
                output, _ = runtime.prepare()
                self.assertEqual([p.name for p in output.iterdir()], ['fixture.so.1'])
                self.assertFalse((folder / '.post-install').exists())
                (output / 'fixture.so.1').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError, 'STAGED_RUNTIME_CHANGED'):
                    runtime.prepare()

    def test_artifact_path_cannot_point_at_arbitrary_executable(self):
        with self.assertRaisesRegex(ValueError, 'FIXED_ARTIFACT_DIRECTORY_REQUIRED'):
            verify.artifact(Path('C:/Windows'))


if __name__ == '__main__':
    unittest.main()
