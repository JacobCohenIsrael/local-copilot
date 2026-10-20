"""Offline regression of real rejected output, prompt scope and fail-closed edits."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import coding_task_2_statement as scope
import bounded_read_statement as statement


def response(code, finish='stop'):
    return {'choices': [{'message': {'content': code}, 'finish_reason': finish}]}


class StatementTests(unittest.TestCase):
    def test_actual_length_limited_response_is_rejected_before_replacement(self):
        result = scope.p.read(scope.REJECTED / 'execution-result.json', 131072)
        actual = result['apiResult']['response']
        with patch.object(statement.spec, 'replacement') as insert:
            with self.assertRaisesRegex(ValueError, 'MODEL_OUTPUT_INCOMPLETE'):
                statement.replacement(actual, b'not accessed')
            insert.assert_not_called()

    def test_even_syntactically_valid_guard_requires_completed_generation(self):
        for finish in ('length', 'tool_calls', None):
            with self.subTest(finish=finish), self.assertRaisesRegex(ValueError, 'MODEL_OUTPUT_INCOMPLETE'):
                statement.guard_from_response(response('if maximum < 0: raise ValueError', finish))

    def test_valid_complete_statement_preserves_bytes_and_passes_real_function_acceptance(self):
        original = (scope.REPO / statement.spec.SOURCE).read_bytes()
        for code in ('if maximum < 0: raise ValueError', 'if maximum < 0: raise ValueError()'):
            updated = statement.replacement(response(code), original)
            newline = b'\r\n' if b'\r\n' in original else b'\n'
            insertion = b'    ' + code.encode() + newline
            self.assertEqual(updated.replace(insertion, b'', 1), original)
            self.assertTrue(statement.spec.acceptance(updated)['negativeLimitsRejectedBeforeAccess'])

    def test_no_fence_repair_extra_statements_or_wrong_condition(self):
        invalid = ['```python\nif maximum < 0: raise ValueError\n```',
                   'if maximum < 0:\n    raise ValueError',
                   'if maximum < 0: raise ValueError; open("secret")',
                   'if maximum <= 0: raise ValueError',
                   'def max_value(values): return values[0]',
                   'if maximum < 0: raise ValueError("negative")',
                   'if maximum < 0: raise ValueError' + ' ' * 129 + '#x']
        for code in invalid:
            with self.subTest(code=code), self.assertRaises((ValueError, SyntaxError)):
                statement.guard_from_response(response(code))

    def test_latest_consumed_attempt_full_inventory_and_approval_are_bound(self):
        proof = scope.rejection_proof(True)
        self.assertFalse(proof['previousAttemptReset'])
        self.assertFalse(proof['previousApprovalReused'])
        with patch.object(scope.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'REJECTED_MANIFEST_CHANGED'):
                scope.rejection_proof()

    def test_only_prompt_can_change_no_other_limit_or_baked_request_drift(self):
        base = scope.p.read(scope.REJECTED / 'review.json', 131072)
        root = scope.REPO / '.runtime/statement-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs = Path(temporary) / 'input'
            inputs.mkdir()
            for path in (Path(base['packageDirectory']) / 'input').iterdir():
                (inputs / path.name).write_bytes(path.read_bytes())
            (inputs / 'request.json').write_text(json.dumps(scope.REQUEST))
            packet = {**base, 'request': copy.deepcopy(scope.REQUEST), 'packageDirectory': temporary}
            with patch.object(scope.p, 'INPUT_SCRIPTS', dict(scope.timing.SCRIPTS)), \
                 patch.object(scope.task, 'WORKER_HELPERS', dict(scope.HELPERS)), \
                 patch.object(scope.task, 'check_task'):
                scope.same_limits(packet)
                changes = [('policy', 'cpuStopC', 98), ('policy', 'gpuStopC', 76),
                           ('policy', 'modelSeconds', 301), ('policy', 'outerSeconds', 411),
                           ('requestTimingChange', 'hardRequestDeadlineSeconds', 151),
                           ('request', 'max_tokens', 33), ('request', 'stream', True),
                           ('request', 'messages', [{'role':'user', 'content':'different'}]),
                           ('configuration', 'engine_silence_s', 80), ('vmEnvelope', 'cpus', 2),
                           ('codingTask', 'maximumGuardBytes', 129), ('codingTask', 'modelCalls', 2),
                           ('codingTask', 'workerEnvelope', {'cpus': 1})]
                for area, key, value in changes:
                    changed = copy.deepcopy(packet)
                    changed[area][key] = value
                    with self.subTest(area=area, key=key), self.assertRaises(ValueError):
                        scope.same_limits(changed)
                (inputs / 'request.json').write_text(json.dumps(base['request']))
                with self.assertRaisesRegex(ValueError, 'STATEMENT_BAKED_REQUEST_OR_CONFIG_CHANGED'):
                    scope.same_limits(packet)

    def test_new_scope_host_and_cli_refuse_missing_and_spent_approvals_before_docker(self):
        script = '''
import sys
from unittest.mock import patch
import coding_task_2_statement as s
s.activate()
assert s.p.APPROVAL.name=='coding-task-2-statement-approval.json'
assert s.task.coding.WORKER==s.WORKER and s.p.LIVE==s.LIVE
assert s.task.WORKER_HELPERS==s.HELPERS
assert s.task.coding.REQUEST==s.REQUEST==s.p.REQUEST
assert s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==150
assert s.task.coding.first_api.WATCH_ENTRYPOINT.name=='coding_task_2_statement.py'
assert s.task.coding.coding_worker.code_from_response.func is s.statement.replacement
with patch.object(s.task.coding.first_api.guard.base,'Docker') as docker, \\
     patch.object(s.p,'APPROVAL',s.ROOT/'deliberately-missing-approval.json'), \\
     patch.object(s.task.coding,'WORKER',s.ROOT/'deliberately-missing-worker'):
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-statement']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    docker.assert_not_called()
for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json']:
    with patch.object(s.p,'APPROVAL',s.HERE/name), patch.object(s.p,'review',return_value=('b'*64,{})):
        try:s.p.authorize()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
        else:raise AssertionError('spent approval reused')
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=scope.HERE,
                       capture_output=True, check=True, timeout=20)


if __name__ == '__main__': unittest.main()
