"""Offline application-timeout correction; native safety bounds stay unchanged."""
import copy
import unittest

import container_test
import native_iq_startup
import prior_api
import runtime_plan as plan

SOURCE=plan.REPO/'.runtime/strata-build/1c9c3253/input/source'


class RequestTimingTests(unittest.TestCase):
    def test_only_inner_application_watchdog_changes_and_actual_parser_accepts_75(self):
        old=prior_api.load(prior_api.FOURTH_FOLDER/'review.json')
        new=plan.config()
        self.assertEqual({k:(old['configuration'][k],v) for k,v in new.items()
                          if old['configuration'][k]!=v},{'engine_silence_s':(30,75)})
        result=native_iq_startup.check(new,SOURCE)
        self.assertEqual(result['engineSilenceSeconds'],75)
        packet=copy.deepcopy(old);packet.update(configuration=new,requestTimingChange=plan.REQUEST_TIMING_CHANGE,
            fileAccessChange=plan.FILE_ACCESS_CHANGE,startupTargetChange=plan.STARTUP_TARGET_CHANGE,
            startupStatusChange=plan.STARTUP_CHANGE,
            policy=dict(plan.safety.POLICY))
        plan.same_limits(packet)
        for value in (0,90,91):
            cfg=plan.config();cfg['engine_silence_s']=value
            with self.assertRaisesRegex(ValueError,'BOUNDED_ENGINE_SILENCE'):native_iq_startup.check(cfg,SOURCE)

    def test_independent_90_second_request_deadline_still_wins(self):
        leases=container_test.Leases(0)
        for now in range(90):
            leases.check(now,{'controller.pulse':now+1,'guard.pulse':now+1},request_deadline=90)
        with self.assertRaisesRegex(TimeoutError,'REQUEST_DEADLINE'):
            leases.check(90,{'controller.pulse':91,'guard.pulse':91},request_deadline=90)

    def test_fourth_failure_inventory_is_not_rewritten(self):
        self.assertEqual(prior_api.fourth_proof()['preservationSha256'],
            '9515d7896260b0ac430e636bd2e617bc5d5270a40b848533c7b2f54b93e0573d')
        result=prior_api.load(prior_api.FOURTH_FOLDER/'execution-result.json')
        self.assertTrue(result['modelReady']);self.assertEqual(result['requestsSubmitted'],1)
        self.assertFalse(result['responseSucceeded'])


if __name__=='__main__':unittest.main()
