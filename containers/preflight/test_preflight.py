import copy
import unittest
from unittest.mock import patch

import probe
import run


class PreflightTests(unittest.TestCase):
    def config(self):
        return {'tokenizer': r'D:\Strata-data\packs\coder-iq1_m\tokenizer',
                'args': ['--pack', r'D:\Strata-data\packs\coder-iq1_m',
                         '--native', r'D:\Strata-data\models\coder-IQ1_M\one.gguf',
                         '--ple-gguf', r'D:\Strata-data\models\coder-IQ1_M\two.gguf',
                         '--mtp', r'D:\Strata-data\mtp\rt',
                         '--expert-profile', r'D:\AI\data\expert-profile-coder.bin',
                         '--resident-experts']}

    def test_translates_paths_without_executing_config(self):
        config = self.config()
        config['exe'] = 'MUST NEVER EXECUTE'
        with patch('subprocess.run', side_effect=AssertionError('no subprocess permitted')):
            mounts, paths = run.model_paths(config)
        self.assertEqual(len(mounts), 4)
        self.assertEqual(paths[2]['container'], '/models/gguf/one.gguf')
        self.assertNotIn('exe', str(paths))

    def test_rejects_escape_relative_sibling_and_device_paths(self):
        for value in [r'D:\Strata-data\packs\coder-iq1_m\..\secret',
                      r'D:\Strata-data\packs\coder-iq1_m-other\tokenizer',
                      r'packs\tokenizer', r'\\.\PhysicalDrive0', r'\\server\secret']:
            with self.subTest(value=value):
                config = self.config()
                config['tokenizer'] = value
                with self.assertRaises(ValueError):
                    run.model_paths(config)

    def test_rejects_duplicate_path_flag(self):
        config = self.config()
        config['args'].extend(['--native', 'anything'])
        with self.assertRaises(ValueError):
            run.model_paths(config)

    def baseline(self):
        return {'cpuMax': '50000 100000', 'memoryMaxBytes': 268435456,
                'swapMaxBytes': 0, 'pidsMax': 32, 'uid': 65534,
                'effectiveCapabilities': '0000000000000000', 'noNewPrivileges': '1',
                'gpuDevices': [], 'networkInterfaces': ['lo'], 'paths': [{'exists': True}]}

    def test_synthetic_limits_and_failures(self):
        baseline = self.baseline()
        self.assertTrue(all(probe.validate(baseline).values()))
        for field, value in [('gpuDevices', ['/dev/dxg']), ('uid', 0),
                             ('memoryMaxBytes', 1073741824), ('swapMaxBytes', 1),
                             ('cpuMax', '100000 100000'), ('noNewPrivileges', '0'),
                             ('networkInterfaces', ['eth0', 'lo']), ('paths', [])]:
            with self.subTest(field=field):
                result = copy.deepcopy(baseline)
                result[field] = value
                self.assertFalse(all(probe.validate(result).values()))

    def inspection(self):
        return {'HostConfig': {
            'Memory': 268435456, 'MemorySwap': 268435456, 'NanoCpus': 500000000,
            'PidsLimit': 32, 'ReadonlyRootfs': True, 'NetworkMode': 'none',
            'Privileged': False, 'Runtime': 'runc', 'RestartPolicy': {'Name': 'no'},
            'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
        }, 'Config': {'User': '65534:65534', 'Entrypoint': ['/usr/local/bin/python3'],
                      'Cmd': ['-I', '-B', '/input/probe.py'],
                      'Labels': {'local-copilot.kind': 'cpu-preflight'}},
            'Mounts': [{'Source': 'D:/models', 'Destination': '/models', 'RW': False}]}

    def test_inspection_blocks_gpu_network_mutable_mount_and_extra_mount(self):
        run.check_inspection(self.inspection(), [('D:/models', '/models')])
        for change in ['gpu', 'network', 'writable', 'extra', 'command']:
            with self.subTest(change=change):
                info = self.inspection()
                if change == 'gpu':
                    info['HostConfig']['DeviceRequests'] = [{'Capabilities': [['gpu']]}]
                elif change == 'network':
                    info['HostConfig']['NetworkMode'] = 'bridge'
                elif change == 'writable':
                    info['Mounts'][0]['RW'] = True
                elif change == 'extra':
                    info['Mounts'].append({'Source': 'C:/secrets', 'Destination': '/secrets', 'RW': False})
                else:
                    info['Config']['Cmd'] = ['/opt/strata/setup.py']
                with self.assertRaises(ValueError):
                    run.check_inspection(info, [('D:/models', '/models')])


if __name__ == '__main__':
    unittest.main()
