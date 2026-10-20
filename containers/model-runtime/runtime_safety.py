"""Runtime-only safety proposal and deterministic gate; no implicit policy activation."""
import math
from collections import deque
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'safety'))
import telemetry

GPU_UUID = 'GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d'
SOURCE_LIMITATION = ('ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration '
    'and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; '
    'this is a new scope, not inherited CPU-build approval.')
POLICY = {'cpuStartC':94, 'cpuStopC':97, 'startupTargetsWarningsOnly':True, 'baselineSeconds':10, 'cpuQuerySeconds':1.5,
    'gpuStartC':60, 'gpuStopC':75, 'gpuStartPowerW':40, 'gpuStopPowerW':100,
    'gpuStartVramMiB':4096, 'gpuStopVramMiB':14336, 'ramStopMiB':28672,
    'hostFreeRamStartMiB':8192, 'freshSeconds':2.5, 'leaseSeconds':2.5,
    'gpuQuerySeconds':1, 'modelSeconds':300, 'outerSeconds':410,
    'admissionSeconds':90, 'stopSeconds':5, 'automaticRetry':False}


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def viability_policy(base=None):
    """Owner-approved advisory resources for NEW coding scopes, never old approvals.

    Deadlines/envelopes are inherited; the caller must bind this complete policy
    into its fresh review and activate it in both controller and watchdog.
    """
    return {**(POLICY if base is None else base),
        'resourceThresholdsWarningsOnly':True, 'resourceTrendSeconds':30,
        'cpuStartC':94, 'gpuStartC':87, 'ramStopMiB':30720,
        'cpuStopC':97, 'gpuStopC':90}


def decode_gpu(raw):
    if len(raw)>2*1024**2:raise ValueError('GPU_RESPONSE_BUDGET')
    root=ET.fromstring(raw);gpu=root.find('gpu')
    if gpu is None or gpu.findtext('uuid')!=GPU_UUID or root.findtext('attached_gpus')!='1':
        raise ValueError('GPU_IDENTITY_CHANGED')
    parsed=telemetry.parse_gpu(raw)
    return {'gpuUuid':GPU_UUID,'driver':parsed['identity']['driver'],**parsed['values']}


