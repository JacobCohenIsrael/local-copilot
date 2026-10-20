"""Deterministic fake-daemon startup overlap; no Docker, sensors or real sleeps."""
import json
import copy
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import first_api
import runtime_plan as plan
import startup_handoff as handoff
import prior_api
from test_runtime import cpu,gpu

CID='a'*64
SHA='b'*64


class HandoffTests(unittest.TestCase):
    def test_startup_review_cannot_raise_deadlines_or_disable_monitoring(self):
        packet=copy.deepcopy(prior_api.load(prior_api.EIGHTH_FOLDER/'review.json'))
        packet.update(startupTargetChange=plan.STARTUP_TARGET_CHANGE,policy=dict(plan.safety.POLICY))
        plan.same_limits(packet)
        for key,value in (('dockerStartSeconds',2),('periodicInspectSeconds',1.5),
                          ('handoffSeconds',3),('telemetryAndLeasesContinue',False),('automaticRetry',True)):
            bad=copy.deepcopy(packet);bad['startupStatusChange'][key]=value
            with self.assertRaisesRegex(ValueError,'CHANGE_MISMATCH'):plan.same_limits(bad)

    def test_one_grant_pending_then_exact_receipt_does_not_extend_budgets(self):
        state=handoff.Handoff(CID,SHA);state.grant(10)
        self.assertTrue(state.pending(10.1,None));self.assertTrue(state.pending(11.4,None))
        self.assertFalse(state.pending(11.5,handoff.receipt(CID,SHA,1.3)))
        self.assertEqual(state.granted_at,10)
        with self.assertRaises(ValueError):state.grant(12)
        self.assertEqual((handoff.CONTRACT['dockerStartSeconds'],handoff.CONTRACT['periodicInspectSeconds'],
                          handoff.CONTRACT['handoffSeconds']),(1.5,1,2.5))

    def test_missing_late_or_malformed_receipt_never_allows_inspect(self):
        for field,value in (('containerId','c'*64),('reviewSha256','c'*64),('startCalls',2),('startCalls',True),
                            ('commandSeconds',1.51),('commandSeconds',float('nan')),('version',True)):
            state=handoff.Handoff(CID,SHA);state.grant(0)
            receipt=handoff.receipt(CID,SHA,1.3);receipt[field]=value
            with self.assertRaises(ValueError):state.pending(1.4,receipt)
        state=handoff.Handoff(CID,SHA);state.grant(0)
        with self.assertRaisesRegex(TimeoutError,'HANDOFF_DEADLINE'):state.pending(2.5,None)
        with self.assertRaisesRegex(TimeoutError,'HANDOFF_DEADLINE'):state.pending(2.5,handoff.receipt(CID,SHA,1))
        with self.assertRaises(ValueError):state.pending(-1,None)

    def test_legacy_status_check_reproduces_timeout_while_start_is_busy(self):
        clock=[10.1]
        def call(*args,timeout):
            self.assertLessEqual(timeout,1);clock[0]+=timeout
            raise subprocess.TimeoutExpired(['docker','container','inspect',CID],timeout)
        docker=Mock();docker.call.side_effect=call
        bounded=first_api.guard.DeadlineDocker(docker,clock[0]+1,lambda:clock[0])
        with self.assertRaises(subprocess.TimeoutExpired):bounded.call('container','inspect',CID)
        self.assertAlmostEqual(clock[0],11.1)


