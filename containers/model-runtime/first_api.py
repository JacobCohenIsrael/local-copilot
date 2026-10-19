"""One approval-gated GPU model/API attempt; independent host and guest leases."""
import argparse
import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import uuid

import runtime_plan as plan
import runtime_safety as safety
from container_test import validate_response
import build_diagnostics
import controller_session as control
import cpu_feed
import runtime_record_io
import startup_handoff

guard=plan.build.guard
WATCH_ENTRYPOINT=Path(__file__).resolve()


@dataclass(frozen=True)
class Target:
    container_id:str
    contract_json:str

    def inspect(self,docker):
        info=docker.inspect(self.container_id)
        if info is None:return None
        expected=json.loads(self.contract_json);cfg=info['Config'];host=info['HostConfig']
        binds=sorted((r['Source'].replace('\\','/').lower(),r['Destination'],r['RW']) for r in info['Mounts'] if r['Type']=='bind')
        requests=host.get('DeviceRequests') or []
        gpu_ok=(len(requests)==1 and requests[0].get('Driver') in ('','nvidia') and requests[0].get('Count')==-1 and
            not requests[0].get('DeviceIDs') and requests[0].get('Capabilities')==[['gpu']] and not requests[0].get('Options'))
        valid=(info['Id']==self.container_id and info['Name']=='/'+expected['name'] and
            info.get('Image') in (expected['imageId'],expected['alternateImageId']) and cfg['Image']==expected['image'] and
            cfg['User']=='65532:65532' and cfg['WorkingDir']=='/work' and cfg['Entrypoint']==expected['entrypoint'] and
            cfg['Cmd']==expected['command'] and all(cfg.get('Labels',{}).get(k)==v for k,v in expected['labels'].items()) and
            all(k+'='+v in cfg.get('Env',[]) for k,v in expected['environment'].items()) and
            all(host.get(k)==v for k,v in expected['host'].items()) and gpu_ok and
            host['RestartPolicy']['Name']=='no' and set(host.get('CapDrop') or [])=={'ALL'} and not host.get('CapAdd') and
            set(host.get('SecurityOpt') or [])=={'no-new-privileges'} and not host.get('Devices') and
            not host.get('DeviceCgroupRules') and not host.get('PortBindings') and not host.get('PublishAllPorts') and
            not host.get('GroupAdd') and not host.get('PidMode') and not host.get('UTSMode') and host.get('IpcMode')=='private' and
            not host.get('Binds') and not host.get('Ulimits') and binds==[tuple(r) for r in expected['binds']] and
            all(r['Type']=='bind' or (r['Type']=='tmpfs' and r['Destination'] in expected['host']['Tmpfs']) for r in info['Mounts']))
        if not valid:raise ValueError('MODEL_CONTAINER_CONTRACT_CHANGED')
        return info

    def matcher(self,docker,_):return self.inspect(docker)

    def stop_matcher(self,docker,_):
        # Resource/isolation drift must not prevent ending our originally
        # created container. An immutable Docker ID cannot name a replacement.
        info=docker.inspect(self.container_id)
        if info is not None and info['Id']!=self.container_id:raise ValueError('MODEL_STOP_ID_CHANGED')
        return info


def stop(docker,target,*,started=None):
    return guard.stop_target(docker,{},target.container_id,matcher=target.stop_matcher,remove=False,started=started)


def target(packet,container_id):
    if not guard.re.fullmatch('[0-9a-f]{64}',container_id):raise ValueError('MODEL_CONTAINER_ID')
    return Target(container_id,json.dumps(packet['contract'],sort_keys=True))


def state_save(state):runtime_record_io.publish(plan.LIVE,state)


def read_state():return runtime_record_io.latest(plan.LIVE)


def state_exists():return runtime_record_io.exists(plan.LIVE)


