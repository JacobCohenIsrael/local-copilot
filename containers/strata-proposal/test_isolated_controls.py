import contextlib
import copy
import ctypes
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import uuid

import isolated_agent as agent
import isolated_engine as engine
import isolated_session as session
import isolated_store as store


def spec(root):
    return engine.Spec('a' * 32, 'sha256:' + 'b' * 64,
                       str(root / 'control'), str(root / 'runtime'), '/dev/sdz')


def capsule_info(contract):
    return {'Id': 'c' * 64, 'Name': '/' + contract.name, 'Image': contract.image_id,
        'Config': {'Labels': contract.labels, 'Image': contract.image_id, 'User': '0:0',
            'Entrypoint': ['/usr/local/bin/python3'], 'Cmd': ['-I', '-B', '/control/isolated_agent.py'],
            'WorkingDir': '/run', 'Volumes': None, 'Env': ['NVIDIA_VISIBLE_DEVICES=void'],
            'Healthcheck': {'Test': ['NONE']}},
        'HostConfig': {'NanoCpus': 1000000000, 'Memory': 4 * engine.GIB, 'MemorySwap': 4 * engine.GIB,
            'PidsLimit': 128, 'Runtime': 'runc', 'ReadonlyRootfs': True, 'NetworkMode': 'none',
            'IpcMode': 'private', 'CgroupnsMode': 'private', 'Privileged': False, 'ShmSize': 65536,
            'Tmpfs': copy.deepcopy(engine.TMPFS),
            'LogConfig': {'Type': 'json-file', 'Config': {'max-size': '128k', 'max-file': '2'}},
            'CapDrop': ['ALL'], 'CapAdd': list(engine.CAPS),
            'SecurityOpt': ['no-new-privileges', 'apparmor=unconfined'],
            'Devices': [{'PathOnHost': contract.device, 'PathInContainer': '/dev/copilot-store',
                         'CgroupPermissions': 'rw'}], 'RestartPolicy': {'Name': 'no'}},
        'Mounts': [{'Type': 'bind', 'Source': p, 'Destination': dest, 'RW': False}
                   for p, dest in ((contract.control, '/control'), (contract.runtime, '/runtime'))],
        'State': {'Status': 'running', 'Running': True, 'Restarting': False, 'Pid': 123, 'ExitCode': 0}}