class ConnectedStartupTests(unittest.TestCase):
    def exercise(self,mode='success'):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'sessions'/('d'*32);session.mkdir(parents=True);(root/'control').mkdir()
            (root/'attempt.json').write_text(json.dumps({'sessionId':'d'*32,'reviewSha256':SHA}))
            (session/'target.json').write_text(json.dumps({'containerId':CID,'readerDirectory':str(root/'reader')}))
            now=[0.];start_at=[None];receipt_sent=[False];inspect_times=[];pulse_times=[];samples=[]
            def current():return first_api.runtime_record_io.latest(root) if first_api.runtime_record_io.exists(root) else None
            def sleep(seconds):
                now[0]+=seconds
                state=current()
                if state and state['phase']=='ARMED' and start_at[0] is None:start_at[0]=now[0]
                if start_at[0] is not None and now[0]-start_at[0]>=1.3 and not receipt_sent[0] and mode!='stalled':
                    value=handoff.receipt(CID,SHA,1.3)
                    if mode=='bad_receipt':value['containerId']='c'*64
                    (root/'control/start-result.json').write_text(json.dumps(value));receipt_sent[0]=True
                if mode=='cancel' and start_at[0] is not None and now[0]-start_at[0]>=.3:
                    (root/'cancel.request').touch()
            def inspect(client):
                inspect_times.append(now[0])
                busy=start_at[0] is not None and not receipt_sent[0]
                if busy or (mode=='post_timeout' and receipt_sent[0]):
                    now[0]+=1
                    raise subprocess.TimeoutExpired(['docker','container','inspect',CID],1)
                if mode=='drift' and receipt_sent[0]:raise ValueError('MODEL_CONTAINER_CONTRACT_CHANGED')
                running=receipt_sent[0] and mode!='not_running'
                return {'Id':CID,'State':{'Running':running,'Status':'running' if running else 'created','ExitCode':0,'OOMKilled':False}}
            owned=Mock(container_id=CID);owned.inspect.side_effect=inspect
            feed=Mock();feed.process.pid=1234;last_slot=[-1]
            def poll():
                slot=int(now[0]+1e-6)
                if slot==last_slot[0]:return None
                last_slot[0]=slot
                state=current();hot=bool(state and state['phase']=='RUNNING') or (mode=='hot' and start_at[0] is not None and now[0]-start_at[0]>=.3)
                frame=cpu(len(samples)+1,1000+now[0],cpuTemperatureC=98 if hot else 95)
                samples.append(frame);return frame
            feed.poll.side_effect=poll
            def age():return 3 if mode=='lease' and start_at[0] is not None and now[0]-start_at[0]>=.3 else 0
            def pulse(path,**kwargs):pulse_times.append(now[0])
            permit=SimpleNamespace(review_sha256=SHA,packet={})
            def snapshot():
                hot=mode=='gpu_hot' and start_at[0] is not None and now[0]-start_at[0]>=.3
                if mode=='advisory':
                    return gpu(1000+now[0],gpuTemperatureC=95,gpuPowerW=140,
                               vramUsedMiB=16000,ramUsedMiB=31500,gpuThermalThrottling=True)
                return gpu(1000+now[0],gpuTemperatureC=75 if hot else 55)
            original_gate=first_api.safety.Gate;gates=[]
            def gate_factory():
                gate=original_gate();gates.append(gate);return gate
            with patch.object(plan,'LIVE',root),patch.object(plan,'authorize',return_value=permit),\
                    patch.object(first_api.safety,'POLICY',first_api.safety.viability_policy(
                        {**first_api.safety.POLICY,'modelSeconds':2}) if mode=='advisory' else first_api.safety.POLICY),\
                    patch.object(first_api,'target',return_value=owned),\
                    patch.object(first_api.guard.base,'Docker',return_value=Mock()),\
                    patch.object(first_api.cpu_feed,'Feed',return_value=feed),\
                    patch.object(first_api.safety,'snapshot',side_effect=snapshot),\
                    patch.object(first_api.safety,'Gate',side_effect=gate_factory),\
                    patch.object(first_api.time,'monotonic',side_effect=lambda:now[0]),\
                    patch.object(first_api.time,'time',side_effect=lambda:1000+now[0]),\
                    patch.object(first_api.time,'sleep',side_effect=sleep),\
                    patch.object(first_api.control,'Pulse',return_value=SimpleNamespace(age=age)),\
                    patch.object(first_api.control,'pulse',side_effect=pulse),\
                    patch.object(first_api,'stop',return_value={'stopConfirmed':True,'retainedStoppedTarget':True}) as stop:
                first_api.watch()
            state=current();states=[json.loads(p.read_text()) for p in sorted((root/'states').glob('state-*.json'))]
            stop.assert_called_once();feed.close.assert_called_once()
            self.assertTrue(state['stopConfirmed']);self.assertIsNotNone(start_at[0])
            self.assertFalse(any(start_at[0]<=t<start_at[0]+1.3 for t in inspect_times))
            if mode=='success':
                self.assertTrue(any(s['phase']=='RUNNING' for s in states))
                self.assertEqual(state['fault'],{'code':'CPU_HOT'});self.assertNotIn('watchError',state)
                self.assertGreaterEqual(sum(start_at[0]<=t<start_at[0]+1.3 for t in pulse_times),2)
                self.assertGreaterEqual(len(samples),12)
                self.assertIn('startupWarnings',next(s for s in states if s['phase']=='ARMED'))
                self.assertLess(gates[0].model_started,start_at[0])
            elif mode=='hot':self.assertEqual(state['fault'],{'code':'CPU_HOT'})
            elif mode=='gpu_hot':self.assertEqual(state['fault'],{'code':'GPU_HOT'})
            elif mode=='lease':self.assertEqual(state['fault'],{'code':'CONTROLLER_LEASE_EXPIRED'})
            elif mode=='cancel':self.assertEqual(state['fault'],{'code':'CANCELLED'})
            elif mode=='not_running':self.assertEqual(state['fault'],{'code':'MODEL_START_RETURNED_NOT_RUNNING'})
            elif mode=='advisory':
                self.assertEqual(state['fault'],{'code':'MODEL_DEADLINE'})
                self.assertTrue(any(s['phase']=='RUNNING' for s in states))
                report=json.loads((session/'resource-trends.json').read_text())
                self.assertEqual(report['mode'],'warnings-only')
                self.assertIn('ramUsedMiB',report['warnings'])
                final=json.loads((session/'guard-result.json').read_text())
                self.assertIn('gpuThermalThrottling',final['resourceObservations']['warnings'])
                self.assertFalse(final['resourceObservations']['deadlinesRenewed'])
            else:
                self.assertEqual(state['fault'],{'code':'MODEL_WATCH_ERROR'})
                expected={'stalled':'HANDOFF_DEADLINE','bad_receipt':'RECEIPT_INVALID',
                          'post_timeout':'timed out','drift':'CONTRACT_CHANGED'}[mode]
                self.assertIn(expected,state['watchError']['reason'])
                if mode=='post_timeout':self.assertEqual(state['watchError']['timeoutSeconds'],1)
            return {'mode':mode,'phase':state['phase'],'fault':state['fault'],'cpuFramesChecked':len(samples),
                    'guardPulses':len(pulse_times),'modelOrDockerExecuted':False,'automaticRetry':False}

    def test_slow_start_handoff_preserves_monitoring_then_status_and_hot_stop(self):self.exercise()
    def test_hot_frame_during_start_still_stops(self):self.exercise('hot')
    def test_gpu_hot_during_start_still_stops(self):self.exercise('gpu_hot')
    def test_controller_lease_loss_during_start_still_stops(self):self.exercise('lease')
    def test_cancel_during_start_still_stops(self):self.exercise('cancel')
    def test_missing_receipt_faults_within_existing_lease_budget(self):self.exercise('stalled')
    def test_wrong_identity_receipt_faults(self):self.exercise('bad_receipt')
    def test_post_start_inspect_timeout_is_not_hidden_or_retried(self):self.exercise('post_timeout')
    def test_contract_drift_still_faults_after_start(self):self.exercise('drift')
    def test_success_receipt_without_running_container_is_a_fault(self):self.exercise('not_running')
    def test_advisory_resources_continue_through_start_and_save_trends_until_deadline(self):
        with patch('builtins.print'):
            self.exercise('advisory')


if __name__=='__main__':unittest.main()
