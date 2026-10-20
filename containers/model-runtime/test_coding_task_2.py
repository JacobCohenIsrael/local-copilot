"""Useful-task acceptance and containment checks; no hardware or worker starts."""
import base64
import contextlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

import bounded_read_task as spec
import coding_task_2 as coding


def response(code):
    return {'choices': [{'message': {'content': code}}]}


class UsefulTaskTests(unittest.TestCase):
    def setUp(self):
        self.original = (coding.REPO / spec.SOURCE).read_bytes()

    def test_existing_negative_limit_defect_is_reproduced_without_real_reads(self):
        with self.assertRaisesRegex(ValueError, 'NEGATIVE_LIMIT_ACCESSED_FILE'):
            spec.acceptance(self.original)

    def test_consumed_worker_scope_is_reported_even_without_model_attempt(self):
        with patch.object(coding, 'WORKER') as worker, patch.object(coding.p, 'summary') as model_summary:
            worker.exists.return_value = True
            result = coding.summary()
            self.assertEqual(result['status'], 'ATTEMPT_CONSUMED')
            self.assertFalse(result['modelLaunchEnabled'])
            self.assertFalse(result['workerLaunchEnabled'])
            model_summary.assert_not_called()

    def test_unused_worker_scope_uses_existing_review_summary(self):
        with patch.object(coding, 'WORKER') as worker, patch.object(coding.p, 'summary', return_value={'status':'NOT_PREPARED_OR_STALE'}) as model_summary:
            worker.exists.return_value = False
            self.assertEqual(coding.summary(), {'status':'NOT_PREPARED_OR_STALE'})
            model_summary.assert_called_once_with()

    def test_model_guard_is_inserted_and_all_other_bytes_preserved(self):
        for code in ('if maximum < 0: raise ValueError', 'if maximum < 0:\n    raise ValueError()',
                     '```python\nif maximum < 0:\n    raise ValueError\n```'):
            with self.subTest(code=code):
                updated = spec.replacement(response(code), self.original)
                self.assertTrue(spec.acceptance(updated)['negativeLimitsRejectedBeforeAccess'])
                newline = b'\r\n' if b'\r\n' in self.original else b'\n'
                guard = spec.guard_from_response(response(code))
                import textwrap
                insertion = textwrap.indent(guard, '    ').replace('\n', newline.decode()).encode() + newline
                self.assertEqual(updated.replace(insertion, b'', 1), self.original)
                self.assertIn(insertion.strip(), updated)

    def test_extra_behavior_wrong_conditions_and_code_budget_rejected(self):
        for code in ('if maximum <= 0: raise ValueError', 'if maximum < 1: raise ValueError',
                     'if other < 0: raise ValueError', 'if maximum < 0: raise RuntimeError',
                     'if maximum < 0: raise ValueError() from RuntimeError()',
                     'if maximum < 0: raise ValueError\nelse: print(1)',
                     'if maximum < 0: raise ValueError\nimport os',
                     'if maximum < 0: raise ValueError()\nopen("secret")',
                     'if maximum < 0: raise ValueError(open("secret"))',
                     'if maximum < 0: raise ValueError' + '#' * 129,
                     '```python\nif maximum < 0: raise ValueError',
                     '```sh\nif maximum < 0: raise ValueError\n```'):
            with self.subTest(code=code):
                with self.assertRaises((ValueError, SyntaxError)):
                    spec.replacement(response(code), self.original)

    def test_changed_repository_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SELECTED_REPOSITORY_SOURCE_CHANGED'):
            spec.replacement(response('if maximum < 0: raise ValueError'), self.original + b'\n')

    def test_pilot_preservation_binding_and_no_spent_approval_reuse(self):
        coding.pilot_proof(True)
        with patch.object(coding.p.build.tools, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'PILOT_MANIFEST_CHANGED'): coding.pilot_proof()
        script = '''
import coding_task_2 as c
import sys
from unittest.mock import patch
c.activate()
with patch.object(c.p, 'APPROVAL', c.ROOT/'deliberately-missing-approval.json'), \\
     patch.object(c.coding, 'WORKER', c.ROOT/'deliberately-missing-worker'), \\
     patch.object(c.coding.first_api.guard.base, 'Docker') as docker:
    try: c.coding.run()
    except ValueError as error: assert str(error) == 'FIRST_MODEL_API_NOT_APPROVED', error
    else: raise AssertionError('missing approval allowed')
    sys.path.insert(0, str(c.REPO))
    import local_worker as cli
    with patch.object(sys, 'argv', ['local_worker.py', 'run-useful-coding-task']):
        try: cli.main()
        except ValueError as error: assert str(error) == 'FIRST_MODEL_API_NOT_APPROVED', error
        else: raise AssertionError('CLI bypassed missing approval')
    docker.assert_not_called()
assert c.p.LIVE.name == 'strata-coding-2-model'
assert c.WORKER.name == 'strata-coding-2-worker'
assert c.p.SCOPE != 'one-codex-strata-generated-single-file-opencode-edit-live-broker'
'''
        subprocess.run([sys.executable, '-B', '-c', script], cwd=coding.HERE, check=True,
                       capture_output=True, timeout=20)

    def test_selected_file_import_returns_applicable_patch_and_rejects_other_files(self):
        root = coding.REPO / '.runtime/useful-task-tests'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            directory = Path(temporary)
            source = directory / 'source'
            source.mkdir()
            (source / spec.SELECTED).write_bytes(self.original)
            (source / 'unselected.txt').write_bytes(b'unchanged')
            bundle = coding.coding.task_bundle
            with patch.object(bundle, 'ROOT', directory / 'bundles'):
                prepared = bundle.prepare({'sourceRoot': str(source), 'files': [spec.SELECTED], 'task': spec.TASK})
                updated = spec.replacement(response('if maximum < 0: raise ValueError'), self.original)
                encoded = base64.b64encode(updated).decode()
                for selected, files in (('unselected.txt', {'unselected.txt': encoded}),
                                         ('../escape', {'../escape': encoded}),
                                         (spec.SELECTED, {spec.SELECTED: encoded, 'unselected.txt': encoded})):
                    with self.assertRaises(ValueError):
                        coding.coding.bundle_rehearsal.import_output(prepared['runId'], files, selected)
                    self.assertEqual((Path(prepared['workspace']) / spec.SELECTED).read_bytes(), self.original)
                result = coding.coding.bundle_rehearsal.import_output(prepared['runId'], {spec.SELECTED: encoded}, spec.SELECTED)
                self.assertEqual(result['changedFiles'], [spec.SELECTED])
                self.assertFalse(result['applied'])
                patch_path = directory / 'returned.patch'
                patch_path.write_bytes(result['patch'].encode())
                subprocess.run(['git', 'apply', '--check', str(patch_path)], cwd=source,
                               check=True, capture_output=True, timeout=10)
                self.assertEqual((source / spec.SELECTED).read_bytes(), self.original)
                self.assertEqual((source / 'unselected.txt').read_bytes(), b'unchanged')
                self.assertTrue(spec.acceptance((Path(prepared['workspace']) / spec.SELECTED).read_bytes())['oversizeStillRejected'])

    def test_connected_host_flow_requires_lineage_and_always_confirms_owned_stop(self):
        root = coding.REPO / '.runtime/useful-task-tests'
        root.mkdir(parents=True, exist_ok=True)
        for tampered, repository_changed in ((False, False), (True, False), (False, True)):
            with self.subTest(tampered=tampered, repository_changed=repository_changed), tempfile.TemporaryDirectory(dir=root) as temporary:
                directory = Path(temporary)
                original = directory / 'original'
                original.mkdir()
                (original / spec.SELECTED).write_bytes(self.original)
                (original / 'unselected.txt').write_bytes(b'unchanged')
                common = coding.coding
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(common.task_bundle, 'ROOT', directory / 'bundles'))
                    prepared = common.task_bundle.prepare({'sourceRoot': str(original), 'files': [spec.SELECTED], 'task': spec.TASK})
                    task = {'selectedFile': spec.SELECTED, 'bundleRunId': prepared['runId'],
                            'originalDirectory': str(original), 'workerInput': str(directory / 'input')}
                    repository_file = directory / 'repository-original.py'
                    repository_file.write_bytes(self.original + (b'# concurrent change' if repository_changed else b''))
                    task.update(repositoryFile=repository_file.relative_to(coding.REPO).as_posix(),
                                sourceSha256=spec.SOURCE_SHA256)
                    answer = response('if maximum < 0: raise ValueError')
                    generated = spec.replacement(answer, self.original)
                    api_path = directory / 'api.json'
                    api_path.write_text(json.dumps({'response': answer}))
                    cid = 'a' * 64
                    docker = Mock()
                    docker.call.side_effect = [cid, '', '0', ''] if not tampered else [cid, '', '']
                    docker.inspect.return_value = {'Id': cid}
                    request = {'model': coding.REQUEST['model'], 'messages': [{'content': spec.TASK}],
                               'tools': [{'function': {'name': 'edit'}}]}
                    worker = {'status': 'REAL_STRATA_CODE_APPLIED', 'modelRequests': 1,
                              'answerUsed': {'responseSha256': coding.p.sha(answer)},
                              'outputFiles': {spec.SELECTED: base64.b64encode(generated + (b'#tamper' if tampered else b'')).decode()}}
                    replacements = [(common, 'activate', Mock()), (common, 'WORKER', directory / 'worker'),
                                    (common, 'check_task', Mock()), (common, 'validate_worker', Mock()),
                                    (common, 'read_worker', Mock(side_effect=[request, worker])),
                                    (common.coding_worker, 'TASK', spec.TASK),
                                    (common.coding_worker, 'code_from_response', lambda value: spec.replacement(value, self.original)),
                                    (common.p, 'authorize', Mock(return_value=Mock(packet={'codingTask': task}, review_sha256='b' * 64))),
                                    (common.first_api, 'state_exists', Mock(return_value=False)),
                                    (common.first_api, 'run', Mock(return_value={'apiResultFile': str(api_path)})),
                                    (common.first_api.guard.base, 'Docker', Mock(return_value=docker)),
                                    (common.first_api.guard, 'stop_target', Mock(return_value={'stopConfirmed': True}))]
                    for module, name, value in replacements: stack.enter_context(patch.object(module, name, value))
                    result = common.run()
                    self.assertTrue(result['originalUnchanged'])
                    self.assertTrue(result['workerStop']['stopConfirmed'])
                    common.first_api.guard.stop_target.assert_called_once()
                    self.assertEqual(common.first_api.guard.stop_target.call_args.args[2], cid)
                    self.assertFalse(common.first_api.guard.stop_target.call_args.kwargs['remove'])
                    self.assertEqual(result['repositoryOriginalUnchanged'], not repository_changed)
                    if tampered or repository_changed:
                        self.assertEqual(result['status'], 'FAULT')
                        self.assertIsNone(result['patch'])
                    else:
                        self.assertEqual(result['status'], 'REAL_STRATA_CODING_PATCH_FOR_REVIEW')
                        self.assertEqual(result['collected']['changedFiles'], [spec.SELECTED])
                    self.assertEqual((original / spec.SELECTED).read_bytes(), self.original)


if __name__ == '__main__': unittest.main()
