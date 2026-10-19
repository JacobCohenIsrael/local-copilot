"""Pinned-source/replayed-configuration tests; no native engine/model execution."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import native_iq_startup as startup
import prior_api
import runtime_plan as plan

SOURCE=plan.REPO/'.runtime/strata-build/1c9c3253/input/source'


class NativeIqStartupTests(unittest.TestCase):
    def test_recorded_argument_failure_is_reproduced_and_minimal_fix_forwarded(self):
        failed=prior_api.load(prior_api.THIRD_FOLDER/'review.json')['configuration']
        with self.assertRaisesRegex(ValueError,'SPEC_BELOW_TWO'):startup.check(failed,SOURCE)
        fixed=plan.config()
        self.assertEqual({k for k in fixed if fixed[k]!=failed[k]},{'args','engine_silence_s'})
        differences=[(a,b) for a,b in zip(failed['args'],fixed['args']) if a!=b]
        self.assertEqual(differences,[('0','2')]);self.assertEqual(len(failed['args']),len(fixed['args']))
        with patch('subprocess.Popen') as spawn:
            result=startup.check(fixed,SOURCE)
        spawn.assert_not_called()
        self.assertEqual(result['engineCommand'],[fixed['exe'],'--serve',*fixed['args']])
        self.assertFalse(result['mtpEnabled']);self.assertEqual(result['suffixDraft'],0)
        self.assertFalse(result['nativeEngineExecuted']);self.assertFalse(result['modelReadinessProven'])

    def test_missing_duplicate_and_invalid_required_arguments_are_rejected(self):
        for change in ('missing','duplicate','spec-one','prefill-zero'):
            cfg=plan.config();args=cfg['args']
            if change=='missing':del args[args.index('--native'):args.index('--native')+2]
            elif change=='duplicate':args.extend(['--spec','2'])
            elif change=='spec-one':args[args.index('--spec')+1]='1'
            else:args[args.index('--prefill')+1]='0'
            with self.assertRaises(ValueError):startup.check(cfg,SOURCE)

    def test_drafter_and_other_expansion_cannot_hide_behind_spec_two(self):
        for flag in ('--mtp','--lookup-chain','--keep-canonical','--batch','--batch-mtp'):
            cfg=plan.config();cfg['args'].append(flag)
            with self.assertRaisesRegex(ValueError,'MINIMAL_STARTUP_ONLY'):startup.check(cfg,SOURCE)
        cfg=plan.config();cfg['args'][cfg['args'].index('--suffix-draft')+1]='3'
        with self.assertRaisesRegex(ValueError,'MINIMAL_STARTUP_ONLY'):startup.check(cfg,SOURCE)

    def test_source_changes_are_rejected_before_any_upstream_function_execution(self):
        original=Path.read_bytes
        def read(path):return original(path)+b'changed' if path==SOURCE/'src/program/generate.cpp' else original(path)
        with patch.object(Path,'read_bytes',read),patch.object(startup.ast,'parse') as parse:
            with self.assertRaisesRegex(ValueError,'PINNED_SOURCE_CHANGED'):startup.check(plan.config(),SOURCE)
            parse.assert_not_called()

    def test_actual_upstream_builder_cannot_add_unreviewed_arguments(self):
        cfg=copy.deepcopy(plan.config());cfg['vram_elastic']=True
        with self.assertRaisesRegex(ValueError,'UPSTREAM_ARGUMENT_REWRITE'):startup.check(cfg,SOURCE)


if __name__=='__main__':unittest.main()
