"""One 246-input-token Fibonacci request; all executed runtime limits retained."""
import argparse
import copy
import json
from pathlib import Path

import simple_function_extended as history

p=history.p
task=history.prior
REPO,HERE=history.REPO,history.HERE
ROOT=REPO/'.runtime/strata-fibonacci-double-review'
LIVE=REPO/'.runtime/strata-fibonacci-double-model'
OPERATION=REPO/'.runtime/strata-fibonacci-double-operation'
SCOPE='one-fibonacci-246-input-16k-context-4k-output-900s-request-1200s-model'
PREVIOUS=REPO/'.runtime/strata-fibonacci-extended-relaunch'
PREVIOUS_MANIFEST='a703fe3c4eafac45adf5ff61590d67f4c637e823b55e68caa6a807872f5b28c1'
CANCELED=history.ROOT/'f49604f6854d0ca84042f6442d9da034abb880a6f60eba2b1640be4892665733'
CANCELED_MANIFEST='9e9858059a5a739e6ac9b71b13a3108e36b0021c006456868e3f6bd5867f8f28'
PROMPT=('Write a Python function fibonacci(n) that returns a list of the first n Fibonacci '
        'numbers, starting with 0, 1. Assume n is a non-negative integer. '
        'For n=0 return []; for n=1 return [0]; for n=7 return [0, 1, 1, 2, 3, 5, 8]. '
        'Each term after the first two is the sum of the two preceding terms; keep both copies of 1. '
        'Treat n as a count, not an upper bound on value or a maximum index. '
        'For n=2 the result is [0, 1]; for n=10 it is [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]. '
        'The caller invokes the function with different values of n, so calls must be independent. '
        'Keep the result as integers in a new list, not an iterator. '
        'Return only the function code, optionally in one Python code fence. '
        'Use standard Python without imports, I/O, examples, or top-level calls. '
        'Do not add other requirements or explanations.')
REQUEST={**task.REQUEST,'messages':[{'role':'user','content':PROMPT}]}
TASK={**task.TASK,'actualPromptTokensExpected':246}
_active=False


def verify_inventory(directory,files,extra=()):
    directory=Path(directory)
    if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()}!=set(files)|set(extra):
        raise ValueError('FIBONACCI_PREVIOUS_FILE_SET_CHANGED')
    for name,item in files.items():
        path=directory/name;p.build.tools.plain(path)
        if path.stat().st_size!=item['bytes'] or p.build.tools.sha(path)!=item['sha256']:
            raise ValueError('FIBONACCI_PREVIOUS_FILE_CHANGED')


def previous_proof(verify=False):
    for directory,digest in ((PREVIOUS,PREVIOUS_MANIFEST),(CANCELED,CANCELED_MANIFEST)):
        if p.build.tools.sha(directory/'execution-preservation.json')!=digest:
            raise ValueError('FIBONACCI_PREVIOUS_MANIFEST_CHANGED')
        manifest=p.read(directory/'execution-preservation.json',1048576)
        if p.build.tools.sha(directory/'execution-result.json')!=manifest['executionResultSha256']:
            raise ValueError('FIBONACCI_PREVIOUS_RESULT_CHANGED')
        if verify:
            verify_inventory(directory,manifest['reviewEvidence'],('execution-preservation.json',))
            if directory==PREVIOUS:
                for record in [manifest[k] for k in ('operation','launcher','attempt','reader')]+manifest['capacityProbeCandidates']:
                    verify_inventory(record['directory'],record['files'])
    result=p.read(PREVIOUS/'execution-result.json',262144)
    if (result['status']!='FIBONACCI_EXTENDED_PASSED_CONFIRMED_STOPPED' or
            result['totalConsumedModelAttempts']!=17 or result['apiResult']['requestsSubmitted']!=1 or
            result['apiResult']['response']['usage']!={'prompt_tokens':123,'completion_tokens':74,'total_tokens':197,
                                                       'prompt_tokens_details':{'cached_tokens':0}} or
            result['functionPassed'] is not True or result['independentShutdownConfirmed'] is not True or
            result['allObservedHostHelpersExited'] is not True or result['allFourModelHelpersRecorded'] is not True or
            result['previousEvidenceVerified'] is not True or result['repositoryEdits'] is not False or
            result['patchApplied'] is not False or result['independentModelState']['Running'] or
            result['independentModelState']['Pid']!=0 or result['independentModelState']['ExitCode']!=0 or
            result['operation']['acceptance']!={'status':'FUNCTION_CASES_PASSED','inputs':[0,1,2,7,10,20]}):
        raise ValueError('FIBONACCI_PREVIOUS_SUCCESS_CHANGED')
    canceled=p.read(CANCELED/'execution-result.json')
    if canceled['modelAttemptClaimed'] is not False or canceled['independentNoStartConfirmed'] is not True:
        raise ValueError('FIBONACCI_CANCELED_LAUNCH_CHANGED')
    approval=PREVIOUS/'owner-approved-decision.json'
    if p.build.tools.sha(HERE/'simple-function-extended-approval.json')!=p.build.tools.sha(approval):
        raise ValueError('FIBONACCI_PREVIOUS_APPROVAL_CHANGED')
    return {'successful123InputManifestSha256':PREVIOUS_MANIFEST,'canceledLaunchManifestSha256':CANCELED_MANIFEST,
            'totalConsumedModelAttempts':17,'previousApprovalReused':False,'previousAttemptReset':False}


