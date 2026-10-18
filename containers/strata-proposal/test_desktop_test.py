"""Tiny offline Desktop import/build tests. Docker and model execution are mocked."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import desktop_test as desktop
import import_rehearsal
import oci_archive


def packet():
    return {'image': {'image': 'nvidia/cuda@sha256:' + 'a' * 64,
                     'configDigest': 'sha256:' + 'b' * 64, 'manifestSha256': 'a' * 64},
        'archive': {'exactBytes': 1024}, 'buildReviewSha256': 'c' * 64,
        'sourceEvidenceSha256': 'd' * 64,
        'thermalPolicy': {'temperature': {'source': 'ASUS DSTS 0x00120094'}},
        'acceptSourceLimitation': desktop.LIMITATION, 'workSeconds': 1800}


def result(value):
    return {'scope': desktop.SCOPE, 'synthetic': False, 'reviewSha256': desktop.build.sha(value),
        'image': value['image']['image'], 'imageId': value['image']['configDigest'],
        'archive': {'archiveBytes': value['archive']['exactBytes']},
        'load': {'clientExitCode': 0}, 'loadRequestCompleted': True, 'daemonStopClaimed': False,
        'imageDownloadEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}


def decision(value):
    return {'version': 1, 'status': 'owner-approved-one-desktop-import-and-cpu-build',
        'scope': desktop.SCOPE, 'reviewSha256': desktop.build.sha(value),
        'buildReviewSha256': value['buildReviewSha256'], 'sourceEvidenceSha256': value['sourceEvidenceSha256'],
        'acceptSourceLimitation': desktop.LIMITATION,
        'acceptSharedDaemonCancellationLimitation': desktop.CANCELLATION,
        'thermalPolicySha256': desktop.build.sha(value['thermalPolicy']),
        'acceptUnknownThrottleForThisScope': True, 'imageImportEnabled': True, 'buildEnabled': True,
        'imageDownloadEnabled': False, 'modelLaunchEnabled': False, 'synthetic': False,
        'maximumAttempts': 1, 'ownerMessage': 'Offline test decision only'}


class DesktopAdmissionTests(unittest.TestCase):
    def test_no_approval_refuses_before_any_process_or_reader(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop, 'APPROVAL', Path(temp) / 'absent'), \
                patch.object(desktop, 'review') as review, patch.object(desktop.guarded.cpu_feed, 'Feed') as feed, \
                patch.object(desktop.first_build, 'run') as build:
            with self.assertRaisesRegex(ValueError, 'NOT_APPROVED'):
                desktop.run()
            review.assert_not_called(); feed.assert_not_called(); build.assert_not_called()

    def test_storage_selection_alone_does_not_authorize_a_workload(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop, 'APPROVAL', Path(temp) / 'absent'), \
                patch.object(desktop, 'STORAGE', Path(temp) / 'storage.json'):
            desktop.STORAGE.write_text('{"status":"owner-approved-normal-desktop-storage-for-first-test"}')
            with self.assertRaisesRegex(ValueError, 'NOT_APPROVED'):
                desktop.authorize()

    def test_approval_cannot_enable_model_omit_limitations_or_swap_build(self):
        value = packet(); receipt = decision(value)
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop, 'APPROVAL', Path(temp) / 'approval.json'), \
                patch.object(desktop, 'review', return_value=(receipt['reviewSha256'], value)):
            for key, bad in [('version', True), ('maximumAttempts', True), ('maximumAttempts', 2),
                    ('scope', 'model-runtime'), ('reviewSha256', 'changed'), ('buildReviewSha256', 'changed'),
                    ('sourceEvidenceSha256', 'changed'), ('acceptSharedDaemonCancellationLimitation', ''),
                    ('acceptUnknownThrottleForThisScope', False), ('imageDownloadEnabled', True),
                    ('modelLaunchEnabled', True), ('synthetic', True), ('ownerMessage', '')]:
                desktop.APPROVAL.write_text(json.dumps({**receipt, key: bad}))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    desktop.authorize()
            desktop.APPROVAL.write_text(json.dumps(receipt))
            self.assertEqual(desktop.authorize().packet, value)

    def test_import_result_rejects_synthetic_wrong_image_or_claimed_daemon_stop(self):
        value = packet(); good = result(value)
        desktop.validate_result(good, value, False)
        for key, bad in [('synthetic', True), ('imageId', 'other'), ('loadRequestCompleted', False),
                         ('daemonStopClaimed', True), ('modelLaunchEnabled', True), ('buildEnabled', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                desktop.validate_result({**good, key: bad}, value, False)

    def test_no_build_delegation_on_failed_synthetic_or_unstopped_import(self):
        value = packet(); permit = desktop.Permit(desktop.build.sha(value), json.dumps(value), 'e' * 64)
        good = {'phase': 'COMPLETE', 'synthetic': False, 'reviewSha256': permit.review_sha256,
                'readerStopped': True, 'stopConfirmed': True, 'result': result(value)}
        with patch.object(desktop.build, 'review') as build_review:
            for key, bad in [('phase', 'FAULT'), ('synthetic', True), ('readerStopped', False),
                             ('stopConfirmed', False), ('reviewSha256', 'wrong')]:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    desktop.delegate_build(permit, {**good, key: bad})
            build_review.assert_not_called()

    def test_build_delegates_exact_combined_owner_scope_without_overwrite(self):
        value = packet(); permit = desktop.Permit(desktop.build.sha(value), json.dumps(value), 'e' * 64)
        state = {'phase': 'COMPLETE', 'synthetic': False, 'reviewSha256': permit.review_sha256,
                 'readerStopped': True, 'stopConfirmed': True, 'result': result(value)}
        bp = {'scope': 'cpu-build', 'sourceReviewSha256': 'f' * 64}
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop.build, 'APPROVAL', Path(temp) / 'build.json'), \
                patch.object(desktop, 'APPROVAL', Path(temp) / 'owner.json'), \
                patch.object(desktop, 'authorize', return_value=permit), \
                patch.object(desktop.build, 'review', return_value=(value['buildReviewSha256'], bp)), \
                patch.object(desktop.build, 'authorize', return_value='authorized'):
            desktop.APPROVAL.write_text(json.dumps(decision(value)))
            self.assertEqual(desktop.delegate_build(permit, state), 'authorized')
            saved = json.loads(desktop.build.APPROVAL.read_text())
            self.assertEqual(saved['combinedReviewSha256'], permit.review_sha256)
            self.assertEqual(saved['acceptSourceQualificationSha256'], bp['sourceReviewSha256'])
            self.assertFalse(saved['modelLaunchEnabled'])
            with self.assertRaises(FileExistsError):
                desktop.delegate_build(permit, state)


class DesktopTransportTests(unittest.TestCase):
    def fixture(self, root):
        rows, blobs = import_rehearsal.fixture(); cache = root / 'cache'; cache.mkdir()
        for digest, raw in blobs.items(): (cache / digest).write_bytes(raw)
        value = packet(); value.update(preserved={'cache': str(cache)}, disk={'hostReserveBytes': 0})
        value['archive']['exactBytes'] = oci_archive.archive_bytes(rows)
        return value, rows, blobs

    def test_complete_archive_hashes_real_fixture_bytes_before_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); value, rows, blobs = self.fixture(root)
            with patch.object(desktop, 'rows', return_value=rows):
                archive, receipt = desktop.write_archive(root, value, lambda: True)
            self.assertEqual(archive.stat().st_size, value['archive']['exactBytes'])
            self.assertEqual(receipt['archiveBytes'], value['archive']['exactBytes'])
            self.assertIn('fileIdentity', receipt)
            self.assertEqual(set(blobs), {p.name for p in (root / 'cache').iterdir()})

    def test_corrupt_or_missing_cache_never_reaches_docker(self):
        for mode in ('corrupt', 'missing'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); value, rows, blobs = self.fixture(root)
                target = root / 'cache' / rows[-1].sha256
                if mode == 'corrupt': target.write_bytes(b'X' * target.stat().st_size)
                else: target.unlink()
                with patch.object(desktop, 'rows', return_value=rows), patch.object(desktop.subprocess, 'Popen') as start:
                    with self.assertRaises(ValueError): desktop.write_archive(root, value, lambda: True)
                    start.assert_not_called()

    def test_guard_loss_keeps_partial_archive_and_never_opens_client(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); value, rows, _ = self.fixture(root)
            with patch.object(desktop, 'rows', return_value=rows):
                with self.assertRaisesRegex(ValueError, 'GUARD_LOST'):
                    desktop.write_archive(root, value, lambda: False)
            self.assertTrue((root / 'cuda-base.oci.tar').exists())

    def test_load_uses_file_input_and_no_registry_or_container_start(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); value = packet(); archive = root / 'archive.tar'
            archive.write_bytes(b'X' * value['archive']['exactBytes'])
            process = Mock(stdout=io.BytesIO(b'Loaded image\n'), returncode=0)
            process.poll.return_value = 0
            start = Mock(return_value=process)
            loaded = desktop.load_archive(root, archive, value, lambda: True, popen=start)
            argv = start.call_args.args[0]
            self.assertEqual(argv[1:3], ['image', 'load'])
            self.assertIn('--input', argv); self.assertNotIn('pull', argv); self.assertNotIn('run', argv)
            self.assertEqual(loaded['clientExitCode'], 0)
            process.kill.assert_not_called()

    def test_revoked_permission_stops_client_and_retains_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); value = packet(); archive = root / 'archive.tar'
            archive.write_bytes(b'X' * value['archive']['exactBytes'])
            process = Mock(stdout=io.BytesIO(b'partial\n'), returncode=125)
            process.poll.return_value = None
            calls = [True, False]
            with self.assertRaises(ValueError):
                desktop.load_archive(root, archive, value, lambda: calls.pop(0), popen=Mock(return_value=process))
            process.kill.assert_called_once()
            self.assertTrue((root / 'load-output.txt').exists())

    def test_daemon_unpack_error_is_failure_even_when_client_exits_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); value = packet(); archive = root / 'archive.tar'
            archive.write_bytes(b'X' * value['archive']['exactBytes'])
            process = Mock(stdout=io.BytesIO(b'Loaded image\nError unpacking image nvidia/cuda: disk full\n'), returncode=0)
            process.poll.return_value = 0
            with self.assertRaisesRegex(ValueError, 'LOAD_FAILED'):
                desktop.load_archive(root, archive, value, lambda: True, popen=Mock(return_value=process))
            self.assertIn(b'Error unpacking', (root / 'load-output.txt').read_bytes())

    def test_oci_name_is_fixed_to_pinned_repository_and_digest(self):
        rows, blobs = import_rehearsal.fixture()
        manifest, config = rows[2].inline, blobs[rows[3].sha256]
        name = 'docker.io/nvidia/cuda@sha256:' + rows[2].sha256
        actual = oci_archive.members(manifest, config, expected_manifest=rows[2].sha256, image_name=name)
        self.assertEqual(json.loads(actual[1].inline)['manifests'][0]['annotations']['io.containerd.image.name'], name)
        with self.assertRaises(ValueError):
            oci_archive.members(manifest, config, expected_manifest=rows[2].sha256, image_name='other:latest')


class ContainerdIdentityTests(unittest.TestCase):
    def test_manifest_ids_are_valid_only_with_matching_descriptor_and_diffids(self):
        value = packet(); identity = value['image']; identity['layers'] = [{'expandedSha256': 'f' * 64}]
        row = {'Id': 'sha256:' + 'a' * 64, 'Descriptor': {'digest': 'sha256:' + 'a' * 64},
               'Os': 'linux', 'Architecture': 'amd64', 'RepoDigests': [identity['image']],
               'RootFS': {'Layers': ['sha256:' + 'f' * 64]}}
        docker = Mock(call=Mock(return_value=json.dumps([row])))
        self.assertEqual(desktop.build.image_ready(docker, value), row['Id'])
        for key, bad in [('Descriptor', {}), ('Id', 'sha256:' + '0' * 64),
                         ('RepoDigests', []), ('RootFS', {'Layers': []})]:
            docker.call.return_value = json.dumps([{**row, key: bad}])
            with self.subTest(key=key), self.assertRaises(ValueError): desktop.build.image_ready(docker, value)


class ConnectedDesktopTests(unittest.TestCase):
    def test_archive_loader_identity_and_result_are_connected_without_native_work(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop, 'LIVE', Path(temp)):
            root = Path(temp)
            value, rows, blobs = DesktopTransportTests().fixture(root)
            permit = desktop.Permit(desktop.build.sha(value), json.dumps(value), 'e' * 64)
            (root / 'attempt.json').write_text(json.dumps({'reviewSha256': permit.review_sha256,
                'scope': desktop.SCOPE, 'synthetic': False}))
            desktop.guarded.controller.pulse(root / 'controller.pulse', maximum=4096)
            process = Mock(stdout=io.BytesIO(b'Loaded image\n'), returncode=0)
            process.poll.return_value = 0
            with patch.object(desktop, 'authorize', return_value=permit), patch.object(desktop, 'rows', return_value=rows), \
                    patch.object(desktop.subprocess, 'Popen', return_value=process) as client, \
                    patch.object(desktop.build, 'image_ready', return_value=value['image']['configDigest']):
                # Resolve the default argument at this test boundary so all
                # native process creation remains mocked.
                real_load = desktop.load_archive
                with patch.object(desktop, 'load_archive', side_effect=lambda *args: real_load(*args, popen=client)):
                    desktop.child()
            saved = json.loads((root / 'worker-result.json').read_text())
            desktop.validate_result(saved, value, False)
            self.assertEqual(saved['archive']['members'], len(rows))
            self.assertEqual(saved['load']['clientExitCode'], 0)
            self.assertFalse(saved['daemonStopClaimed'])
            self.assertEqual(client.call_count, 1)

    def run_parent(self, root, phase, *, build_failure=False):
        value = packet()
        value.update(preserved={}, preservedNative={},
            proposedVmEnvelope={'proposalSha256': 'f' * 64}, disk={'hostReserveBytes': 0, 'budget': {}},
            readerSamples=1920)
        permit = desktop.Permit(desktop.build.sha(value), json.dumps(value), 'e' * 64)
        state = {'phase': phase, 'synthetic': False, 'readerStopped': True, 'stopConfirmed': True,
                 'reviewSha256': permit.review_sha256}
        if phase == 'COMPLETE': state['result'] = result(value)
        proof = root / 'capacity'; proof.mkdir()
        (proof / 'result.json').write_text('{"guestSwapTotalBytes":0}')
        events = []
        def execute(*args, **kwargs):
            events.append('import-monitor')
            self.assertTrue(kwargs['import_enabled']); self.assertFalse(kwargs['download_enabled'])
            (root / 'live/load-requested.json').write_text('{}')
            return state
        def delegate(*args): events.append('delegate-build')
        def compile():
            events.append('cpu-build')
            if build_failure: raise ValueError('SYNTHETIC_BUILD_FAILURE')
            return {'phase': 'COMPLETE', 'modelLaunchEnabled': False}
        with patch.object(desktop, 'LIVE', root / 'live'), patch.object(desktop, 'authorize', return_value=permit), \
                patch.object(desktop.build, 'APPROVAL', root / 'absent-build-approval'), \
                patch.object(desktop.build, 'LIVE', root / 'build'), \
                patch.object(desktop.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=1), \
                patch.object(desktop.tools, 'sha', return_value='f' * 64), \
                patch.object(desktop.preserved_import, 'binding', return_value={}), \
                patch.object(desktop, 'native_binding', return_value={}), \
                patch.object(desktop.build, 'vm_ready'), \
                patch.object(desktop.guarded.probe_image_storage, 'probe', return_value=proof), \
                patch.object(desktop.images, 'capacity', return_value={'withinProposedBudgetAtProbe': True}), \
                patch.object(desktop.guarded.cpu_feed, 'Feed', return_value=types.SimpleNamespace(directory=root / 'reader')), \
                patch.object(desktop.guarded, '_execute', side_effect=execute), \
                patch.object(desktop, 'delegate_build', side_effect=delegate), \
                patch.object(desktop.first_build, 'run', side_effect=compile):
            value = desktop.run()
        return value, events

    def test_guarded_import_then_existing_build_is_one_linear_operation(self):
        with tempfile.TemporaryDirectory() as temp:
            value, events = self.run_parent(Path(temp), 'COMPLETE')
            self.assertEqual(events, ['import-monitor', 'delegate-build', 'cpu-build'])
            self.assertEqual(value['phase'], 'COMPLETE')
            self.assertFalse(value['modelLaunchEnabled'])

    def test_failed_import_blocks_build_and_keeps_daemon_uncertainty(self):
        with tempfile.TemporaryDirectory() as temp:
            value, events = self.run_parent(Path(temp), 'FAULT')
            self.assertEqual(events, ['import-monitor'])
            self.assertTrue(value['sharedDaemonCancellationUnconfirmed'])

    def test_build_failure_keeps_import_evidence_and_never_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_BUILD_FAILURE'):
                self.run_parent(root, 'COMPLETE', build_failure=True)
            saved = json.loads((root / 'live/cpu-build-error.json').read_text())
            self.assertFalse(saved['automaticRetry'])
            self.assertEqual(json.loads((root / 'live/state.json').read_text())['phase'], 'COMPLETE')


if __name__ == '__main__':
    unittest.main()
