"""Fresh 246-token test with explicitly approved GPU warning 87 / stop 90 C."""
import argparse
import copy
import json
from pathlib import Path

import simple_function_double as prior

p=prior.p
task=prior.task
REPO,HERE=prior.REPO,prior.HERE
ROOT=REPO/'.runtime/strata-fibonacci-gpu90-review'
LIVE=REPO/'.runtime/strata-fibonacci-gpu90-model'
OPERATION=REPO/'.runtime/strata-fibonacci-gpu90-operation'
SCOPE='one-fibonacci-246-input-gpu-warn-above87-stop90-other-limits-unchanged'
FAILED=prior.ROOT/'86755db0f8e6477bfe036a7847be3eca2a49cec831fa9ab3079632e8101d0f06'
FAILED_MANIFEST='f0bd8516a5ace3a5abc33caa5d46ae3ddf2ee10194a198adb145c72a5dad539d'
GPU_CHANGE={'previousStopC':75,'stopC':90,'previousAdvisoryStartupC':60,
            'startupAdvisoryC':87,'warnAboveC':87,'warningComparison':'>',
            'stopComparison':'>=','runtimeWarnings':True,'warningEvidenceRecordsMaximum':1,
            'rawTemperatureReadingsRetained':True,'otherLimitsUnchanged':True}
BaseGate=p.safety.Gate
_active=False


def record_gpu_warning(record):
    claim=p.read(LIVE/'attempt.json')
    if claim['reviewSha256']!=p.read(ROOT/'candidate.json')['reviewSha256']:
        raise ValueError('GPU_WARNING_REVIEW_MISMATCH')
    # One immutable warning receipt. Every subsequent temperature is already
    # retained in bounded raw GPU telemetry; warnings never renew any deadline.
    task.save(LIVE/'sessions'/claim['sessionId']/'gpu-temperature-warning.json',record)
    print('GPU_TEMPERATURE_WARNING '+json.dumps(record),flush=True)


class Gpu90Gate(BaseGate):
    def __init__(self):
        super().__init__()
        self.gpu_warning=None

    def observe(self,cpu,gpu,**kwargs):
        eligible=super().observe(cpu,gpu,**kwargs)
        # Only validated telemetry can produce a warning. GPU_HOT is checked
        # after channel validation, so a first reading at 90 also saves it.
        if self.gpu_warning is None and self.fault in (None,'GPU_HOT') and gpu['gpuTemperatureC']>p.safety.POLICY['gpuWarnC']:
            self.gpu_warning={'code':'GPU_TEMPERATURE_WARNING','warnAboveC':87,'stopAtC':90,
                              'observedC':gpu['gpuTemperatureC'],'recordedAtUnix':gpu['recordedAtUnix'],
                              'fault':False,'deadlinesRenewed':False}
            record_gpu_warning(dict(self.gpu_warning))
        return eligible


def previous_proof(verify=False):
    if p.build.tools.sha(FAILED/'execution-preservation.json')!=FAILED_MANIFEST:
        raise ValueError('GPU75_FAILURE_MANIFEST_CHANGED')
    manifest=p.read(FAILED/'execution-preservation.json',1048576)
    if p.build.tools.sha(FAILED/'execution-result.json')!=manifest['executionResultSha256']:
        raise ValueError('GPU75_FAILURE_RESULT_CHANGED')
    result=p.read(FAILED/'execution-result.json',262144)
    if (result['status']!='FIBONACCI_DOUBLE_INPUT_FAULT_CONFIRMED_STOPPED' or
            result['totalConsumedModelAttempts']!=18 or result['modelState']['fault']['code']!='GPU_HOT' or
            result['independentShutdownConfirmed'] is not True or result['allObservedHostHelpersExited'] is not True or
            result['allFourModelHelpersRecorded'] is not True or result['previousEvidenceVerified'] is not True or
            result['apiResult'] is not None or result['functionPassed'] is not False or
            result['independentModelState']['Running'] or result['independentModelState']['Pid']!=0 or
            result['independentModelState']['ExitCode']!=137 or result['metrics']['gpuTemperatureC']['max']!=75 or
            result['repositoryEdits'] is not False or result['patchApplied'] is not False):
        raise ValueError('GPU75_FAILURE_COMPLETION_CHANGED')
    if p.build.tools.sha(HERE/'simple-function-double-approval.json')!=manifest['reviewEvidence']['owner-approved-decision.json']['sha256']:
        raise ValueError('GPU75_FAILURE_APPROVAL_CHANGED')
    if verify:
        prior.verify_inventory(FAILED,manifest['reviewEvidence'],('execution-preservation.json',))
        for record in [manifest[k] for k in ('operation','launcher','attempt','reader')]+manifest['capacityProbeCandidates']:
            prior.verify_inventory(record['directory'],record['files'])
    return {'gpu75FailurePreservationSha256':FAILED_MANIFEST,'totalConsumedModelAttempts':18,
            'previousApprovalReused':False,'previousAttemptReset':False}


def same_limits(packet):
    old=p.read(FAILED/'review.json',131072)
    expected={**old['policy'],'gpuStartC':87,'gpuWarnC':87,'gpuStopC':90}
    if packet['policy']!=expected or packet.get('gpuTemperatureChange')!=GPU_CHANGE:
        raise ValueError('ONLY_REVIEWED_GPU_TEMPERATURE_CHANGE_ALLOWED')
    if p.safety.Gate is not Gpu90Gate or p.safety.POLICY!=expected:
        raise ValueError('GPU90_MONITOR_POLICY_CHANGED')
    checked=copy.deepcopy(packet);checked['policy']=old['policy']
    prior.same_limits(checked)


def activate():
    global _active
    if _active:return
    prior.activate()
    previous,proofs,prepare_packet=p.previous,p.expected_proofs,p.prepare
    task.ROOT,task.LIVE,task.OPERATION=ROOT,LIVE,OPERATION
    p.ROOT,p.LIVE,p.APPROVAL,p.SCOPE=ROOT,LIVE,HERE/'simple-function-gpu90-approval.json',SCOPE
    p.safety.POLICY={**p.safety.POLICY,'gpuStartC':87,'gpuWarnC':87,'gpuStopC':90}
    p.safety.Gate=Gpu90Gate
    p.previous=lambda:{**previous(),'gpu75Failure':previous_proof(True)}
    p.expected_proofs=lambda:{**proofs(),'gpu75Failure':previous_proof()}
    p.prepare=lambda extra=None:prepare_packet({**(extra or {}),'gpuTemperatureChange':copy.deepcopy(GPU_CHANGE)})
    p.same_limits=same_limits
    task.history.task.coding.first_api.WATCH_ENTRYPOINT=Path(__file__).resolve()
    _active=True


def prepare():
    activate()
    return task.prepare()


def summary():
    activate()
    return task.summary()


def run():
    activate()
    return task.run()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['prepare','review','run'])
    parser.add_argument('--watch',action='store_true');options=parser.parse_args()
    if not options.watch and options.command is None:parser.error('command required')
    activate()
    if options.watch:task.history.task.coding.first_api.watch()
    else:
        result=prepare() if options.command=='prepare' else summary() if options.command=='review' else run()
        print(json.dumps(result,indent=2),flush=True)
        if options.command=='run' and result['status']!='STRATA_SIMPLE_FUNCTION_PASSED':raise SystemExit(3)
