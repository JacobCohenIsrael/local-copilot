"""Offline only: tiny files and fake Windows/WSL/Docker APIs; no disk/device I/O."""
import copy
import ctypes as c
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import isolated_agent as agent
import isolated_bridge as bridge
import isolated_engine as engine
import isolated_guest as guest
import isolated_runtime as runtime
import isolation_native as native
import isolation_preparation as admission
import runtime_launcher as launcher
import test_isolated_controls as fixtures


def packet():
    return {'sessionId': 'a' * 32, 'sourceEvidenceSha256': 'b' * 64,
            'acceptSourceLimitation': 'test-only limitation',
            'thermalPolicy': {'temperature': {'source': 'ASUS DSTS 0x00120094'}},
            'capsulePrivileges': {'testOnly': True}}


def decision(value):
    return {'version': 1, 'status': 'owner-approved-one-native-isolation-canary',
        'scope': guest.SCOPE, 'reviewSha256': native.guarded.build.sha(value),
        'sourceEvidenceSha256': value['sourceEvidenceSha256'],
        'acceptSourceLimitation': value['acceptSourceLimitation'],
        'thermalPolicySha256': native.guarded.build.sha(value['thermalPolicy']),
        'acceptUnknownThrottleForThisScope': True,
        'acceptCapsulePrivilegesSha256': native.guarded.build.sha(value['capsulePrivileges']),
        'nativeRehearsalEnabled': True, 'maximumAttempts': 1, 'synthetic': False,
        'ownerMessage': 'Offline fixture only; not a real approval',
        'imageDownloadEnabled': False, 'imageImportEnabled': False,
        'buildEnabled': False, 'modelLaunchEnabled': False}


def events(token='d' * 64):
    ready = {'event': 'READY', 'deviceToken': token,
        'limits': {'cpu.max': '100000 100000', 'memory.max': str(4 * engine.GIB),
                   'memory.swap.max': '0', 'pids.max': '128'},
        'engine': {'Images': 0, 'Containers': 0, 'DockerRootDir': '/store/docker',
                   'containerdSocket': '/run/copilot/containerd.sock'}}
    stopped = {'event': 'STOPPED', 'deviceToken': token, 'ready': True,
        'fault': 'OWNER_LEASE_EXPIRED', 'enginesStopped': True, 'unmounted': True,
        'exclusiveDeviceClaim': True, 'imageImportEnabled': False,
        'buildEnabled': False, 'modelLaunchEnabled': False}
    return ready, stopped


