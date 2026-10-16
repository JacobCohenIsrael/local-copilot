import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import supervisor as s


class FakeDocker:
    def __init__(self):
        self.info = None
        self.calls = []
        self.hold = False
        self.force = False
        self.foreign = False
        self.stop_fault = None
        self.directory = None

    def call(self, *args, **_kwargs):
        self.calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return '[]'
        if args[0] == 'create':
            def value(key):
                return args[args.index(key) + 1]
            mounts = []
            for index, arg in enumerate(args):
                if arg == '--mount':
                    fields = dict(v.split('=', 1) for v in args[index + 1].split(',') if '=' in v)
                    mounts.append({'Source': fields['source'], 'Destination': fields['target'], 'RW': False})
            labels = dict(args[i+1].split('=', 1) for i, v in enumerate(args) if v == '--label')
            self.info = {'Id': 'fake-id', 'Name': '/' + value('--name'),
                         'HostConfig': {'Memory': 268435456, 'MemorySwap': 268435456, 'NanoCpus': 500000000,
                           'PidsLimit': 32, 'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Runtime': 'runc',
                           'Privileged': False, 'RestartPolicy': {'Name': 'no'}, 'CapDrop': ['ALL'],
                           'LogConfig': {'Type': 'json-file', 'Config': {'max-size': '64k', 'max-file': '1'}},
                           'SecurityOpt': ['no-new-privileges']},
                         'Config': {'Image': s.IMAGE, 'Labels': labels, 'User': '65534:65534',
                           'Entrypoint': ['/usr/local/bin/python3'], 'Cmd': list(args[-4:])},
                         'Mounts': mounts, 'State': {'Running': False, 'ExitCode': 0, 'OOMKilled': False}}
            if self.foreign:
                self.info['Config']['Labels']['local-copilot.run'] = 'foreign'
            return 'fake-id'
        if args[0] == 'start':
            self.info['State']['Running'] = self.hold
            return 'fake-id'
        if args[0] == 'stop':
            self.stop_fault = json.loads((self.directory / 'state.json').read_text())['fault']
            self.info['State'].update(Running=False, ExitCode=137 if self.force else 0)
            return 'fake-id'
        if args[0] == 'logs':
            return '{"event":"completed"}\n'
        if args[0] == 'kill':
            self.info['State'].update(Running=False, ExitCode=137)
            return 'fake-id'
        if args[0] == 'rm':
            self.info = None
            return 'fake-id'
        raise AssertionError(args)

    def inspect(self, _name):
        return copy.deepcopy(self.info)

    owned = s.Docker.owned


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        test_root = s.ROOT / '.runtime' / 'docker-dummy-unit'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        def cleanup():
            Path(self.temp.name).resolve().relative_to(test_root.resolve())
            self.temp.cleanup()
        self.addCleanup(cleanup)
        self.directory = Path(self.temp.name)
        self.docker = FakeDocker()
        self.docker.directory = self.directory
        self.supervisor = s.Supervisor(self.directory, self.docker)

    def test_success_cleanup_receipt_and_off(self):
        result = self.supervisor.run('success')
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(self.supervisor.status()['state'], 'OFF')
        self.assertTrue(result['cleanup']['removed'])
        self.assertFalse(result['codingPerformed'])

    def test_fault_persists_before_stop_and_blocks_next_run(self):
        self.docker.hold = True
        self.supervisor.signal_cancel = False
        with patch.object(s.time, 'sleep'):
            # Advance only supervisor time; no hardware or process is used.
            ticks = iter(i * 0.3 for i in range(200))
            with patch.object(s.time, 'monotonic', side_effect=lambda: next(ticks)):
                result = self.supervisor.run('gpu-hot')
        self.assertEqual(result['fault']['code'], 'SYNTHETIC_GPU_HOT')
        self.assertEqual(self.docker.stop_fault['code'], 'SYNTHETIC_GPU_HOT')
        before = len(self.docker.calls)
        with self.assertRaises(s.Rejected):
            self.supervisor.run('success')
        self.assertEqual(len(self.docker.calls), before)
        self.supervisor.reset('Reviewed synthetic test evidence', True)
        self.assertEqual(self.supervisor.status()['state'], 'OFF')

    def test_cancelled_run_stops_cleanly(self):
        self.docker.hold = True
        self.supervisor.signal_cancel = True
        result = self.supervisor.run('wait')
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['cleanup']['graceful'])
        self.assertEqual(self.supervisor.status()['state'], 'OFF')

    def test_forced_stop_latches_fault(self):
        self.docker.hold = self.docker.force = True
        self.supervisor.signal_cancel = True
        result = self.supervisor.run('ignore-stop')
        self.assertEqual(result['fault']['code'], 'STOP_TIMEOUT')
        self.assertTrue(result['cleanup']['removed'])

    def test_foreign_identity_is_never_stopped_or_removed(self):
        self.docker.foreign = True
        result = self.supervisor.run('success')
        self.assertEqual(result['status'], 'fault')
        self.assertFalse(any(c[0] in ('stop', 'rm') for c in self.docker.calls))
        self.assertFalse(self.supervisor.state['cleanupComplete'])

    def test_busy_lock_is_released_by_os_without_deleting_file(self):
        with s.lock(self.directory):
            with self.assertRaises(s.Busy):
                with s.lock(self.directory):
                    pass
        with s.lock(self.directory):
            self.assertTrue((self.directory / 'supervisor.lock').exists())

    def test_corrupt_state_and_changed_policy_block_admission(self):
        for change in [{'policyHash': 'changed'}, {'fault': 'invalid'}, {'runId': '../escape'}]:
            state = s.fresh()
            state.update(change)
            s.atomic(self.directory / 'state.json', state)
            with self.assertRaises(s.Rejected):
                self.supervisor.run('success')
        self.assertEqual(self.docker.calls, [])

    def test_unclean_active_state_latches_and_recovers_known_identity(self):
        state = s.fresh()
        state.update(state='RUNNING', runId='a'*32, containerName='copilot-dummy-'+'a'*32,
                     cleanupComplete=False)
        s.atomic(self.directory / 'state.json', state)
        result = self.supervisor.status()
        self.assertEqual(result['fault']['code'], 'UNCLEAN_EXIT')
        self.assertTrue(result['cleanupComplete'])

    def test_isolation_mismatch_never_starts(self):
        original = self.docker.call
        def call(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[0] == 'create':
                self.docker.info['HostConfig']['DeviceRequests'] = [{'Capabilities': [['gpu']]}]
            return result
        self.docker.call = call
        result = self.supervisor.run('success')
        self.assertEqual(result['status'], 'fault')
        self.assertFalse(any(c[0] == 'start' for c in self.docker.calls))
        self.assertIsNone(self.docker.info)

    def test_wrong_cancel_identity_rejected(self):
        with self.assertRaises(s.Rejected):
            self.supervisor.cancel('wrong')

    def test_log_failure_does_not_prevent_removal(self):
        original = self.docker.call
        def call(*args, **kwargs):
            if args[0] == 'logs':
                raise RuntimeError('Injected log driver failure')
            return original(*args, **kwargs)
        self.docker.call = call
        result = self.supervisor.run('success')
        self.assertEqual(result['status'], 'fault')
        self.assertIsNone(self.docker.info)
        self.assertTrue(self.supervisor.state['cleanupComplete'])

    def test_journal_failure_does_not_prevent_stop_and_removal(self):
        self.docker.hold = True
        self.supervisor.signal_cancel = True
        original = self.supervisor.event
        def event(kind, **fields):
            if kind == 'stop-requested':
                raise RuntimeError('Injected journal failure')
            return original(kind, **fields)
        self.supervisor.event = event
        result = self.supervisor.run('wait')
        self.assertEqual(result['status'], 'fault')
        self.assertIsNone(self.docker.info)
        self.assertTrue(any(c[0] == 'stop' for c in self.docker.calls))

    def test_reset_requires_acknowledgment_and_reason(self):
        for reason, acknowledged in [('short', True), ('Reviewed dummy', False)]:
            with self.assertRaises(s.Rejected):
                self.supervisor.reset(reason, acknowledged)

    def test_stop_state_write_failure_still_stops_and_removes(self):
        self.docker.hold = True
        self.supervisor.signal_cancel = True
        original = self.supervisor.save
        def save():
            if self.supervisor.state['state'] == 'STOPPING':
                raise OSError('Injected state write failure')
            original()
        self.supervisor.save = save
        result = self.supervisor.run('wait')
        self.assertEqual(result['fault']['code'], 'PERSISTENCE_FAILURE')
        self.assertIsNone(self.docker.info)
        self.assertTrue(result['cleanup']['removed'])

    def test_failed_stop_command_uses_owned_kill_then_removes(self):
        self.docker.hold = True
        self.supervisor.signal_cancel = True
        original = self.docker.call
        def call(*args, **kwargs):
            if args[0] == 'stop':
                raise TimeoutError('Injected stop timeout')
            return original(*args, **kwargs)
        self.docker.call = call
        result = self.supervisor.run('wait')
        self.assertEqual(result['fault']['code'], 'STOP_TIMEOUT')
        self.assertTrue(any(c[0] == 'kill' for c in self.docker.calls))
        self.assertIsNone(self.docker.info)

    def test_heartbeat_has_a_fixed_byte_budget(self):
        for _ in range(128):
            s.heartbeat(self.directory)
        with self.assertRaises(RuntimeError):
            s.heartbeat(self.directory)
        self.assertEqual((self.directory / 'heartbeat').stat().st_size, 128)


if __name__ == '__main__':
    unittest.main()
