import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import build_admission as admission
import build_policy_review as policy
import controller_session as controller
import cpu_feed
import cpu_source_review as source
import first_build
import offline_target
from test_controller_session import Clock, Docker
from test_artifact_export import archive, elf
import tarfile


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.probe, self.reference = self.root / 'probe.json', self.root / 'reference.txt'
        self.reference.write_bytes(b'public const int Temp_CPU = 0x00120094;\nreturn BitConverter.ToInt32(status, 0) - 65536;')
        self.data = {'version': 1, 'status': 'TEN_SAMPLES_OBSERVED_NOT_CERTIFIED', 'synthetic': False,
                     'readerSha256': source.READER_SHA, 'validatedCpuSensor': False, 'cpuThermalThrottling': None,
                     'workloadStarted': False, 'readerStopped': True,
                     'samples': [policy.synthetic(i + 1, i, synthetic=False, validatedCpuSensor=False,
                                   cpuTemperatureC=75 + i % 3) for i in range(10)]}
        self.scope = patch.multiple(source, PROBE=self.probe, REFERENCE=self.reference,
                                    REFERENCE_SHA=hashlib.sha256(self.reference.read_bytes()).hexdigest())
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def report(self):
        raw = admission.encoded(self.data)
        self.probe.write_bytes(raw)
        with patch.object(source, 'PROBE_SHA', hashlib.sha256(raw).hexdigest()):
            return source.report()

    def test_candidate_is_qualified_only_for_review_without_activation(self):
        result = self.report()
        self.assertEqual(result['status'], 'QUALIFIED_FOR_OWNER_REVIEW_NOT_ACTIVATED')
        self.assertTrue(all(result['checks'].values()))
        self.assertFalse(result['validatedCpuSensor'])
        self.assertFalse(result['buildEnabled'])
        self.assertIn(source.LIMITATION, result['limitations'])

    def test_source_changes_synthetic_frames_query_overrun_and_bad_coverage_reject(self):
        original = copy.deepcopy(self.data)
        changes = [lambda r: r.update(synthetic=True), lambda r: r.update(readerStopped=False),
                   lambda r: r['samples'][1].update(sequence=1),
                   lambda r: r['samples'][1].update(querySeconds=1.1),
                   lambda r: r['samples'][1].update(recordedAtUnix=1005),
                   lambda r: r['samples'][1].update(cpuThermalThrottling=False),
                   lambda r: r['samples'][1].update(validatedCpuSensor=True),
                   lambda r: r.update(readerSha256='0' * 64)]
        for change in changes:
            self.data = copy.deepcopy(original)
            change(self.data)
            with self.assertRaises(ValueError):
                self.report()

    def test_unchanging_or_nonoverlapping_values_do_not_pass_review(self):
        for value in (75, 120):
            for row in self.data['samples']:
                row['cpuTemperatureC'] = value
            with self.assertRaises(ValueError):
                self.report()

    def test_probe_and_reference_bytes_are_bound(self):
        self.probe.write_bytes(admission.encoded(self.data))
        with self.assertRaises(ValueError):
            source.report()
        self.reference.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.report()


class FullSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'strata-build'
        self.package = self.root / '12345678'
        self.source = self.package / 'input/source'
        self.source.mkdir(parents=True)
        downloads = self.root / 'downloads'
        downloads.mkdir()
        rows = []
        for label, repo, commit, relative in [('strata', 'org/s', 'a' * 40, 'unfingerprinted.txt'),
                                               ('llama', 'org/l', 'b' * 40, 'file.cpp')]:
            archive = downloads / (label + '-' + commit + '.zip')
            payload = b'tiny pinned source\n'
            with zipfile.ZipFile(archive, 'w') as stream:
                stream.writestr(repo.split('/')[1] + '-' + commit + '/' + relative, payload)
            target = self.source / relative if label == 'strata' else self.source / 'third_party/llama.cpp' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            rows.append({'repository': repo, 'commit': commit, 'archiveBytes': archive.stat().st_size,
                         'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
        (self.package / 'build-manifest.json').write_text(json.dumps({'sources': rows}))
        self.plan = {'sourcePackage': str(self.package)}

    def test_every_file_is_compared_against_the_pinned_archives(self):
        result = admission.source_tree(self.plan)
        self.assertEqual(result['files'], 2)
        self.assertTrue(result['verifiedAgainstPinnedArchives'])

    def test_changed_extra_missing_and_hardlinked_source_are_rejected(self):
        path = self.source / 'unfingerprinted.txt'
        original = path.read_bytes()
        path.write_bytes(b'x' * len(original))
        with self.assertRaisesRegex(ValueError, 'differs'):
            admission.source_tree(self.plan)
        path.write_bytes(original)
        extra = self.source / 'extra.cmake'
        extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'Extra'):
            admission.source_tree(self.plan)
        extra.unlink()
        extra.hardlink_to(path)
        with self.assertRaises(ValueError):
            admission.source_tree(self.plan)
        extra.unlink()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            admission.source_tree(self.plan)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'approval.json'
        self.packet = {'scope': 'one-cpu-only-linux-compile-no-engine-execution', 'sourceReviewSha256': 'a' * 64}
        self.digest = admission.sha(self.packet)
        self.approval = {'version': 1, 'status': 'owner-approved-one-cpu-build', 'synthetic': False,
                         'buildEnabled': True, 'reviewSha256': self.digest, 'scope': self.packet['scope'],
                         'acceptSourceQualificationSha256': 'a' * 64, 'acceptSourceLimitation': source.LIMITATION,
                         'maximumAttempts': 1, 'ownerMessage': 'UNIT TEST ONLY: no real authorization',
                         'modelLaunchEnabled': False, 'imageDownloadEnabled': False, 'imageImportEnabled': False}
        self.scopes = [patch.object(admission, 'APPROVAL', self.path),
                       patch.object(admission, 'review', return_value=(self.digest, self.packet))]
        for scope in self.scopes:
            scope.start()
            self.addCleanup(scope.stop)

    def authorize(self):
        self.path.write_text(json.dumps(self.approval))
        return admission.authorize()

    def test_missing_approval_rejects_before_any_real_process_or_docker(self):
        with patch.object(first_build.guard.base, 'Docker') as docker, patch.object(cpu_feed.Feed, 'start_reader') as reader:
            with self.assertRaisesRegex(ValueError, 'NOT_APPROVED'):
                first_build.run()
            docker.assert_not_called()
            reader.assert_not_called()

    def test_approval_cannot_widen_scope_reuse_hash_or_omit_source_acceptance(self):
        original = copy.deepcopy(self.approval)
        for key, value in [('reviewSha256', 'b' * 64), ('scope', 'model-runtime'), ('synthetic', True),
                           ('buildEnabled', False), ('maximumAttempts', 2), ('maximumAttempts', True),
                           ('modelLaunchEnabled', True), ('imageImportEnabled', True),
                           ('acceptSourceLimitation', ''), ('acceptSourceQualificationSha256', 'b' * 64),
                           ('ownerMessage', '')]:
            self.approval = {**original, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.authorize()

    def test_permit_preserves_unknown_channel_and_never_rewrites_raw_frame(self):
        permit = admission.Permit('a' * 64, admission.encoded({
            'controls': {'source': 'ASUS DSTS 0x00120094'}, 'sourceReviewSha256': 'c' * 64}).decode(), 'b' * 64)
        raw = policy.synthetic(1, 0, synthetic=False, validatedCpuSensor=False)
        admitted = permit.qualify(raw)
        self.assertFalse(raw['validatedCpuSensor'])
        self.assertTrue(admitted['validatedCpuSensor'])
        self.assertFalse(admitted['rawValidatedCpuSensor'])
        self.assertIsNone(admitted['cpuThermalThrottling'])
        for field, value in [('synthetic', True), ('validatedCpuSensor', True), ('cpuThermalThrottling', False)]:
            with self.assertRaises(ValueError):
                permit.qualify({**raw, field: value})

    def test_one_attempt_claim_cannot_be_reopened_after_any_outcome(self):
        root = self.path.parent
        permit = SimpleNamespace(review_sha256='a' * 64)
        with patch.object(admission, 'LIVE', root):
            first_build._claim(root / 'sessions' / ('a' * 32), permit)
            with self.assertRaisesRegex(ValueError, 'CONSUMED'):
                first_build._claim(root / 'sessions' / ('b' * 32), permit)

    def test_exact_image_content_platform_and_ordered_diff_ids_required(self):
        identity = {'image': 'nvidia/cuda@sha256:' + 'a' * 64, 'configDigest': 'sha256:' + 'b' * 64,
                    'layers': [{'expandedSha256': 'c' * 64}]}
        image = {'Id': identity['configDigest'], 'Os': 'linux', 'Architecture': 'amd64',
                 'RepoDigests': [identity['image']], 'RootFS': {'Layers': ['sha256:' + 'c' * 64]}}
        docker = Mock()
        docker.call.return_value = json.dumps([image])
        self.assertEqual(admission.image_ready(docker, {'image': identity}), identity['configDigest'])
        for key, value in [('Id', 'changed'), ('Architecture', 'arm64'), ('RepoDigests', []),
                           ('RootFS', {'Layers': ['sha256:' + 'd' * 64]})]:
            docker.call.return_value = json.dumps([{**image, key: value}])
            with self.assertRaises(ValueError):
                admission.image_ready(docker, {'image': identity})

    def test_daemon_envelope_requires_the_reviewed_vm_limits(self):
        packet = {'proposedVmEnvelope': {'logicalProcessors': 1, 'maximumReportedMemoryBytes': 6 * 1024**3}}
        docker = Mock()
        docker.call.return_value = json.dumps({'NCPU': 1, 'MemTotal': 5 * 1024**3})
        self.assertEqual(admission.vm_ready(docker, packet)['logicalProcessors'], 1)
        for data in ({'NCPU': 24, 'MemTotal': 16 * 1024**3}, {'NCPU': 1, 'MemTotal': 7 * 1024**3},
                     {'NCPU': True, 'MemTotal': 5 * 1024**3}):
            docker.call.return_value = json.dumps(data)
            with self.assertRaisesRegex(ValueError, 'NOT_ACTIVE'):
                admission.vm_ready(docker, packet)


class AdmittedControllerTests(unittest.TestCase):
    """Real-mode kernel with fake transport/frames; no live approval is written."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / 'live'
        self.directory = self.live / 'sessions' / ('a' * 32)
        self.directory.mkdir(parents=True)
        offline_directory, plan_sha, _ = admission.selected()
        controls = policy.load_effective_controls()
        self.packet = {'offlineDirectory': str(offline_directory), 'offlinePlanSha256': plan_sha,
                       'liveNamespace': str(self.live), 'controls': controls['temperature'],
                       'outerSeconds': 1910, 'admissionWaitSeconds': 90, 'sourceReviewSha256': 'c' * 64}
        self.permit = admission.Permit(admission.sha(self.packet), admission.encoded(self.packet).decode(), 'd' * 64)
        self.scope = patch.object(admission, 'LIVE', self.live)
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.target = offline_target.from_proposal(offline_directory, plan_sha, 'a' * 64)
        self.clock = Clock()
        self.docker = Docker(self.target, self.clock)
        self.docker.info['Image'] = admission.image_plan.metadata()['configDigest']
        reader_root = self.root / 'readers'
        reader = reader_root / ('b' * 32)
        reader.mkdir(parents=True)
        with patch.object(cpu_feed, 'ROOT', reader_root):
            self.feed = cpu_feed.Feed(reader, clock=self.clock, source_permit=self.permit)
        self.feed.process = Mock()
        self.feed.process.poll.return_value = None
        self.monitor = cpu_feed.Monitor(self.feed, unix=lambda: 1000 + self.clock())
        self.session = controller.Session(self.live, self.directory, self.target, self.docker,
                                         clock=self.clock, unix=lambda: 1000 + self.clock(),
                                         monitor=self.monitor, permit=self.permit)

    def tick(self, second, temperature=92):
        self.clock.value = second
        frame = policy.synthetic(second + 1, second, synthetic=False, validatedCpuSensor=False,
                                  cpuTemperatureC=temperature)
        (self.feed.directory / f'sample-{second+1:08d}.json').write_text(json.dumps(frame))
        return self.session.poll()

    def test_admitted_real_mode_needs_fresh_baseline_and_stops_at_97(self):
        for second in range(10):
            self.assertEqual(self.tick(second)['phase'], 'WAITING_BASELINE')
        self.assertEqual(self.tick(10)['phase'], 'ARMED')
        self.docker.info['State'].update(Running=True, Status='running')
        self.assertEqual(self.tick(11, 95)['phase'], 'RUNNING')
        state = self.tick(12, 97)
        self.assertEqual(state['phase'], 'FAULT')
        self.assertEqual(state['fault']['code'], 'CPU_HOT')
        self.assertTrue(state['stopConfirmed'])
        self.assertFalse(state['cleanupComplete'])
        self.assertTrue(state['retainedStoppedTarget'])
        self.assertIsNone(self.monitor.gate.throttle)
        with self.assertRaisesRegex(ValueError, 'consumed'):
            controller.Session(self.live, self.directory, self.target, self.docker,
                clock=self.clock, monitor=self.monitor, permit=self.permit)

    def test_feed_loss_during_running_still_stops_with_approvals_unreadable(self):
        for second in range(11):
            self.tick(second)
        self.docker.info['State'].update(Running=True, Status='running')
        self.clock.value = 14
        with patch.object(admission, 'authorize', side_effect=OSError('approval unavailable')):
            state = self.session.poll()
        self.assertEqual(state['phase'], 'FAULT')
        self.assertTrue(state['stopConfirmed'])
        self.assertFalse(state['cleanupComplete'])
        self.assertTrue(state['retainedStoppedTarget'])

    def test_source_permit_never_qualifies_without_an_owned_live_reader(self):
        self.feed.process = None
        self.assertEqual(self.tick(0)['phase'], 'FAULT')

    def test_wrong_namespace_or_changed_container_image_cannot_proceed(self):
        with self.assertRaisesRegex(ValueError, 'namespace'):
            self.permit.target(self.target, self.root / 'other')
        self.docker.info['Image'] = 'sha256:' + '0' * 64
        state = self.tick(0)
        self.assertEqual(state['phase'], 'FAULT')
        self.assertFalse(state['stopConfirmed'])

    def test_real_mode_export_requires_matching_guard_and_bound_receipt(self):
        for second in range(11):
            self.tick(second)
        self.docker.info['State'].update(Running=True, Status='running')
        self.tick(11)
        self.session.state['phase'] = 'EXPORTING'
        self.session._save()
        lease = SimpleNamespace(age=lambda: 0, changed=True, clock=self.clock)
        transport = controller.GuardedExport(self.live, self.target, self.docker, lease, permit=self.permit)
        self.assertTrue(transport.verify())
        metadata = (Path(self.packet['offlineDirectory']) / 'input/BUILD.json').read_bytes()
        data = archive([('engine', b'', tarfile.DIRTYPE), ('engine/strata', elf(), tarfile.REGTYPE),
                        ('engine/BUILD.json', metadata, tarfile.REGTYPE)])
        transport.copy = lambda path, _end: path.write_bytes(data)
        acknowledged = []
        transport.acknowledge = lambda _end: acknowledged.append(True)
        with patch.object(controller.export, 'ROOT', self.root / 'artifacts'):
            folder, receipt = controller.export.collect(transport, container_id=self.target.container_id,
                        plan_sha256=self.target.plan_sha256, metadata_sha256=self.target.metadata_sha256,
                        synthetic=False, clock=self.clock)
            self.assertTrue(acknowledged)
            self.assertFalse(receipt['synthetic'])
            self.assertEqual(self.session._receipt(folder), str(folder))
            self.docker.info['State'].update(Running=False, Status='exited', ExitCode=0)
            state = self.session.poll(export_directory=folder)
            self.assertEqual(state['phase'], 'COMPLETE')
            self.assertTrue(state['cleanupComplete'])


class FirstBuildRunnerTests(unittest.TestCase):
    """End-to-end production protocol using fake guard/Docker, no OS child."""
    def run_fixture(self, *, failure=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            live = root / 'live'
            source_tree = {'treeSha256': 'a' * 64}
            identity = admission.image_plan.metadata()
            packet = {'sourceTree': source_tree, 'image': identity, 'outerSeconds': 1910,
                      'proposedVmEnvelope': {'guestSwapBytes': 0},
                      'offlineDirectory': 'unused', 'offlinePlanSha256': 'b' * 64,
                      'createArgs': ['create', 'fixed-approved-input']}
            permit = SimpleNamespace(packet=packet, review_sha256='c' * 64)
            target = Mock(container_id='d' * 64, plan_sha256='b' * 64, metadata_sha256='e' * 64)
            stop_events = []
            state_file = live / 'state.json'
            docker = Mock()
            docker.call.return_value = 'd' * 64
            class Watchdog:
                returncode = None
                def poll(self):
                    session = next((live / 'sessions').iterdir())
                    with (session / 'guard.pulse').open('ab') as pulse:
                        pulse.write(b'x')
                    state = json.loads(state_file.read_text()) if state_file.exists() else {'phase': 'ARMED'}
                    if failure and state['phase'] == 'RUNNING':
                        state.update(phase='FAULT', fault={'code':'UNEXPECTED_WORKER_EXIT'},
                                     stopConfirmed=True, cleanupComplete=False)
                        self.returncode = 0
                    if (session / 'export.request').exists():
                        state['phase'] = 'EXPORTING'
                    if (session / 'export.result.json').exists():
                        state.update(phase='COMPLETE', stopConfirmed=True, cleanupComplete=True)
                        self.returncode = 0
                    state_file.write_text(json.dumps(state))
                    return self.returncode
                def wait(self, timeout):
                    if not stop_events:
                        raise AssertionError('Guard wait must not precede emergency stopping')
                    return self.returncode
                def kill(self):
                    raise AssertionError('Completed guard must not be killed')
            watch = Watchdog()
            def call(*args, **kwargs):
                if args[0] == 'start':
                    state_file.write_text(json.dumps({'phase': 'RUNNING'}))
                return 'd' * 64
            docker.call.side_effect = call
            capacity_dir = root / 'capacity'
            capacity_dir.mkdir()
            (capacity_dir / 'result.json').write_text(json.dumps({'guestSwapTotalBytes': 0}))
            artifact = root / 'artifact'
            artifact.mkdir()
            with patch.object(admission, 'LIVE', live), \
                    patch.object(admission, 'authorize', return_value=permit), \
                    patch.object(admission, 'selected', return_value=(None, None, {'toolDirectory': 'unused'})), \
                    patch.object(admission, 'source_tree', return_value=source_tree), \
                    patch.object(admission, 'image_ready'), \
                    patch.object(admission, 'vm_ready'), \
                    patch.object(first_build.ctypes.windll.shell32, 'IsUserAnAdmin', return_value=1), \
                    patch.object(offline_target, 'from_proposal', return_value=target), \
                    patch.object(first_build.offline, 'verified_tools'), \
                    patch.object(first_build.probe_image_storage, 'probe', return_value=capacity_dir), \
                    patch.object(first_build.image_plan, 'capacity', return_value={'withinProposedBudgetAtProbe': True}), \
                    patch.object(first_build.guard.base, 'Docker', return_value=docker), \
                    patch.object(first_build.subprocess, 'Popen', return_value=watch) as launch, \
                    patch.object(first_build, '_ready', return_value=True), \
                    patch.object(first_build.controller, 'GuardedExport'), \
                    patch.object(first_build.export, 'collect', return_value=(artifact, {})), \
                    patch.object(first_build.build_diagnostics, 'collect') as diagnostic, \
                    patch.object(first_build.guard, 'stop_target', side_effect=lambda *a, **k:
                        (stop_events.append(True) or {'stopConfirmed': True, 'cleanupComplete': not failure,
                                                     'retainedStoppedTarget': failure})) as stop:
                if failure:
                    with self.assertRaisesRegex(ValueError,'FIRST_BUILD_FAILED'):
                        first_build.run()
                    diagnostic.assert_called_once()
                    self.assertFalse((live/'emergency.json').exists())
                    self.assertEqual(json.loads(state_file.read_text())['fault']['code'],'UNEXPECTED_WORKER_EXIT')
                else:
                    result = first_build.run()
                    self.assertEqual(result['phase'], 'COMPLETE')
                    diagnostic.assert_not_called()
                self.assertEqual([c.args[0] for c in docker.call.call_args_list].count('start'), 1)
                self.assertTrue((live / 'attempt.json').exists())
                launch.assert_called_once()
                stop.assert_called_once()
                self.assertIs(stop.call_args.kwargs['remove'],False)

    def test_guard_exit_race_is_reread_and_successful_run_cleans_owned_target(self):
        self.run_fixture()

    def test_startup_failure_is_stopped_retained_and_logged_without_false_emergency(self):
        self.run_fixture(failure=True)


if __name__ == '__main__':
    unittest.main()
