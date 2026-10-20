"""Offline 16K allocation/coding probe; no real model, Docker or sensors."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import context_16k as scope
import context_16k_guest as guest
from test_runtime import answer


def response(prompt=23,output=64,finish='stop'):
    result = answer()
    result['usage'] = {'prompt_tokens':prompt,'completion_tokens':output,'total_tokens':prompt+output}
    result['choices'][0]['finish_reason'] = finish
    return result


class Context16Tests(unittest.TestCase):
    def test_guest_host_admission_accepts_64_and_enforces_context_margin(self):
        for count in (1,32,33,64): self.assertIsNotNone(guest.validate_response(response(output=count)))
        self.assertIsNotNone(guest.validate_response(response(16312)))
        self.assertIsNotNone(guest.validate_response(response(finish='length')))
        for prompt,output in [(16313,64),(23,65),(True,64),(23,True),(23,0)]:
            with self.assertRaises(ValueError): guest.validate_response(response(prompt,output))
        for limit in (32,65,True):
            with self.assertRaises(ValueError): guest.validate_response(response(),limit)

    def test_length_is_preserved_for_strict_code_rejection(self):
        from bounded_read_statement import guard_from_response
        r = response(finish='length')
        r['choices'][0]['message']['content'] = 'if maximum < 0: raise ValueError'
        guest.validate_response(r)
        with self.assertRaisesRegex(ValueError,'MODEL_OUTPUT_INCOMPLETE'): guard_from_response(r)

    def test_controller_watch_and_missing_spent_approval_never_launch(self):
        script = '''
from unittest.mock import patch
import sys,runpy
import context_16k as s
with patch.object(s.task.coding.first_api.guard.base,'Docker') as docker,patch.object(s.p.safety,'snapshot') as sensors,patch.object(s.prior.history.readiness,'read_once') as read:
    s.activate()
    assert s.task.MAXIMUM_OUTPUT_TOKENS==64 and s.p.REQUEST['max_tokens']==64
    assert s.p.config()['args'][s.p.config()['args'].index('--max-context')+1]=='16384'
    assert s.p.safety.POLICY['ramStopMiB']==30720
    assert s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==150
    assert s.task.coding.first_api.validate_response is s.guest.validate_response
    assert s.task.coding.first_api.WATCH_ENTRYPOINT==s.Path(s.__file__).resolve()
    assert s.PROBE['fullWindowCapacityEstablishedBySuccess'] is False
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval admitted')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-context-16k-coding-probe']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json','coding-task-2-compact-approval.json','coding-task-2-ram30-approval.json']:
        with patch.object(s.p,'APPROVAL',s.HERE/name),patch.object(s.p,'review',return_value=('b'*64,{})):
            try:s.p.authorize()
            except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
            else:raise AssertionError('spent approval admitted')
    with patch.object(s.task.coding.first_api,'watch') as watch,patch.object(sys,'argv',[s.__file__,'--watch']):
        runpy.run_path(s.__file__,run_name='__main__');watch.assert_called_once()
        assert s.p.config()['args'][s.p.config()['args'].index('--max-context')+1]=='16384'
    docker.assert_not_called();sensors.assert_not_called();read.assert_not_called()
'''
        r = subprocess.run([sys.executable,'-B','-c',script],cwd=scope.HERE,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_only_context_output_and_bound_probe_change(self):
        old = scope.p.read(scope.PREVIOUS/'review.json',131072)
        root = scope.REPO/'.runtime/context16-offline-tests';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs = Path(temporary)/'input';inputs.mkdir()
            packet = copy.deepcopy(old)
            packet.update(configuration=scope.larger_context(old['configuration']),request=scope.REQUEST,
                          packageDirectory=temporary,contextProbe=dict(scope.PROBE))
            args = packet['startupSourceAudit']['engineCommand'];args[args.index('--max-context')+1]='16384'
            packet['codingTask']['maximumModelOutputTokens']=64
            for name,source in scope.SCRIPTS.items():
                (inputs/name).write_bytes((scope.HERE/source).read_bytes().replace(b'\r\n',b'\n'))
            (inputs/'request.json').write_text(__import__('json').dumps(scope.REQUEST))
            (inputs/'strata.json').write_text(__import__('json').dumps(packet['configuration']))
            packet['inputSha256']={x.name:scope.p.build.tools.sha(x) for x in inputs.iterdir()}
            with patch.object(scope.p,'INPUT_SCRIPTS',dict(scope.SCRIPTS)),patch.object(scope.task,'MAXIMUM_OUTPUT_TOKENS',64),patch.object(scope.task,'WORKER_HELPERS',dict(scope.prior.HELPERS)),patch.object(scope.task,'check_task'):
                scope.same_limits(packet)
                for area,key,value in [('policy','cpuStopC',98),('policy','ramStopMiB',30721),
                        ('requestTimingChange','hardRequestDeadlineSeconds',151),('request','max_tokens',128),
                        ('request','messages',[]),('contextProbe','fullWindowCapacityTest',True),
                        ('codingTask','maximumGuardBytes',129)]:
                    changed = copy.deepcopy(packet);changed[area][key]=value
                    with self.subTest(area=area,key=key),self.assertRaises(ValueError):scope.same_limits(changed)

    def test_previous_attempt_is_bound_and_remains_consumed(self):
        self.assertFalse(scope.previous_proof()['previousAttemptReset'])
        with patch.object(scope,'PREVIOUS_MANIFEST','0'*64):
            with self.assertRaisesRegex(ValueError,'RAM30_MANIFEST_CHANGED'):scope.previous_proof()


if __name__=='__main__':unittest.main()