class EngineContractTests(unittest.TestCase):
    def setUp(self):
        self.spec = spec(Path.cwd())
        self.row = capsule_info(self.spec)
        self.docker = Mock(inspect=Mock(side_effect=lambda _: copy.deepcopy(self.row)))
        self.target = engine.Capsule(self.spec, 'c' * 64, self.docker)

    def exit(self):
        self.row['State'].update(Status='exited', Running=False, Pid=0)

    def test_renderer_has_only_qualified_device_and_readonly_inputs(self):
        args = engine.create_args(self.spec)
        self.assertIn('--pull=never', args)
        self.assertIn('--read-only', args)
        self.assertIn(self.spec.image_id, args)
        self.assertNotIn('--privileged', args)
        self.assertNotIn('--gpus', args)
        self.assertNotIn('/var/run/docker.sock', ' '.join(args))
        self.assertEqual(args[args.index('--memory') + 1], args[args.index('--memory-swap') + 1])
        self.target.inspect()

    def test_changed_limits_devices_and_shared_namespaces_rejected(self):
        original = copy.deepcopy(self.row)
        for key, value in {'Memory': 0, 'MemorySwap': -1, 'PidsLimit': -1, 'NetworkMode': 'host',
                'PidMode': 'host', 'Privileged': True, 'DeviceRequests': [{'Capabilities': [['gpu']]}],
                'DeviceCgroupRules': ['a *:* rwm'], 'CgroupnsMode': 'host', 'Binds': ['/var/run/docker.sock']}.items():
            self.row = copy.deepcopy(original)
            self.row['HostConfig'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'CONFIGURATION_CHANGED'):
                self.target.inspect()

    def test_writable_or_extra_mounts_rejected(self):
        self.row['Mounts'][0]['RW'] = True
        with self.assertRaisesRegex(ValueError, 'CONFIGURATION_CHANGED'):
            self.target.inspect()
        self.row = capsule_info(self.spec)
        self.row['Mounts'].append({'Type': 'volume', 'Destination': '/unexpected', 'RW': True})
        with self.assertRaisesRegex(ValueError, 'CONFIGURATION_CHANGED'):
            self.target.inspect()

    def test_drift_does_not_disable_emergency_stopping(self):
        self.row['HostConfig']['Memory'] = 0
        self.docker.call.side_effect = lambda *a, **k: self.exit()
        self.assertTrue(self.target.stop()['stopConfirmed'])
        self.assertEqual(self.docker.call.call_args.args[0], 'stop')

    def test_hung_graceful_stop_escalates_only_owned_full_id(self):
        def call(*args, **kwargs):
            if args[0] == 'stop':
                raise TimeoutError()
            self.assertEqual(args, ('kill', '--signal', 'KILL', 'c' * 64))
            self.exit()
        self.docker.call.side_effect = call
        result = self.target.stop()
        self.assertTrue(result['stopConfirmed'])
        self.assertTrue(result['forced'])

    def test_lost_identity_or_unresponsive_engine_never_confirms_stop(self):
        self.row['Config']['Labels'] = {}
        self.assertFalse(self.target.stop()['stopConfirmed'])
        self.docker.call.assert_not_called()
        self.row = capsule_info(self.spec)
        self.docker.call.side_effect = TimeoutError()
        self.assertFalse(self.target.stop()['stopConfirmed'])

    def test_dead_missing_or_restarting_state_is_not_safe_exit(self):
        for state in ({'Running': False, 'Restarting': False, 'Pid': 0, 'Status': 'dead', 'ExitCode': 0},
                      {'Running': False, 'Restarting': True, 'Pid': 0, 'Status': 'exited', 'ExitCode': 0}):
            self.assertFalse(engine.Capsule.stopped({'State': state}))

    def test_native_cgroup_values_reject_unlimited_or_extra_fields(self):
        valid = {'cpu.max': '100000 100000', 'memory.max': str(4 * engine.GIB),
                 'memory.swap.max': '0', 'pids.max': '128'}
        engine.validate_cgroup(valid)
        for name in valid:
            bad = dict(valid, **{name: 'max'})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'CGROUP_INVALID'):
                engine.validate_cgroup(bad)

    def test_daemon_and_containerd_paths_cannot_reuse_desktop_store(self):
        config = engine.daemon_configuration()
        self.assertEqual(config['containerd'], '/run/copilot/containerd.sock')
        self.assertEqual(config['data-root'], '/store/docker')
        self.assertEqual(config['hosts'], ['unix:///run/copilot/docker.sock'])
        import tomllib
        containerd = tomllib.loads(engine.containerd_configuration())
        self.assertEqual(containerd['root'], '/store/containerd')
        self.assertEqual(containerd['temp'], '/store/tmp/containerd')

    def test_visible_store_and_whole_filesystem_mount_are_required(self):
        rows = [{'path': p, 'options': ['ro']} for p in ('/', '/control', '/runtime')]
        rows += [{'path': '/store', 'device': '0:99', 'fstype': 'tmpfs', 'options': ['rw'], 'root': '/'},
                 {'path': '/store', 'device': '8:32', 'fstype': 'ext4', 'options': ['rw'], 'root': '/'}]
        engine.validate_mounts(rows, '8:32', 32 * engine.GIB, visible_store_device='8:32')
        for visible in ('0:99', '8:16'):
            with self.assertRaisesRegex(ValueError, 'STORE_MOUNT_INVALID'):
                engine.validate_mounts(rows, '8:32', 32 * engine.GIB, visible_store_device=visible)
        rows.append({'path': '/store/docker', 'device': '0:99', 'fstype': 'tmpfs', 'options': ['rw'], 'root': '/'})
        with self.assertRaisesRegex(ValueError, 'STORE_MOUNT_INVALID'):
            engine.validate_mounts(rows, '8:32', 32 * engine.GIB, visible_store_device='8:32')


class StoreControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.spec = store.Spec(uuid.uuid4().hex, logical_bytes=128 * store.MIB)
        self.disk = store.Store(self.spec, root=Path(self.temp.name))
        self.properties = {'identifier': self.disk.identifier, 'virtualBytes': self.spec.logical_bytes,
            'physicalBytes': self.spec.logical_bytes + 8 * store.MIB, 'providerSubtype': 2, 'sectorBytes': 512}
        # Tiny ordinary fixture, never a VHDX or mounted/formatted device.
        self.backend = Mock(create_fixed=Mock(side_effect=lambda p, *_: p.write_bytes(b'fake-disk')),
                            properties=Mock(side_effect=lambda _: dict(self.properties)))

    def create(self):
        with patch.object(store.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=100 * store.GIB)):
            return self.disk.create(self.backend)

    def test_owned_namespace_create_is_one_attempt_and_not_native_proof(self):
        result = self.create()
        self.assertFalse(result['physicalAllocationCeilingNativeProven'])
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(self.backend.create_fixed.call_count, 1)

    def test_disk_capacity_type_identifier_and_physical_ceiling_checked(self):
        for change in ({'virtualBytes': 64 * store.GIB}, {'providerSubtype': 3}, {'identifier': 'wrong'},
                       {'physicalBytes': self.spec.maximum_file_bytes + 1}, {'physicalBytes': 1}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'PROPERTIES_INVALID'):
                store.validate_properties(self.spec, {**self.properties, **change}, self.disk.identifier)

    def test_insufficient_host_reserve_does_not_claim_or_call_native_api(self):
        with patch.object(store.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, 'HOST_RESERVE'):
                self.disk.create(self.backend)
        self.assertFalse(self.disk.directory.exists())
        self.backend.create_fixed.assert_not_called()

    def test_failed_create_leaves_claim_and_no_automatic_cleanup_retry(self):
        self.backend.create_fixed.side_effect = OSError('Synthetic provider failure')
        with self.assertRaises(OSError):
            self.create()
        self.assertTrue((self.disk.directory / 'owner.json').is_file())
        with self.assertRaises(FileExistsError):
            self.create()

    def test_unqualified_mapping_cannot_be_detached_even_with_stop_flag(self):
        self.create()
        bridge = Mock()
        with self.assertRaisesRegex(ValueError, 'DETACH_WITHOUT_STOP_PROOF'):
            self.disk.detach(bridge, writers_stopped=True)
        bridge.detach_owned.assert_not_called()

    def test_marker_is_specific_to_owner_and_nonzero_nonce(self):
        agent.validate_marker(self.disk.marker)
        other = store.Store(self.spec, root=Path(self.temp.name))
        self.assertNotEqual(self.disk.marker, other.marker)
        for raw in (b'\0' * 512, self.disk.marker[:-1], b'X' + self.disk.marker[1:]):
            with self.assertRaisesRegex(ValueError, 'MARKER_INVALID'):
                agent.validate_marker(raw)
        with self.assertRaisesRegex(ValueError, 'NONCE_INVALID'):
            agent.device_marker(self.spec.session, b'\0' * 32)

    def test_guest_cannot_open_any_device_with_an_empty_marker(self):
        with patch.object(agent.os, 'open') as opened:
            with self.assertRaisesRegex(ValueError, 'MARKER_INVALID'):
                agent.BlockDevice(b'\0' * 512, 128 * store.MIB)
            opened.assert_not_called()

    def test_windows_abi_parameters_have_expected_64_bit_layout(self):
        self.assertEqual(ctypes.sizeof(store.GUID), 16)
        self.assertEqual(store.CreateParameters.v2.offset, 8)
        self.assertEqual(ctypes.sizeof(store.CreateParameters), 128)
        self.assertEqual(store.Info.value.offset, 8)
        self.assertEqual(ctypes.sizeof(store.Info), 32)


