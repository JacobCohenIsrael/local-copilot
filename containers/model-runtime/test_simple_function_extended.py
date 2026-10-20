"""Offline duration consistency and unchanged emergency-stop checks."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import container_test_duration as base
import runtime_safety as safety
import simple_function_extended as scope
from test_runtime import cpu,gpu


class ExtendedFibonacciTests(unittest.TestCase):
    def policy(self):
        old=scope.p.read(scope.FAILED/'review.json',131072)['policy']
        return {**old,'modelSeconds':1200,'outerSeconds':1310}

    def test_1200_second_model_deadline_still_hard_and_latched(self):
        with patch.object(safety,'POLICY',self.policy()):
            gate=safety.Gate();gate.model_started=0
            for i in range(1200):
                self.assertTrue(gate.observe(cpu(i+1,1000+i),gpu(1000+i),now=i,unix=1000+i,controller_age=0))
            self.assertFalse(gate.observe(cpu(1201,2200),gpu(2200),now=1200,unix=2200,controller_age=0))
            self.assertEqual(gate.fault,'MODEL_DEADLINE')
            self.assertFalse(gate.observe(cpu(1202,2201),gpu(2201),now=1201,unix=2201,controller_age=0))

    def test_reader_coverage_is_scaled_but_thermal_memory_and_lease_limits_stay(self):
        with patch.object(safety,'POLICY',self.policy()):
            for remaining,fault in [(1204,'CPU_READER_COVERAGE'),(1205,None),(1499,None)]:
                gate=safety.Gate();gate.observe(cpu(readerRemainingSeconds=remaining),gpu(),now=0,unix=1000,controller_age=0)
                self.assertEqual(gate.fault,fault)
            for c,g,age,reason in [({'cpuTemperatureC':97},{},0,'CPU_HOT'),
                    ({},{'gpuTemperatureC':75},0,'GPU_HOT'),({},{'gpuPowerW':100},0,'GPU_POWER_HIGH'),
                    ({},{'vramUsedMiB':14336},0,'VRAM_HIGH'),({},{'ramUsedMiB':30720},0,'HOST_RAM_HIGH'),
                    ({},{},2.51,'CONTROLLER_LEASE_EXPIRED'),({},{'recordedAtUnix':996},0,'TELEMETRY_STALE_OR_MISSING')]:
                gate=safety.Gate()
                gate.observe(cpu(readerRemainingSeconds=1499,**c),gpu(**g),now=0,unix=1000,controller_age=age)
                self.assertEqual(gate.fault,reason)

    def test_guest_deadlines_are_not_renewed_by_heartbeat_activity(self):
        with patch.object(base,'MODEL_SECONDS',1200),patch.object(base,'LEASE_BYTES',4096):
            lease=base.Leases(0)
            for i in range(1800):lease.check(i/2,{'controller.pulse':i+1,'guard.pulse':i+1},900)
            with self.assertRaisesRegex(TimeoutError,'REQUEST_DEADLINE'):
                lease.check(900,{'controller.pulse':1801,'guard.pulse':1801},900)
            lease=base.Leases(0)
            for i in range(2400):lease.check(i/2,{'controller.pulse':i+1,'guard.pulse':i+1})
            with self.assertRaisesRegex(TimeoutError,'CONTAINER_DEADLINE'):
                lease.check(1200,{'controller.pulse':2401,'guard.pulse':2401})
            lease=base.Leases(0);lease.check(0,{'controller.pulse':1,'guard.pulse':1})
            with self.assertRaisesRegex(TimeoutError,'HOST_LEASE_EXPIRED'):
                lease.check(2.51,{'controller.pulse':1,'guard.pulse':1})

    def test_scoped_guest_applies_all_duration_and_response_bounds_before_main(self):
        fake=SimpleNamespace(main=Mock(return_value=17))
        with patch.dict(sys.modules,{'container_test_base':fake}):
            self.assertEqual(scope.guest.main(),17)
        fake.main.assert_called_once()
        self.assertEqual((fake.REQUEST_SECONDS,fake.MODEL_SECONDS,fake.LEASE_BYTES),(900,1200,4096))
        self.assertEqual(fake.MAX_RESPONSE,262144)
        self.assertIs(fake.validate_response,scope.prior.guest.validate_response)

    def test_child_watch_cli_and_spent_approvals_use_fresh_scope(self):
        script='''
import sys,runpy
from unittest.mock import patch
import simple_function_extended as s
s.activate();api=s.prior.history.task.coding.first_api
assert s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==900
assert s.p.safety.POLICY['modelSeconds']==1200 and s.p.safety.POLICY['outerSeconds']==1310
assert s.p.safety.POLICY['ramStopMiB']==30720 and s.p.APPROVAL_WORKER is False
assert api.READER_SAMPLES==1500 and api.GPU_SAMPLE_LIMIT==1536 and api.PULSE_BYTES==4096
assert api.WATCH_ENTRYPOINT==s.Path(s.__file__).resolve()
assert s.prior.OPERATION==s.OPERATION and s.prior.LIVE==s.LIVE
assert s.p.REQUEST==s.prior.REQUEST and s.prior.TASK['actualPromptTokensExpected']==123
# The executed scope stays spent. Use explicitly absent paths for the missing
# approval fixture, without resetting the recorded operation or its decision.
s.prior.OPERATION=s.REPO/'.runtime/missing-extended-fibonacci-offline-operation'
s.p.APPROVAL=s.HERE/'missing-extended-fibonacci-offline-approval.json'
with patch.object(api.guard.base,'Docker') as docker,patch.object(s.p.safety,'snapshot') as sensors:
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval admitted')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-extended-fibonacci-test']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json','coding-task-2-ram30-approval.json','simple-function-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval admitted')
    with patch.object(api,'watch') as watch,patch.object(sys,'argv',[s.__file__,'--watch']):
        runpy.run_path(s.__file__,run_name='__main__');watch.assert_called_once()
        assert api.READER_SAMPLES==1500 and s.p.safety.POLICY['modelSeconds']==1200
    docker.assert_not_called();sensors.assert_not_called()
'''
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_only_reviewed_duration_and_support_budgets_can_change(self):
        old=scope.p.read(scope.FAILED/'review.json',131072)
        root=scope.REPO/'.runtime/extended-fibonacci-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs=Path(temporary)/'input';inputs.mkdir()
            packet=copy.deepcopy(old)
            packet.update(policy=self.policy(),requestTimingChange={**old['requestTimingChange'],'hardRequestDeadlineSeconds':900},
                          durationChange=copy.deepcopy(scope.DURATION),packageDirectory=temporary)
            for name,source in scope.SCRIPTS.items():(inputs/name).write_bytes((scope.HERE/source).read_bytes().replace(b'\r\n',b'\n'))
            (inputs/'request.json').write_text(json.dumps(packet['request']));(inputs/'strata.json').write_text(json.dumps(packet['configuration']))
            packet['inputSha256']={x.name:scope.p.build.tools.sha(x) for x in inputs.iterdir()}
            api=scope.prior.history.task.coding.first_api
            with patch.object(scope.p,'INPUT_SCRIPTS',dict(scope.SCRIPTS)),patch.object(api,'READER_SAMPLES',1500), \
                 patch.object(api,'GPU_SAMPLE_LIMIT',1536),patch.object(api,'PULSE_BYTES',4096), \
                 patch.object(api,'API_RESULT_BYTES',262144),patch.object(api,'API_RESULT_RECORD_BYTES',262144), \
                 patch.object(api,'validate_response',scope.prior.guest.validate_response):
                scope.same_limits(packet)
                for area,key,value in [('policy','cpuStopC',98),('policy','ramStopMiB',30721),
                        ('policy','modelSeconds',1201),('requestTimingChange','hardRequestDeadlineSeconds',901),
                        ('request','max_tokens',8192),('durationChange','pulseBytes',8192),
                        ('functionTask','actualPromptTokensExpected',124)]:
                    changed=copy.deepcopy(packet);changed[area][key]=value
                    with self.subTest(area=area,key=key),self.assertRaises(ValueError):scope.same_limits(changed)
                with patch.object(api,'READER_SAMPLES',480),self.assertRaises(ValueError):scope.same_limits(packet)

    def test_timeout_evidence_and_report_are_pinned(self):
        self.assertFalse(scope.timeout_proof()['previousApprovalReused'])
        with patch.object(scope,'FAILED_MANIFEST','0'*64):
            with self.assertRaisesRegex(ValueError,'FIBONACCI_FAILURE_MANIFEST_CHANGED'):scope.timeout_proof()


if __name__=='__main__':unittest.main()
