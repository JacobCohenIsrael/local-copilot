import json
import unittest
from unittest.mock import patch

from opencode_fake_probe import RecordingGate, denial_kind
import verify_opencode


class OpenCodeActionsTests(unittest.TestCase):
    def error(self, kind, message):
        return json.dumps({'error': {'type': kind, 'message': message}})

    def test_only_specific_denial_evidence_counts(self):
        shell = self.error('tool.execution', 'No tool named "shell" is currently available. Please use available tools.')
        old_name = self.error('tool.execution', 'No tool named "bash" is currently available.')
        invalid = self.error('tool.execution', 'Invalid arguments for tool "read": path missing')
        external = self.error('permission.rejected', 'Permission denied: external_directory')
        edit = self.error('permission.rejected', 'Permission denied: edit')
        self.assertEqual(denial_kind([shell], 'deny-shell'), 'tool-unavailable')
        self.assertIsNone(denial_kind([old_name, invalid, 'permission denied'], 'deny-shell'))
        self.assertIsNone(denial_kind([edit], 'deny-external'))
        self.assertEqual(denial_kind([external], 'deny-external'), 'permission-denied')
        self.assertEqual(denial_kind([edit], 'deny-file-write'), 'permission-denied')

    def test_request_summary_excludes_prompt_content(self):
        gate = RecordingGate(model='synthetic-coder', count_prompt=lambda request: 80)
        gate.admit(json.dumps({'model': 'synthetic-coder', 'messages': [
            {'role': 'user', 'content': 'PRIVATE FIXTURE CONTENT'}]}).encode())
        self.assertNotIn('PRIVATE', json.dumps(gate.request_summaries))
        self.assertEqual(gate.calls, 1)

    def test_unknown_scenario_never_contacts_docker(self):
        with patch.object(verify_opencode, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'FIXED_SCENARIO_REQUIRED'):
                verify_opencode.run('unused', fake=True, scenario='arbitrary-command')
            docker.assert_not_called()


if __name__ == '__main__':
    unittest.main()
