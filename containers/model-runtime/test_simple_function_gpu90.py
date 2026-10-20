"""Offline GPU warning/stop boundaries and unchanged control checks."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

import simple_function_gpu90 as scope
from test_runtime import cpu,gpu


class Gpu90FibonacciTests(unittest.TestCase):
    def policy(self):
        old=scope.p.read(scope.FAILED/'review.json',131072)['policy']
        return {**old,'gpuStartC':87,'gpuWarnC':87,'gpuStopC':90}

    def test_warning_band_continues_and_stop_is_exact_and_latched(self):
        with patch.object(scope.p.safety,'POLICY',self.policy()),patch.object(scope,'record_gpu_warning') as warn:
            gate=scope.Gpu90Gate();gate.model_started=0
            for i,temp in enumerate([75,87,87.01,89.99]):
                self.assertTrue(gate.observe(cpu(i+1,1000+i),gpu(1000+i,gpuTemperatureC=temp),now=i,unix=1000+i,controller_age=0))
                self.assertIsNone(gate.fault);self.assertEqual(gate.model_started,0)
            warn.assert_called_once();self.assertEqual(warn.call_args.args[0]['observedC'],87.01)
            self.assertFalse(gate.observe(cpu(5,1004),gpu(1004,gpuTemperatureC=90),now=4,unix=1004,controller_age=0))
            self.assertEqual(gate.fault,'GPU_HOT')
            self.assertFalse(gate.observe(cpu(6,1005),gpu(1005,gpuTemperatureC=60),now=5,unix=1005,controller_age=0))
            warn.assert_called_once()

    def test_warn_only_above87_and_first_reading_at90_is_stopped(self):
        with patch.object(scope.p.safety,'POLICY',self.policy()):
            for temp,warning,fault in [(87,False,None),(87.1,True,None),(89,True,None),(90,True,'GPU_HOT')]:
                with self.subTest(temp=temp),patch.object(scope,'record_gpu_warning') as warn:
                    gate=scope.Gpu90Gate();gate.model_started=0
                    gate.observe(cpu(),gpu(gpuTemperatureC=temp),now=0,unix=1000,controller_age=0)
                    self.assertEqual(gate.fault,fault);self.assertEqual(warn.called,warning)

    def test_cpu_power_vram_ram_throttle_and_time_stops_are_unchanged(self):
        with patch.object(scope.p.safety,'POLICY',self.policy()),patch.object(scope,'record_gpu_warning'):
            cases=[({'cpuTemperatureC':97},{},'CPU_HOT'),({}, {'gpuPowerW':100},'GPU_POWER_HIGH'),
                   ({},{'vramUsedMiB':14336},'VRAM_HIGH'),({},{'ramUsedMiB':30720},'HOST_RAM_HIGH'),
                   ({},{'gpuThermalThrottling':True},'GPU_THROTTLE_MISSING_OR_ACTIVE')]
            for c,g,fault in cases:
                gate=scope.Gpu90Gate();gate.model_started=0
                gate.observe(cpu(**c),gpu(**g),now=0,unix=1000,controller_age=0)
                self.assertEqual(gate.fault,fault)
            gate=scope.Gpu90Gate();gate.model_started=-1200
            gate.observe(cpu(),gpu(),now=0,unix=1000,controller_age=0)
            self.assertEqual(gate.fault,'MODEL_DEADLINE')
            gate=scope.Gpu90Gate();gate.observe(cpu(),gpu(),now=0,unix=1000,controller_age=2.51)
            self.assertEqual(gate.fault,'CONTROLLER_LEASE_EXPIRED')
            gate=scope.Gpu90Gate();gate.observe(cpu(recordedAtUnix=997),gpu(),now=0,unix=1000,controller_age=0)
            self.assertEqual(gate.fault,'TELEMETRY_STALE_OR_MISSING')

    def test_one_immutable_runtime_warning_receipt_preserves_all_later_raw_readings(self):
        root=scope.REPO/'.runtime/gpu90-fibonacci-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            directory=Path(temp);live=directory/'live';review=directory/'review'
            session=live/'sessions'/('a'*32);session.mkdir(parents=True);review.mkdir()
            (live/'attempt.json').write_text(json.dumps({'sessionId':'a'*32,'reviewSha256':'b'*64}))
            (review/'candidate.json').write_text(json.dumps({'reviewSha256':'b'*64}))
            with patch.object(scope,'LIVE',live),patch.object(scope,'ROOT',review),patch.object(scope.p.safety,'POLICY',self.policy()):
                gate=scope.Gpu90Gate();gate.model_started=0
                for i,temp in enumerate((88,89,88)):
                    self.assertTrue(gate.observe(cpu(i+1,1000+i),gpu(1000+i,gpuTemperatureC=temp),now=i,unix=1000+i,controller_age=0))
                files=list(session.iterdir());self.assertEqual([p.name for p in files],['gpu-temperature-warning.json'])
                receipt=json.loads(files[0].read_text());self.assertEqual(receipt['observedC'],88)
                self.assertFalse(receipt['fault']);self.assertFalse(receipt['deadlinesRenewed'])
                self.assertLess(files[0].stat().st_size,1024)

    def test_watch_cli_and_previous_approvals_never_reuse_consumed_scope(self):
        script='''
import sys,runpy
from unittest.mock import patch
import simple_function_gpu90 as s
s.activate();api=s.task.history.task.coding.first_api
assert s.p.safety.Gate is s.Gpu90Gate
assert s.p.safety.POLICY['gpuStopC']==90 and s.p.safety.POLICY['gpuWarnC']==87 and s.p.safety.POLICY['gpuStartC']==87
assert s.p.safety.POLICY['cpuStopC']==97 and s.p.safety.POLICY['ramStopMiB']==30720
assert s.p.safety.POLICY['modelSeconds']==1200 and s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==900
assert s.p.REQUEST==s.prior.REQUEST and s.task.TASK['actualPromptTokensExpected']==246
assert api.READER_SAMPLES==1500 and api.GPU_SAMPLE_LIMIT==1536 and api.PULSE_BYTES==4096
assert api.WATCH_ENTRYPOINT==s.Path(s.__file__).resolve()
assert s.task.LIVE==s.LIVE and s.task.OPERATION==s.OPERATION
with patch.object(api.guard.base,'Docker') as docker,patch.object(s.p.safety,'snapshot') as sensors:
    try:s.run()
    except ValueError as e:assert str(e) in ('FIRST_MODEL_API_NOT_APPROVED','FUNCTION_OPERATION_ALREADY_CONSUMED'),e
    else:raise AssertionError('missing approval admitted')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-gpu90-fibonacci-test']):
        try:cli.main()
        except ValueError as e:assert str(e) in ('FIRST_MODEL_API_NOT_APPROVED','FUNCTION_OPERATION_ALREADY_CONSUMED'),e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-ram30-approval.json','simple-function-approval.json','simple-function-extended-approval.json','simple-function-double-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval admitted')
    with patch.object(api,'watch') as watch,patch.object(sys,'argv',[s.__file__,'--watch']):
        runpy.run_path(s.__file__,run_name='__main__');watch.assert_called_once()
        assert s.p.safety.POLICY['gpuStopC']==90 and s.p.safety.POLICY['gpuWarnC']==87
    docker.assert_not_called();sensors.assert_not_called()
'''
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_only_gpu_temperature_policy_can_change(self):
        packet=copy.deepcopy(scope.p.read(scope.FAILED/'review.json',131072))
        packet.update(policy=self.policy(),gpuTemperatureChange=copy.deepcopy(scope.GPU_CHANGE))
        api=scope.task.history.task.coding.first_api
        with patch.object(scope.p.safety,'POLICY',self.policy()),patch.object(scope.p.safety,'Gate',scope.Gpu90Gate), \
             patch.object(scope.p,'INPUT_SCRIPTS',scope.prior.history.SCRIPTS),patch.object(api,'READER_SAMPLES',1500), \
             patch.object(api,'GPU_SAMPLE_LIMIT',1536),patch.object(api,'PULSE_BYTES',4096), \
             patch.object(api,'API_RESULT_BYTES',262144),patch.object(api,'API_RESULT_RECORD_BYTES',262144), \
             patch.object(api,'validate_response',scope.task.guest.validate_response):
            scope.same_limits(packet)
            for area,key,value in [('policy','gpuStopC',91),('policy','gpuWarnC',86),('policy','gpuStartC',60),
                    ('policy','cpuStopC',98),('policy','ramStopMiB',30721),('policy','modelSeconds',1201),
                    ('request','max_tokens',8192),('requestTimingChange','hardRequestDeadlineSeconds',901)]:
                changed=copy.deepcopy(packet);changed[area][key]=value
                with self.subTest(area=area,key=key),self.assertRaises(ValueError):scope.same_limits(changed)

    def test_previous_gpu75_fault_remains_sealed_and_spent(self):
        self.assertEqual(scope.previous_proof(True)['totalConsumedModelAttempts'],18)
        with patch.object(scope,'FAILED_MANIFEST','0'*64):
            with self.assertRaisesRegex(ValueError,'GPU75_FAILURE_MANIFEST_CHANGED'):scope.previous_proof()


if __name__=='__main__':unittest.main()
