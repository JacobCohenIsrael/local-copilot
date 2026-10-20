"""Offline pinned silence-loop replay, unchanged limits and fresh approval gates."""
import ast
import contextlib
import copy
import io
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import coding_task_2_compact as scope


def replay(events, prompt_tokens=34):
    """Execute only pinned pure Python methods with fake time and engine pipes."""
    source = scope.REPO / '.runtime/strata-build/1c9c3253/input/source/serve/server.py'
    if scope.p.build.tools.sha(source) != scope.timing.p.native_iq_startup.SERVER_SHA:
        raise ValueError('PINNED_SILENCE_SOURCE_CHANGED')
    tree = ast.parse(source.read_bytes())
    methods = {}
    for class_name, method in [('StrataEngine', 'generate'), ('Service', '_progress')]:
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        methods[method] = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method)
    clock = SimpleNamespace(now=0.0)
    clock.monotonic = clock.time = lambda: clock.now
    remaining = list(events)
    class Lines:
        def get(self, timeout):
            if remaining and remaining[0][0] <= clock.now + timeout:
                clock.now, line = remaining.pop(0)
                return line
            clock.now += timeout
            raise queue.Empty
    namespace = {'time': clock, 'queue': queue, 'PP_CHUNK_MAX': 32768,
                 'PP_FLOOR_TOK_S': 50.0, 'PP_SLACK': 3.0, 'ENGINE_STALL_S': 0,
                 'EngineDied': RuntimeError, 'EngineNonFinite': RuntimeError,
                 'bias_api': SimpleNamespace(validate_request=lambda *_: None)}
    exec(compile(ast.Module(body=list(methods.values()), type_ignores=[]), str(source), 'exec'), namespace)
    engine = SimpleNamespace(alive=lambda: True, batch=0, silence_s=75,
                             sampling_keys=lambda _: '', proc=SimpleNamespace(stdin=io.StringIO()),
                             lines=Lines(), can_stop=False, last={'finish': 'stop'},
                             _parse_done=lambda _: None, _silent=lambda text: RuntimeError(text))
    service = SimpleNamespace(status_lock=contextlib.nullcontext(), engine=engine,
                              status={'started': 0, 'first_token': None, 'prompt_tokens': prompt_tokens})
    output = io.StringIO()
    values, last_print, error = [], 0, None
    with contextlib.redirect_stdout(output):
        try:
            for value in namespace['generate'](engine, list(range(prompt_tokens)), 32, {}, SimpleNamespace(is_set=lambda: False)):
                values.append(value)
                if value is None:
                    last_print = namespace['_progress'](service, last_print)
        except RuntimeError as exc:
            error = str(exc)
    return {'seconds': clock.now, 'statusText': output.getvalue(), 'values': values,
            'error': error, 'engineProgress': engine.progress}


