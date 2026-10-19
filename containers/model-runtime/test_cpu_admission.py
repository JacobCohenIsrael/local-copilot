"""Startup targets warn; emergency stops unchanged; all execution/hardware are simulated."""
import copy
from pathlib import Path
import unittest

import prior_api
import runtime_plan as plan
import runtime_safety as safety
from test_runtime import cpu,gpu


class AdmissionTests(unittest.TestCase):
    def test_only_startup_enforcement_changes_keep_every_other_policy_value(self):
        old=prior_api.load(prior_api.EIGHTH_FOLDER/'review.json')
        self.assertEqual({k:(old['policy'][k],v) for k,v in safety.POLICY.items()
                          if k in old['policy'] and old['policy'][k]!=v},{})
        self.assertIs(safety.POLICY['startupTargetsWarningsOnly'],True)
        packet=copy.deepcopy(old);packet.update(policy=dict(safety.POLICY),startupTargetChange=plan.STARTUP_TARGET_CHANGE,
                                              startupStatusChange=plan.STARTUP_CHANGE)
        plan.same_limits(packet)
        for key,value in (('baselineSeconds',9),('cpuStopC',99),('freshSeconds',3),('leaseSeconds',3),
                          ('admissionSeconds',120),('cpuQuerySeconds',2),('gpuStartPowerW',50),('stopSeconds',6)):
            bad=copy.deepcopy(packet);bad['policy'][key]=value
            with self.assertRaisesRegex(ValueError,'POLICY_CHANGED'):plan.same_limits(bad)

    def test_all_startup_exceedances_warn_without_resetting_baseline(self):
        gate=safety.Gate()
        for n in range(11):
            eligible=gate.observe(cpu(n+1,1000+n,cpuTemperatureC=96),
                gpu(1000+n,gpuTemperatureC=65,gpuPowerW=45,vramUsedMiB=5000,ramUsedMiB=25000),
                now=n,unix=1000+n,controller_age=0)
            self.assertEqual(eligible,n==10)
            self.assertIsNone(gate.fault)
        self.assertEqual(set(gate.startup_warnings),
            {'cpuTemperatureC','gpuTemperatureC','gpuPowerW','vramUsedMiB','hostFreeRamMiB'})
        gate.model_started=10
        self.assertFalse(gate.observe(cpu(12,1011,cpuTemperatureC=97),gpu(1011),
            now=11,unix=1011,controller_age=0))
        self.assertEqual(gate.fault,'CPU_HOT')

    def test_cpu_budget_is_unchanged_and_does_not_add_core_affinity(self):
        old=prior_api.load(prior_api.EIGHTH_FOLDER/'review.json')
        args,contract=plan.launch(Path('C:/fixture-package'),Path('C:/fixture-engine'),
                                  Path('C:/fixture-runtime'),Path('C:/fixture-source'))
        self.assertEqual(contract['host'],old['contract']['host'])
        self.assertEqual(contract['host']['NanoCpus'],1000000000)
        self.assertEqual(args[args.index('--cpus')+1],'1')
        self.assertFalse(any(arg.startswith('--cpuset') for arg in args))
        self.assertEqual(old['vmEnvelope'],{'cpus':1,'maxMemoryBytes':6*1024**3,'swapBytes':0})


if __name__=='__main__':unittest.main()
