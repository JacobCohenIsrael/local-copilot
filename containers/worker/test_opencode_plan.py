import unittest

from test_task_bundle import TaskBundleTests
import opencode_plan


class OpenCodePlanTests(unittest.TestCase):
    setUp = TaskBundleTests.setUp
    prepare = TaskBundleTests.prepare
    def test_disabled_and_file_scoped(self):
        run = self.prepare()
        plan = opencode_plan.plan(run['runId'])
        self.assertFalse(plan['executionEnabled'])
        self.assertFalse(plan['modelEnabled'])
        self.assertIsNone(plan['opencode']['imageDigest'])
        rules = plan['config']['permission']
        self.assertEqual(rules['*'], 'deny')
        self.assertEqual(rules['read'], {'*': 'deny', '/workspace/fix.py': 'allow'})
        self.assertEqual(plan['config']['agent']['bounded']['permission'], rules)
        self.assertEqual(plan['config']['enabled_providers'], ['strata'])
        self.assertEqual(len(plan['containerCandidates']['mounts']), 2)

    def test_control_and_env_files_rejected(self):
        for name in ['opencode.json', 'AGENTS.md', '.env', '.env.local', '.opencode/plugin.js']:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}')
            run = self.prepare(files=[name])
            with self.assertRaisesRegex(ValueError, 'WORKER_CONTROL_OR_SECRET_FILE'):
                opencode_plan.plan(run['runId'])

    def test_changed_workspace_rejected(self):
        run = self.prepare()
        (self.store / run['runId'] / 'workspace' / 'fix.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'PRISTINE_WORKSPACE_REQUIRED'):
            opencode_plan.plan(run['runId'])


# Avoid discovering the imported test class twice.
del TaskBundleTests

if __name__ == '__main__':
    unittest.main()
