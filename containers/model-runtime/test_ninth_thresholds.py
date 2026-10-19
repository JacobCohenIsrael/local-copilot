"""Ninth startup warnings and emergency boundaries and eighth preservation; all hardware is simulated."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prior_api
import runtime_plan as plan
import runtime_safety as safety
from test_runtime import cpu,gpu
import test_runtime


class NinthThresholdTests(unittest.TestCase):
    def test_stop_boundary_during_running_and_cannot_reset_after_cooling(self):
        gate=safety.Gate();gate.model_started=0
        for second,temp in enumerate((94,95,96,96.999,97,90)):
            eligible=gate.observe(cpu(second+1,1000+second,cpuTemperatureC=temp),
                gpu(1000+second),now=second,unix=1000+second,controller_age=0)
            self.assertEqual(eligible,second<4)
            self.assertEqual(gate.fault,None if second<4 else 'CPU_HOT')

    def test_gpu_power_warning_does_not_reset_admission(self):
        gate=safety.Gate()
        for second in range(11):
            power=40.01 if second==9 else 40
            eligible=gate.observe(cpu(second+1,1000+second,cpuTemperatureC=95),
                gpu(1000+second,gpuPowerW=power),now=second,unix=1000+second,controller_age=0)
            self.assertEqual(eligible,second==10)
            self.assertIsNone(gate.fault)

    def test_threshold_metadata_and_old_policy_are_not_accepted(self):
        packet=copy.deepcopy(prior_api.load(prior_api.EIGHTH_FOLDER/'review.json'))
        packet.update(policy=dict(safety.POLICY),startupTargetChange=copy.deepcopy(plan.STARTUP_TARGET_CHANGE))
        plan.same_limits(packet)
        for group,key,value in (('policy','startupTargetsWarningsOnly',False),('policy','cpuStopC',98),
                                ('policy','cpuStartC',95),('policy','cpuStopC',99)):
            bad=copy.deepcopy(packet);bad[group][key]=value
            with self.assertRaisesRegex(ValueError,'POLICY_CHANGED'):plan.same_limits(bad)
        bad=copy.deepcopy(packet);bad['startupTargetChange']['emergencyStops']='disabled'
        with self.assertRaisesRegex(ValueError,'CHANGE_MISMATCH'):plan.same_limits(bad)

    def test_warning_mode_must_be_accepted_by_new_decision(self):
        packet={'sourceReviewSha256':'a'*64,'limitations':['fixture']}
        for decision_change in ('missing','old-stop','higher-start'):
            decision=test_runtime.ApiAndInputTests().decision(packet)
            decision['acceptStartupTargetChange']=copy.deepcopy(plan.STARTUP_TARGET_CHANGE)
            if decision_change=='missing':del decision['acceptStartupTargetChange']
            elif decision_change=='old-stop':decision['acceptStartupTargetChange']['emergencyStops']='disabled'
            else:decision['acceptStartupTargetChange']['to']='all-warning'
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'fixture.json';path.write_text(json.dumps(decision))
                with patch.object(plan,'APPROVAL',path),patch.object(plan,'review',return_value=(plan.sha(packet),packet)):
                    with self.assertRaisesRegex(ValueError,'APPROVAL_INVALID'):plan.authorize()

    def test_eighth_manifest_tampering_fails_before_trusting_inventory_paths(self):
        original=prior_api.digest
        with patch.object(prior_api,'digest',side_effect=lambda path:
                '0'*64 if path==prior_api.EIGHTH_FOLDER/'execution-preservation.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'EIGHTH_API_MANIFEST_CHANGED'):
                prior_api.verify_eighth(plain=plan.build.tools.plain)

    def test_eighth_frozen_helper_tampering_is_detected_without_writing_history(self):
        original=Path.read_bytes
        def changed(path):
            raw=original(path)
            return raw+b'changed' if path==prior_api.EIGHTH_FOLDER/'helpers/containers/model-runtime/first_api.py' else raw
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'EIGHTH_API_FROZEN_HELPER_CHANGED'):
                prior_api.verify_eighth(plain=plan.build.tools.plain)


if __name__=='__main__':unittest.main()
