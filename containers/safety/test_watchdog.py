import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import uuid

import watchdog as w
from test_supervisor import FakeDocker


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.directory = w.ROOT / uuid.uuid4().hex
        (self.directory / 'input').mkdir(parents=True)
        (self.directory / 'control').mkdir()
        def cleanup():
            self.directory.resolve().relative_to(w.ROOT.resolve())
            shutil.rmtree(self.directory)
        self.addCleanup(cleanup)
        source = Path(w.__file__).with_name('uncooperative.py')
        shutil.copyfile(source, self.directory / 'input/worker.py')
        w.base.atomic(self.directory / 'manifest.json', {'runId': self.directory.name,
                      'workerSha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        w.base.heartbeat(self.directory / 'control')
        self.identity = {'runId': self.directory.name, 'containerName': 'copilot-dummy-' + self.directory.name}
        self.docker = FakeDocker()
        args = w.base.create_args(self.identity, self.directory / 'input', self.directory / 'control', 'ignore-stop')
        args[1:1] = ['--label', 'local-copilot.guard=' + w.GUARD_TAG]
        self.docker.call(*args)
        self.docker.info['State']['Running'] = True
        original = self.docker.call
        def call(*args, **kwargs):
            if args[0] == 'stop':
                state = json.loads((self.directory / 'watchdog-state.json').read_text())
                self.assertEqual(state['phase'], 'FAULT')
                self.assertIsNotNone(state['fault'])
                self.docker.calls.append(args)
                self.docker.info['State'].update(Running=False, ExitCode=137)
                return 'fake-id'
            return original(*args, **kwargs)
        self.docker.call = call

    def test_stalled_supervisor_external_stop_and_latch(self):
        ticks = iter(i * .25 for i in range(100))
        with patch.object(w.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(w.time, 'sleep'):
            result = w.supervise(self.directory, self.docker)
        self.assertEqual(result['fault']['code'], 'SUPERVISOR_LEASE_EXPIRED')
        self.assertEqual(result['workerExitCode'], 137)
        self.assertTrue(result['cleanupComplete'])
        self.assertIsNone(self.docker.info)
        with self.assertRaises(w.base.Rejected):
            w.supervise(self.directory, self.docker)

    def test_wrong_guard_label_never_stops_target(self):
        self.docker.info['Config']['Labels']['local-copilot.guard'] = 'foreign'
        with self.assertRaises(w.base.Rejected):
            w.supervise(self.directory, self.docker)
        self.assertFalse(any(c[0] in ('stop', 'kill', 'rm') for c in self.docker.calls))

    def test_gpu_enabled_target_rejected_before_arming(self):
        self.docker.info['HostConfig']['DeviceRequests'] = [{'Capabilities': [['gpu']]}]
        with self.assertRaises(w.base.Rejected):
            w.supervise(self.directory, self.docker)
        self.assertFalse((self.directory / 'watchdog-state.json').exists())

    def test_changed_dummy_source_rejected(self):
        (self.directory / 'input/worker.py').write_text('raise RuntimeError("not allowed")')
        with self.assertRaises(w.base.Rejected):
            w.supervise(self.directory, self.docker)

    def test_session_path_escape_rejected(self):
        with self.assertRaises(w.base.Rejected):
            w.session(self.directory.parent / 'not-a-session')


if __name__ == '__main__':
    unittest.main()