class ProviderOperationTests(unittest.TestCase):
    def backend(self, statuses, allowed=lambda: True):
        backend = object.__new__(store.WindowsVhdx)
        values = iter(statuses)
        def query(handle, operation, result):
            ctypes.cast(result, ctypes.POINTER(store.Progress)).contents.status = next(values)
            return 0
        backend.api = Mock(GetVirtualDiskOperationProgress=Mock(side_effect=query))
        backend.kernel = Mock(WaitForSingleObject=Mock(return_value=258), CancelIoEx=Mock(return_value=True))
        backend.allowed, backend.operation_seconds = allowed, 180
        return backend

    def test_native_dll_exports_bind_without_disk_or_handle_creation(self):
        if sys.platform != 'win32':
            self.skipTest('Windows export binding only')
        # Only resolves installed function signatures; performs no disk calls.
        backend = store.WindowsVhdx(allowed=lambda: False)
        self.assertIsNotNone(backend.kernel.CancelIoEx.argtypes)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'store.vhdx'
            with self.assertRaisesRegex(ValueError, 'NATIVE_GUARD_LOST'):
                backend.create_fixed(path, 128 * store.MIB, str(uuid.uuid4()))
            self.assertFalse(path.exists())

    def test_completed_provider_operation_is_confirmed(self):
        backend = self.backend([997, 0])
        completion = {'confirmed': False}
        backend.await_completion(123, store.Overlapped(), clock=iter([0, 0, 1]).__next__, completion=completion)
        self.assertTrue(completion['confirmed'])
        backend.kernel.CancelIoEx.assert_not_called()

    def test_cancel_request_is_followed_to_provider_completion(self):
        backend = self.backend([997, 0], allowed=lambda: False)
        completion = {'confirmed': False}
        with self.assertRaisesRegex(ValueError, 'GUARD_OR_DEADLINE'):
            backend.await_completion(123, store.Overlapped(), clock=iter([0, 0, 1]).__next__, completion=completion)
        self.assertTrue(completion['confirmed'])
        backend.kernel.CancelIoEx.assert_called_once()

    def test_provider_refusing_cancel_never_gets_stop_confirmation(self):
        backend = self.backend([997, 997], allowed=lambda: False)
        completion = {'confirmed': False}
        with self.assertRaisesRegex(ValueError, 'PROVIDER_STOP_UNCONFIRMED'):
            backend.await_completion(123, store.Overlapped(), clock=iter([0, 0, 5]).__next__, completion=completion)
        self.assertFalse(completion['confirmed'])
        backend.kernel.CancelIoEx.assert_called_once()

    def test_completion_after_deadline_is_not_workload_success(self):
        backend = self.backend([0])
        completion = {'confirmed': False}
        with self.assertRaisesRegex(ValueError, 'GUARD_OR_DEADLINE'):
            backend.await_completion(123, store.Overlapped(), clock=iter([0, 180]).__next__, completion=completion)
        self.assertTrue(completion['confirmed'])

    def test_failed_provider_operation_is_terminal_but_not_success(self):
        backend = self.backend([995])
        completion = {'confirmed': False}
        with self.assertRaises(OSError):
            backend.await_completion(123, store.Overlapped(), clock=iter([0, 1]).__next__, completion=completion)
        self.assertTrue(completion['confirmed'])


