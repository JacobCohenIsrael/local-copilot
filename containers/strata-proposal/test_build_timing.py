"""Replay recorded data and fake processes only; never read live sensors/Docker."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import build_timing as timing
import cpu_feed
import first_build
import build_policy_review as policy
import test_build_admission as fixtures


class TimingTests(unittest.TestCase):
    def permit(self, packet=None):
        packet = packet or {'controls': policy.load_effective_controls()['temperature'],
                            'sourceReviewSha256': 'c'*64}
        return timing.Permit(timing.base.sha(packet), timing.base.encoded(packet).decode(), 'b'*64)

    def test_reader_variant_has_only_the_reviewed_cutoff_change(self):
        contract = timing.reader_contract()
        self.assertEqual(contract['sha256'], timing.READER_SHA)
        self.assertEqual(timing.tools.sha(timing.HERE/'cpu_reader.ps1'), timing.cpu.READER_SHA)

    def test_all_840_recorded_frames_pass_new_query_budget_but_old_budget_rejects_final(self):
        reader = timing.REPO/'.runtime/compiler-guard/9ff26442471f488fbed6f17f9b5a888f'
        paths = sorted(reader.glob('sample-????????.json'))
        self.assertEqual(len(paths), 840)
        gate = policy.CpuBuildReadinessGate()
        gate.draft['temperature']['maxQuerySeconds'] = 1.5
        old_gate = policy.CpuBuildReadinessGate()
        first = None
        for path in paths:
            frame = json.loads(path.read_text(encoding='utf-8-sig'))
            first = frame['recordedAtUnix'] if first is None else first
            qualified = self.permit().qualify(frame)
            observation = gate.observe(qualified, elapsed=frame['recordedAtUnix']-first,
                                       unix=frame['recordedAtUnix']+.04, controller_age=.1)
            self.assertIsNone(observation['fault'], path.name)
            old = old_gate.observe(qualified, elapsed=frame['recordedAtUnix']-first,
                                   unix=frame['recordedAtUnix']+.04, controller_age=.1)
        self.assertEqual(frame['querySeconds'], 1.0943863)
        self.assertEqual(old['fault'], 'SENSOR_QUERY_TIMEOUT')
        self.assertFalse(frame['validatedCpuSensor'])

    def gate(self):
        feed = Mock(synthetic=False, source_permit=self.permit(), clock=lambda: 0)
        return cpu_feed.Monitor(feed).gate

    def test_scoped_monitor_changes_only_query_budget(self):
        expected = policy.load_effective_controls()
        expected['temperature']['maxQuerySeconds'] = 1.5
        self.assertEqual(self.gate().draft, expected)
        self.assertEqual(policy.CpuBuildReadinessGate().draft['temperature']['maxQuerySeconds'], 1)
        self.assertEqual(self.permit().reader_contract, (timing.READER, timing.READER_SHA))

    def test_hot_stale_slow_throttled_and_lease_loss_still_fault_and_latch(self):
        for changes, age, fault in (({'cpuTemperatureC':97}, 0, 'CPU_HOT'),
            ({'recordedAtUnix':996}, 0, 'SENSOR_STALE'),
            ({'querySeconds':1.50001}, 0, 'SENSOR_QUERY_TIMEOUT'),
            ({'cpuThermalThrottling':True}, 0, 'CPU_THROTTLING'),
            ({}, 2.51, 'CONTROLLER_LEASE_EXPIRED')):
            gate = self.gate()
            sample = policy.synthetic(1,0,synthetic=False,**changes)
            self.assertEqual(gate.observe(sample,elapsed=0,unix=1000,controller_age=age)['fault'],fault)
            self.assertEqual(gate.observe(policy.synthetic(2,1,synthetic=False),elapsed=1,unix=1001)['fault'],fault)
        gate = self.gate()
        gate.observe(policy.synthetic(1,0,synthetic=False),elapsed=0,unix=1000)
        self.assertEqual(gate.tick(elapsed=2.51,unix=1002.51,controller_age=0)['fault'],'SENSOR_STALE')

    def test_terminal_reader_error_survives_controller_stop_without_consuming_final_frame(self):
        fixture = fixtures.AdmittedControllerTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        frame = policy.synthetic(1,0,synthetic=False,validatedCpuSensor=False,querySeconds=1.6)
        (fixture.feed.directory/'sample-00000001.json').write_text(json.dumps(frame))
        fixture.feed.process.poll.return_value = 0
        state = fixture.session.poll()
        self.assertEqual(state['phase'],'FAULT')
        self.assertTrue(state['stopConfirmed'])
        self.assertTrue(state['retainedStoppedTarget'])
        self.assertEqual(state['monitorError']['reason'],'READER_EXITED')
        self.assertEqual(state['monitorError']['operation'],'liveness')
        self.assertEqual(state['monitorError']['readerExitCode'],0)
        self.assertEqual(fixture.feed.sequence,0)
        saved=json.loads(fixture.session.file.read_text())
        self.assertEqual(saved['monitorError'],state['monitorError'])

    def test_readiness_timeout_is_bounded_and_keeps_exact_command_in_error_record(self):
        docker=Mock();target=Mock(container_id='a'*64)
        docker.call.side_effect=subprocess.TimeoutExpired(['docker','exec','fixed-ready-read'],1.5)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            first_build._ready(docker,target,timeout=1.5)
        self.assertEqual(docker.call.call_args.kwargs['timeout'],1.5)
        record=first_build.parent_error_record(caught.exception)
        self.assertEqual(record['timeoutSeconds'],1.5)
        self.assertEqual(record['command'],['docker','exec','fixed-ready-read'])
        self.assertFalse(record['automaticRetry'])

    def decision(self, packet):
        return {'version':1,'status':'owner-approved-one-cpu-build-timing','scope':timing.SCOPE,
            'reviewSha256':timing.base.sha(packet),'acceptBuildTiming':copy.deepcopy(timing.TIMING),
            'acceptSourceQualificationSha256':packet['sourceReviewSha256'],
            'acceptSourceLimitation':timing.cpu.LIMITATION,'maximumAttempts':1,'synthetic':False,
            'buildEnabled':True,'imageDownloadEnabled':False,'imageImportEnabled':False,'modelLaunchEnabled':False,
            'acceptStoppedFailureContainerRetention':True,'ownerMessage':'Test fixture only'}

    def test_absent_approval_refuses_before_prior_evidence_or_live_access(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(timing,'APPROVAL',Path(temp)/'absent'), \
                patch.object(timing,'previous') as prior, patch.object(first_build,'run') as run:
            with self.assertRaisesRegex(ValueError,'NOT_APPROVED'):timing.run()
            prior.assert_not_called();run.assert_not_called()

    def test_approval_requires_exact_timing_scope_and_disabled_model_import_download(self):
        packet={'sourceReviewSha256':'c'*64}
        for key,value in (('acceptBuildTiming',{**timing.TIMING,'sensorQuerySeconds':2}),
                          ('maximumAttempts',True),('modelLaunchEnabled',True),('imageImportEnabled',True),
                          ('imageDownloadEnabled',True),('scope','old-scope'),('reviewSha256','0'*64),
                          ('acceptStoppedFailureContainerRetention',False)):
            with tempfile.TemporaryDirectory() as temp:
                decision=self.decision(packet);decision[key]=value;path=Path(temp)/'approval.json'
                path.write_text(json.dumps(decision))
                with patch.object(timing,'APPROVAL',path),patch.object(timing,'review',return_value=(timing.base.sha(packet),packet)):
                    with self.assertRaisesRegex(ValueError,'APPROVAL_INVALID'):timing.authorize()

    def test_consumed_namespace_refuses_before_any_build_or_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'attempt.json').write_text('{}')
            with patch.object(timing,'LIVE',root),patch.object(timing,'authorize',return_value=self.permit()), \
                    patch.object(first_build,'run') as run:
                with self.assertRaisesRegex(ValueError,'CONSUMED'):timing.run()
                run.assert_not_called()

    def test_exact_decision_binds_new_namespace_and_legacy_permit_keeps_default_reader(self):
        packet={'sourceReviewSha256':'c'*64}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'approval.json';path.write_text(json.dumps(self.decision(packet)))
            with patch.object(timing,'APPROVAL',path),patch.object(timing,'review',return_value=(timing.base.sha(packet),packet)):
                permit=timing.authorize()
            self.assertEqual(permit.live_namespace,timing.LIVE)
            self.assertEqual(permit.query_budget,1.5)
            legacy=timing.base.Permit(timing.base.sha(packet),json.dumps(packet),'b'*64)
            self.assertFalse(hasattr(legacy,'reader_contract'))
            self.assertFalse(hasattr(legacy,'query_budget'))

    def test_launch_selects_only_scoped_reader_and_does_not_modify_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);feed_path=root/('a'*32)
            process=Mock()
            with patch.object(cpu_feed,'ROOT',root),patch.object(cpu_feed.windows_job,'Process',return_value=process) as launch:
                feed=cpu_feed.Feed(feed_path,source_permit=self.permit())
                feed.start_reader(samples=10)
                self.assertIn(str(timing.READER),launch.call_args.args[0])
                self.assertNotIn(str(cpu_feed.READER),launch.call_args.args[0])
                feed.close()
            self.assertEqual(timing.tools.sha(cpu_feed.READER),cpu_feed.READER_SHA)

    def test_cancel_uses_only_new_namespace_without_start_authority(self):
        import sys
        import contextlib
        import io
        sys.path.insert(0,str(timing.REPO))
        import local_worker
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'sessions'/('a'*32);session.mkdir(parents=True)
            (root/'attempt.json').write_text(json.dumps({'sessionId':'a'*32}))
            (root/'state.json').write_text(json.dumps({'phase':'RUNNING'}))
            with patch.object(timing,'LIVE',root),patch.object(sys,'argv',['local_worker.py','cancel-build-timing']), \
                    patch.object(timing,'authorize',side_effect=AssertionError('cancel needs no start approval')), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(local_worker.main(),0)
            self.assertTrue((session/'cancel.request').exists())


if __name__=='__main__': unittest.main()
