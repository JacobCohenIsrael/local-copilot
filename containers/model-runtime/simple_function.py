"""One direct Strata function experiment; no repository edit or automatic next step."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import context_16k as history
import simple_function_guest as guest
import simple_function_task as task

p = history.p
REPO,HERE = history.REPO,history.HERE
ROOT = REPO/'.runtime/strata-simple-function-review'
LIVE = REPO/'.runtime/strata-simple-function-model'
OPERATION = REPO/'.runtime/strata-simple-function-operation'
SCOPE = 'one-simple-fibonacci-function-16k-context-4k-output-512-input-budget'
REQUEST = {**history.prior.REQUEST,'messages':[{'role':'user','content':task.PROMPT}],'max_tokens':4096}
SCRIPTS = {'api_wrapper.py':'api_wrapper.py','container_test.py':'simple_function_guest.py',
           'container_test_base.py':'container_test.py'}
TASK = {'name':'fibonacci-list','inputBudgetTokens':512,'actualPromptTokensExpected':123,
        'configuredContextTokens':16384,'outputCeilingTokens':4096,'marginTokens':8,
        'apiResultBytes':262144,'codeBytes':32768,'modelCalls':1,'workerContainers':0,
        'evaluation':{'processes':1,'memoryMiB':128,'singleCpu':True,'seconds':2,
                      'cases':[0,1,2,7,10,20],'staticAdmissionFirst':True},
        'promptPadding':False,'outputCeilingMustBeConsumed':False,
        'fullWindowCapacityEstablishedBySuccess':False,'nativeToolCallingTested':False,
        'repositoryEdits':False,'automaticNextAttempt':False,'automaticRetry':False}
SUPERSEDED = history.ROOT/'534020a6c8d4c56480a71a610da3579828a8cfce12a2e5884dff2b9f2a98ec93'
SUPERSEDED_MANIFEST='257531f96c6e818254e5abf35f7f3e81119944bd408dd5f2eb4940cfefc89688'
_active=False


def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as out:json.dump(value,out,indent=2);out.write('\n')


def superseded_proof(verify=False):
    path=SUPERSEDED/'preparation-preservation.json'
    if p.build.tools.sha(path)!=SUPERSEDED_MANIFEST:raise ValueError('SUPERSEDED_REVIEW_CHANGED')
    manifest=p.read(path,1048576)
    if verify:
        if {x.relative_to(SUPERSEDED).as_posix() for x in SUPERSEDED.rglob('*') if x.is_file()}!=set(manifest['files'])|{'preparation-preservation.json'}:
            raise ValueError('SUPERSEDED_FILE_SET_CHANGED')
        for name,item in manifest['files'].items():
            file=SUPERSEDED/name;p.build.tools.plain(file)
            if file.stat().st_size!=item['bytes'] or p.build.tools.sha(file)!=item['sha256']:
                raise ValueError('SUPERSEDED_FILE_CHANGED')
    return {'reviewSha256':manifest['reviewSha256'],'preservationSha256':SUPERSEDED_MANIFEST,
            'status':'SUPERSEDED_UNRUN_NO_APPROVAL_REUSE'}


def same_limits(packet):
    old=p.read(history.PREVIOUS/'review.json',131072)
    for key in ('policy','requestTimingChange','fileAccessChange','startupTargetChange','startupStatusChange',
                'vmEnvelope','settings','modelFiles','sourceLimitation','sourceReviewSha256','runtimeBundle',
                'buildProof','sourceTree','sourcePlan','limitations','controls','modelLargeFileBinding'):
        if packet[key]!=old[key]:raise ValueError('FUNCTION_OTHER_LIMIT_CHANGED')
    if packet['configuration']!=history.larger_context(old['configuration']) or packet['request']!=REQUEST:
        raise ValueError('FUNCTION_CONFIG_OR_REQUEST_CHANGED')
    audit=copy.deepcopy(old['startupSourceAudit']);args=audit['engineCommand']
    args[args.index('--max-context')+1]='16384'
    if packet['startupSourceAudit']!=audit:raise ValueError('FUNCTION_SOURCE_AUDIT_CHANGED')
    if packet.get('functionTask')!=TASK or 'hostRamReadiness' in packet or 'codingTask' in packet:
        raise ValueError('FUNCTION_TASK_CHANGED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key]!=old['contract'][key]:raise ValueError('FUNCTION_CONTAINER_CHANGED')
    if p.INPUT_SCRIPTS!=SCRIPTS:raise ValueError('FUNCTION_GUEST_MAP_CHANGED')
    inputs=Path(packet['packageDirectory'])/'input'
    if set(packet['inputSha256'])!=set(SCRIPTS)|{'request.json','strata.json'} or {x.name for x in inputs.iterdir()}!=set(packet['inputSha256']):
        raise ValueError('FUNCTION_INPUT_SET_CHANGED')
    if p.read(inputs/'request.json')!=REQUEST or p.read(inputs/'strata.json')!=packet['configuration']:
        raise ValueError('FUNCTION_BAKED_INPUT_CHANGED')
    import hashlib
    for name,source in SCRIPTS.items():
        expected=hashlib.sha256((HERE/source).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if packet['inputSha256'][name]!=expected or p.build.tools.sha(inputs/name)!=expected:
            raise ValueError('FUNCTION_GUEST_CHANGED')


def activate():
    global _active
    if _active:return
    # Reuse the last executed scope's safeguards, not the superseded 64-output run.
    history.prior.activate()
    previous,proofs,config=p.previous,p.expected_proofs,p.config
    p.ROOT,p.LIVE,p.APPROVAL,p.SCOPE=ROOT,LIVE,HERE/'simple-function-approval.json',SCOPE
    p.APPROVAL_WORKER=False
    p.REQUEST=REQUEST;p.INPUT_SCRIPTS=dict(SCRIPTS)
    p.config=lambda:history.larger_context(config())
    p.previous=lambda:{**previous(),'ram30Output':history.previous_proof(True),'superseded64Output':superseded_proof(True)}
    p.expected_proofs=lambda:{**proofs(),'ram30Output':history.previous_proof(),'superseded64Output':superseded_proof()}
    p.same_limits=same_limits
    api=history.task.coding.first_api
    api.API_RESULT_BYTES=api.API_RESULT_RECORD_BYTES=guest.RESPONSE_BYTES
    api.validate_response=guest.validate_response
    api.WATCH_ENTRYPOINT=Path(__file__).resolve()
    _active=True


def prepare():
    activate()
    if LIVE.exists() or OPERATION.exists():raise ValueError('FUNCTION_OPERATION_ALREADY_CONSUMED')
    folder,packet=p.prepare({'functionTask':copy.deepcopy(TASK)})
    return {'reviewSha256':p.sha(packet),'reviewFile':str(folder/'review.json'),
            'modelLaunchEnabled':False,'workerLaunchEnabled':False}


def summary():
    activate()
    if OPERATION.exists():return {'status':'ATTEMPT_CONSUMED','operationDirectory':str(OPERATION),'modelLaunchEnabled':False,'workerLaunchEnabled':False}
    return p.summary()


def evaluate_file(code_path,directory,*,process_factory=None):
    import windows_job
    factory=process_factory or windows_job.Process
    result_path=directory/'function-cases.json'
    env={k:v for k,v in os.environ.items() if k.lower() in ('systemroot','windir')}
    env.update(TEMP=str(directory),TMP=str(directory),PATH=str(Path(sys.executable).parent))
    child=factory([sys.executable,'-I','-B',str(HERE/'simple_function_task.py'),'--evaluate',str(code_path),str(result_path)],
                  cwd=directory,env=env,memory_bytes=128*1024**2,processes=1,single_cpu=True)
    timed_out=False
    try:
        save(directory/'evaluation-process.json',{'pid':child.pid,'memoryMiB':128,'processes':1,'singleCpu':True,'seconds':2})
        try:child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            timed_out=True;child.kill();child.wait(timeout=1)
        if child.poll() is None:raise ValueError('EVALUATION_STOP_UNCONFIRMED')
        save(directory/'evaluation-exit.json',{'pid':child.pid,'exitCode':child.returncode,'confirmedExited':True,'timedOut':timed_out})
    finally:
        child.close() # kill-on-close remains enforced even on observation failure.
    if timed_out:raise ValueError('FUNCTION_EVALUATION_TIMEOUT')
    record=p.read(result_path,4096)
    if child.returncode!=0 or record.get('status')!='FUNCTION_CASES_PASSED':raise ValueError('FUNCTION_CASES_FAILED')
    return record


def run():
    activate()
    if OPERATION.exists():raise ValueError('FUNCTION_OPERATION_ALREADY_CONSUMED')
    permit=p.authorize() # Missing or stale approval refuses before any live access.
    OPERATION.mkdir(parents=True,exist_ok=False)
    save(OPERATION/'attempt.json',{'reviewSha256':permit.review_sha256,'approvalSha256':permit.approval_sha256,'automaticRetry':False})
    record={'status':'FUNCTION_TEST_FAULT','reviewSha256':permit.review_sha256,'operationApprovalConsumed':True,
            'patchApplied':False,'repositoryEdits':False,'automaticRetry':False,'workerContainersStarted':0}
    try:
        model=history.task.coding.first_api.run()
        record['apiResultFile']=model['apiResultFile']
        if model['phase']!='COMPLETE' or model['stopConfirmed'] is not True:raise ValueError('MODEL_STOP_REQUIRED_BEFORE_EVALUATION')
        response=p.read(Path(model['apiResultFile']),guest.RESPONSE_BYTES)['response']
        if response['usage']['prompt_tokens']!=TASK['actualPromptTokensExpected']:raise ValueError('FUNCTION_INPUT_TOKEN_COUNT_CHANGED')
        code=task.code_from_response(response)
        path=OPERATION/'fibonacci.py'
        with path.open('x',encoding='utf-8',newline='\n') as out:out.write(code)
        record['codeFile']=str(path)
        record['acceptance']=evaluate_file(path,OPERATION)
        record['status']='STRATA_SIMPLE_FUNCTION_PASSED'
    except BaseException as error:
        record['error']={'type':type(error).__name__,'message':str(error)[:512]}
    save(OPERATION/'result.json',record)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['prepare','review','run'])
    parser.add_argument('--watch',action='store_true');options=parser.parse_args()
    if not options.watch and options.command is None:parser.error('command required')
    activate()
    if options.watch:history.task.coding.first_api.watch()
    else:
        result=prepare() if options.command=='prepare' else summary() if options.command=='review' else run()
        print(json.dumps(result,indent=2),flush=True)
        if options.command=='run' and result['status']!='STRATA_SIMPLE_FUNCTION_PASSED':raise SystemExit(3)