def snapshot(*,capture=subprocess.run,clock=time.monotonic,unix=time.time):
    started=clock()
    process=capture([telemetry.SMI,'--id=0','-q','-x'],capture_output=True,timeout=1,check=True,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    values=decode_gpu(process.stdout)
    query=clock()-started
    if query>1:raise ValueError('GPU_QUERY_TIMEOUT')
    return {**values,**telemetry.native_windows(),'recordedAtUnix':unix(),'querySeconds':query}


class Gate:
    def __init__(self,policy=None):
        self.policy=POLICY if policy is None else dict(policy)
        self.fault=None;self.cool_since=None;self.last_sequence=0;self.startup_warnings={}
        self.last_cpu=None;self.cpu_received=None;self.last_tick=None;self.model_started=None;self.last_unix=None
        self.resource_trends={};self.resource_warnings={};self._resource_samples={};self._resource_started={}

    def resources(self,cpu,gpu,now):
        """Bounded 30-second observations; no resource trend can renew a deadline."""
        channels=(('cpuTemperatureC',cpu,self.policy['cpuStartC']),
            ('gpuTemperatureC',gpu,self.policy['gpuStartC']),
            ('gpuPowerW',gpu,self.policy['gpuStopPowerW']),
            ('vramUsedMiB',gpu,self.policy['gpuStopVramMiB']),
            ('ramUsedMiB',gpu,self.policy['ramStopMiB']))
        window=self.policy.get('resourceTrendSeconds',30)
        for name,sample,threshold in channels:
            history=self._resource_samples.setdefault(name,deque(maxlen=512))
            self._resource_started.setdefault(name,now)
            stamp=sample['recordedAtUnix'];value=sample[name]
            # The monitor reuses GPU frames while draining CPU frames.
            if not history or history[-1][2]!=stamp:
                history.append((now,value,stamp))
            while history and now-history[0][0]>window:history.popleft()
            values=[x[1] for x in history];span=history[-1][0]-history[0][0]
            delta=values[-1]-values[0]
            self.resource_trends[name]={'current':value,'minimum':min(values),'maximum':max(values),
                'mean':sum(values)/len(values),'delta':delta,'spanSeconds':span,
                'windowSeconds':window,'windowComplete':now-self._resource_started[name]>=window,
                'samples':len(values),'threshold':threshold,'aboveOrAtThreshold':value>=threshold,
                'direction':'rising' if delta>0 else 'falling' if delta<0 else 'steady'}
            if value>=threshold:
                previous=self.resource_warnings.get(name,{})
                self.resource_warnings[name]={'threshold':threshold,
                    'peak':max(value,previous.get('peak',value)),
                    'firstAtUnix':previous.get('firstAtUnix',stamp),'lastAtUnix':stamp,'fault':False}
        for name,sample in (('cpuThermalThrottling',cpu),('gpuThermalThrottling',gpu)):
            if sample.get(name) is True:
                self.resource_warnings[name]={'active':True,'lastAtUnix':sample['recordedAtUnix'],'fault':False}
            elif name in self.resource_warnings:
                self.resource_warnings[name]={**self.resource_warnings[name],'active':False}

    def resource_report(self):
        return {'mode':'warnings-only','windowSeconds':self.policy.get('resourceTrendSeconds',30),
            'trends':dict(self.resource_trends),'warnings':dict(self.resource_warnings),
            'deadlinesRenewed':False}

    def trip(self,reason):self.fault=self.fault or reason;return False

    def observe(self,cpu,gpu,*,now,unix,controller_age,cancelled=False):
        if self.fault:return False
        if not all(finite(v) for v in (now,unix,controller_age)) or controller_age<0 or (
                self.last_tick is not None and (now<self.last_tick or now-self.last_tick>2.5 or
                    abs((unix-self.last_unix)-(now-self.last_tick))>2.5)):
            return self.trip('CLOCK_OR_MONITOR_GAP')
        self.last_tick=now;self.last_unix=unix
        if cancelled:return self.trip('CANCELLED')
        if controller_age>2.5:return self.trip('CONTROLLER_LEASE_EXPIRED')
        if cpu is not None:
            if (cpu.get('synthetic') is not False or cpu.get('validatedCpuSensor') is not False or
                    cpu.get('source')!='ASUS DSTS 0x00120094' or cpu.get('error') or
                    type(cpu.get('version')) is not int or cpu['version']!=1 or
                    type(cpu.get('sequence')) is not int or cpu['sequence']!=self.last_sequence+1):
                return self.trip('CPU_SOURCE_OR_SEQUENCE')
            if not finite(cpu.get('querySeconds')) or not 0<=cpu['querySeconds']<=1.5:
                return self.trip('CPU_QUERY_TIMEOUT')
            self.last_sequence=cpu['sequence'];self.last_cpu=cpu;self.cpu_received=now
        cpu=self.last_cpu
        for sample,query_limit in ((cpu,1.5),(gpu,1)):
            if (not isinstance(sample,dict) or not finite(sample.get('recordedAtUnix')) or
                    not 0<=unix-sample['recordedAtUnix']<=2.5 or
                    not finite(sample.get('querySeconds')) or not 0<=sample['querySeconds']<=query_limit):
                return self.trip('TELEMETRY_STALE_OR_MISSING')
        if now-self.cpu_received>2.5:return self.trip('CPU_FEED_LOST')
        for channel in ('cpuTemperatureC',):
            if not finite(cpu.get(channel)) or not 0<cpu[channel]<=125:return self.trip('CPU_TEMPERATURE_MISSING')
        for channel in ('gpuTemperatureC','gpuPowerW','vramUsedMiB','vramTotalMiB','ramUsedMiB','ramTotalMiB'):
            if not finite(gpu.get(channel)) or gpu[channel]<0:return self.trip('GPU_OR_HOST_CHANNEL_MISSING')
        if gpu.get('gpuUuid')!=GPU_UUID or gpu.get('vramTotalMiB')<16000:return self.trip('GPU_IDENTITY_CHANGED')
        if not 0<gpu['gpuTemperatureC']<=125 or gpu['vramUsedMiB']>gpu['vramTotalMiB'] or gpu['ramUsedMiB']>gpu['ramTotalMiB']:
            return self.trip('GPU_OR_HOST_CHANNEL_INVALID')
        advisory=self.policy.get('resourceThresholdsWarningsOnly',False)
        if type(cpu.get('cpuThermalThrottling')) not in (type(None),bool) or (not advisory and cpu.get('cpuThermalThrottling') is True):
            return self.trip('CPU_THROTTLE_FLAG')
        if type(gpu.get('gpuThermalThrottling')) is not bool or (not advisory and gpu['gpuThermalThrottling']):return self.trip('GPU_THROTTLE_MISSING_OR_ACTIVE')
        if gpu.get('acConnected') is not True:return self.trip('AC_DISCONNECTED_OR_UNKNOWN')
        if advisory:self.resources(cpu,gpu,now)
        else:
            if cpu['cpuTemperatureC']>=self.policy['cpuStopC']:return self.trip('CPU_HOT')
            if gpu['gpuTemperatureC']>=self.policy['gpuStopC']:return self.trip('GPU_HOT')
            if gpu['gpuPowerW']>=self.policy['gpuStopPowerW']:return self.trip('GPU_POWER_HIGH')
            if gpu['vramUsedMiB']>=self.policy['gpuStopVramMiB']:return self.trip('VRAM_HIGH')
            if gpu['ramUsedMiB']>=self.policy['ramStopMiB']:return self.trip('HOST_RAM_HIGH')
        if self.model_started is not None:
            if now-self.model_started>=self.policy['modelSeconds']:return self.trip('MODEL_DEADLINE')
            return True
        if not finite(cpu.get('readerRemainingSeconds')) or cpu['readerRemainingSeconds']<self.policy['modelSeconds']+self.policy['stopSeconds']:
            return self.trip('CPU_READER_COVERAGE')
        # Startup targets are advisory. Require ten seconds of valid, monitored
        # samples, without restarting that window when a target is exceeded.
        for channel,value,target,minimum in (
                ('cpuTemperatureC',cpu['cpuTemperatureC'],self.policy['cpuStartC'],False),
                ('gpuTemperatureC',gpu['gpuTemperatureC'],self.policy['gpuStartC'],False),
                ('gpuPowerW',gpu['gpuPowerW'],self.policy['gpuStartPowerW'],False),
                ('vramUsedMiB',gpu['vramUsedMiB'],self.policy['gpuStartVramMiB'],False),
                ('hostFreeRamMiB',gpu['ramTotalMiB']-gpu['ramUsedMiB'],self.policy['hostFreeRamStartMiB'],True)):
            if value<target if minimum else value>target:
                old=self.startup_warnings.get(channel)
                worst=value if old is None else (min if minimum else max)(old['observed'],value)
                self.startup_warnings[channel]={'target':target,'observed':worst,'minimum':minimum}
        if self.cool_since is None:self.cool_since=now
        return self.cool_since is not None and now-self.cool_since>=10