class LifecycleTests(unittest.TestCase):
    def test_connected_faults_stop_before_detach_and_no_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            for case in session.CASES:
                backend = session.FakeBackend(case)
                directory = Path(temp) / case
                controller = session.Session(directory, backend, lease_seconds=.05,
                    operation_seconds=.03 if case == 'deadline' else 3)
                result = controller.execute()
                with self.subTest(case=case):
                    self.assertEqual(result['phase'], 'COMPLETE' if case == 'success' else 'FAULT')
                    self.assertFalse(backend.running)
                    if case != 'success':
                        self.assertIsNotNone(result['fault'])
                    if 'detach' in backend.events:
                        self.assertTrue(result['stopConfirmed'])
                        self.assertLess(backend.events.index('stop'), backend.events.index('detach'))
                    with self.assertRaises(FileExistsError):
                        session.Session(directory, session.FakeBackend('success'))
                    self.assertFalse(result['imageImportEnabled'])
            self.assertNotIn('detach', session.FakeBackend('stop-unconfirmed').events)

    def test_native_backend_rejects_before_namespace_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'not-created'
            with self.assertRaisesRegex(ValueError, 'NATIVE_ADMISSION_NOT_WIRED'):
                session.Session(path, types.SimpleNamespace(synthetic=False))
            self.assertFalse(path.exists())

    def test_journal_failure_happens_after_stopping_and_detach(self):
        with tempfile.TemporaryDirectory() as temp:
            backend = session.FakeBackend('success')
            controller = session.Session(Path(temp) / 'case', backend)
            with patch.object(session.tools.base, 'atomic', side_effect=OSError('Journal unavailable')):
                with self.assertRaises(OSError):
                    controller.execute()
            self.assertFalse(backend.running)
            self.assertEqual(backend.events[-2:], ['stop', 'detach'])

    def test_unexpected_exception_and_interrupt_stop_before_propagation_or_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            for error in (LookupError('Synthetic unclassified error'), KeyboardInterrupt()):
                backend = session.FakeBackend('success')
                backend.exercise = Mock(side_effect=error)
                controller = session.Session(Path(temp) / type(error).__name__, backend)
                if isinstance(error, KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        controller.execute()
                else:
                    result = controller.execute()
                    self.assertEqual(result['operationError']['category'], 'LookupError')
                self.assertFalse(backend.running)
                self.assertIn('stop', backend.events)

    def test_failed_stop_call_retains_store_and_fault_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            backend = session.FakeBackend('success')
            backend.stop = Mock(side_effect=LookupError('Synthetic stop failed'))
            result = session.Session(Path(temp) / 'case', backend).execute()
            self.assertEqual(result['fault'], 'ENGINE_STOP_UNCONFIRMED')
            self.assertFalse(result['storeDetached'])
            self.assertNotIn('detach', backend.events)

    def test_guest_script_refuses_before_device_or_process_access(self):
        with patch.object(agent.os, 'open') as opened, patch.object(agent.subprocess, 'run') as run, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(agent.main(), 3)
        opened.assert_not_called()
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['status'], 'NATIVE_ISOLATION_BOOTSTRAP_DISABLED')

    def test_namespace_wide_fuse_cannot_arm_in_host_process(self):
        with patch.object(agent.os, 'getpid', return_value=999):
            with self.assertRaisesRegex(ValueError, 'PRIVATE_PID_ONE_REQUIRED'):
                agent.namespace_fuse('/never-opened')

    def test_only_qualified_mount_or_formatter_commands_are_accepted(self):
        agent.qualified_command(['/runtime/usr/bin/mount'], expected='mount')
        agent.qualified_command(['/runtime/ld-linux.so', '--library-path', '/runtime/lib', '/runtime/mkfs.ext4'],
                                expected='mkfs.ext4')
        for command in (['/bin/mount'], ['/runtime/sh', '-c', 'anything'],
                ['/runtime/../host/mount'], ['/runtime/mount', '--bind'],
                ['/runtime/ld-linux.so', '--library-path', '/lib', '/runtime/mount']):
            with self.subTest(command=command), self.assertRaisesRegex(ValueError, 'RUNTIME_COMMAND_INVALID'):
                agent.qualified_command(command, expected='mount')

    def test_new_cli_refusal_never_instantiates_native_adapters(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import local_worker as worker
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(worker.isolation_preparation, 'APPROVAL', Path(temporary) / 'absent.json'), \
                patch.object(sys, 'argv', ['local_worker.py', 'run-isolation']), \
                patch.object(store.WindowsVhdx, '__init__') as disk, \
                patch.object(worker.isolation_preparation, 'material') as packet, \
                patch.object(worker.subprocess, 'Popen') as process, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(worker.main(), 3)
        self.assertEqual(json.loads(output.getvalue())['status'], 'ISOLATION_NOT_APPROVED')
        disk.assert_not_called()
        packet.assert_not_called()
        process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
