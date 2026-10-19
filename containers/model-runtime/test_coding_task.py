"""Offline checks for the narrow live adapter; no model, Docker or sensor calls."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import coding_task as coding
import coding_worker as worker
import container_test
from test_runtime import answer

class CodingTests(unittest.TestCase):
    def test_response_supplies_actual_code_and_optional_fences(self):
        for content,expected in [('VALUE = 2','VALUE = 2\n'),('VALUE=2','VALUE=2\n'),
                ('```python\nVALUE = 2\n```','VALUE = 2\n')]:
            response=answer();response['choices'][0]['message']['content']=content
            self.assertEqual(worker.code_from_response(response),expected.encode())

    def test_wrong_or_additional_code_never_becomes_an_edit(self):
        for content in ('VALUE = 1','OTHER = 2','VALUE = True','VALUE = 2\nimport os',
                'VALUE = 2\nprint(VALUE)','x'*129,'```python\nVALUE = 2'):
            response=answer();response['choices'][0]['message']['content']=content
            with self.assertRaises((ValueError,SyntaxError)):worker.code_from_response(response)

    def test_coding_output_cap_is_explicit_and_context_stays_512(self):
        response=answer();response['usage'].update(prompt_tokens=30,completion_tokens=9,total_tokens=39)
        with self.assertRaises(ValueError):container_test.validate_response(response)
        container_test.validate_response(response,32)
        response['usage'].update(prompt_tokens=481,total_tokens=490)
        with self.assertRaises(ValueError):container_test.validate_response(response,32)
        self.assertEqual(coding.REQUEST['max_tokens'],32)
        self.assertLess(len(coding.REQUEST['messages'][0]['content'].encode()),128)

    def test_worker_has_no_network_gpu_or_original_project_mount(self):
        task={'workerInput':str(coding.REPO/'.runtime/strata-coding-preparation/fixture/worker-input')}
        name,args=coding.worker_args(task)
        self.assertEqual(args[args.index('--network')+1],'none')
        self.assertNotIn('--gpus',args);self.assertNotIn('--privileged',args)
        self.assertEqual(args[args.index('--memory')+1],'512m')
        self.assertEqual(args[args.index('--memory-swap')+1],'512m')
        mounts=[args[n+1] for n,value in enumerate(args) if value=='--mount']
        self.assertEqual(len(mounts),2)
        self.assertTrue(all(value.endswith(',readonly') for value in mounts))
        self.assertTrue(all('original' not in value and 'worker-bundles' not in value for value in mounts))

    def test_real_answer_manifest_is_verified_and_cannot_be_silently_replaced(self):
        coding.ninth_proof()
        with patch.object(coding.p.build.tools,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'NINTH_MANIFEST_CHANGED'):coding.ninth_proof()

if __name__=='__main__':unittest.main()
