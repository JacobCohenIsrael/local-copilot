"""Synthetic offline checks only: no sensor, Docker, model or reader execution."""
import copy
import unittest

import runtime_safety as safety


def cpu(second=0,**changes):
    return {'version':1,'sequence':second+1,'synthetic':False,
        'source':'ASUS DSTS 0x00120094','validatedCpuSensor':False,
        'cpuThermalThrottling':None,'cpuTemperatureC':90,'error':None,
        'querySeconds':.02,'recordedAtUnix':1000+second,
        'readerRemainingSeconds':2000,**changes}


def gpu(second=0,**changes):
    return {'gpuUuid':safety.GPU_UUID,'gpuTemperatureC':55,'gpuPowerW':20,
        'vramUsedMiB':1800,'vramTotalMiB':16384,'gpuThermalThrottling':False,
        'ramUsedMiB':16000,'ramTotalMiB':32768,'acConnected':True,
        'querySeconds':.2,'recordedAtUnix':1000+second,**changes}


class ViabilityPolicyTests(unittest.TestCase):
    def observe(self,gate,second=0,c=None,g=None,**changes):
        return gate.observe(cpu(second,**(c or {})),gpu(second,**(g or {})),
            now=second,unix=1000+second,controller_age=0,**changes)

    def test_profile_does_not_mutate_defaults_or_deadlines(self):
        original=copy.deepcopy(safety.POLICY)
        profile=safety.viability_policy()
        self.assertEqual(safety.POLICY,original)
        self.assertTrue(profile['resourceThresholdsWarningsOnly'])
        for name in ('modelSeconds','outerSeconds','stopSeconds','leaseSeconds','freshSeconds','automaticRetry'):
            self.assertEqual(profile[name],original[name])
        gate=safety.Gate()
        self.observe(gate,c={'cpuTemperatureC':97})
        self.assertEqual(gate.fault,'CPU_HOT')

    def test_all_resource_crossings_including_sustained_pressure_only_warn(self):
        gate=safety.Gate(safety.viability_policy())
        for second in range(61):
            eligible=self.observe(gate,second,c={'cpuTemperatureC':101,'cpuThermalThrottling':True},
                g={'gpuTemperatureC':96,'gpuPowerW':140,'vramUsedMiB':16000,
                   'ramUsedMiB':32768,'gpuThermalThrottling':True})
            self.assertIsNone(gate.fault)
            self.assertEqual(eligible,second>=10)
            if second==10:gate.model_started=10
        self.assertEqual(len(gate.resource_warnings),7)
        self.assertTrue(gate.resource_trends['ramUsedMiB']['windowComplete'])
        self.assertEqual(gate.resource_trends['ramUsedMiB']['spanSeconds'],30)
        self.assertFalse(gate.resource_report()['deadlinesRenewed'])

    def test_spike_then_recovery_is_visible_and_old_spike_leaves_window(self):
        gate=safety.Gate(safety.viability_policy())
        for second in range(33):
            self.observe(gate,second,g={'ramUsedMiB':32000 if second==1 else 16000})
            if second==2:
                self.assertEqual(gate.resource_trends['ramUsedMiB']['maximum'],32000)
                self.assertFalse(gate.resource_trends['ramUsedMiB']['aboveOrAtThreshold'])
        self.assertEqual(gate.resource_trends['ramUsedMiB']['maximum'],16000)
        self.assertEqual(gate.resource_warnings['ramUsedMiB']['peak'],32000)
        self.assertIsNone(gate.fault)

    def test_rising_falling_mean_and_partial_window(self):
        gate=safety.Gate(safety.viability_policy())
        self.observe(gate,0,g={'ramUsedMiB':16000})
        self.observe(gate,1,g={'ramUsedMiB':18000})
        trend=gate.resource_trends['ramUsedMiB']
        self.assertEqual((trend['mean'],trend['delta'],trend['direction']),(17000,2000,'rising'))
        self.assertFalse(trend['windowComplete'])
        self.observe(gate,2,g={'ramUsedMiB':14000})
        self.assertEqual(gate.resource_trends['ramUsedMiB']['direction'],'falling')

    def test_reused_frames_are_not_extra_samples(self):
        gate=safety.Gate(safety.viability_policy())
        self.observe(gate)
        gate.observe(None,gpu(),now=.1,unix=1000.1,controller_age=0)
        self.assertEqual(gate.resource_trends['ramUsedMiB']['samples'],1)
        self.assertEqual(gate.resource_trends['cpuTemperatureC']['samples'],1)

    def test_throttle_recovery_updates_active_state(self):
        gate=safety.Gate(safety.viability_policy())
        self.observe(gate,g={'gpuThermalThrottling':True})
        self.observe(gate,1)
        self.assertFalse(gate.resource_warnings['gpuThermalThrottling']['active'])

    def test_deadline_still_expires_while_resources_warn(self):
        policy=safety.viability_policy();policy['modelSeconds']=2
        gate=safety.Gate(policy);gate.model_started=0
        for second in range(3):self.observe(gate,second,g={'ramUsedMiB':32000})
        self.assertEqual(gate.fault,'MODEL_DEADLINE')
        self.assertFalse(self.observe(gate,3))

    def test_invalid_monitoring_cancellation_and_ac_still_fault(self):
        cases=[({'cpuTemperatureC':float('nan')},{},False,'CPU_TEMPERATURE_MISSING'),
            ({},{'gpuThermalThrottling':None},False,'GPU_THROTTLE_MISSING_OR_ACTIVE'),
            ({},{'ramUsedMiB':40000},False,'GPU_OR_HOST_CHANNEL_INVALID'),
            ({},{'recordedAtUnix':996},False,'TELEMETRY_STALE_OR_MISSING'),
            ({},{'acConnected':False},False,'AC_DISCONNECTED_OR_UNKNOWN'),
            ({},{},True,'CANCELLED')]
        for c,g,cancel,expected in cases:
            with self.subTest(expected=expected):
                gate=safety.Gate(safety.viability_policy())
                self.observe(gate,c=c,g=g,cancelled=cancel)
                self.assertEqual(gate.fault,expected)
        gate=safety.Gate(safety.viability_policy())
        gate.observe(cpu(),gpu(),now=0,unix=1000,controller_age=3)
        self.assertEqual(gate.fault,'CONTROLLER_LEASE_EXPIRED')


if __name__=='__main__':unittest.main()