def same_limits(packet):
    old=p.read(CANCELED/'review.json',131072)
    for key in ('policy','requestTimingChange','durationChange','configuration','fileAccessChange',
                'startupTargetChange','startupStatusChange','vmEnvelope','settings','modelFiles',
                'sourceLimitation','sourceReviewSha256','runtimeBundle','buildProof','sourceTree',
                'sourcePlan','limitations','controls','modelLargeFileBinding','startupSourceAudit'):
        if packet[key]!=old[key]:raise ValueError('DOUBLE_INPUT_OTHER_LIMIT_CHANGED')
    if packet['request']!=REQUEST or packet['functionTask']!=TASK or 'hostRamReadiness' in packet:
        raise ValueError('DOUBLE_INPUT_TASK_CHANGED')
    if {**old['request'],'messages':REQUEST['messages']}!=REQUEST or {**old['functionTask'],'actualPromptTokensExpected':246}!=TASK:
        raise ValueError('DOUBLE_INPUT_ONLY_PROMPT_CHANGE_ALLOWED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key]!=old['contract'][key]:raise ValueError('DOUBLE_INPUT_CONTAINER_CHANGED')
    api=task.history.task.coding.first_api
    if (p.INPUT_SCRIPTS!=history.SCRIPTS or api.READER_SAMPLES!=1500 or api.GPU_SAMPLE_LIMIT!=1536 or
            api.PULSE_BYTES!=4096 or api.API_RESULT_BYTES!=262144 or api.API_RESULT_RECORD_BYTES!=262144 or
            api.validate_response is not task.guest.validate_response or history.guest.REQUEST_SECONDS!=900 or
            history.guest.MODEL_SECONDS!=1200 or history.guest.LEASE_BYTES!=4096):
        raise ValueError('DOUBLE_INPUT_RUNTIME_COVERAGE_CHANGED')
    inputs=Path(packet['packageDirectory'])/'input'
    if set(packet['inputSha256'])!=set(old['inputSha256']) or {x.name for x in inputs.iterdir()}!=set(old['inputSha256']):
        raise ValueError('DOUBLE_INPUT_FILE_SET_CHANGED')
    if p.read(inputs/'request.json')!=REQUEST or p.read(inputs/'strata.json')!=old['configuration']:
        raise ValueError('DOUBLE_INPUT_BAKED_REQUEST_CHANGED')
    for name in packet['inputSha256']:
        if p.build.tools.sha(inputs/name)!=packet['inputSha256'][name]:raise ValueError('DOUBLE_INPUT_CHANGED')
        if name!='request.json' and packet['inputSha256'][name]!=old['inputSha256'][name]:
            raise ValueError('DOUBLE_INPUT_GUEST_OR_CONFIG_CHANGED')


def activate():
    global _active
    if _active:return
    history.activate()
    previous,proofs=p.previous,p.expected_proofs
    task.ROOT,task.LIVE,task.OPERATION=ROOT,LIVE,OPERATION
    task.REQUEST,task.TASK=copy.deepcopy(REQUEST),copy.deepcopy(TASK)
    p.ROOT,p.LIVE,p.APPROVAL,p.SCOPE=ROOT,LIVE,HERE/'simple-function-double-approval.json',SCOPE
    p.REQUEST=copy.deepcopy(REQUEST)
    p.previous=lambda:{**previous(),'fibonacci123Passed':previous_proof(True)}
    p.expected_proofs=lambda:{**proofs(),'fibonacci123Passed':previous_proof()}
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