def error_record(error,operation):
    from first_build import parent_error_record
    record=parent_error_record(error)
    record.update(operation=operation,reason=str(error)[:1024],
        traceback=[{'file':Path(item.filename).name,'line':item.lineno,'function':item.name}
                   for item in traceback.extract_tb(error.__traceback__,limit=8)])
    for key in ('errno','winerror','filename','filename2'):
        value=getattr(error,key,None)
        if value is not None:record[key]=value if isinstance(value,int) else str(value)[:512]
    return record


def fail(state,reason,docker,owned):
    if state.get('fault'):return state
    started=time.monotonic();state.update(phase='FAULT',fault={'code':reason})
    try:state_save(state)
    finally:
        state.update(stop(docker,owned,started=started));state_save(state)
    return state


def watch():
    permit=plan.authorize();packet=permit.packet
    claim=plan.read(plan.LIVE/'attempt.json')
    if claim['reviewSha256']!=permit.review_sha256:raise ValueError('MODEL_WATCH_CLAIM_CHANGED')
    directory=plan.LIVE/'sessions'/claim['sessionId'];request=plan.read(directory/'target.json')
    owned=target(packet,request['containerId']);docker=guard.base.Docker()
    state={'version':1,'phase':'WAITING_BASELINE','fault':None,'containerId':owned.container_id,
        'sessionId':claim['sessionId'],'reviewSha256':permit.review_sha256,'modelLaunchEnabled':True,
        'workerLaunchEnabled':False,'stopConfirmed':False,'cleanupComplete':False,'cpuReaderDirectory':request['readerDirectory']}
    feed=cpu_feed.Feed(Path(request['readerDirectory']),source_permit=permit)
    gate=safety.Gate();started=time.monotonic();latest_gpu=None;next_gpu=next_guard=0;gpu_sequence=0
    startup=startup_handoff.Handoff(owned.container_id,permit.review_sha256)
    with guard.base.lock(plan.LIVE/'guard-lock'):
        if state_exists() or (plan.LIVE/'state.json').exists():raise ValueError('MODEL_WATCH_STATE_ALREADY_EXISTS')
        try:
            owned.inspect(docker);feed.start_reader(samples=480)
            guard.base.atomic(directory/'reader-process.json',{'pid':feed.process.pid,'ownedByWatchdogPid':os.getpid()})
            state_save(state);lease=control.Pulse(plan.LIVE/'control/controller.pulse',maximum=2048)
            while state['phase'] not in ('FAULT','COMPLETE'):
                now=time.monotonic()
                if now-started>=410:fail(state,'SESSION_DEADLINE',docker,owned);break
                if time.monotonic()>=next_gpu:
                    latest_gpu=safety.snapshot();next_gpu=time.monotonic()+1;gpu_sequence+=1
                    if gpu_sequence>512:raise ValueError('GPU_SAMPLE_BUDGET')
                    guard.base.atomic(directory/f'gpu-{gpu_sequence:04d}.json',latest_gpu)
                cpu=feed.poll()
                if cpu is None and gate.last_cpu is None and now-started<=5:
                    time.sleep(.05);continue # No model can start before baseline.
                eligible=gate.observe(cpu,latest_gpu,now=time.monotonic(),unix=time.time(),controller_age=lease.age(),
                    cancelled=(plan.LIVE/'cancel.request').exists())
                # Drain a small publication backlog, checking EVERY CPU frame:
                # a hot frame cannot be skipped by a later cooler value.
                for _ in range(7):
                    if gate.fault:break
                    cpu=feed.poll()
                    if cpu is None:break
                    eligible=gate.observe(cpu,latest_gpu,now=time.monotonic(),unix=time.time(),controller_age=lease.age())
                if gate.fault:fail(state,gate.fault,docker,owned);break
                if (plan.LIVE/'api.failure').exists():fail(state,'API_TEST_FAILED',docker,owned);break
                previous=state['phase']
                if previous=='WAITING_BASELINE':
                    if time.monotonic()-started>90:fail(state,'BASELINE_NOT_MET',docker,owned);break
                    if eligible:
                        state['phase']='ARMED'
                        state['startupWarnings']=dict(gate.startup_warnings)
                pending=False
                if previous=='ARMED':
                    receipt_path=plan.LIVE/'control/start-result.json'
                    receipt=runtime_record_io.read_json(receipt_path) if receipt_path.exists() else None
                    pending=startup.pending(time.monotonic(),receipt)
                # The parent may be inside the existing 1.5-second Docker start
                # call. Do not compete for status until it returns. Telemetry,
                # leases and every fault above still run on every iteration.
                if pending:
                    if time.monotonic()>=next_guard:
                        control.pulse(plan.LIVE/'control/guard.pulse',maximum=2048);next_guard=time.monotonic()+.5
                    time.sleep(.1);continue
                info=owned.inspect(guard.DeadlineDocker(docker,time.monotonic()+1,time.monotonic))
                if info is None:fail(state,'MODEL_CONTAINER_MISSING',docker,owned);break
                if info['State'].get('OOMKilled'):fail(state,'MODEL_OOM',docker,owned);break
                if info['State']['Running']:
                    if previous=='WAITING_BASELINE':fail(state,'MODEL_STARTED_BEFORE_ADMISSION',docker,owned);break
                    if gate.model_started is None:
                        # Count the 300-second host lifetime from before start,
                        # never from a later successful status observation.
                        gate.model_started=startup.granted_at;state['phase']='RUNNING'
                elif info['State'].get('Status')!='created':
                    saved=directory/'api-result.json'
                    if (plan.LIVE/'control/finish.request').exists() and saved.exists() and info['State']['ExitCode']==0:
                        api=plan.read(saved,20000)
                        if api.get('status')!='REAL_STRATA_API_ANSWER':raise ValueError('API_RESULT_NOT_SUCCESS')
                        validate_response(api['response']);state.update(stop(docker,owned))
                        state['phase']='COMPLETE' if state['stopConfirmed'] else 'FAULT'
                        if state['phase']=='FAULT':state['fault']={'code':'STOP_UNCONFIRMED'}
                        state_save(state);break
                    fail(state,'UNEXPECTED_MODEL_CONTAINER_EXIT',docker,owned);break
                elif previous=='ARMED' and startup.completed:
                    fail(state,'MODEL_START_RETURNED_NOT_RUNNING',docker,owned);break
                if state['phase']!=previous:
                    if state['phase']=='ARMED':startup.grant(time.monotonic())
                    state_save(state)
                if time.monotonic()>=next_guard:
                    control.pulse(plan.LIVE/'control/guard.pulse',maximum=2048);next_guard=time.monotonic()+.5
                time.sleep(.1)
        except BaseException as error:
            state['watchError']=error_record(error,'watch_status_or_start_handoff')
            if isinstance(error,cpu_feed.FeedError):state['monitorError']=cpu_feed.error_record(feed,error)
            fail(state,'MODEL_WATCH_ERROR',docker,owned)
        finally:
            try:
                if state['phase'] not in ('COMPLETE','FAULT'):fail(state,'WATCH_INTERRUPTED',docker,owned)
            finally:
                try:feed.close()
                except BaseException as error:
                    state.update(phase='FAULT',fault=state.get('fault') or {'code':'CPU_READER_STOP_UNCONFIRMED'},
                        readerStopError=type(error).__name__);state_save(state)
                    raise
                finally:guard.base.atomic(directory/'guard-result.json',state)


