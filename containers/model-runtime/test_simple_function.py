"""Offline API bounds, generated-code admission and owned correctness jobs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

import first_api
import simple_function as scope
import simple_function_guest as guest
import simple_function_task as task

GOOD='''def fibonacci(n):
    result = []
    a, b = 0, 1
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result
'''


def response(code=GOOD,finish='stop',prompt=123,output=90):
    return {'choices':[{'message':{'role':'assistant','content':code},'finish_reason':finish}],
            'usage':{'prompt_tokens':prompt,'completion_tokens':output,'total_tokens':prompt+output}}


class SimpleFunctionTests(unittest.TestCase):
    def test_plain_and_fenced_functions_work_without_forcing_algorithm(self):
        for code in (GOOD,'```python\n'+GOOD+'```'):
            generated=task.code_from_response(response(code))
            self.assertEqual(task.evaluate(generated)['inputs'],[0,1,2,7,10,20])
        self.assertEqual(task.evaluate('def fibonacci(n):\n    a = [0, 1]\n    for i in range(2,n): a.append(a[-1]+a[-2])\n    return a[:n]\n')['status'],'FUNCTION_CASES_PASSED')

    def test_bad_finish_wrong_behavior_and_unsafe_syntax_rejected(self):
        with self.assertRaisesRegex(ValueError,'MODEL_OUTPUT_INCOMPLETE'):task.code_from_response(response(finish='length'))
        for code in ['import os\n'+GOOD,'def fibonacci(n):\n    return open("secret").read()\n',
                     'def fibonacci(n):\n    return n.__class__\n','@print\n'+GOOD,
                     'def fibonacci(n):\n    exec("pass")\n',GOOD+'fibonacci(4)\n']:
            with self.subTest(code=code),self.assertRaises(ValueError):task.code_from_response(response(code))
        with self.assertRaisesRegex(ValueError,'FUNCTION_RESULT_WRONG'):task.evaluate('def fibonacci(n):\n    return [0]\n')

    def test_4k_output_512_input_and_transport_bounds_are_independent(self):
        guest.validate_response(response(output=4096,prompt=512))
        for prompt,output in [(513,4096),(123,4097),(123,True),(True,90)]:
            with self.assertRaises(ValueError):guest.validate_response(response(prompt=prompt,output=output))
        payload=json.dumps({'response':response('x'*30000)})
        docker=Mock();docker.call.return_value=payload
        with patch.object(first_api,'API_RESULT_BYTES',guest.RESPONSE_BYTES):
            self.assertIn('response',first_api.read_result(docker,Mock(container_id='a'*64)))
            self.assertIn(str(guest.RESPONSE_BYTES+1),docker.call.call_args.args)
            docker.call.return_value='x'*(guest.RESPONSE_BYTES+1)
            with self.assertRaisesRegex(ValueError,'API_RESULT_BUDGET'):first_api.read_result(docker,Mock(container_id='a'*64))

    def test_timeout_kills_and_confirms_evaluation_child_without_retry(self):
        root=scope.REPO/'.runtime/simple-function-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            directory=Path(temporary);code=directory/'function.py';code.write_text(GOOD)
            child=Mock(pid=1234,returncode=125);child.wait.side_effect=[subprocess.TimeoutExpired('fixture',2),125];child.poll.return_value=125
            factory=Mock(return_value=child)
            with self.assertRaisesRegex(ValueError,'FUNCTION_EVALUATION_TIMEOUT'):scope.evaluate_file(code,directory,process_factory=factory)
            child.kill.assert_called_once();child.close.assert_called_once();factory.assert_called_once()
            record=json.loads((directory/'evaluation-exit.json').read_text())
            self.assertTrue(record['confirmedExited']);self.assertTrue(record['timedOut'])
            self.assertEqual(factory.call_args.kwargs['memory_bytes'],128*1024**2)

    @unittest.skipUnless(sys.platform=='win32','Windows job-bound evaluator')
    def test_known_function_passes_real_restricted_job_without_model_or_gpu(self):
        root=scope.REPO/'.runtime/simple-function-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            directory=Path(temporary);code=directory/'function.py';code.write_text(GOOD)
            self.assertEqual(scope.evaluate_file(code,directory)['status'],'FUNCTION_CASES_PASSED')
            self.assertTrue(json.loads((directory/'evaluation-exit.json').read_text())['confirmedExited'])

    def test_missing_spent_and_consumed_scopes_refuse_before_live_access(self):
        script='''
import sys
from unittest.mock import patch
import simple_function as s
s.activate()
assert s.p.APPROVAL_WORKER is False
assert s.p.REQUEST['max_tokens']==4096 and s.p.safety.POLICY['ramStopMiB']==30720
assert s.history.task.coding.first_api.API_RESULT_BYTES==262144
assert s.history.task.coding.first_api.API_RESULT_RECORD_BYTES==262144
assert s.history.task.coding.first_api.validate_response is s.guest.validate_response
# The original live operation is spent; use explicit missing paths for this
# refusal fixture, without resetting or modifying its approval/evidence.
s.p.APPROVAL=s.HERE/'missing-simple-function-offline-approval.json'
s.OPERATION=s.REPO/'.runtime/missing-simple-function-offline-operation'
with patch.object(s.history.task.coding.first_api.guard.base,'Docker') as docker,patch.object(s.p.safety,'snapshot') as sensors:
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval admitted')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-simple-function-test']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json','coding-task-2-ram30-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval admitted')
    with patch.object(s,'OPERATION',s.history.prior.WORKER):
        try:s.run()
        except ValueError as e:assert str(e)=='FUNCTION_OPERATION_ALREADY_CONSUMED',e
        else:raise AssertionError('consumed scope admitted')
    docker.assert_not_called();sensors.assert_not_called()
'''
        r=subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_unchanged_limits_and_function_contract_are_bound(self):
        old=scope.p.read(scope.history.PREVIOUS/'review.json',131072)
        root=scope.REPO/'.runtime/simple-function-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs=Path(temporary)/'input';inputs.mkdir()
            packet=copy.deepcopy(old);packet.pop('codingTask')
            packet.update(configuration=scope.history.larger_context(old['configuration']),request=scope.REQUEST,
                          functionTask=copy.deepcopy(scope.TASK),packageDirectory=temporary)
            args=packet['startupSourceAudit']['engineCommand'];args[args.index('--max-context')+1]='16384'
            for name,source in scope.SCRIPTS.items():(inputs/name).write_bytes((scope.HERE/source).read_bytes().replace(b'\r\n',b'\n'))
            (inputs/'request.json').write_text(json.dumps(scope.REQUEST));(inputs/'strata.json').write_text(json.dumps(packet['configuration']))
            packet['inputSha256']={x.name:scope.p.build.tools.sha(x) for x in inputs.iterdir()}
            with patch.object(scope.p,'INPUT_SCRIPTS',dict(scope.SCRIPTS)):
                scope.same_limits(packet)
                for area,key,value in [('policy','cpuStopC',98),('policy','ramStopMiB',30721),
                        ('requestTimingChange','hardRequestDeadlineSeconds',151),('request','max_tokens',8192),
                        ('functionTask','inputBudgetTokens',1024),('functionTask','fullWindowCapacityEstablishedBySuccess',True)]:
                    changed=copy.deepcopy(packet);changed[area][key]=value
                    with self.subTest(area=area,key=key),self.assertRaises(ValueError):scope.same_limits(changed)


if __name__=='__main__':unittest.main()
