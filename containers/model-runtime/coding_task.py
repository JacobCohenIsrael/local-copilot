"""One Codex-submitted live Strata code generation -> OpenCode edit -> bounded patch."""
import argparse,base64,copy,functools,hashlib,json,os,shutil,subprocess,sys,threading,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'worker'))
import runtime_plan as p
import first_api
import container_test
import coding_worker
import task_bundle
import bundle_rehearsal
import verify_opencode

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime/strata-coding-1-review'
WORKER=REPO/'.runtime/strata-coding-1-worker'
NINTH=REPO/'.runtime/model-api-startup-warnings-review/9213527ebc1861f5ee83004a9a1393c1b9903d3184fba118453c023efd48cad9'
MANIFEST='129e6a88fe24f9ffab058b7cedea6963989f2959457e43db3e9acbc91783b83a'
REQUEST={**container_test.REQUEST,'messages':[{'role':'user','content':'Set VALUE to 2. Return only the updated code:\nVALUE = 1\n'}],'max_tokens':32}
_original_previous=p.previous
_original_proofs=p.expected_proofs
_active=False

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)

def ninth_proof(verify=False):
    if p.build.tools.sha(NINTH/'execution-preservation.json')!=MANIFEST:raise ValueError('NINTH_MANIFEST_CHANGED')
    manifest=p.read(NINTH/'execution-preservation.json',1048576)
    if p.build.tools.sha(NINTH/'execution-result.json')!=manifest['executionResultSha256']:raise ValueError('NINTH_RESULT_CHANGED')
    result=p.read(NINTH/'execution-result.json')
    if result['status']!='REAL_STRATA_API_ANSWER_CONFIRMED_STOPPED' or not result['allFourHostProcessesExited']:
        raise ValueError('NINTH_SUCCESS_UNCONFIRMED')
    if verify:
        for key in ('attempt','reader','launcher','capacityProbe'):
            record=manifest[key];directory=Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()}!=set(record['files']):
                raise ValueError('NINTH_EVIDENCE_FILE_SET_CHANGED')
            for name,item in record['files'].items():
                file=directory/name;p.build.tools.plain(file)
                if file.stat().st_size!=item['bytes'] or p.build.tools.sha(file)!=item['sha256']:
                    raise ValueError('NINTH_EVIDENCE_CHANGED')
        for name,item in manifest['reviewEvidence'].items():
            file=NINTH/name
            if p.build.tools.sha(file)!=item['sha256']:raise ValueError('NINTH_REVIEW_EVIDENCE_CHANGED')
        old=p.read(NINTH/'review.json')
        for name,expected in old['helperSha256'].items():
            if hashlib.sha256((NINTH/'helpers'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
                raise ValueError('NINTH_FROZEN_HELPER_CHANGED')
    return {'reviewSha256':result['reviewSha256'],'preservationSha256':MANIFEST,
        'resultSha256':manifest['executionResultSha256'],'retainedContainerId':result['containerId'],'previousAttemptReset':False}

def check_task(task):
    original=Path(task['originalDirectory']);source=Path(task['workerInput'])
    if original.parent.parent!=REPO/'.runtime/strata-coding-preparation' or source.parent!=original.parent:
        raise ValueError('CODING_PREPARATION_PATH')
    if task_bundle.collect(task['bundleRunId'])['changedFiles']:raise ValueError('CODING_BUNDLE_CHANGED')
    if (original/'example.py').read_bytes()!=b'VALUE = 1\n' or task['task']!=coding_worker.TASK:
        raise ValueError('CODING_TASK_CHANGED')
    if set(task['workerFiles'])!={x.relative_to(source).as_posix() for x in source.rglob('*') if x.is_file()}:
        raise ValueError('WORKER_FILE_SET_CHANGED')
    for name,digest in task['workerFiles'].items():
        path=source/name;p.build.tools.plain(path)
        if p.build.tools.sha(path)!=digest:raise ValueError('WORKER_INPUT_CHANGED')
    if task['workerFiles']['opencode']!=task_bundle.read_json(HERE.parent/'worker/opencode-lock.json')['binarySha256']:
        raise ValueError('OPENCODE_IDENTITY_CHANGED')

def same_limits(packet):
    old=p.read(NINTH/'review.json')
    if packet['policy']!=old['policy'] or packet['request']!=REQUEST:raise ValueError('CODING_POLICY_OR_REQUEST_CHANGED')
    for key in ('configuration','requestTimingChange','fileAccessChange','startupTargetChange','startupStatusChange',
                'vmEnvelope','settings','sourceLimitation','sourceReviewSha256','runtimeBundle','buildProof',
                'sourceTree','sourcePlan','modelFiles','limitations'):
        if packet[key]!=old[key]:raise ValueError('CODING_UNAPPROVED_LIMIT_OR_INPUT_CHANGED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key]!=old['contract'][key]:raise ValueError('CODING_MODEL_CONTRACT_CHANGED')
    check_task(packet['codingTask'])

def activate():
    global _active
    if _active:return
    _active=True
    p.ROOT=ROOT;p.LIVE=REPO/'.runtime/strata-coding-1-model'
    p.APPROVAL=HERE/'coding-task-1-approval.json'
    p.SCOPE='one-codex-strata-generated-single-file-opencode-edit-live-broker'
    p.REQUEST=copy.deepcopy(REQUEST);p.APPROVAL_WORKER=True
    p.previous=lambda:{**_original_previous(),'ninth':ninth_proof(True)}
    p.expected_proofs=lambda:{**_original_proofs(),'ninth':ninth_proof()}
    p.same_limits=same_limits
    first_api.WATCH_ENTRYPOINT=Path(__file__).resolve()
    first_api.validate_response=functools.partial(container_test.validate_response,maximum_output_tokens=32)

def prepare():
    activate()
    base=REPO/'.runtime/strata-coding-preparation'/uuid.uuid4().hex
    original=base/'original';source=base/'worker-input';original.mkdir(parents=True);source.mkdir()
    (original/'example.py').write_bytes(b'VALUE = 1\n')
    (original/'unselected.txt').write_bytes(b'UNSELECTED SYNTHETIC FILE\n')
    prepared=task_bundle.prepare({'sourceRoot':str(original),'files':['example.py'],'task':coding_worker.TASK})
    artifact=verify_opencode.artifact(REPO/'.runtime/opencode-linux/2.0.26-musl-44f176ba')
    shutil.copyfile(artifact/'staged/opencode',source/'opencode')
    shutil.copyfile(HERE/'coding_worker.py',source/'probe.py')
    shutil.copyfile(original/'example.py',source/'example.py')
    libraries=REPO/'.runtime/opencode-linux/alpine-runtime'
    runtime=task_bundle.read_json(libraries/'runtime.json')
    (source/'libs').mkdir()
    for item in runtime['libraries']:
        path=libraries/'staged'/item['library']
        if p.build.tools.sha(path)!=item['librarySha256']:raise ValueError('PINNED_WORKER_LIBRARY_CHANGED')
        shutil.copyfile(path,source/'libs'/path.name)
    task={'task':coding_worker.TASK,'bundleRunId':prepared['runId'],'originalDirectory':str(original),
        'workerInput':str(source),'workerFiles':{x.relative_to(source).as_posix():p.build.tools.sha(x)
            for x in sorted(source.rglob('*')) if x.is_file()},'workerEnvelope':{'cpus':.5,'memoryMiB':512,
            'swapMiB':0,'tmpMiB':64,'deadlineSeconds':410,'leaseSeconds':2.5,'network':'none','gpu':False},
        'modelCalls':1,'opencodeCalls':2,'maximumModelOutputTokens':32,'nativeToolCallingTested':False}
    folder,packet=p.prepare({'codingTask':task})
    return {'reviewSha256':p.sha(packet),'reviewFile':str(folder/'review.json')}

def worker_args(task):
    name='copilot-strata-coding-1-worker-'+Path(task['workerInput']).parent.name
    source=Path(task['workerInput']);control=WORKER/'control'
    args=['create','--name',name,'--label','local-copilot.kind=opencode-live-strata-edit','--pull=never',
        '--platform','linux/amd64','--runtime','runc','--network','none','--cpus','0.5','--memory','512m',
        '--memory-swap','512m','--pids-limit','64','--read-only','--user','65532:65532',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--log-driver','json-file','--log-opt','max-size=64k',
        '--log-opt','max-file=1','--env','NVIDIA_VISIBLE_DEVICES=void','--env','HOME=/tmp/home',
        '--env','LD_LIBRARY_PATH=/input/libs','--mount',f'type=bind,source={source},target=/input,readonly',
        '--mount',f'type=bind,source={control},target=/bridge,readonly',
        '--entrypoint','python',verify_opencode.IMAGE,'-B','/input/probe.py']
    return name,args

def validate_worker(info,task):
    mounts=info['Mounts'];bridge=[m for m in mounts if m['Destination']=='/bridge']
    if len(bridge)!=1 or bridge[0]['RW'] or bridge[0]['Type']!='bind' or Path(bridge[0]['Source'])!=WORKER/'control':
        raise ValueError('WORKER_BRIDGE_CHANGED')
    checked=copy.deepcopy(info);checked['Mounts']=[m for m in mounts if m['Destination']!='/bridge']
    verify_opencode.validate(checked,worker_args(task)[0],Path(task['workerInput']),'opencode-live-strata-edit')

def read_worker(docker,cid,name,maximum):
    try:raw=docker.call('exec','--user','65532:65532',cid,'/usr/bin/head','-c',str(maximum+1),'/tmp/'+name,timeout=1.5)
    except subprocess.CalledProcessError as error:
        if 'No such file or directory' in (error.stderr or ''):return None
        raise
    if len(raw.encode())>maximum:raise ValueError('WORKER_READ_BUDGET')
    return json.loads(raw)

def run():
    activate()
    if WORKER.exists():raise ValueError('CODING_WORKER_ATTEMPT_CONSUMED')
    permit=p.authorize();task=permit.packet['codingTask'];check_task(task)
    control=WORKER/'control';control.mkdir(parents=True)
    save(WORKER/'attempt.json',{'reviewSha256':permit.review_sha256})
    docker=first_api.guard.base.Docker();cid=None;done=threading.Event();thread_fault=[]
    pulse_path=control/'worker.pulse';first_api.control.pulse(pulse_path,maximum=2048)
    def pulses():
        try:
            while not done.wait(.5):
                first_api.control.pulse(pulse_path,maximum=2048)
                if first_api.state_exists() and first_api.read_state()['phase']=='FAULT':
                    (control/'cancel.worker').touch(exist_ok=True)
        except BaseException as error:
            thread_fault.append(str(error));(control/'cancel.worker').touch(exist_ok=True)
    threading.Thread(target=pulses,daemon=True).start()
    result={'status':'FAULT','adapter':'live-one-file-code-to-edit','reviewSha256':permit.review_sha256,
        'modelToolCallingTested':False,'modelStarted':False,'workerStarted':False,'patch':None}
    original=Path(task['originalDirectory']);fingerprints={x.name:p.build.tools.sha(x) for x in original.iterdir()}
    try:
        name,args=worker_args(task);cid=docker.call(*args,timeout=10).strip()
        if not first_api.guard.re.fullmatch('[0-9a-f]{64}',cid):raise ValueError('WORKER_CONTAINER_ID')
        result['workerContainerId']=cid;save(WORKER/'created-container.json',docker.inspect(cid))
        validate_worker(docker.inspect(cid),task);docker.call('start',cid,timeout=1.5)
        result['workerStarted']=True;end=time.monotonic()+15
        while time.monotonic()<end:
            request=read_worker(docker,cid,'request.json',65536)
            if request is not None:break
            time.sleep(.2)
        else:raise TimeoutError('OPENCODE_FIRST_REQUEST_DEADLINE')
        if (request.get('model')!=REQUEST['model'] or coding_worker.TASK not in json.dumps(request.get('messages',[])) or
                'edit' not in [t.get('function',{}).get('name') for t in request.get('tools',[])]):
            raise ValueError('OPENCODE_REQUEST_MISMATCH')
        save(WORKER/'opencode-request.json',request)
        model=first_api.run();result['modelStarted']=True;result['modelResult']=model
        api=p.read(Path(model['apiResultFile']),20000)
        generated=coding_worker.code_from_response(api['response'])
        if (control/'answer.json').exists():raise ValueError('MODEL_ANSWER_ALREADY_PUBLISHED')
        p.build.tools.base.atomic(control/'answer.json',{'response':api['response'],'responseSha256':p.sha(api['response'])})
        end=time.monotonic()+15
        while time.monotonic()<end:
            worker=read_worker(docker,cid,'result.json',32768)
            if worker is not None:break
            time.sleep(.2)
        else:raise TimeoutError('OPENCODE_APPLY_DEADLINE')
        save(WORKER/'worker-result.json',worker)
        if (worker['status']!='REAL_STRATA_CODE_APPLIED' or worker.get('modelRequests')!=1 or
                worker['answerUsed']['responseSha256']!=p.sha(api['response']) or
                base64.b64decode(worker['outputFiles']['example.py'],validate=True)!=generated):
            raise ValueError('REAL_CODE_LINEAGE_OR_EDIT_FAILED')
        (control/'finish.worker').touch(exist_ok=False)
        exit_code=int(docker.call('wait',cid,timeout=5).strip())
        if exit_code!=0 or thread_fault:raise ValueError('WORKER_EXIT_OR_MONITOR_FAILED')
        validate_worker(docker.inspect(cid),task)
        collected=bundle_rehearsal.import_output(task['bundleRunId'],worker['outputFiles'])
        if collected['changedFiles']!=['example.py']:raise ValueError('EXPECTED_SINGLE_FILE_PATCH')
        result.update(status='REAL_STRATA_CODING_PATCH_FOR_REVIEW',patch=collected['patch'],collected=collected,
            modelResponseSha256=p.sha(api['response']),workerResult=worker,appliedToOriginal=False)
    except BaseException as error:
        result.update(error=first_api.error_record(error,'strata-opencode-integration'),patch=None)
    finally:
        (control/'cancel.worker').touch(exist_ok=True)
        if cid is not None:
            def matcher(client,_):
                info=client.inspect(cid)
                if info is not None and info['Id']!=cid:raise ValueError('WORKER_STOP_ID_CHANGED')
                return info
            stopped=first_api.guard.stop_target(docker,{},cid,matcher=matcher,remove=False)
            result['workerStop']=stopped
            save(WORKER/'stopped-container.json',docker.inspect(cid))
            logs=docker.call('logs',cid,timeout=5)
            if len(logs.encode())<=65536:save(WORKER/'worker-logs.json',{'logs':logs})
            if stopped.get('stopConfirmed') is not True:result.update(status='FAULT',patch=None)
        done.set()
        result['originalUnchanged']=all(p.build.tools.sha(original/name)==digest for name,digest in fingerprints.items())
        if not result['originalUnchanged']:result.update(status='FAULT',patch=None,error='ORIGINAL_CHANGED')
        save(WORKER/'integration-result.json',result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',nargs='?',choices=['prepare','review','run'])
    parser.add_argument('--watch',action='store_true');options=parser.parse_args();activate()
    if options.watch:first_api.watch()
    else:
        result=prepare() if options.command=='prepare' else p.summary() if options.command=='review' else run()
        print(json.dumps(result,indent=2),flush=True)
        if options.command=='run' and result['status']!='REAL_STRATA_CODING_PATCH_FOR_REVIEW':raise SystemExit(3)