def read_result(docker,owned):
    try:
        raw=docker.call('exec','--user','65532:65532',owned.container_id,
            '/usr/bin/head','-c','16385','/work/result.json',timeout=1.5)
    except subprocess.CalledProcessError as error:
        if 'No such file or directory' in (error.stderr or ''):return None
        info=owned.inspect(docker)
        if info is not None and not info['State']['Running']:return None
        raise
    if len(raw.encode())>16384:raise ValueError('API_RESULT_BUDGET')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('API_RESULT_SHAPE')
    return result


def run():
    permit=plan.authorize() # Absent approval refuses before live access.
    if plan.LIVE.exists() and any(p.name!='controller-lock' for p in plan.LIVE.iterdir()):raise ValueError('MODEL_API_ATTEMPT_CONSUMED')
    if os.name!='nt' or not ctypes.windll.shell32.IsUserAnAdmin():raise ValueError('ADMINISTRATOR_REQUIRED_FOR_CPU_SOURCE')
    packet=permit.packet;plan.verify_inputs(packet);docker=guard.base.Docker()
    plan.build.image_ready(docker,{'image':plan.build.image_plan.metadata()})
    plan.build.vm_ready(docker,{'proposedVmEnvelope':{'logicalProcessors':1,'maximumReportedMemoryBytes':6*1024**3}})
    gpu=safety.snapshot()
    if not str(gpu['driver']).split('.')[0].isdigit() or int(gpu['driver'].split('.')[0])<580:raise ValueError('CUDA_DRIVER_VERSION')
    # Reuse the existing tiny no-GPU capacity/swap probe within this approved operation.
    import probe_image_storage
    probe=probe_image_storage.probe();capacity=plan.read(probe/'result.json')
    if capacity.get('guestSwapTotalBytes')!=0:raise ValueError('WSL_SWAP_CHANGED')
    if not plan.build.image_plan.capacity(capacity,plan.build.image_plan.storage_budget(plan.build.image_plan.metadata()))['withinProposedBudgetAtProbe']:
        raise ValueError('MODEL_RUNTIME_DISK_CAPACITY')
    with guard.base.lock(plan.LIVE/'controller-lock'):
        if (plan.LIVE/'attempt.json').exists():raise ValueError('MODEL_API_ATTEMPT_CONSUMED')
        directory=plan.LIVE/'sessions'/uuid.uuid4().hex;directory.mkdir(parents=True)
        with (plan.LIVE/'attempt.json').open('x',encoding='utf-8') as stream:
            json.dump({'sessionId':directory.name,'reviewSha256':permit.review_sha256},stream)
        (plan.LIVE/'control').mkdir()
        owned=watchdog=None;parent_error=None;operation='create_container'
        try:
            container_id=docker.call(*packet['createArgs'],timeout=10).strip();owned=target(packet,container_id)
            operation='publish_owned_target'
            guard.base.atomic(directory/'target.json',{'containerId':container_id,'readerDirectory':str(cpu_feed.ROOT/uuid.uuid4().hex)})
            operation='inspect_created_container'
            info=owned.inspect(docker);guard.base.atomic(directory/'created-container.json',info)
            operation='initial_controller_pulse'
            control.pulse(plan.LIVE/'control/controller.pulse',maximum=2048)
            operation='start_watchdog'
            with (directory/'watch.log').open('xb') as output:
                watchdog=subprocess.Popen([sys.executable,'-B','-E','-s',str(WATCH_ENTRYPOINT),'--watch'],
                    stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                operation='publish_owned_processes'
                guard.base.atomic(directory/'host-processes.json',{'parentPid':os.getpid(),'watchdogPid':watchdog.pid})
                lease=control.Pulse(plan.LIVE/'control/guard.pulse',maximum=2048)
                end=time.monotonic()+410;started=False;next_pulse=next_result=0;claimed_result=False
                while time.monotonic()<end:
                    now=time.monotonic()
                    operation='controller_pulse'
                    if now>=next_pulse:control.pulse(plan.LIVE/'control/controller.pulse',maximum=2048);next_pulse=now+.5
                    operation='read_watch_state'
                    state=read_state() if state_exists() else None
                    operation='poll_watchdog'
                    if watchdog.poll() is not None:
                        operation='read_terminal_watch_state'
                        state=read_state() if state_exists() else None
                        if state is None or state['phase'] not in ('FAULT','COMPLETE'):raise ValueError('MODEL_WATCH_DIED')
                        break
                    operation='guard_lease'
                    if lease.path.exists() and lease.age()>2.5:raise ValueError('MODEL_GUARD_LEASE_LOST')
                    if state and state['phase']=='ARMED' and not started:
                        if not lease.changed or lease.age()>2.5:raise ValueError('MODEL_GUARD_NOT_PROGRESSING')
                        operation='recheck_start_approval'
                        if plan.authorize()!=permit:raise ValueError('MODEL_APPROVAL_CHANGED')
                        if read_state()['phase']!='ARMED' or lease.age()>2.5:
                            raise ValueError('MODEL_START_PERMISSION_LOST')
                        operation='start_container'
                        start_clock=time.monotonic()
                        docker.call('start',container_id,timeout=1.5);started=True
                        seconds=time.monotonic()-start_clock
                        operation='publish_start_receipt'
                        receipt_path=plan.LIVE/'control/start-result.json'
                        if receipt_path.exists():raise ValueError('MODEL_START_RECEIPT_ALREADY_EXISTS')
                        guard.base.atomic(receipt_path,startup_handoff.receipt(container_id,permit.review_sha256,seconds))
                    if state and state['phase']=='RUNNING' and now>=next_result and not claimed_result:
                        operation='read_api_result'
                        next_result=now+1;result=read_result(docker,owned)
                        if result is not None:
                            operation='publish_api_result'
                            guard.base.atomic(directory/'api-result.json',result);claimed_result=True
                            if result.get('status')=='REAL_STRATA_API_ANSWER':
                                if result.get('requestsSubmitted')!=1:raise ValueError('API_REQUEST_COUNT')
                                operation='publish_finish'
                                validate_response(result['response']);(plan.LIVE/'control/finish.request').touch(exist_ok=False)
                            else:
                                operation='publish_api_failure'
                                (plan.LIVE/'api.failure').touch(exist_ok=False)
                    if state and state['phase'] in ('COMPLETE','FAULT'):break
                    time.sleep(.1)
                else:raise TimeoutError('MODEL_API_OUTER_DEADLINE')
        except BaseException as error:
            parent_error=error_record(error,operation)
            raise
        finally:
            (plan.LIVE/'cancel.request').touch(exist_ok=True)
            stopped=stop(docker,owned) if owned is not None else {'stopConfirmed':False,'stopFault':'CREATE_UNCONFIRMED'}
            if not stopped['stopConfirmed']:guard.base.atomic(plan.LIVE/'emergency.json',stopped)
            if watchdog is not None and stopped['stopConfirmed']:
                try:watchdog.wait(timeout=8)
                except subprocess.TimeoutExpired:watchdog.kill();watchdog.wait(timeout=2)
            if owned is not None and stopped['stopConfirmed'] and stopped.get('retainedStoppedTarget'):
                try:build_diagnostics.collect(directory,owned,docker)
                except Exception as error:guard.base.atomic(directory/'diagnostic-error.json',{'type':type(error).__name__})
            if parent_error:guard.base.atomic(directory/'parent-error.json',parent_error)
            if state_exists():guard.base.atomic(directory/'result.json',read_state())
        state=read_state()
        if (state['phase']!='COMPLETE' or state.get('stopConfirmed') is not True or
                (plan.LIVE/'emergency.json').exists() or watchdog is None or watchdog.returncode!=0):
            raise ValueError('MODEL_API_FAILED_OR_STOP_UNCONFIRMED')
        response=plan.read(directory/'api-result.json',20000)['response']
        return {**state,'apiResultFile':str(directory/'api-result.json'),
            'answer':response['choices'][0]['message']['content'],'usage':response['usage']}


def cancel():
    state=read_state()
    if state['phase'] in ('COMPLETE','FAULT'):raise ValueError('MODEL_API_ALREADY_TERMINAL')
    (plan.LIVE/'cancel.request').touch(exist_ok=True)
    return {'status':'CANCELLATION_REQUESTED'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true',required=True)
    parser.parse_args();watch()
