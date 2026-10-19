"""Offline preservation and one native-IQ argument correction; no native calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import first_api
import prior_api
import runtime_plan as plan


class SecondAttemptTests(unittest.TestCase):
    def test_recorded_fault_and_supplement_are_preserved_without_live_access(self):
        with patch.object(first_api.guard.base, 'Docker') as docker:
            proof = plan.previous()
        self.assertEqual(proof['first']['retainedContainerId'], prior_api.CONTAINER)
        self.assertEqual(proof['second']['retainedContainerId'], prior_api.SECOND_CONTAINER)
        self.assertEqual(proof['third']['retainedContainerId'], prior_api.THIRD_CONTAINER)
        self.assertFalse(proof['first']['previousAttemptReset'])
        self.assertFalse(proof['second']['previousAttemptReset'])
        self.assertFalse(proof['third']['previousAttemptReset'])
        self.assertEqual(proof['fourth']['retainedContainerId'],prior_api.FOURTH_CONTAINER)
        self.assertFalse(proof['fourth']['previousAttemptReset'])
        self.assertEqual(proof['fifth']['retainedContainerId'],prior_api.FIFTH_CONTAINER)
        self.assertFalse(proof['fifth']['previousAttemptReset'])
        self.assertEqual(proof['sixth']['retainedContainerId'],prior_api.SIXTH_CONTAINER)
        self.assertFalse(proof['sixth']['previousAttemptReset'])
        self.assertEqual(proof['seventh']['retainedContainerId'],prior_api.SEVENTH_CONTAINER)
        self.assertFalse(proof['seventh']['previousAttemptReset'])
        self.assertEqual(proof['eighth']['retainedContainerId'],prior_api.EIGHTH_CONTAINER)
        self.assertFalse(proof['eighth']['previousAttemptReset'])
        self.assertEqual(set(proof),{'first','second','third','fourth','fifth','sixth','seventh','eighth'})
        docker.assert_not_called()
        self.assertNotEqual(plan.LIVE, plan.REPO / '.runtime/first-model-api-1')
        self.assertNotEqual(plan.APPROVAL.name, 'first-model-api-approval.json')
        self.assertNotEqual(plan.LIVE, plan.REPO / '.runtime/model-api-2')
        self.assertNotEqual(plan.APPROVAL.name, 'model-api-2-approval.json')
        self.assertNotEqual(plan.LIVE, plan.REPO / '.runtime/model-api-3')
        self.assertNotEqual(plan.APPROVAL.name, 'model-api-3-approval.json')

    def test_changed_preservation_inventory_is_rejected_before_paths_are_used(self):
        original = prior_api.digest
        with patch.object(prior_api, 'digest', side_effect=lambda path:
                '0'*64 if path.name == 'execution-preservation.json' else original(path)):
            with self.assertRaisesRegex(ValueError, 'MANIFEST_CHANGED'):
                plan.previous()

    def test_changed_frozen_helper_is_rejected_without_touching_historical_files(self):
        original = Path.read_bytes
        def read(path):
            raw = original(path)
            return raw + b'changed' if path == prior_api.FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaisesRegex(ValueError, 'FROZEN_HELPER_CHANGED'):
                plan.previous()

    def test_policy_and_budgets_cannot_change_alongside_the_argument_fix(self):
        original = prior_api.load(prior_api.EIGHTH_FOLDER/'review.json')
        original['configuration'] = plan.config()
        original['requestTimingChange'] = dict(plan.REQUEST_TIMING_CHANGE)
        original['fileAccessChange'] = dict(plan.FILE_ACCESS_CHANGE)
        original['startupTargetChange'] = dict(plan.STARTUP_TARGET_CHANGE)
        original['startupStatusChange'] = dict(plan.STARTUP_CHANGE)
        original['policy'] = dict(plan.safety.POLICY)
        plan.same_limits(original)
        for group, field, value in (('policy', 'cpuStartC', 93), ('policy', 'cpuStartC', 96), ('policy', 'cpuStopC', 99),
                ('policy', 'hostFreeRamStartMiB', 7936), ('policy', 'gpuStopPowerW', 110),
                ('request', 'max_tokens', 16), ('vmEnvelope', 'cpus', 2)):
            packet = copy.deepcopy(original); packet[group][field] = value
            with self.assertRaisesRegex(ValueError, 'CHANGE_MISMATCH|POLICY_CHANGED|LIMIT_OR_INPUT_CHANGED'):
                plan.same_limits(packet)
        packet = copy.deepcopy(original); packet['contract']['host']['Memory'] += 1
        with self.assertRaisesRegex(ValueError, 'CONTRACT_CHANGED'):
            plan.same_limits(packet)

    def test_old_owner_decision_cannot_approve_new_attempt(self):
        for folder in (prior_api.FOLDER, prior_api.SECOND_FOLDER, prior_api.THIRD_FOLDER, prior_api.FOURTH_FOLDER,prior_api.FIFTH_FOLDER,prior_api.SIXTH_FOLDER,prior_api.SEVENTH_FOLDER,prior_api.EIGHTH_FOLDER):
            old = prior_api.load(folder/'owner-approval.json')
            packet = prior_api.load(folder/'review.json')
            with tempfile.TemporaryDirectory() as directory:
                decision = Path(directory)/'approval.json'; decision.write_text(json.dumps(old))
                with patch.object(plan, 'APPROVAL', decision), patch.object(plan, 'review', return_value=('a'*64, packet)):
                    with self.assertRaisesRegex(ValueError, 'APPROVAL_INVALID'):
                        plan.authorize()

    def test_second_inventory_and_frozen_helpers_cannot_be_changed(self):
        original_digest = prior_api.digest
        with patch.object(prior_api, 'digest', side_effect=lambda path:
                '0'*64 if path == prior_api.SECOND_FOLDER/'execution-preservation.json' else original_digest(path)):
            with self.assertRaisesRegex(ValueError, 'SECOND_API_MANIFEST_CHANGED'):
                plan.previous()
        original_bytes = Path.read_bytes
        def read(path):
            raw = original_bytes(path)
            return raw + b'changed' if path == prior_api.SECOND_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaisesRegex(ValueError, 'SECOND_API_FROZEN_HELPER_CHANGED'):
                plan.previous()

    def test_unapproved_new_attempt_refuses_before_docker_or_sensor_input_checks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(plan, 'APPROVAL', Path(directory)/'absent'), \
                patch.object(first_api.guard.base, 'Docker') as docker, patch.object(plan, 'verify_inputs') as verify:
            with self.assertRaisesRegex(ValueError, 'NOT_APPROVED'):
                first_api.run()
            docker.assert_not_called(); verify.assert_not_called()

    def test_third_inventory_and_frozen_helpers_are_preserved(self):
        original_digest = prior_api.digest
        with patch.object(prior_api,'digest',side_effect=lambda path:
                '0'*64 if path == prior_api.THIRD_FOLDER/'execution-preservation.json' else original_digest(path)):
            with self.assertRaisesRegex(ValueError,'THIRD_API_MANIFEST_CHANGED'):plan.previous()
        original_bytes = Path.read_bytes
        def read(path):
            raw = original_bytes(path)
            return raw+b'changed' if path == prior_api.THIRD_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(ValueError,'THIRD_API_FROZEN_HELPER_CHANGED'):plan.previous()


    def test_fifth_inventory_and_helpers_are_preserved_before_paths_are_trusted(self):
        original=prior_api.digest
        with patch.object(prior_api,'digest',side_effect=lambda path:
                '0'*64 if path==prior_api.FIFTH_FOLDER/'execution-preservation.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'FIFTH_API_MANIFEST_CHANGED'):plan.previous()
        original_bytes=Path.read_bytes
        def read(path):
            raw=original_bytes(path)
            return raw+b'changed' if path==prior_api.FIFTH_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(ValueError,'FIFTH_API_FROZEN_HELPER_CHANGED'):plan.previous()


    def test_sixth_inventory_and_frozen_helpers_cannot_change(self):
        original=prior_api.digest
        with patch.object(prior_api,'digest',side_effect=lambda path:
                '0'*64 if path==prior_api.SIXTH_FOLDER/'execution-preservation.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'SIXTH_API_MANIFEST_CHANGED'):plan.previous()
        original_bytes=Path.read_bytes
        def read(path):
            raw=original_bytes(path)
            return raw+b'changed' if path==prior_api.SIXTH_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(ValueError,'SIXTH_API_FROZEN_HELPER_CHANGED'):plan.previous()


    def test_seventh_inventory_and_frozen_helpers_cannot_change(self):
        original=prior_api.digest
        with patch.object(prior_api,'digest',side_effect=lambda path:
                '0'*64 if path==prior_api.SEVENTH_FOLDER/'execution-preservation.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'SEVENTH_API_MANIFEST_CHANGED'):plan.previous()
        original_bytes=Path.read_bytes
        def read(path):
            raw=original_bytes(path)
            return raw+b'changed' if path==prior_api.SEVENTH_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(ValueError,'SEVENTH_API_FROZEN_HELPER_CHANGED'):plan.previous()


if __name__ == '__main__':
    unittest.main()
