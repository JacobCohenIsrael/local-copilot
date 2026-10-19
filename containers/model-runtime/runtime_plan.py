"""Prepare/authorize one model API test. Preparation has no Docker start route."""
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'strata-proposal'))
import build_admission as build
import build_timing
import cpu_feed
import offline_target
import runtime_safety as safety
import prior_api
import native_iq_startup
import startup_handoff
from container_test import REQUEST

ROOT=REPO/'.runtime/model-api-startup-warnings-review'
PACKAGES=REPO/'.runtime/model-api-packages'
LIVE=REPO/'.runtime/model-api-9'
APPROVAL=HERE/'model-api-9-warnings-approval.json'
SCOPE='one-ninth-docker-strata-model-api-test-startup-warnings-emergency-stops-unchanged-no-worker'
STARTUP_CHANGE=startup_handoff.CONTRACT
STARTUP_TARGET_CHANGE={'targets':'cpu-temperature,gpu-temperature,gpu-power,vram,host-free-ram',
    'from':'blocking-ten-second-target-baseline','to':'warnings-with-ten-second-valid-telemetry',
    'emergencyStops':'unchanged-from-eighth-attempt'}
REQUEST_TIMING_CHANGE={'setting':'engine_silence_s','from':30,'to':75,'hardRequestDeadlineSeconds':90}
FILE_ACCESS_CHANGE={'statePublication':'immutable-sequenced-snapshots-no-replacement',
    'stateRead':'single-read-share-read-delete-not-write','maximumStateRecords':16,'maximumStateBytes':16384,
    'parentErrorDetails':'bounded-operation-message-errno-winerror-filenames-traceback',
    'automaticRetries':False,'permissionChanges':False}
APPROVAL_WORKER=False
BUILD_SHA='5201aa43ea96c130e96b1b89cd97c9d913919a86e6f14b748783aaa682005fc5'
BUILT=REPO/'.runtime/cpu-build-timing-review'/BUILD_SHA
RUNTIME=REPO/'.runtime/model-runtime-inputs'
read=build_timing.read
sha=build.sha


def previous():
    first=prior_api.verify(plain=build.tools.plain)
    second=prior_api.verify_second(plain=build.tools.plain)
    third=prior_api.verify_third(plain=build.tools.plain)
    fourth=prior_api.verify_fourth(plain=build.tools.plain)
    fifth=prior_api.verify_fifth(plain=build.tools.plain)
    sixth=prior_api.verify_sixth(plain=build.tools.plain)
    seventh=prior_api.verify_seventh(plain=build.tools.plain)
    eighth=prior_api.verify_eighth(plain=build.tools.plain)
    old=prior_api.load(prior_api.SECOND_FOLDER/'review.json')
    latest=prior_api.load(prior_api.THIRD_FOLDER/'review.json')
    if (sha(prior_api.load(prior_api.FOLDER/'review.json'))!=prior_api.REVIEW_SHA or
            sha(old)!=prior_api.SECOND_SHA or old['recoveryOf']!=first or
            sha(latest)!=prior_api.THIRD_SHA or latest['recoveryOf']!={'first':first,'second':second}):
        raise ValueError('PRIOR_API_PACKET_CHANGED')
    if (sha(prior_api.load(prior_api.FOURTH_FOLDER/'review.json'))!=prior_api.FOURTH_SHA or
            prior_api.load(prior_api.FOURTH_FOLDER/'review.json')['recoveryOf']!={'first':first,'second':second,'third':third}):
        raise ValueError('FOURTH_API_PACKET_CHANGED')
    if prior_api.load(prior_api.FIFTH_FOLDER/'review.json')['recoveryOf']!={'first':first,'second':second,'third':third,'fourth':fourth}:
        raise ValueError('FIFTH_API_PROOF_CHAIN_CHANGED')
    if prior_api.load(prior_api.SIXTH_FOLDER/'review.json')['recoveryOf']!={'first':first,'second':second,'third':third,'fourth':fourth,'fifth':fifth}:
        raise ValueError('SIXTH_API_PROOF_CHAIN_CHANGED')
    if prior_api.load(prior_api.SEVENTH_FOLDER/'review.json')['recoveryOf']!={'first':first,'second':second,'third':third,'fourth':fourth,'fifth':fifth,'sixth':sixth}:
        raise ValueError('SEVENTH_API_PROOF_CHAIN_CHANGED')
    if prior_api.load(prior_api.EIGHTH_FOLDER/'review.json')['recoveryOf']!={'first':first,'second':second,'third':third,'fourth':fourth,'fifth':fifth,'sixth':sixth,'seventh':seventh}:
        raise ValueError('EIGHTH_API_PROOF_CHAIN_CHANGED')
    return {'first':first,'second':second,'third':third,'fourth':fourth,'fifth':fifth,'sixth':sixth,'seventh':seventh,'eighth':eighth}