class CompactTests(unittest.TestCase):
    def test_waiting_narration_and_keepalive_do_not_refresh_actual_silence_clock(self):
        result = replay([(0, 'RESUME 0')])
        self.assertIn('the engine said nothing', result['error'])
        self.assertAlmostEqual(result['seconds'], 75 + 34 / 50)
        self.assertEqual(result['values'], [None] * 7)
        self.assertEqual(result['statusText'].count('reading the prompt: 34 tokens'), 7)
        self.assertIsNone(result['engineProgress'])

    def test_actual_engine_pp_line_refreshes_clock_and_reports_real_position(self):
        result = replay([(0, 'RESUME 0'), (50, 'PP 22 23 50000 50'), (90, 'DONE')], 23)
        self.assertIsNone(result['error'])
        self.assertEqual(result['seconds'], 90)
        self.assertEqual(result['engineProgress'], (22, 23))
        self.assertIn('22 of 23', result['statusText'])

    def test_latest_fault_and_spent_decision_full_inventory_remain_bound(self):
        proof = scope.silence_proof(True)
        self.assertFalse(proof['previousAttemptReset'])
        self.assertFalse(proof['previousApprovalReused'])
        with patch.object(scope.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'REJECTED_MANIFEST_CHANGED'):
                scope.silence_proof()

    def test_only_compact_message_changes_silence_deadlines_and_worker_stay_fixed(self):
        base = scope.p.read(scope.REJECTED / 'review.json', 131072)
        root = scope.REPO / '.runtime/compact-offline-tests'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            inputs = Path(temporary) / 'input'
            inputs.mkdir()
            for path in (Path(base['packageDirectory']) / 'input').iterdir():
                (inputs / path.name).write_bytes(path.read_bytes())
            import json
            (inputs / 'request.json').write_text(json.dumps(scope.REQUEST))
            packet = {**base, 'request': copy.deepcopy(scope.REQUEST), 'packageDirectory': temporary}
            with patch.object(scope.p, 'INPUT_SCRIPTS', dict(scope.timing.SCRIPTS)), \
                 patch.object(scope.task, 'WORKER_HELPERS', dict(scope.HELPERS)), \
                 patch.object(scope.task, 'check_task'):
                scope.same_limits(packet)
                for area, key, value in [('configuration', 'engine_silence_s', 76),
                        ('policy', 'modelSeconds', 301), ('policy', 'cpuStopC', 98),
                        ('requestTimingChange', 'hardRequestDeadlineSeconds', 151),
                        ('request', 'max_tokens', 33), ('request', 'stream', True),
                        ('request', 'messages', base['request']['messages']),
                        ('codingTask', 'modelCalls', 2), ('vmEnvelope', 'cpus', 2),
                        ('codingTask', 'workerEnvelope', {'cpus': 1})]:
                    changed = copy.deepcopy(packet)
                    changed[area][key] = value
                    with self.subTest(area=area, key=key), self.assertRaises(ValueError):
                        scope.same_limits(changed)
                (inputs / 'request.json').write_text(json.dumps(base['request']))
                with self.assertRaisesRegex(ValueError, 'COMPACT_BAKED_REQUEST_OR_CONFIG_CHANGED'):
                    scope.same_limits(packet)

    def test_host_cli_and_all_spent_decisions_refuse_before_docker(self):
        script = '''
import sys
from unittest.mock import patch
import coding_task_2_compact as s
s.activate()
assert s.p.APPROVAL.name=='coding-task-2-compact-approval.json'
assert s.task.coding.WORKER==s.WORKER and s.p.LIVE==s.LIVE
assert s.task.WORKER_HELPERS==s.prior.HELPERS==s.HELPERS
assert s.task.coding.REQUEST==s.REQUEST==s.p.REQUEST
assert s.p.REQUEST_TIMING_CHANGE['hardRequestDeadlineSeconds']==150
assert s.p.config()['engine_silence_s']==75
assert s.task.coding.first_api.WATCH_ENTRYPOINT.name=='coding_task_2_compact.py'
assert s.task.coding.coding_worker.code_from_response.func is s.statement.replacement
with patch.object(s.task.coding.first_api.guard.base,'Docker') as docker, \\
     patch.object(s.p,'APPROVAL',s.ROOT/'deliberately-missing-approval.json'), \\
     patch.object(s.task.coding,'WORKER',s.ROOT/'deliberately-missing-worker'):
    try:s.run()
    except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
    else:raise AssertionError('missing approval allowed')
    sys.path.insert(0,str(s.REPO));import local_worker as cli
    with patch.object(sys,'argv',['local_worker.py','run-useful-coding-task-compact']):
        try:cli.main()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_NOT_APPROVED',e
        else:raise AssertionError('CLI bypassed approval')
    docker.assert_not_called()
for name in ['coding-task-2-approval.json','coding-task-2-recovery-approval.json','coding-task-2-timing-approval.json','coding-task-2-statement-approval.json']:
    with patch.object(s.p,'APPROVAL',s.HERE/name), patch.object(s.p,'review',return_value=('b'*64,{})):
        try:s.p.authorize()
        except ValueError as e:assert str(e)=='FIRST_MODEL_API_APPROVAL_INVALID',e
        else:raise AssertionError('spent approval reused')
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=scope.HERE,
                       capture_output=True, check=True, timeout=20)


if __name__ == '__main__': unittest.main()