class AdmissionTests(unittest.TestCase):
    def test_exact_scope_policy_privileges_and_disabled_workloads(self):
        value, receipt = packet(), decision(packet())
        self.assertEqual(guest.approved(value, receipt), receipt['reviewSha256'])
        for key, bad in [('version', True), ('version', 2), ('maximumAttempts', True),
                ('maximumAttempts', 2), ('scope', 'old-image-approval'),
                ('nativeRehearsalEnabled', False), ('synthetic', True), ('ownerMessage', ''),
                ('acceptUnknownThrottleForThisScope', False), ('thermalPolicySha256', 'changed'),
                ('acceptCapsulePrivilegesSha256', 'changed'), ('sourceEvidenceSha256', 'changed'),
                ('acceptSourceLimitation', 'changed'), ('reviewSha256', 'changed'),
                ('imageDownloadEnabled', True), ('imageImportEnabled', True),
                ('buildEnabled', True), ('modelLaunchEnabled', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                guest.approved(value, {**receipt, key: bad})

    def test_refusal_precedes_native_api_reader_or_review(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(admission, 'APPROVAL', Path(temp) / 'absent.json'), \
                patch.object(admission, 'review') as review, patch.object(native.store, 'WindowsVhdx') as api, \
                patch.object(native.guarded.cpu_feed, 'Feed') as feed:
            self.assertEqual(admission.run()['status'], 'ISOLATION_NOT_APPROVED')
            with self.assertRaisesRegex(ValueError, 'EXACT_PERMIT'):
                native.run(object())
            review.assert_not_called(); api.assert_not_called(); feed.assert_not_called()

    def test_disabled_receipt_cannot_approve(self):
        value = packet()
        with self.assertRaises(ValueError):
            guest.approved(value, {**decision(value), 'status': 'NOT_APPROVED', 'nativeRehearsalEnabled': False})

    def test_qualified_copy_keeps_original_raw_and_native_scope(self):
        permit = admission.Permit('a' * 64, json.dumps(packet()), 'c' * 64)
        raw = {'version': 1, 'synthetic': False, 'validatedCpuSensor': False,
               'cpuThermalThrottling': None, 'source': 'ASUS DSTS 0x00120094'}
        qualified = permit.qualify(raw)
        self.assertFalse(raw['validatedCpuSensor'])
        self.assertIsNone(qualified['cpuThermalThrottling'])
        self.assertEqual(qualified['acceptanceScope'], guest.SCOPE)
        for key, bad in [('version', True), ('synthetic', True), ('validatedCpuSensor', True),
                         ('cpuThermalThrottling', False), ('source', 'other')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                permit.qualify({**raw, key: bad})

    def test_shared_monitor_renews_guest_only_after_healthy_poll(self):
        import verify_image_stage
        value = verify_image_stage.fixture()[0]
        with tempfile.TemporaryDirectory() as temp:
            root, renew = Path(temp), Mock()
            feed = Mock(sequence=0)
            monitor = Mock(last_error=None)
            monitor.poll.return_value = {'fault': 'CPU_HOT'}
            with patch.object(native.guarded, 'Monitor', return_value=monitor):
                state = native.guarded._execute(root, value, feed, Mock(), synthetic=True,
                    download_enabled=False, on_monitor_pass=renew)
            self.assertEqual(state['fault'], 'CPU_HOT')
            self.assertFalse(state['imageDownloadEnabled'])
            renew.assert_not_called(); feed.close.assert_called_once()


class RuntimeTests(unittest.TestCase):
    def test_closure_rejects_missing_and_ambiguous_dependency(self):
        rows = {path: {'extent': i + 1, 'bytes': 32, 'name': path} for i, path in enumerate(runtime.COMMANDS.values())}
        loader = {'extent': 100, 'bytes': 32, 'name': 'loader'}
        iso = Mock()
        def resolve(path):
            if path.endswith('/ld.so'): return loader
            return rows[path]
        iso.resolve.side_effect = resolve
        iso.elf.side_effect = lambda row: {'interpreter': None if row is loader else '/lib/ld.so',
                                            'needed': ['missing.so'] if row is loader else []}
        with self.assertRaisesRegex(ValueError, 'MISSING_OR_AMBIGUOUS'):
            runtime.closure(iso)
        alternate = {**loader, 'extent': 101}
        iso.resolve.side_effect = lambda path: alternate if path == '/usr/lib64/ld.so' else resolve(path)
        with self.assertRaisesRegex(ValueError, 'MISSING_OR_AMBIGUOUS'):
            runtime.closure(iso)

    def test_guest_copy_hashes_bytes_before_any_runtime_execution(self):
        for damaged in (False, True):
            with self.subTest(damaged=damaged), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'runtime').mkdir(); (root / 'exec').mkdir()
                raw = b'tiny-runtime-fixture'
                (root / 'runtime/launcher.py').write_bytes(raw if not damaged else b'X' * len(raw))
                value = {'files': {'launcher.py': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}},
                         'commands': {}, 'staticCommands': [], 'loader': 'lib/ld.so'}
                def paths(name):
                    if str(name).startswith(('/runtime', '/exec')):
                        return root / str(name).lstrip('/')
                    return Path(name)
                with patch.object(guest, 'Path', side_effect=paths), patch.object(guest.subprocess, 'run') as execute:
                    if damaged:
                        with self.assertRaisesRegex(ValueError, 'HASH_CHANGED'):
                            guest.copy_runtime(value, Mock())
                    else:
                        guest.copy_runtime(value, Mock())
                    execute.assert_not_called()
                self.assertEqual((root / 'exec/.qualified').exists(), not damaged)

    def test_elf_static_header_and_rejected_machine_segment(self):
        raw = bytearray(120)
        raw[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', raw, 18, 62)
        struct.pack_into('<Q', raw, 32, 64)
        struct.pack_into('<HH', raw, 54, 56, 1)
        struct.pack_into('<IIQQQQQQ', raw, 64, 1, 5, 0, 0, 0, 120, 120, 4096)
        iso = runtime.Iso.__new__(runtime.Iso)
        iso.read = lambda offset, size: bytes(raw[offset:offset + size])
        self.assertEqual(iso.elf({'extent': 0, 'bytes': 120}), {'interpreter': None, 'needed': []})
        struct.pack_into('<H', raw, 18, 183)
        with self.assertRaisesRegex(ValueError, 'AMD64'):
            iso.elf({'extent': 0, 'bytes': 120})
        struct.pack_into('<H', raw, 18, 62)
        struct.pack_into('<Q', raw, 64 + 32, 121)
        with self.assertRaisesRegex(ValueError, 'SEGMENT'):
            iso.elf({'extent': 0, 'bytes': 120})

    def test_symlink_parent_traversal_cannot_reset_link_budget(self):
        iso = runtime.Iso.__new__(runtime.Iso)
        iso.root = {'name': 'root'}
        directory, link = {'name': 'a', 'link': None}, {'name': 'b', 'link': '../a/b'}
        iso.entries = lambda row: {'a': directory} if row is iso.root else {'b': link}
        with self.assertRaisesRegex(ValueError, 'LINK_LIMIT'):
            iso.resolve('/a/b')
        with self.assertRaisesRegex(ValueError, 'LINK_ESCAPE'):
            iso.resolve('/../a')

    def test_read_limits_before_any_iso_read(self):
        iso = runtime.Iso.__new__(runtime.Iso)
        iso.before = types.SimpleNamespace(st_size=4096)
        iso.file = Mock(); iso.metadata_bytes = 0
        for offset, size in [(0, 131073), (4096, 1), (-1, 1), (0, True)]:
            with self.assertRaisesRegex(ValueError, 'READ_LIMIT'):
                iso.read(offset, size)
        iso.file.read.assert_not_called()

    def test_runtime_manifest_rejects_replaced_extra_and_escaping_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(runtime, 'ROOT', Path(temp)):
            root = Path(temp); directory = root / ('a' * 32); directory.mkdir()
            body = directory / 'launcher.py'; body.write_bytes(b'tiny fixture')
            info = body.stat()
            manifest = {'status': 'ELF_CLOSURE_STAGED_NOT_EXECUTED', 'bytes': info.st_size,
                'files': {'launcher.py': {'bytes': info.st_size, 'sha256': hashlib.sha256(body.read_bytes()).hexdigest()}},
                'identities': {'launcher.py': {'bytes': info.st_size, 'fileId': info.st_ino, 'mtimeNs': info.st_mtime_ns}}}
            def save():
                (directory / 'runtime.json').write_text(json.dumps(manifest))
                (root / 'candidate.json').write_text(json.dumps({'directory': directory.name,
                    'manifestSha256': runtime.tools.sha(directory / 'runtime.json')}))
            save(); runtime.review()
            (directory / 'extra').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'EXTRA_FILES'):
                runtime.review()
            (directory / 'extra').unlink()
            body.write_bytes(b'changed size')
            with self.assertRaisesRegex(ValueError, 'METADATA_CHANGED'):
                runtime.review()
            manifest['identities'] = {'../outside': manifest['identities']['launcher.py']}
            manifest['files'] = {'../outside': manifest['files']['launcher.py']}; save()
            with self.assertRaisesRegex(ValueError, 'MANIFEST_PATH'):
                runtime.review()

    def test_launchers_use_only_closed_commands_and_loader(self):
        manifest = {'commands': {'runc': 'elf/runc', 'shim': 'elf/shim'},
                    'staticCommands': ['shim'], 'loader': 'lib/ld.so'}
        self.assertEqual(launcher.command('shim', manifest), ['/exec/elf/shim'])
        self.assertEqual(launcher.command('runc', manifest),
            ['/exec/lib/ld.so', '--library-path', '/exec/lib', '/exec/elf/runc'])
        with self.assertRaises(ValueError):
            launcher.command('/bin/sh', manifest)


class MarkerTests(unittest.TestCase):
    def fixture(self, *, size=134217728, physical='\\\\.\\PhysicalDrive7', nonzero=False, allowed=True):
        state = {'raw': b'X' * 4096 if nonzero else b'\0' * 4096, 'writes': 0, 'opens': []}
        api, kernel = Mock(), Mock()
        def open_disk(*args):
            c.cast(args[-1], c.POINTER(c.c_void_p))[0] = 11
            return 0
        api.OpenVirtualDisk.side_effect = open_disk
        api.AttachVirtualDisk.return_value = 0; api.DetachVirtualDisk.return_value = 0
        def path(handle, length, output):
            output.value = physical; return 0
        api.GetVirtualDiskPhysicalPath.side_effect = path
        def create(path, *args):
            state['opens'].append(path); return 12
        kernel.CreateFileW.side_effect = create
        def ioctl(handle, code, _, __, output, length, used, overlapped):
            if code == 0x7405C:
                c.cast(output, c.POINTER(c.c_int64))[0] = size
            else:
                value = c.cast(output, c.POINTER(c.c_uint32))
                value[0], value[1], value[2] = 7, 7, 0
            c.cast(used, c.POINTER(c.c_uint32))[0] = length
            return 1
        kernel.DeviceIoControl.side_effect = ioctl
        kernel.SetFilePointerEx.return_value = 1; kernel.FlushFileBuffers.return_value = 1
        def read(handle, output, length, count, _):
            c.memmove(output, state['raw'], length)
            c.cast(count, c.POINTER(c.c_uint32))[0] = length
            return 1
        def write(handle, incoming, length, count, _):
            state['writes'] += 1; state['raw'] = c.string_at(incoming, length)
            c.cast(count, c.POINTER(c.c_uint32))[0] = length
            return 1
        kernel.ReadFile.side_effect = read; kernel.WriteFile.side_effect = write
        backend = types.SimpleNamespace(api=api, kernel=kernel, storage=native.store.StorageType(),
            allowed=lambda: allowed, checked=lambda value: self.assertEqual(value, 0))
        disk = types.SimpleNamespace(spec=types.SimpleNamespace(logical_bytes=134217728), marker=b'M' * 512,
                    path=Path('owned.vhdx'), check=Mock())
        return bridge.WindowsMarker(backend), disk, state, api, kernel

    def test_only_own_handle_derived_disk_written_and_read_back(self):
        marker, disk, state, api, kernel = self.fixture()
        proof = marker.mark(disk)
        self.assertTrue(proof['windowsDetachConfirmed'])
        self.assertEqual(state['opens'], ['\\\\.\\PhysicalDrive7'])
        self.assertEqual(state['writes'], 1)
        self.assertEqual(state['raw'], disk.marker.ljust(4096, b'\0'))
        self.assertEqual(api.AttachVirtualDisk.call_args.args[2], 2)
        api.DetachVirtualDisk.assert_called_once()

    def test_invalid_capacity_path_nonempty_or_guard_never_writes(self):
        for change in ({'size': 999}, {'physical': '\\\\.\\PhysicalDrive8'},
                       {'physical': 'C:/some-file'}, {'nonzero': True}, {'allowed': False}):
            marker, disk, state, api, kernel = self.fixture(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                marker.mark(disk)
            self.assertEqual(state['writes'], 0)


class BridgeAndGuestTests(unittest.TestCase):
    def test_attach_binds_scanned_nonce_to_store_not_device_order(self):
        marker = agent.device_marker('a' * 32, b'n' * 32)
        disk = types.SimpleNamespace(path=Path('C:/owned/new.vhdx'), check=Mock(), qualify_guest=Mock(),
            marker=marker, identifier='a', file_identity=(1, 2),
            spec=types.SimpleNamespace(logical_bytes=134217728, session='a' * 32))
        scanned = {'device': '/dev/sdz', 'majorMinor': '8:240', 'diskSequence': 7, 'logicalBytes': 134217728}
        calls = Mock(side_effect=['', json.dumps(scanned)])
        transport = bridge.WslBridge(disk, types.SimpleNamespace(allowed=lambda: True), Path.cwd() / 'wsl_bridge.sh', call=calls)
        with patch.object(bridge, 'WindowsMarker') as marker_api:
            marker_api.return_value.mark.return_value = {'markerSha256': hashlib.sha256(marker).hexdigest()}
            proof = transport.attach()
        self.assertEqual(proof['hostFileIdentity'], [1, 2])
        self.assertEqual(proof['diskSequence'], 7)
        disk.qualify_guest.assert_called_once_with(proof)
        self.assertEqual(calls.call_args_list[0].args[0], ['--mount', '--vhd', str(disk.path), '--bare'])
        self.assertEqual(calls.call_args_list[1].args[0][-1], marker.hex())

    def test_attach_timeout_retains_unknown_mapping_and_does_not_unmount(self):
        disk = types.SimpleNamespace(path=Path('C:/owned/new.vhdx'), check=Mock())
        calls = Mock(side_effect=TimeoutError())
        transport = bridge.WslBridge(disk, types.SimpleNamespace(allowed=lambda: True), 'unused', call=calls)
        with patch.object(bridge, 'WindowsMarker') as marker_api, self.assertRaises(TimeoutError):
            transport.attach()
        self.assertIsNone(transport.proof)
        self.assertEqual(calls.call_count, 1)

    def test_fuse_requires_new_growth_and_kills_only_mock_namespace_on_timeout(self):
        class EndCycle(BaseException): pass
        initial = types.SimpleNamespace(st_mode=0o100600, st_size=2, st_dev=1, st_ino=7)
        for case in ('fresh', 'stale', 'replacement'):
            observed = copy.copy(initial)
            observed.st_size = 3 if case != 'stale' else 2
            if case == 'replacement': observed.st_ino = 8
            with self.subTest(case=case), patch.object(agent.sys, 'platform', 'linux'), \
                    patch.object(agent.os, 'getpid', return_value=1), patch.object(agent.os, 'pipe2', return_value=(10, 11), create=True), \
                    patch.object(agent.os, 'O_NONBLOCK', 2048, create=True), patch.object(agent.os, 'O_CLOEXEC', 524288, create=True), \
                    patch.object(agent.os, 'stat', side_effect=[initial, observed]), patch.object(agent.os, 'fork', return_value=0, create=True), \
                    patch.object(agent.os, 'close'), patch.object(agent.os, 'write') as write, patch.object(agent.os, 'kill') as kill, \
                    patch.object(agent.signal, 'SIGKILL', 9, create=True), \
                    patch.object(agent.time, 'monotonic', side_effect=[0, 0, 3 if case == 'stale' else .1]), \
                    patch.object(agent.time, 'sleep', side_effect=EndCycle):
                with self.assertRaises(EndCycle): agent.namespace_fuse('fake-pulse')
                if case == 'fresh':
                    self.assertEqual(write.call_args.args, (11, b'B')); kill.assert_not_called()
                else:
                    self.assertEqual(write.call_args.args, (11, b'L' if case == 'stale' else b'I'))
                    self.assertEqual(kill.call_args_list[0].args, (-1, agent.signal.SIGKILL))

    def test_mapping_validates_exact_types_paths_capacity(self):
        good = {'device': '/dev/sdz', 'majorMinor': '8:240', 'diskSequence': 7, 'logicalBytes': 134217728}
        bridge.validate_scan(good)
        for key, bad in [('device', '/dev/sda1'), ('device', '/dev/dxg'), ('diskSequence', True),
                         ('diskSequence', 0), ('logicalBytes', 32 * engine.GIB), ('majorMinor', 'invalid')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                bridge.validate_scan({**good, key: bad})

    def test_detach_requires_all_stop_proofs_then_exact_owned_path(self):
        disk = types.SimpleNamespace(path=Path('C:/owned/store.vhdx'), check=Mock(),
                    spec=types.SimpleNamespace(logical_bytes=134217728, session='a' * 32))
        mapping = {'deviceToken': 'd' * 64, 'device': '/dev/sdz', 'diskSequence': 7}
        call = Mock(return_value='{"releaseCheck":true}')
        transport = bridge.WslBridge(disk, Mock(), Path.cwd() / 'wsl_bridge.sh', call=call)
        transport.proof = mapping
        ready, stopped = events()
        for key in ('enginesStopped', 'unmounted', 'exclusiveDeviceClaim', 'deviceToken'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                transport.detach(guest={**stopped, key: False}, capsule_stopped=True)
        call.assert_not_called()
        self.assertTrue(transport.detach(guest=stopped, capsule_stopped=True))
        self.assertEqual(call.call_args.args[0], ['--unmount', str(disk.path)])
        self.assertTrue(all(args.args[0] != ['--unmount'] for args in call.call_args_list))

    def test_tmpfs_actual_caps_and_flags(self):
        sizes = {'/exec': '262144k', '/run': '65536k', '/tmp': '64k', '/store': '4k', '/dev/shm': '64k'}
        rows = [{'path': path, 'fstype': 'tmpfs', 'superOptions': ['size=' + size],
                 'options': ['rw', 'nosuid', 'nodev'] + ([] if path == '/exec' else ['noexec'])}
                for path, size in sizes.items()]
        guest.validate_tmpfs(rows)
        for name, change in [('/exec', {'superOptions': ['size=524288k']}),
                             ('/tmp', {'options': ['rw', 'nosuid', 'nodev']}),
                             ('/store', {'fstype': 'ext4'})]:
            bad = [{**r, **change} if r['path'] == name else r for r in rows]
            with self.subTest(name=name), self.assertRaises(ValueError):
                guest.validate_tmpfs(bad)

    def test_readiness_and_stop_missing_identity_or_proof_rejected(self):
        ready, stopped = events()
        native.validate_guest(ready, stopped, 'd' * 64)
        for key in ('unmounted', 'enginesStopped', 'exclusiveDeviceClaim'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                native.validate_guest(ready, {**stopped, key: False}, 'd' * 64)
        ready['engine']['Images'] = 1
        with self.assertRaises(ValueError):
            native.validate_ready(ready, 'd' * 64)


class ConnectedNativeOperationTests(unittest.TestCase):
    def exercise(self, root, *, bad_ready=False, missing_stop=False, drift=False, permission=True, cleanup_unconfirmed=False):
        runtime_root = root / 'runtime'; runtime_root.mkdir()
        raw = b'{"tiny":"fixture"}'; (runtime_root / 'runtime.json').write_bytes(raw)
        approval = root / 'approval-fixture.json'; approval.write_text('{}')
        (root / 'guest').mkdir()
        value = {**packet(), 'capsuleImageId': 'sha256:' + 'b' * 64,
            'runtime': {'directory': str(runtime_root), 'manifestSha256': hashlib.sha256(raw).hexdigest()},
            'daemonConfiguration': engine.daemon_configuration(), 'containerdConfiguration': engine.containerd_configuration(),
            'nativeInputSha256': {n: hashlib.sha256((admission.image.HERE / n).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                 for n in ('isolated_agent.py', 'isolated_guest.py', 'wsl_bridge.sh')}}
        permit = admission.Permit(native.guarded.build.sha(value), json.dumps(value), 'test')
        disk = types.SimpleNamespace(marker=agent.device_marker('a' * 32, b'n' * 32),
            spec=types.SimpleNamespace(logical_bytes=134217728), create=Mock(return_value={'test': 'no native disk created'}))
        mapping = {'device': '/dev/sdz', 'deviceToken': 'd' * 64, 'diskSequence': 7, 'majorMinor': '8:240'}
        transport = Mock(attach=Mock(return_value=mapping), detach=Mock(return_value=True))
        contract = engine.Spec('a' * 32, value['capsuleImageId'], str(root / 'guest'), str(runtime_root), '/dev/sdz', permit.review_sha256)
        row = fixtures.capsule_info(contract)
        row['Config']['Env'].append('COPILOT_REVIEW_SHA256=' + permit.review_sha256)
        row['State'].update(Status='created', Running=False, Pid=0)
        ready, stopped = events()
        if bad_ready:
            ready['limits']['memory.max'] = 'max'
        calls, log_count = [], [0]
        def call(*args, **kwargs):
            calls.append(args)
            if args[0] == 'create': return 'c' * 64
            if args[0] == 'start': row['State'].update(Status='running', Running=True, Pid=42)
            if args[0] == 'logs':
                log_count[0] += 1
                if log_count[0] == 1: return json.dumps(ready)
                row['State'].update(Status='exited', Running=False, Pid=0)
                if drift: row['HostConfig']['Memory'] = 0
                return '\n'.join(json.dumps(e) for e in ([ready] if missing_stop else [ready, stopped]))
            if args[0] in ('stop', 'kill'): row['State'].update(Status='exited', Running=False, Pid=0)
            return ''
        docker = Mock(call=Mock(side_effect=call), inspect=Mock(side_effect=lambda _: copy.deepcopy(row)))
        with patch.object(admission, 'APPROVAL', approval), patch.object(native.time, 'sleep'):
            try:
                result = native.operation(permit, root, lambda: permission,
                    disk_factory=lambda *_: disk, backend_factory=lambda **_: Mock(),
                    bridge_factory=lambda *_: transport, docker_factory=lambda: docker)
                return result, transport, calls
            finally:
                self.assertTrue(all(a[0] in ('create', 'start', 'logs', 'stop', 'kill') for a in calls))
                self.assertNotIn('pull', [a[0] for a in calls])
                if (root / 'capsule-owned.json').exists():
                    self.assertEqual(json.loads((root / 'native-stop.json').read_text())['stopConfirmed'], not cleanup_unconfirmed)

    def test_connected_create_bridge_inputs_start_fault_stop_detach(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result, transport, calls = self.exercise(root)
            self.assertTrue(result['storeDetached'])
            self.assertTrue((root / 'withhold.request').exists())
            self.assertTrue((root / 'guest/isolated_guest.py').exists())
            self.assertFalse(result['imageImportEnabled'])
            transport.detach.assert_called_once()
            args = calls[0]
            self.assertIn('--pull=never', args)
            self.assertIn('--read-only', args)

    def test_bad_readiness_stop_or_configuration_keeps_store_attached(self):
        for case in ('bad_ready', 'missing_stop', 'drift'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with self.assertRaises(ValueError):
                    self.exercise(root, **{case: True})
                self.assertFalse((root / 'guest-stopped.json').exists() and
                                 json.loads((root / 'native-stop.json').read_text())['storeDetached'])
                if case == 'bad_ready':
                    self.assertFalse((root / 'withhold.request').exists())

    def test_permission_lost_never_creates_disk_or_capsule(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'PERMISSION_LOST'):
                self.exercise(Path(temp), permission=False)
            self.assertFalse((Path(temp) / 'native-created.json').exists())

    def test_final_stop_uncertainty_cannot_return_success(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(engine.Capsule, 'stop',
                return_value={'stopConfirmed': False, 'forced': True, 'errors': ['STOP_UNCONFIRMED']}):
            with self.assertRaisesRegex(ValueError, 'NATIVE_ENGINE_STOP_UNCONFIRMED'):
                self.exercise(Path(temp), cleanup_unconfirmed=True)


if __name__ == '__main__':
    unittest.main()
