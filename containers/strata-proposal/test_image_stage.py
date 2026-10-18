import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import image_admission as admission
import image_stage as stage
import verify_image_stage as fixture


class ImageAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in [('ROOT', self.root / 'review'), ('LIVE', self.root / 'live'), ('APPROVAL', self.root / 'approval.json')]:
            scope = patch.object(admission, name, value)
            scope.start()
            self.addCleanup(scope.stop)

    def decision(self, digest, packet):
        return {'version': 1, 'status': 'owner-approved-one-image-stage', 'scope': admission.SCOPE,
                'reviewSha256': digest, 'sourceEvidenceSha256': packet['sourceEvidenceSha256'],
                'recoveryOfFailedSession': packet['recoveryOf']['sessionId'],
                'acceptSourceLimitation': admission.LIMITATION,
                'acceptImageThermalPolicySha256': stage.build.sha(packet['thermalPolicy']),
                'acceptUnknownThrottleForThisScope': True, 'maximumAttempts': 1,
                'ownerMessage': 'Synthetic test decision only', 'synthetic': False,
                'imageDownloadEnabled': True, 'imageImportEnabled': False,
                'buildEnabled': False, 'modelLaunchEnabled': False}

    def test_no_approval_rejects_before_transport_reader_process_or_namespace(self):
        with patch.object(stage.download, 'RegistrySource') as transport, patch.object(stage.cpu_feed, 'Feed') as reader, \
                patch.object(stage.windows_job, 'Process') as process, patch.object(stage.probe_image_storage, 'probe') as probe:
            for action in (stage.run, stage.child, stage.download.stage_pinned):
                with self.assertRaisesRegex(ValueError, 'IMAGE_STAGING_NOT_APPROVED'):
                    action()
            transport.assert_not_called()
            reader.assert_not_called()
            process.assert_not_called()
            probe.assert_not_called()
        self.assertFalse(admission.LIVE.exists())

    def test_preparation_is_disabled_and_hashes_bind_exact_operation(self):
        directory, packet = admission.prepare()
        digest, checked = admission.review()
        self.assertEqual(packet, checked)
        self.assertEqual(directory.name, digest)
        self.assertEqual(packet['image']['lockedBlobBytes'], 3951095908)
        self.assertEqual(packet['job'], {'singleLogicalProcessor': True, 'memoryBytes': 128 * 1024**2, 'processes': 1})
        self.assertFalse(admission.summary()['approved'])
        self.assertEqual(admission.summary()['status'], 'READY_FOR_OWNER_APPROVAL')
        changed = copy.deepcopy(packet)
        changed['job']['singleLogicalProcessor'] = False
        stage.download.tools.base.atomic(directory / 'review.json', changed)
        with self.assertRaisesRegex(ValueError, 'changed'):
            admission.review()

    def test_approval_cannot_broaden_scope_omit_source_acceptance_or_enable_import(self):
        directory, packet = admission.prepare()
        decision = self.decision(directory.name, packet)
        bad = [('version', 2), ('version', True), ('scope', 'cpu-only-build'), ('reviewSha256', '0' * 64),
               ('recoveryOfFailedSession', 'other'),
               ('sourceEvidenceSha256', '0' * 64), ('acceptSourceLimitation', 'accepted'),
               ('acceptImageThermalPolicySha256', '0' * 64), ('acceptUnknownThrottleForThisScope', False),
               ('maximumAttempts', True), ('maximumAttempts', 2), ('synthetic', True),
               ('imageDownloadEnabled', False), ('imageImportEnabled', True), ('buildEnabled', True),
               ('modelLaunchEnabled', True), ('ownerMessage', '')]
        for key, value in bad:
            admission.APPROVAL.write_text(json.dumps({**decision, key: value}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'SCOPE_OR_HASH'):
                admission.authorize()
        admission.APPROVAL.write_text(json.dumps(decision))
        permit = admission.authorize()
        self.assertEqual(permit.review_sha256, directory.name)

    def test_helper_change_invalidates_saved_review_and_approval(self):
        directory, packet = admission.prepare()
        admission.APPROVAL.write_text(json.dumps(self.decision(directory.name, packet)))
        with patch.object(stage.build, 'helpers', return_value={'changed': 'helper'}):
            with self.assertRaisesRegex(ValueError, 'changed'):
                admission.authorize()

    def test_consumed_attempt_rejects_before_any_fresh_probe_or_worker(self):
        directory, packet = admission.prepare()
        permit = admission.Permit(directory.name, stage.build.encoded(packet).decode(), 'test')
        admission.LIVE.mkdir()
        (admission.LIVE / 'attempt.json').write_text('{}')
        with patch.object(admission, 'authorize', return_value=permit), \
                patch.object(stage.probe_image_storage, 'probe') as probe, patch.object(stage.cpu_feed, 'Feed') as feed:
            with self.assertRaisesRegex(ValueError, 'ATTEMPT_ALREADY_CONSUMED'):
                stage.run()
            probe.assert_not_called()
            feed.assert_not_called()

    def test_spent_approval_cannot_authorize_recovery_or_create_a_new_claim(self):
        admission.prepare()
        previous = admission.HERE / 'image-stage-approval.json'
        admission.APPROVAL.write_bytes(previous.read_bytes())
        with patch.object(stage.cpu_feed, 'Feed') as reader, patch.object(stage.probe_image_storage, 'probe') as probe:
            with self.assertRaisesRegex(ValueError, 'SCOPE_OR_HASH_INVALID'):
                stage.run()
            reader.assert_not_called()
            probe.assert_not_called()
        self.assertFalse(admission.LIVE.exists())

    def test_qualified_copy_preserves_raw_unknown_and_is_image_scoped(self):
        directory, packet = admission.prepare()
        permit = admission.Permit(directory.name, stage.build.encoded(packet).decode(), 'test')
        raw = {'version': 1, 'synthetic': False, 'validatedCpuSensor': False,
               'cpuThermalThrottling': None, 'source': 'ASUS DSTS 0x00120094'}
        qualified = permit.qualify(raw)
        self.assertFalse(raw['validatedCpuSensor'])
        self.assertTrue(qualified['validatedCpuSensor'])
        self.assertIsNone(qualified['cpuThermalThrottling'])
        self.assertEqual(qualified['acceptanceScope'], admission.SCOPE)
        for key, value in [('synthetic', True), ('validatedCpuSensor', True), ('source', 'other'), ('version', True),
                           ('cpuThermalThrottling', False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                permit.qualify({**raw, key: value})

    def test_child_requires_exact_immutable_handoff_before_constructing_transport(self):
        directory, packet = admission.prepare()
        permit = admission.Permit(directory.name, stage.build.encoded(packet).decode(), 'test')
        admission.LIVE.mkdir()
        claim = {'sessionId': 'a' * 32, 'reviewSha256': directory.name, 'synthetic': False}
        (admission.LIVE / 'attempt.json').write_text(json.dumps(claim))
        (admission.LIVE / 'state.json').write_text('mutable state intentionally unreadable')
        (admission.LIVE / 'start.json').write_text(json.dumps({**claim, 'scope': admission.SCOPE}))
        with patch.object(admission, 'authorize', return_value=permit), patch.object(stage, 'pipeline') as pipeline:
            stage.child()
            pipeline.assert_called_once()
            pipeline.reset_mock()
            (admission.LIVE / 'start.json').write_text(json.dumps({**claim, 'scope': 'other'}))
            with self.assertRaisesRegex(ValueError, 'CLAIM_INVALID'):
                stage.child()
            pipeline.assert_not_called()


class ImageGateAndLifecycleTests(unittest.TestCase):
    def sample(self, seconds, **changes):
        return stage.policy.synthetic(int(seconds) + 1, seconds, synthetic=False,
                                      recordedAtUnix=1000 + seconds, **changes)

    def test_real_format_requires_full_ten_second_baseline_then_stops_at_97(self):
        gate = stage.Gate(admission.material(), False)
        for second in range(10):
            self.assertEqual(gate.observe(self.sample(second, cpuTemperatureC=92),
                         elapsed=second, unix=1000 + second)['state'], 'WAITING')
        self.assertEqual(gate.observe(self.sample(10, cpuTemperatureC=92), elapsed=10, unix=1010)['state'],
                         'ELIGIBLE_FOR_IMAGE_PREPARATION')
        self.assertEqual(gate.observe(self.sample(11, cpuTemperatureC=97), elapsed=11, unix=1011)['fault'], 'CPU_HOT')

    def test_real_gate_faults_missing_source_known_throttle_staleness_and_coverage(self):
        cases = [({'validatedCpuSensor': False}, 'CPU_SENSOR_UNVALIDATED'),
                 ({'cpuThermalThrottling': True}, 'CPU_THROTTLING'),
                 ({'readerRemainingSeconds': 5}, 'READER_COVERAGE_INSUFFICIENT'),
                 ({'synthetic': True}, 'IMAGE_SENSOR_PROVENANCE'),
                 ({'querySeconds': 2}, 'SENSOR_QUERY_TIMEOUT'),
                 ({'source': 'other'}, 'SENSOR_SOURCE')]
        for changes, fault in cases:
            sample = self.sample(0)
            sample.update(changes)
            gate = stage.Gate(admission.material(), False)
            self.assertEqual(gate.observe(sample, elapsed=0, unix=1000)['fault'], fault)
        gate = stage.Gate(admission.material(), False)
        gate.observe(self.sample(0), elapsed=0, unix=1000)
        self.assertEqual(gate.tick(elapsed=3, unix=1003, controller_age=0)['fault'], 'SENSOR_STALE')

    def test_real_lifecycle_rejects_missing_permit_before_starting_reader(self):
        feed = Mock()
        with self.assertRaisesRegex(ValueError, 'EXACT_PERMIT'):
            stage._execute(Path('unused'), fixture.fixture()[0], feed, Mock(), synthetic=False)
        feed.start_reader.assert_not_called()

    def engine(self, root, *, process=None, cancel=False, fail_journal=False):
        packet, _, _ = fixture.fixture()
        now = [0.0]
        class Feed:
            synthetic = True
            sequence = 0
            closed = False
            received = None
            def start_reader(self, **kwargs):
                pass
            def poll(self):
                if self.received == now[0]:
                    return None
                self.received = now[0]
                self.sequence += 1
                return {'version': 1, 'sequence': self.sequence, 'synthetic': True,
                    'source': 'ASUS DSTS 0x00120094', 'error': None, 'validatedCpuSensor': True,
                    'cpuTemperatureC': 65, 'recordedAtUnix': 1000 + now[0], 'querySeconds': .01,
                    'cpuThermalThrottling': None, 'readerRemainingSeconds': 90}
            def close(self):
                self.closed = True
        feed = Feed()
        if cancel:
            (root / 'cancel.request').touch()
        def sleep(seconds):
            now[0] += .11
        original = stage.download.tools.base.atomic
        def atomic(path, value):
            if fail_journal and value.get('workerStarted') is True:
                raise OSError('Synthetic full disk')
            original(path, value)
        with patch.object(stage.download.tools.base, 'atomic', side_effect=atomic):
            try:
                return stage._execute(root, packet, feed, lambda: process, synthetic=True,
                             clock=lambda: now[0], unix=lambda: 1000 + now[0], sleep=sleep), feed
            except OSError:
                return None, feed

    def test_cancelled_baseline_never_launches_worker_and_consumes_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, feed = self.engine(root, cancel=True)
            self.assertEqual(state['fault'], 'CANCELLED')
            self.assertFalse(state['workerStarted'])
            self.assertTrue(state['stopConfirmed'])
            self.assertTrue(feed.closed)
            with self.assertRaisesRegex(ValueError, 'RESTART_REJECTED'):
                self.engine(root)

    def test_unconfirmed_stop_never_returns_success_or_omits_reader_cleanup(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('fixed-worker', 0)
        process.terminate.side_effect = OSError('Synthetic outage')
        with tempfile.TemporaryDirectory() as directory:
            state, feed = self.engine(Path(directory), process=process)
        self.assertEqual(state['phase'], 'FAULT')
        self.assertFalse(state['stopConfirmed'])
        self.assertNotIn('result', state)
        self.assertTrue(feed.closed)
        process.close.assert_called_once()

    def test_journal_failure_after_launch_still_stops_owned_worker_and_reader(self):
        process = Mock()
        process.poll.side_effect = [None, None, 125]
        process.wait.side_effect = [subprocess.TimeoutExpired('fixed-worker', 0), 125]
        with tempfile.TemporaryDirectory() as directory:
            _, feed = self.engine(Path(directory), process=process, fail_journal=True)
        process.terminate.assert_called()
        process.close.assert_called()
        self.assertTrue(feed.closed)

    def test_synthetic_pipeline_rejects_partial_receipt_or_scope_hash_and_import_flags(self):
        packet, config, packed = fixture.fixture()
        from test_image_download import Response
        class Source:
            def __init__(self, blobs):
                self.blobs = blobs
            def open(self, blob, context):
                return Response(config if blob.digest == packet['image']['configDigest'] else packed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage.controller.pulse(root / 'controller.pulse', maximum=4096)
            result = stage.pipeline(root, packet, Source, synthetic=True)
            self.assertEqual(stage.validate_result(result, packet, True), result)
            for key, value in [('scope', 'other'), ('synthetic', False), ('reviewSha256', '0' * 64),
                               ('imageImportEnabled', True), ('buildEnabled', True), ('modelLaunchEnabled', True)]:
                with self.subTest(key=key), self.assertRaises(ValueError):
                    stage.validate_result({**result, key: value}, packet, True)
            broken = copy.deepcopy(result)
            broken['streams']['layers'][0]['expandedBytes'] = True
            with self.assertRaises(ValueError):
                stage.validate_result(broken, packet, True)
            broken = copy.deepcopy(result)
            broken['streams']['layers'] = []
            with self.assertRaises(ValueError):
                stage.validate_result(broken, packet, True)


if __name__ == '__main__':
    unittest.main()