def same_limits(packet):
    old=prior_api.load(prior_api.EIGHTH_FOLDER/'review.json')
    if (packet['configuration']!=old['configuration'] or
            packet.get('requestTimingChange')!=REQUEST_TIMING_CHANGE or
            packet.get('fileAccessChange')!=FILE_ACCESS_CHANGE or
            packet.get('startupTargetChange')!=STARTUP_TARGET_CHANGE or
            packet.get('startupStatusChange')!=STARTUP_CHANGE):
        raise ValueError('NINTH_API_CHANGE_MISMATCH')
    expected_policy={**old['policy'],'startupTargetsWarningsOnly':True}
    if packet['policy']!=expected_policy:raise ValueError('NINTH_API_POLICY_CHANGED')
    for key in ('request','vmEnvelope','settings','sourceLimitation','sourceReviewSha256',
                'runtimeBundle','buildProof','sourceTree','sourcePlan','modelFiles','limitations'):
        if packet[key]!=old[key]:raise ValueError('NINTH_API_LIMIT_OR_INPUT_CHANGED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key]!=old['contract'][key]:raise ValueError('NINTH_API_CONTRACT_CHANGED')


def identity(path,*,contents=False):
    path=Path(path).absolute();build.tools.plain(path);stat=path.stat()
    result={'path':str(path),'bytes':stat.st_size,'mtimeNs':stat.st_mtime_ns,'fileIdentity':[stat.st_dev,stat.st_ino]}
    if contents:result['sha256']=build.tools.sha(path)
    else:
        with path.open('rb') as stream:result['prefixSha256']=hashlib.sha256(stream.read(16)).hexdigest()
    return result


def model_identities():
    files=[Path('D:/AI/strata-coder-iq1_m.json'),Path('D:/AI/run-coder-iq1_m.bat'),Path('D:/AI/data/expert-profile-coder.bin')]
    pack=Path('D:/Strata-data/packs/coder-iq1_m')
    files+=sorted(p for p in pack.rglob('*') if p.is_file())
    files+=sorted(Path('D:/Strata-data/models/coder-IQ1_M').glob('*.gguf'))
    if len(files)>64 or len([p for p in files if p.suffix=='.gguf'])!=2:raise ValueError('MODEL_FILE_SET')
    return [identity(p,contents=p.stat().st_size<=32*1024**2) for p in files]


def preserved_build():
    packet=read(BUILT/'review.json');manifest=read(BUILT/'execution-preservation.json',1048576)
    if sha(packet)!=BUILD_SHA or manifest['reviewSha256']!=BUILD_SHA:raise ValueError('SUCCESSFUL_BUILD_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe','artifacts'):
        record=manifest[key];directory=Path(record['directory'])
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual!=set(record['files']):raise ValueError('SUCCESSFUL_BUILD_FILE_SET_CHANGED')
        for relative,item in record['files'].items():
            path=directory/relative;build.tools.plain(path)
            if path.stat().st_size!=item['bytes'] or build.tools.sha(path)!=item['sha256']:
                raise ValueError('SUCCESSFUL_BUILD_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path=BUILT/name
        if path.stat().st_size!=item['bytes'] or build.tools.sha(path)!=item['sha256']:
            raise ValueError('SUCCESSFUL_BUILD_REVIEW_EVIDENCE_CHANGED')
    for relative,expected in packet['helperSha256'].items():
        if hashlib.sha256(build.cpu.bounded(BUILT/'helpers'/relative,131072).replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('SUCCESSFUL_BUILD_HELPER_CHANGED')
    result=read(BUILT/'execution-result.json')
    if result['status']!='CPU_BUILD_COMPLETE_ARTIFACTS_EXPORTED' or result['stopConfirmed'] is not True or result['modelRan'] is not False:
        raise ValueError('SUCCESSFUL_BUILD_RESULT_CHANGED')
    if build_timing.previous()!=packet['recoveryOf']:raise ValueError('PRIOR_BUILD_EVIDENCE_CHANGED')
    return {'reviewSha256':BUILD_SHA,'preservationSha256':build.tools.sha(BUILT/'execution-preservation.json'),
            'resultSha256':build.tools.sha(BUILT/'execution-result.json'),'artifactDirectory':result['artifactDirectory']}


def bundle():
    receipt=read(RUNTIME/'bundle-receipt.json',1048576);directory=Path(receipt['directory'])
    if directory!=RUNTIME/'bundle' or receipt['status']!='STAGED_NOT_EXECUTED':raise ValueError('RUNTIME_BUNDLE_IDENTITY')
    if receipt['downloads']!=json.loads((HERE/'runtime-dependencies.lock.json').read_text()):raise ValueError('RUNTIME_DEPENDENCY_LOCK_CHANGED')
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual!=set(receipt['files']):raise ValueError('RUNTIME_BUNDLE_FILE_SET')
    for relative,item in receipt['files'].items():
        path=directory/relative;build.tools.plain(path)
        if path.stat().st_size!=item['bytes'] or build.tools.sha(path)!=item['sha256']:raise ValueError('RUNTIME_BUNDLE_CHANGED')
    return {'directory':str(directory),'receiptSha256':build.tools.sha(RUNTIME/'bundle-receipt.json'),
            'files':len(actual),'bytes':sum(r['bytes'] for r in receipt['files'].values()),'downloads':receipt['downloads']}


def config():
    return {'exe':'/engine/strata','args':['--pack','/models/pack','--native',
        '/models/gguf/Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-00001-of-00002.gguf','--ple-gguf',
        '/models/gguf/Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-00002-of-00002.gguf','--expert-profile','/models/profile.bin',
        '--mmap-experts','--expert-cache','64','--vram-reserve-mib','4096','--prefill','32',
        '--max-context','512','--kv','int8','--spec','2','--suffix-draft','0','--pcie-frac','0.20',
        '--pool-workers','1','--prompt-cache','0','--conversation-cache-mib','0','--ple-io','mmap'],
        'cwd':'/work','tokenizer':'/models/pack/tokenizer','model_name':REQUEST['model'],
        'gpu':0,'reasoning_effort':'none','log':'/work/engine.log','lazy_load':False,'open_browser':False,
        'api_monitor':False,'engine_silence_s':75,'reasoning_close_retry':False,'mcp_servers':{}}


def helpers():
    paths={**build.helpers(),**{p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        for p in HERE.glob('*.py') if not p.name.startswith('test_')}}
    paths['containers/safety/telemetry.py']=hashlib.sha256((HERE.parent/'safety/telemetry.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    return paths


def launch(package,artifact,runtime,source):
    mounts=[(artifact/'files','/engine'),(runtime,'/runtime'),(source,'/source'),(package/'input','/input'),
        (LIVE/'control','/control'),(Path('D:/Strata-data/packs/coder-iq1_m'),'/models/pack'),
        (Path('D:/Strata-data/models/coder-IQ1_M'),'/models/gguf'),(Path('D:/AI/data/expert-profile-coder.bin'),'/models/profile.bin')]
    env={'NVIDIA_VISIBLE_DEVICES':'all','NVIDIA_DRIVER_CAPABILITIES':'compute,utility',
        'CUDA_VISIBLE_DEVICES':'0','PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
        'PYTHONHOME':'/runtime/python','PYTHONPATH':'/runtime/site','LD_LIBRARY_PATH':'/engine:/usr/local/cuda/lib64',
        'STRATA_START_RETRIES':'0','STRATA_ENGINE_READY_S':'180','STRATA_MEMORY_LIMIT_MIB':'4096',
        'STRATA_PLE_PROBE':'1','STRATA_FETCH_THREADS':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
    name='copilot-first-model-api-'+package.name
    host=offline_target.host_profile();host['Tmpfs']={'/work':'rw,noexec,nosuid,nodev,size=67108864,mode=1777',
        '/tmp':'rw,noexec,nosuid,nodev,size=67108864,mode=1777'}
    args=['create','--name',name,'--label','local-copilot.kind=first-strata-api','--label','local-copilot.session='+package.name,
        '--platform','linux/amd64','--pull=never','--runtime','runc','--gpus','all','--cpus','1','--memory','4g',
        '--memory-swap','4g','--pids-limit','128','--read-only','--network','none','--cap-drop','ALL',
        '--security-opt','no-new-privileges','--user','65532:65532','--restart','no','--shm-size','16m',
        '--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=2',
        '--tmpfs','/work:'+host['Tmpfs']['/work'],'--tmpfs','/tmp:'+host['Tmpfs']['/tmp'],
        '--entrypoint','/runtime/python/bin/python3.13','--workdir','/work']
    for key,value in env.items():args+=['--env',key+'='+value]
    for origin,target in mounts:args+=['--mount',f'type=bind,source={origin},target={target},readonly']
    args += [build.image_plan.metadata()['image'],'-B','/input/container_test.py']
    contract={'name':name,'image':build.image_plan.metadata()['image'],'imageId':build.image_plan.metadata()['configDigest'],
        'alternateImageId':build.image_plan.metadata()['image'].split('@',1)[1],
        'entrypoint':['/runtime/python/bin/python3.13'],'command':['-B','/input/container_test.py'],
        'labels':{'local-copilot.kind':'first-strata-api','local-copilot.session':package.name},'environment':env,
        'host':host,'binds':offline_target.binds(mounts),
        'gpuRequests':[{'Driver':'','Count':-1,'DeviceIDs':None,'Capabilities':[['gpu']],'Options':{}}]}
    return args,contract


def prepare(extra=None):
    prior=previous();proof=preserved_build();runtime=bundle();old=read(BUILT/'review.json')
    plan=build.offline.checked_proposal(old['offlineDirectory'],old['offlinePlanSha256'])
    source_tree=build.source_tree(plan)
    if source_tree!=old['sourceTree']:raise ValueError('PINNED_SOURCE_CHANGED')
    package=PACKAGES/uuid.uuid4().hex;inputs=package/'input';inputs.mkdir(parents=True)
    for name in ('api_wrapper.py','container_test.py'):(inputs/name).write_bytes((HERE/name).read_bytes().replace(b'\r\n',b'\n'))
    build.tools.base.atomic(inputs/'strata.json',config())
    build.tools.base.atomic(inputs/'request.json',REQUEST)
    args,contract=launch(package,Path(proof['artifactDirectory']),Path(runtime['directory']),Path(plan['sourcePackage'])/'input/source')
    packet={'version':1,'status':'MODEL_API_READY_FOR_APPROVAL','scope':SCOPE,'maximumAttempts':1,
        'modelLaunchEnabled':False,'buildEnabled':False,'imageDownloadEnabled':False,'imageImportEnabled':False,
        'workerLaunchEnabled':False,'policy':safety.POLICY,'requestTimingChange':REQUEST_TIMING_CHANGE,
        'fileAccessChange':FILE_ACCESS_CHANGE,
        'startupTargetChange':STARTUP_TARGET_CHANGE,
        'startupStatusChange':STARTUP_CHANGE,
        'startupSourceAudit':native_iq_startup.check(config(),Path(plan['sourcePackage'])/'input/source'),
        'sourceLimitation':safety.SOURCE_LIMITATION,'recoveryOf':prior,
        'sourceReviewSha256':sha(build.cpu.report()),'controls':{'source':'ASUS DSTS 0x00120094'},
        'buildProof':proof,'sourceTree':source_tree,'sourcePlan':{'directory':old['offlineDirectory'],'sha256':old['offlinePlanSha256']},
        'runtimeBundle':runtime,'modelFiles':model_identities(),'modelLargeFileBinding':'identity,size,mtime,prefix16; no full model hash',
        'configuration':config(),'request':REQUEST,'packageDirectory':str(package),
        'inputSha256':{p.name:build.tools.sha(p) for p in inputs.iterdir()},'createArgs':args,'contract':contract,
        'preparationObservation':{'gpuJsonSha256':build.tools.sha(RUNTIME/'gpu-availability.json'),
            'gpuXmlSha256':build.tools.sha(RUNTIME/'gpu-availability.xml'),'observationOnly':True},
        'helperSha256':helpers(),'liveNamespace':str(LIVE),
        'settings':{'wslSha256':build.tools.sha(Path.home()/'.wslconfig'),
            'desktopSha256':build.tools.sha(Path.home()/'AppData/Roaming/Docker/settings-store.json')},
        'vmEnvelope':{'cpus':1,'maxMemoryBytes':6*1024**3,'swapBytes':0},
        'limitations':['Memory fit and Linux/GPU compatibility are unproven; OOM/time/guard failures end this one attempt.',
            'GPU power/VRAM limits are monitored stop thresholds, not hard GPU quotas or hardware power settings.',
            'Driver/host/daemon/suspend failure can prevent software stopping; shared-Docker cancellation limitations remain.',
            'Existing large model file contents are not fully hashed; read-only mounts and metadata checks cannot exclude same-metadata external mutation.']}
    if extra:
        if set(extra)&set(packet):raise ValueError('EXTRA_PACKET_FIELD_COLLISION')
        packet.update(extra)
    same_limits(packet)
    digest=sha(packet);folder=ROOT/digest;folder.mkdir(parents=True,exist_ok=False)
    build.tools.base.atomic(folder/'review.json',packet)
    build.tools.base.atomic(ROOT/'candidate.json',{'reviewSha256':digest})
    for relative,expected in packet['helperSha256'].items():
        raw=(REPO/relative).read_bytes().replace(b'\r\n',b'\n')
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('PREPARED_HELPER_RACE')
        target=folder/'helpers'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return folder,packet


def expected_proofs():
    return {'first':prior_api.proof(),'second':prior_api.second_proof(),'third':prior_api.third_proof(),
        'fourth':prior_api.fourth_proof(),'fifth':prior_api.fifth_proof(),'sixth':prior_api.sixth_proof(),
        'seventh':prior_api.seventh_proof(),'eighth':prior_api.eighth_proof()}


def review():
    digest=read(ROOT/'candidate.json',4096)['reviewSha256']
    if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('MODEL_API_REVIEW_ID')
    packet=read(ROOT/digest/'review.json',131072)
    source_plan=build.offline.checked_proposal(packet['sourcePlan']['directory'],packet['sourcePlan']['sha256'])
    expected_args,expected_contract=launch(Path(packet['packageDirectory']),Path(packet['buildProof']['artifactDirectory']),
        Path(packet['runtimeBundle']['directory']),Path(source_plan['sourcePackage'])/'input/source')
    if (sha(packet)!=digest or packet['scope']!=SCOPE or packet['policy']!=safety.POLICY or
            packet['status']!='MODEL_API_READY_FOR_APPROVAL' or packet['createArgs']!=expected_args or
            sha(packet['contract'])!=sha(expected_contract) or packet['sourceLimitation']!=safety.SOURCE_LIMITATION or
            packet['sourceReviewSha256']!=sha(build.cpu.report()) or type(packet['maximumAttempts']) is not int or
            packet['runtimeBundle']['downloads']!=json.loads((HERE/'runtime-dependencies.lock.json').read_text()) or
            packet['helperSha256']!=helpers() or packet['configuration']!=config() or packet['request']!=REQUEST or
            packet['liveNamespace']!=str(LIVE) or packet['maximumAttempts']!=1 or
            any(packet[key] is not False for key in ('modelLaunchEnabled','buildEnabled','imageDownloadEnabled','imageImportEnabled','workerLaunchEnabled'))):
        raise ValueError('MODEL_API_REVIEW_STALE')
    for name,expected in packet['inputSha256'].items():
        if build.tools.sha(Path(packet['packageDirectory'])/'input'/name)!=expected:raise ValueError('MODEL_API_INPUT_CHANGED')
    if packet.get('recoveryOf')!=expected_proofs():
        raise ValueError('PRIOR_API_PROOF_CHANGED')
    if packet.get('startupSourceAudit')!=native_iq_startup.check(config(),Path(source_plan['sourcePackage'])/'input/source'):
        raise ValueError('NATIVE_IQ_SOURCE_AUDIT_CHANGED')
    same_limits(packet)
    return digest,packet


class Permit(build.Permit):
    @property
    def reader_contract(self):return build_timing.READER,build_timing.READER_SHA
    def qualify(self,frame):
        if (frame.get('synthetic') is not False or frame.get('validatedCpuSensor') is not False or
                frame.get('source')!='ASUS DSTS 0x00120094' or frame.get('cpuThermalThrottling') is not None):
            raise ValueError('RUNTIME_CPU_CHANNEL_CHANGED')
        return dict(frame) # Scoped acceptance never claims raw validation.


def authorize():
    if not APPROVAL.exists():raise ValueError('FIRST_MODEL_API_NOT_APPROVED')
    digest,packet=review();decision=read(APPROVAL,16384)
    if (decision.get('status')!='owner-approved-one-model-api-test' or type(decision.get('version')) is not int or decision['version']!=1 or
            decision.get('scope')!=SCOPE or decision.get('reviewSha256')!=digest or
            decision.get('acceptRequestTimingChange')!=REQUEST_TIMING_CHANGE or
            decision.get('acceptFileAccessChange')!=FILE_ACCESS_CHANGE or
            decision.get('acceptStartupTargetChange')!=STARTUP_TARGET_CHANGE or
            decision.get('acceptStartupStatusChange')!=STARTUP_CHANGE or
            decision.get('acceptPolicySha256')!=sha(safety.POLICY) or decision.get('acceptSourceLimitation')!=safety.SOURCE_LIMITATION or
            decision.get('acceptSourceReviewSha256')!=packet['sourceReviewSha256'] or
            decision.get('acceptLimitations')!=packet['limitations'] or decision.get('acceptRetainedStoppedContainer') is not True or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts']!=1 or
            decision.get('modelLaunchEnabled') is not True or decision.get('synthetic') is not False or
            decision.get('workerLaunchEnabled') is not APPROVAL_WORKER or
            any(decision.get(k) is not False for k in ('buildEnabled','imageDownloadEnabled','imageImportEnabled')) or
            not isinstance(decision.get('ownerMessage'),str) or not decision['ownerMessage'].strip()):
        raise ValueError('FIRST_MODEL_API_APPROVAL_INVALID')
    return Permit(digest,build.encoded(packet).decode(),sha(decision))


def verify_inputs(packet):
    if previous()!=packet['recoveryOf']:raise ValueError('PRIOR_API_EVIDENCE_CHANGED')
    if preserved_build()!=packet['buildProof'] or bundle()!=packet['runtimeBundle'] or model_identities()!=packet['modelFiles']:
        raise ValueError('MODEL_API_INPUT_IDENTITY_CHANGED')
    old=packet['sourcePlan'];plan=build.offline.checked_proposal(old['directory'],old['sha256'])
    if build.source_tree(plan)!=packet['sourceTree']:raise ValueError('MODEL_API_SOURCE_CHANGED')
    if (build.tools.sha(Path.home()/'.wslconfig')!=packet['settings']['wslSha256'] or
        build.tools.sha(Path.home()/'AppData/Roaming/Docker/settings-store.json')!=packet['settings']['desktopSha256']):
        raise ValueError('MODEL_API_MACHINE_SETTINGS_CHANGED')


def summary():
    try:digest,packet=review()
    except (OSError,ValueError,KeyError):return {'status':'NOT_PREPARED_OR_STALE','modelLaunchEnabled':False}
    return {'status':'ATTEMPT_CONSUMED' if (LIVE/'attempt.json').exists() else packet['status'],
        'reviewSha256':digest,'reviewFile':str(ROOT/digest/'review.json'),'approvalExists':APPROVAL.exists(),
        'modelLaunchEnabled':False,'workerLaunchEnabled':False}


def build_summary():
    """Recorded progress, never launch authority or a fresh runtime check."""
    try:
        result=read(BUILT/'execution-result.json');manifest=read(BUILT/'execution-preservation.json',1048576)
        if (build.tools.sha(BUILT/'execution-result.json')!=manifest['executionResultSha256'] or
                result['reviewSha256']!=BUILD_SHA or result['status']!='CPU_BUILD_COMPLETE_ARTIFACTS_EXPORTED' or
                result['stopConfirmed'] is not True or result['containerExitCode']!=0):
            raise ValueError('RECORDED_BUILD_UNCONFIRMED')
        return {'status':'COMPLETE_RECORDED','artifactDirectory':result['artifactDirectory'],'runtimeApprovalGranted':False}
    except (OSError,ValueError,KeyError):return {'status':'UNCONFIRMED','runtimeApprovalGranted':False}
