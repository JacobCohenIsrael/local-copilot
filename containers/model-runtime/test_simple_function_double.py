"""Offline drift, previous-evidence, input-count and approval boundary checks."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import simple_function_double as scope


class DoubleInputFibonacciTests(unittest.TestCase):
    def test_only_input_prompt_and_expected_count_change(self):
        old=scope.p.read(scope.CANCELED/'review.json',131072)
        self.assertEqual(scope.REQUEST,{**old['request'],'messages':[{'role':'user','content':scope.PROMPT}]})
        self.assertEqual(scope.TASK,{**old['functionTask'],'actualPromptTokensExpected':246})
        self.assertTrue(scope.PROMPT.isascii())
        self.assertEqual(scope.TASK['evaluation']['cases'],[0,1,2,7,10,20])
        self.assertFalse(scope.TASK['repositoryEdits'])

    def test_drift_in_resources_deadlines_output_or_task_is_refused(self):
        old=scope.p.read(scope.CANCELED/'review.json',131072)
        root=scope.REPO/'.runtime/double-fibonacci-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs=Path(temporary)/'input';inputs.mkdir()
            packet=copy.deepcopy(old)
            packet.update(request=copy.deepcopy(scope.REQUEST),functionTask=copy.deepcopy(scope.TASK),packageDirectory=temporary)
            for name in old['inputSha256']:
                (inputs/name).write_bytes((scope.PREVIOUS/'input'/name).read_bytes())
            (inputs/'request.json').write_text(json.dumps(scope.REQUEST))
            packet['inputSha256']={p.name:scope.p.build.tools.sha(p) for p in inputs.iterdir()}
            api=scope.task.history.task.coding.first_api
            with patch.object(scope.p,'INPUT_SCRIPTS',scope.history.SCRIPTS),patch.object(api,'READER_SAMPLES',1500), \
                 patch.object(api,'GPU_SAMPLE_LIMIT',1536),patch.object(api,'PULSE_BYTES',4096), \
                 patch.object(api,'API_RESULT_BYTES',262144),patch.object(api,'API_RESULT_RECORD_BYTES',262144), \
                 patch.object(api,'validate_response',scope.task.guest.validate_response):
                scope.same_limits(packet)
                for area,key,value in [('policy','cpuStopC',98),('policy','ramStopMiB',30721),
                        ('policy','modelSeconds',1201),('requestTimingChange','hardRequestDeadlineSeconds',901),
                        ('request','max_tokens',8192),('configuration','reasoning_effort','high'),
                        ('durationChange','pulseBytes',8192),('functionTask','actualPromptTokensExpected',123)]:
                    changed=copy.deepcopy(packet);changed[area][key]=value
                    with self.subTest(area=area,key=key),self.assertRaises(ValueError):scope.same_limits(changed)
                changed=copy.deepcopy(packet);changed['contract']['environment']['OMP_NUM_THREADS']='2'
                with self.assertRaises(ValueError):scope.same_limits(changed)
                with patch.object(api,'READER_SAMPLES',480),self.assertRaises(ValueError):scope.same_limits(packet)

    def test_cli_watch_and_all_previous_approvals_cannot_admit_live_access(self):
        script='''
import sys,runpy
from unittest.mock import patch
import simple_function_double as s
s.activate();api=s.task.history.task.coding.first_api
assert s.p.REQUEST==s.REQUEST and s.task.TASK['actualPromptTokensExpected']==246
assert s.p.safety.POLICY['modelSeconds']==1200 and s.p.safety.POLICY['outerSeconds']==1310
assert s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==900
assert s.p.safety.POLICY['ramStopMiB']==30720 and s.p.APPROVAL_WORKER is False
assert api.READER_SAMPLES==1500 and api.GPU_SAMPLE_LIMIT==1536 and api.PULSE_BYTES==4096
assert api.WATCH_ENTRYPOINT==s.Path(s.__file__).resolve()
assert s.task.ROOT==s.ROOT and s.task.LIVE==s.LIVE and s.task.OPERATION==s.OPERATION
# Keep the consumed real scope intact; missing-approval fixtures use absent paths.
s.task.OPERATION=s.REPO/'.runtime/missing-double-fibonacci-offline-operation'
s.p.APPROVAL=s.HERE/'missing-double-fibonacci-offline-approval.json'
with patch.object(api.guard.base,'Docker') as docker,patch.object(s.p.safety,'snapshot') as sensors:
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval admitted')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-double-input-fibonacci-test']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json','coding-task-2-ram30-approval.json','simple-function-approval.json','simple-function-extended-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval admitted')
    with patch.object(api,'watch') as watch,patch.object(sys,'argv',[s.__file__,'--watch']):
        runpy.run_path(s.__file__,run_name='__main__');watch.assert_called_once()
        assert s.p.REQUEST==s.REQUEST and s.task.TASK['actualPromptTokensExpected']==246
    with patch.object(s.task,'OPERATION',s.PREVIOUS):
        try:s.run()
        except ValueError as e:assert str(e)=='FUNCTION_OPERATION_ALREADY_CONSUMED',e
        else:raise AssertionError('consumed operation admitted')
    docker.assert_not_called();sensors.assert_not_called()
'''
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_previous_success_and_canceled_launch_are_sealed(self):
        self.assertEqual(scope.previous_proof(True)['totalConsumedModelAttempts'],17)
        with patch.object(scope,'PREVIOUS_MANIFEST','0'*64):
            with self.assertRaisesRegex(ValueError,'FIBONACCI_PREVIOUS_MANIFEST_CHANGED'):scope.previous_proof()

    def test_old_input_count_refuses_evaluation_after_one_simulated_request(self):
        script='''
import json,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import simple_function_double as s
s.activate();api=s.task.history.task.coding.first_api
root=s.REPO/'.runtime/double-fibonacci-offline-tests';root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root) as temp:
    directory=Path(temp);answer=directory/'api.json'
    answer.write_text(json.dumps({'response':{'usage':{'prompt_tokens':123}}}))
    with patch.object(s.p,'authorize',return_value=Mock(review_sha256='a'*64,approval_sha256='b'*64)),patch.object(s.task,'OPERATION',directory/'operation'),patch.object(api,'run',return_value={'phase':'COMPLETE','stopConfirmed':True,'apiResultFile':str(answer)}) as model,patch.object(s.task,'evaluate_file') as evaluate:
        result=s.run();model.assert_called_once();evaluate.assert_not_called()
        assert result['error']['message']=='FUNCTION_INPUT_TOKEN_COUNT_CHANGED'
        assert result['repositoryEdits'] is False and result['automaticRetry'] is False
'''
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
