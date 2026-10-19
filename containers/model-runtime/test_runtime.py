"""Offline contracts, fault injection and a fake connected run; no GPU/model calls."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import runtime_plan as plan
import runtime_safety as safety
import first_api
import container_test
import stage_model_runtime as stage
import api_wrapper
import prior_api


def cpu(sequence=1,stamp=1000,**changes):
    return {'version':1,'sequence':sequence,'synthetic':False,'source':'ASUS DSTS 0x00120094',
        'validatedCpuSensor':False,'cpuThermalThrottling':None,'cpuTemperatureC':90,'error':None,
        'querySeconds':.02,'recordedAtUnix':stamp,'readerRemainingSeconds':479,**changes}


def gpu(stamp=1000,**changes):
    return {'gpuUuid':safety.GPU_UUID,'driver':'617.14','gpuTemperatureC':55,'gpuPowerW':20,
        'vramUsedMiB':1800,'vramTotalMiB':16384,'gpuThermalThrottling':False,
        'ramUsedMiB':16000,'ramTotalMiB':32000,'acConnected':True,'querySeconds':.2,'recordedAtUnix':stamp,**changes}


def answer():
    return {'choices':[{'message':{'role':'assistant','content':'READY'},'finish_reason':'stop'}],
        'usage':{'prompt_tokens':30,'completion_tokens':1,'total_tokens':31}}


class GateTests(unittest.TestCase):
    def observe(self,gate,second,**kwargs):
        return gate.observe(cpu(second+1,1000+second,**kwargs),gpu(1000+second),now=second,unix=1000+second,controller_age=0)

    def test_monitored_baseline_then_running_preserves_emergency_stop(self):
        gate=safety.Gate()
        for i in range(10):self.assertFalse(self.observe(gate,i,cpuTemperatureC=96))
        self.assertTrue(self.observe(gate,10,cpuTemperatureC=96));gate.model_started=10
        self.assertEqual(gate.startup_warnings['cpuTemperatureC']['observed'],96)
        self.assertFalse(self.observe(gate,11,cpuTemperatureC=97))
        self.assertEqual(gate.fault,'CPU_HOT')
        self.assertFalse(self.observe(gate,12,cpuTemperatureC=90))

    def test_policy_faults_latch_for_all_required_channels_and_limits(self):
        for cpu_changes,gpu_changes,age,cancel,reason in (
            ({'cpuTemperatureC':97},{},0,False,'CPU_HOT'),
            ({'querySeconds':1.51},{},0,False,'CPU_QUERY_TIMEOUT'),
            ({},{'gpuTemperatureC':75},0,False,'GPU_HOT'),
            ({},{'gpuPowerW':100},0,False,'GPU_POWER_HIGH'),
            ({},{'vramUsedMiB':14336},0,False,'VRAM_HIGH'),
            ({},{'ramUsedMiB':28672},0,False,'HOST_RAM_HIGH'),
            ({},{'acConnected':False},0,False,'AC_DISCONNECTED_OR_UNKNOWN'),
            ({},{'gpuThermalThrottling':None},0,False,'GPU_THROTTLE_MISSING_OR_ACTIVE'),
            ({},{'gpuThermalThrottling':True},0,False,'GPU_THROTTLE_MISSING_OR_ACTIVE'),
            ({'cpuThermalThrottling':True},{},0,False,'CPU_THROTTLE_FLAG'),
            ({},{},2.51,False,'CONTROLLER_LEASE_EXPIRED'),
            ({},{},0,True,'CANCELLED'),
            ({'recordedAtUnix':996},{},0,False,'TELEMETRY_STALE_OR_MISSING'),
            ({},{'gpuPowerW':None},0,False,'GPU_OR_HOST_CHANNEL_MISSING'),
            ({'readerRemainingSeconds':304},{},0,False,'CPU_READER_COVERAGE')):
            with self.subTest(reason=reason):
                gate=safety.Gate();self.assertFalse(gate.observe(cpu(**cpu_changes),gpu(**gpu_changes),now=0,unix=1000,controller_age=age,cancelled=cancel))
                self.assertEqual(gate.fault,reason)
                self.assertFalse(self.observe(gate,1));self.assertEqual(gate.fault,reason)

    def test_warm_start_warns_and_stale_missing_replay_or_clock_never_admit(self):
        gate=safety.Gate()
        for i in range(8):self.observe(gate,i)
        self.observe(gate,8,cpuTemperatureC=96)
        self.assertFalse(self.observe(gate,9))
        self.assertTrue(self.observe(gate,10))
        for now,unix,reason in ((3,1003,'CLOCK_OR_MONITOR_GAP'),(1,1010,'CLOCK_OR_MONITOR_GAP'),(1,1001,'CPU_SOURCE_OR_SEQUENCE')):
            gate=safety.Gate();self.observe(gate,0)
            gate.observe(cpu(),gpu(unix),now=now,unix=unix,controller_age=0)
            self.assertEqual(gate.fault,reason)
        gate=safety.Gate();self.observe(gate,0)
        gate.observe(None,gpu(1002.4),now=2.4,unix=1002.4,controller_age=0)
        gate.observe(None,gpu(1002.6),now=2.6,unix=1002.6,controller_age=0)
        self.assertEqual(gate.fault,'TELEMETRY_STALE_OR_MISSING')

    def test_model_deadline_is_independent_of_hot_or_missing_data(self):
        gate=safety.Gate();gate.model_started=0
        for i in range(300):self.assertTrue(self.observe(gate,i))
        self.assertFalse(self.observe(gate,300));self.assertEqual(gate.fault,'MODEL_DEADLINE')

    def test_actual_read_only_nvidia_observation_decodes_without_a_live_query(self):
        raw=(plan.RUNTIME/'gpu-availability.xml').read_bytes();decoded=safety.decode_gpu(raw)
        self.assertEqual(decoded['gpuUuid'],safety.GPU_UUID);self.assertEqual(decoded['vramTotalMiB'],16384)
        self.assertIs(decoded['gpuThermalThrottling'],False)
        with self.assertRaisesRegex(ValueError,'IDENTITY'):safety.decode_gpu(raw.replace(safety.GPU_UUID.encode(),b'GPU-wrong'))


class ApiAndInputTests(unittest.TestCase):
    def test_review_accepts_its_own_json_serialized_container_contract(self):
        # A temporary disabled packet makes this normalization regression
        # independent of whether a new production candidate has been prepared.
        packet=copy.deepcopy(prior_api.load(prior_api.FOURTH_FOLDER/'review.json'))
        packet.update(scope=plan.SCOPE,policy=dict(safety.POLICY),liveNamespace=str(plan.LIVE),
            configuration=plan.config(),requestTimingChange=dict(plan.REQUEST_TIMING_CHANGE),
            fileAccessChange=dict(plan.FILE_ACCESS_CHANGE),
            startupTargetChange=dict(plan.STARTUP_TARGET_CHANGE),
            startupStatusChange=dict(plan.STARTUP_CHANGE),
            recoveryOf=plan.previous(),helperSha256=plan.helpers())
        packet.pop('startupArgumentChange',None)
        source_plan=plan.build.offline.checked_proposal(packet['sourcePlan']['directory'],packet['sourcePlan']['sha256'])
        packet['startupSourceAudit']=plan.native_iq_startup.check(plan.config(),Path(source_plan['sourcePackage'])/'input/source')
        packet['createArgs'],packet['contract']=plan.launch(Path(packet['packageDirectory']),
            Path(packet['buildProof']['artifactDirectory']),Path(packet['runtimeBundle']['directory']),
            Path(source_plan['sourcePackage'])/'input/source')
        digest=plan.sha(packet)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/digest).mkdir()
            (root/digest/'review.json').write_text(json.dumps(packet))
            (root/'candidate.json').write_text(json.dumps({'reviewSha256':digest}))
            with patch.object(plan,'ROOT',root):actual,reviewed=plan.review()
        self.assertEqual(actual,digest);self.assertFalse(reviewed['modelLaunchEnabled'])
    def test_kernel_qualification_rejects_swap_network_and_capabilities_before_engine_start(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            values={'sys/fs/cgroup/cpu.max':'100000 100000','sys/fs/cgroup/memory.max':str(4*1024**3),
                'sys/fs/cgroup/memory.swap.max':'0','sys/fs/cgroup/pids.max':'128',
                'proc/self/status':'CapEff:\t0000000000000000\nNoNewPrivs:\t1\n',
                'proc/meminfo':'MemTotal: 5800000 kB\nSwapTotal: 0 kB\n'}
            for name,value in values.items():
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
            (root/'sys/class/net/lo').mkdir(parents=True)
            with patch.object(container_test.os,'getuid',return_value=65532,create=True):
                self.assertFalse(container_test.qualify_environment(root)['modelStartedDuringQualification'])
                for name,value in (('sys/fs/cgroup/memory.swap.max','1'),('sys/fs/cgroup/cpu.max','200000 100000'),
                    ('proc/self/status','CapEff:\t1\nNoNewPrivs:\t1\n')):
                    (root/name).write_text(value)
                    with self.assertRaisesRegex(ValueError,'LIMITS_MISMATCH'):container_test.qualify_environment(root)
                    (root/name).write_text(values[name])
                (root/'sys/class/net/eth0').mkdir()
                with self.assertRaisesRegex(ValueError,'LIMITS_MISMATCH'):container_test.qualify_environment(root)

    def test_shutdown_first_requests_upstream_graceful_close_then_reaps_owned_group(self):
        process=Mock(pid=12345)
        with patch.object(container_test.os,'killpg',create=True) as kill,patch.object(container_test.signal,'SIGKILL',9,create=True):
            container_test.shutdown(process)
        process.terminate.assert_called_once();self.assertEqual(process.wait.call_args_list[0].kwargs['timeout'],2)
        self.assertEqual(kill.call_args.args[0],12345)

    def test_guest_lease_loss_regression_and_request_deadline_end_work(self):
        for sizes,now,deadline,reason in (({'controller.pulse':1,'guard.pulse':1},2.6,None,'EXPIRED'),
            ({'controller.pulse':0,'guard.pulse':2},1,None,'INVALID'),
            ({'controller.pulse':2,'guard.pulse':2},1,.9,'REQUEST_DEADLINE'),
            ({'controller.pulse':3,'guard.pulse':3},300,None,'CONTAINER_DEADLINE')):
            gate=container_test.Leases(0);gate.check(0,{'controller.pulse':1,'guard.pulse':1})
            with self.assertRaisesRegex((ValueError,TimeoutError),reason):gate.check(now,sizes,deadline)
        gate=container_test.Leases(0);gate.check(0,{'controller.pulse':1,'guard.pulse':1})
        gate.check(2,{'controller.pulse':2,'guard.pulse':2})
        with self.assertRaisesRegex(ValueError,'REGRESSION'):gate.check(1,{'controller.pulse':3,'guard.pulse':3})

    def test_api_wrapper_refuses_a_second_engine_launch_and_any_restart(self):
        server=SimpleNamespace(START_RETRIES=3,EngineDied=RuntimeError,popen=Mock(),
            StrataEngine=type('Engine',(),{'restart':lambda self:None}))
        def fake_main():
            server.popen('the Strata engine',['fixed'])
            with self.assertRaisesRegex(RuntimeError,'reload'):server.popen('the Strata engine',['fixed'])
            with self.assertRaisesRegex(RuntimeError,'restart'):server.StrataEngine().restart()
            return 0
        server.main=fake_main;original=server.popen
        with patch.dict(sys.modules,{'serve':SimpleNamespace(server=server)}),\
                patch.object(api_wrapper.threading,'Thread'),patch.object(sys,'path',list(sys.path)),patch.object(sys,'argv',[]):
            with self.assertRaises(SystemExit) as exit_result:api_wrapper.main()
        self.assertEqual(exit_result.exception.code,0);original.assert_called_once();self.assertEqual(server.START_RETRIES,0)

    def test_response_has_nonempty_real_text_and_strict_token_accounting(self):
        self.assertEqual(container_test.validate_response(answer()),answer())
        for field,value in (('completion_tokens',9),('completion_tokens',True),('prompt_tokens',505),('total_tokens',999)):
            response=answer();response['usage'][field]=value
            with self.assertRaises(ValueError):container_test.validate_response(response)
        response=answer();response['choices'][0]['message']['content']=''
        with self.assertRaises(ValueError):container_test.validate_response(response)

    def test_configuration_uses_minimum_native_iq_window_without_drafter(self):
        cfg=plan.config();args=cfg['args']
        for flag,value in (('--max-context','512'),('--spec','2'),('--suffix-draft','0'),('--pool-workers','1'),
                           ('--expert-cache','64'),('--prefill','32'),('--pcie-frac','0.20')):
            self.assertEqual(args[args.index(flag)+1],value)
        self.assertIn('--mmap-experts',args);self.assertNotIn('--resident-experts',args)
        self.assertNotIn('--calibrate',args);self.assertFalse(cfg['reasoning_close_retry'])
        self.assertNotIn('--mtp',args);self.assertNotIn('--lookup-chain',args)
        self.assertEqual(container_test.REQUEST['max_tokens'],8)

    def test_archive_rejects_escape_links_and_duplicate_code_but_omits_terminal_aliases(self):
        for mode in ('escape','duplicate','terminal'):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);archive=root/'bundle.tgz'
                with tarfile.open(archive,'w:gz') as out:
                    item=tarfile.TarInfo('python/bin/python3.13');item.size=1;out.addfile(item,io.BytesIO(b'x'))
                    if mode=='escape':
                        link=tarfile.TarInfo('python/bin/python');link.type=tarfile.SYMTYPE;link.linkname='../../../outside';out.addfile(link)
                    else:
                        for name in (('python/Bin/Python3.13',) if mode=='duplicate' else ('python/share/terminfo/A','python/share/terminfo/a')):
                            item=tarfile.TarInfo(name);item.size=1;out.addfile(item,io.BytesIO(b'x'))
                if mode=='terminal':
                    stage.extract_python(archive,root/'extracted');self.assertTrue((root/'extracted/python/bin/python3.13').is_file())
                else:
                    with self.assertRaises(ValueError):stage.extract_python(archive,root/'extracted')
                    self.assertFalse((root/'extracted').exists())

    def test_no_approval_refuses_before_any_native_or_model_input_access(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(plan,'APPROVAL',Path(temp)/'absent'),\
                patch.object(first_api.guard.base,'Docker') as docker,patch.object(plan,'verify_inputs') as verify:
            with self.assertRaisesRegex(ValueError,'NOT_APPROVED'):first_api.run()
            docker.assert_not_called();verify.assert_not_called()

    def decision(self,packet):
        return {'version':1,'status':'owner-approved-one-model-api-test','scope':plan.SCOPE,
            'reviewSha256':plan.sha(packet),'acceptPolicySha256':plan.sha(safety.POLICY),
            'acceptRequestTimingChange':dict(plan.REQUEST_TIMING_CHANGE),
            'acceptFileAccessChange':dict(plan.FILE_ACCESS_CHANGE),
            'acceptStartupTargetChange':dict(plan.STARTUP_TARGET_CHANGE),
            'acceptStartupStatusChange':dict(plan.STARTUP_CHANGE),
            'acceptSourceLimitation':safety.SOURCE_LIMITATION,'acceptSourceReviewSha256':packet['sourceReviewSha256'],
            'acceptLimitations':packet['limitations'],'acceptRetainedStoppedContainer':True,'maximumAttempts':1,
            'modelLaunchEnabled':True,'synthetic':False,'workerLaunchEnabled':False,'buildEnabled':False,
            'imageDownloadEnabled':False,'imageImportEnabled':False,'ownerMessage':'Synthetic fixture only'}

    def test_approval_cannot_reuse_build_scope_change_policy_or_enable_worker(self):
        packet={'sourceReviewSha256':'a'*64,'limitations':['unproven fit']}
        for key,value in (('scope','build-scope'),('acceptPolicySha256','0'*64),('workerLaunchEnabled',True),
            ('maximumAttempts',True),('imageDownloadEnabled',True),('acceptSourceLimitation','build-only acceptance'),
            ('acceptRetainedStoppedContainer',False),('acceptLimitations',[]),('acceptRequestTimingChange',None),
            ('acceptFileAccessChange',None),('acceptStartupTargetChange',None),('acceptStartupStatusChange',None)):
            with tempfile.TemporaryDirectory() as temp:
                decision=self.decision(packet);decision[key]=value;path=Path(temp)/'approval.json';path.write_text(json.dumps(decision))
                with patch.object(plan,'APPROVAL',path),patch.object(plan,'review',return_value=(plan.sha(packet),packet)):
                    with self.assertRaisesRegex(ValueError,'APPROVAL_INVALID'):plan.authorize()

    def test_exact_fourth_decision_accepts_only_the_reviewed_argument_change_offline(self):
        packet={'sourceReviewSha256':'a'*64,'limitations':['unproven fit']}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture-only.json';decision=self.decision(packet)
            path.write_text(json.dumps(decision))
            with patch.object(plan,'APPROVAL',path),patch.object(plan,'review',return_value=(plan.sha(packet),packet)):
                permit=plan.authorize()
                self.assertEqual(permit.packet,packet)
                decision['acceptRequestTimingChange']['to']=76
                path.write_text(json.dumps(decision))
                with self.assertRaisesRegex(ValueError,'APPROVAL_INVALID'):plan.authorize()

    def test_consumed_attempt_cannot_restart_or_clear_fault(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'attempt.json').write_text('{}')
            with patch.object(plan,'LIVE',root),patch.object(plan,'authorize',return_value=Mock()),patch.object(first_api.guard.base,'Docker') as docker:
                with self.assertRaisesRegex(ValueError,'CONSUMED'):first_api.run()
                docker.assert_not_called()


class TargetAndWatchTests(unittest.TestCase):
    def fixture(self):
        _,contract=plan.launch(Path('C:/package'),Path('C:/artifacts'),Path('C:/runtime'),Path('C:/source'))
        host=copy.deepcopy(contract['host']);host.update(RestartPolicy={'Name':'no'},CapDrop=['ALL'],CapAdd=None,
            SecurityOpt=['no-new-privileges'],Devices=[],DeviceRequests=contract['gpuRequests'],PortBindings={},
            IpcMode='private')
        info={'Id':'a'*64,'Name':'/'+contract['name'],'Image':contract['alternateImageId'],
            'Config':{'Image':contract['image'],'User':'65532:65532','Entrypoint':contract['entrypoint'],
                'Cmd':contract['command'],'WorkingDir':'/work','Labels':contract['labels'],
                'Env':[k+'='+v for k,v in contract['environment'].items()]},
            'HostConfig':host,'Mounts':[{'Type':'bind','Source':row[0],'Destination':row[1],'RW':row[2]} for row in contract['binds']],
            'State':{'Running':False,'Status':'created','ExitCode':0}}
        return contract,info

    def test_gpu_target_rejects_isolation_mutations_and_stop_uses_immutable_id(self):
        contract,info=self.fixture();owned=first_api.target({'contract':contract},'a'*64)
        docker=Mock();docker.inspect.return_value=info;self.assertEqual(owned.inspect(docker),info)
        for key,value in (('Memory',8*1024**3),('Privileged',True),('NetworkMode','bridge'),('DeviceRequests',[]),
            ('PortBindings',{'8080/tcp':[{'HostPort':'8080'}]}),('CapAdd',['SYS_ADMIN'])):
            mutated=copy.deepcopy(info);mutated['HostConfig'][key]=value;docker.inspect.return_value=mutated
            with self.assertRaises(ValueError):owned.inspect(docker)
        mutated=copy.deepcopy(info);mutated['Mounts'][0]['RW']=True;docker.inspect.return_value=mutated
        with self.assertRaises(ValueError):owned.inspect(docker)
        # The same owned ID still has stop authority after resource drift.
        self.assertEqual(owned.stop_matcher(docker,{}),mutated)
        docker.inspect.return_value={**mutated,'Id':'b'*64}
        with self.assertRaisesRegex(ValueError,'STOP_ID_CHANGED'):owned.stop_matcher(docker,{})
        with patch.object(first_api.guard,'stop_target',return_value={'stopConfirmed':True}) as stop:
            first_api.stop(docker,owned);self.assertEqual(stop.call_args.args[2],'a'*64);self.assertFalse(stop.call_args.kwargs['remove'])

    def test_watch_hot_frame_stops_retains_and_closes_reader_without_starting_model(self):
        contract,info=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/'sessions'/('a'*32);directory.mkdir(parents=True);(root/'control').mkdir()
            (root/'attempt.json').write_text(json.dumps({'reviewSha256':'b'*64,'sessionId':'a'*32}))
            (directory/'target.json').write_text(json.dumps({'containerId':'a'*64,'readerDirectory':str(root/'reader')}))
            permit=SimpleNamespace(review_sha256='b'*64,packet={'contract':contract})
            feed=Mock();feed.process.pid=1234;feed.poll.return_value=cpu(cpuTemperatureC=98)
            docker=Mock();docker.inspect.return_value=info
            with patch.object(plan,'LIVE',root),patch.object(plan,'authorize',return_value=permit),\
                patch.object(first_api.cpu_feed,'Feed',return_value=feed),patch.object(first_api.guard.base,'Docker',return_value=docker),\
                patch.object(safety,'snapshot',return_value=gpu()),patch.object(first_api.time,'time',return_value=1000),\
                patch.object(first_api.time,'monotonic',return_value=0),\
                patch.object(first_api.control,'Pulse',return_value=SimpleNamespace(age=lambda:0)),\
                patch.object(first_api,'stop',return_value={'stopConfirmed':True,'retainedStoppedTarget':True}) as stop:
                first_api.watch()
            state=first_api.runtime_record_io.latest(root);self.assertEqual(state['fault']['code'],'CPU_HOT')
            self.assertTrue(state['stopConfirmed']);stop.assert_called_once();feed.close.assert_called_once()
            self.assertFalse(any(c.args and c.args[0]=='start' for c in docker.call.call_args_list))


class ConnectedRunnerTests(unittest.TestCase):
    def fixture(self,*,api_failure=False,guard_lost=False,state_read_failure=False,start_timeout=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);live=root/'live';capacity=root/'capacity';capacity.mkdir()
            (capacity/'result.json').write_text(json.dumps({'guestSwapTotalBytes':0}))
            packet={'createArgs':['create','fixed-reviewed-input']}
            permit=SimpleNamespace(packet=packet,review_sha256='b'*64)
            docker=Mock();owned=Mock(container_id='a'*64);owned.inspect.return_value={'Id':'a'*64,'State':{'Running':False}}
            class Watchdog:
                returncode=None;pid=4321
                def poll(self):
                    control=live/'control';(control/'guard.pulse').write_bytes(b'..')
                    current=first_api.runtime_record_io.latest(live) if first_api.runtime_record_io.exists(live) else {'phase':'ARMED','fault':None}
                    if (control/'finish.request').exists():
                        current.update(phase='COMPLETE',stopConfirmed=True,retainedStoppedTarget=True,containerId='a'*64)
                        self.returncode=0
                    if (live/'api.failure').exists():
                        current.update(phase='FAULT',fault={'code':'API_TEST_FAILED'},stopConfirmed=True)
                        self.returncode=0
                    first_api.runtime_record_io.publish(live,current);return self.returncode
                def wait(self,timeout):self.returncode=0;return 0
                def kill(self):self.returncode=1
            watchdog=Watchdog()
            original_read=first_api.runtime_record_io.read_json;read_calls=[0]
            def state_read(path):
                read_calls[0]+=1
                if state_read_failure and read_calls[0]==1:
                    raise PermissionError(13,'fixture state access denied',str(path))
                return original_read(path)
            def call(*args,**kwargs):
                if args[0]=='start' and start_timeout:
                    raise subprocess.TimeoutExpired(['docker','start','a'*64],kwargs['timeout'])
                if args[0]=='start':first_api.runtime_record_io.publish(live,{'phase':'RUNNING','fault':None})
                return 'a'*64
            docker.call.side_effect=call
            result=({'status':'FAULT','requestsSubmitted':1,'error':'fixture'} if api_failure else
                {'status':'REAL_STRATA_API_ANSWER','requestsSubmitted':1,'response':answer()})
            with patch.object(plan,'LIVE',live),patch.object(plan,'authorize',return_value=permit),\
                patch.object(plan,'verify_inputs'),patch.object(first_api.guard.base,'Docker',return_value=docker),\
                patch.object(first_api.ctypes.windll.shell32,'IsUserAnAdmin',return_value=1),\
                patch.object(plan.build,'image_ready'),patch.object(plan.build,'vm_ready'),\
                patch.object(safety,'snapshot',return_value=gpu()),\
                patch('probe_image_storage.probe',return_value=capacity),\
                patch.object(plan.build.image_plan,'capacity',return_value={'withinProposedBudgetAtProbe':True}),\
                patch.object(first_api,'target',return_value=owned),\
                patch.object(first_api.subprocess,'Popen',return_value=watchdog),\
                patch.object(first_api.control,'Pulse',return_value=SimpleNamespace(path=live/'control/guard.pulse',
                    changed=True,age=lambda:3 if guard_lost else 0)),\
                patch.object(first_api,'read_result',return_value=result) as read_result,\
                patch.object(first_api,'stop',return_value={'stopConfirmed':True,'retainedStoppedTarget':True}) as stop,\
                patch.object(first_api.build_diagnostics,'collect') as capture,\
                patch.object(first_api.runtime_record_io,'read_json',side_effect=state_read):
                if start_timeout:
                    with self.assertRaises(subprocess.TimeoutExpired):first_api.run()
                    failure=json.loads(next((live/'sessions').glob('*/parent-error.json')).read_text())
                    self.assertEqual(failure['operation'],'start_container');self.assertEqual(failure['timeoutSeconds'],1.5)
                    self.assertFalse((live/'control/start-result.json').exists())
                elif state_read_failure:
                    with self.assertRaises(PermissionError):first_api.run()
                    failure=json.loads(next((live/'sessions').glob('*/parent-error.json')).read_text())
                    self.assertEqual(failure['operation'],'read_watch_state')
                    self.assertEqual(failure['errno'],13);self.assertTrue(failure['filename'].endswith('state-0001.json'))
                    self.assertFalse(failure['automaticRetry']);self.assertTrue(failure['traceback'])
                elif api_failure or guard_lost:
                    with self.assertRaisesRegex(ValueError,'FAILED|LEASE_LOST'):first_api.run()
                else:
                    output=first_api.run();self.assertEqual(output['phase'],'COMPLETE');self.assertEqual(output['answer'],'READY')
                self.assertEqual(sum(c.args[0]=='create' for c in docker.call.call_args_list),1)
                self.assertEqual(sum(c.args[0]=='start' for c in docker.call.call_args_list),0 if guard_lost or state_read_failure else 1)
                stop.assert_called_once();capture.assert_called_once()
                self.assertFalse((live/'emergency.json').exists())
                self.assertTrue((live/'attempt.json').exists())
                if guard_lost or state_read_failure or start_timeout:read_result.assert_not_called()
                else:read_result.assert_called_once()

    def test_success_saves_exact_one_answer_then_confirms_stop_and_retains_logs(self):self.fixture()
    def test_request_failure_ends_the_single_attempt_without_retry(self):self.fixture(api_failure=True)
    def test_lost_independent_guard_prevents_start_and_stops_owned_target(self):self.fixture(guard_lost=True)
    def test_unreadable_state_stops_without_start_or_retry_and_preserves_cause(self):self.fixture(state_read_failure=True)
    def test_docker_start_timeout_remains_fatal_one_call_and_no_receipt(self):self.fixture(start_timeout=True)


if __name__=='__main__':unittest.main()
