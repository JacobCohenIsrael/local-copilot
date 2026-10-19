"""Offline startup, retention and one-attempt recovery regression checks."""
import copy
import contextlib
import hashlib
import json
import os
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import build_diagnostics as diagnostics
import build_recovery as recovery
import build_guard as guard
import offline_target
from test_stop_deadline import Clock, Docker


class StartupScriptTests(unittest.TestCase):
    """Run only shell stubs; never execute the pinned ELF tools or a compiler."""
    def fixture(self, root, *, old=False, ninja_version=recovery.NINJA_VERSION.decode(), missing=False):
        source, tools, work, inputs = [root / name for name in ('source', 'tools', 'work', 'input')]
        for path in (source/'third_party/llama.cpp/ggml', tools/'cmake/bin', tools/'ninja/bin', work/'build', inputs):
            path.mkdir(parents=True)
        for path in (source/'CMakeLists.txt', source/'third_party/llama.cpp/ggml/CMakeLists.txt', work/'export.complete'):
            path.write_text('fixture')
        (inputs/'BUILD.json').write_text('{}')
        cmake = tools/'cmake/bin/cmake'
        cmake.write_text('#!/bin/bash\nif [ "$1" = --version ]; then printf "cmake version 4.4.3\\n\\nCMake suite fixture\\n"; exit 0; fi\nprintf "FAKE_CMAKE_INVOKED\\n"\nif [ "$1" = --build ]; then printf fixture > "'+work.as_posix()+'/build/strata"; fi\n')
        ninja = tools/'ninja/bin/ninja'
        ninja.write_text('#!/bin/bash\nprintf "%s\\n" "'+ninja_version+'"\n')
        for name in ('gpp', 'nvcc'):
            (root/name).write_text('#!/bin/bash\nexit 99\n')
        if missing: ninja.unlink()
        if old:
            # Shell inputs are frozen in the spent package rather than the Python helper inventory.
            script = recovery.REPO/'.runtime/offline-build/c47d018e42244443a72bf166081da9c4/input/compile_offline.sh'
        else:
            script = recovery.HERE/'compile_offline.sh'
        raw = script.read_text(encoding='utf-8')
        for original, target in (('/usr/bin/g++',root/'gpp'),('/usr/local/cuda/bin/nvcc',root/'nvcc'),
                                 ('/tools',tools),('/source',source),('/work',work),('/input',inputs)):
            raw = raw.replace(original,target.as_posix())
        path=root/'fixture.sh';path.write_text(raw,encoding='utf-8',newline='\n')
        bash=Path(r'C:\Program Files\Git\bin\bash.exe')
        self.assertTrue(bash.exists(), 'Git Bash is required for these inert shell fixtures')
        return subprocess.run([str(bash),'--noprofile','--norc',str(path)],capture_output=True,text=True,timeout=10)

    def test_old_literal_check_reproduces_exit_one_before_any_configure(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.fixture(Path(temp),old=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertNotIn('FAKE_CMAKE_INVOKED',result.stdout)

    def test_exact_pinned_ninja_suffix_reaches_configure_build_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.fixture(Path(temp))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('STRATA_BUILD_STAGE configure',result.stdout)
            self.assertIn('STRATA_BUILD_STAGE compile',result.stdout)
            self.assertEqual(result.stdout.count('FAKE_CMAKE_INVOKED'),2)
            self.assertTrue((Path(temp)/'work/ready.json').exists())

    def test_unpinned_version_reports_the_named_startup_check(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.fixture(Path(temp),ninja_version='1.13.3')
            self.assertEqual(result.returncode,31)
            self.assertIn('check=ninja-version',result.stderr)
            self.assertIn('stage=tool-versions',result.stderr)
            self.assertNotIn('FAKE_CMAKE_INVOKED',result.stdout)

    def test_missing_executable_reports_its_name_before_version_or_compilation(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.fixture(Path(temp),missing=True)
            self.assertEqual(result.returncode,31)
            self.assertIn('check=ninja-executable',result.stderr)
            self.assertNotIn('FAKE_CMAKE_INVOKED',result.stdout)


class DiagnosticTests(unittest.TestCase):
    def target(self, *, running=False):
        target=Mock(container_id='a'*64)
        target.inspect.return_value={'Id':'a'*64,'State':{'Running':running,'ExitCode':1,'OOMKilled':False}}
        return target

    def test_stderr_and_bounded_tail_survive_a_failed_start(self):
        with tempfile.TemporaryDirectory() as temp:
            capture=Mock(return_value=SimpleNamespace(returncode=0,stdout=b'x'*70000+b'STRATA_STARTUP_FAILURE check=ninja-version\n'))
            result=diagnostics.collect(Path(temp),self.target(),Mock(),capture=capture)
            self.assertEqual(capture.call_args.kwargs['stderr'],subprocess.STDOUT)
            self.assertEqual(result['logBytes'],65536)
            self.assertTrue(result['truncated'])
            self.assertTrue((Path(temp)/'startup.log').read_bytes().endswith(b'check=ninja-version\n'))
            self.assertTrue(result['containerRetainedStopped'])
            with self.assertRaisesRegex(ValueError,'ALREADY_CAPTURED'):
                diagnostics.collect(Path(temp),self.target(),Mock(),capture=capture)

    def test_a_live_replaced_or_absent_target_is_never_queried_for_logs(self):
        for mode in ('live','replaced','absent'):
            with tempfile.TemporaryDirectory() as temp:
                target=self.target(running=mode=='live')
                if mode=='replaced':target.inspect.return_value['Id']='b'*64
                if mode=='absent':target.inspect.return_value=None
                capture=Mock()
                with self.assertRaisesRegex(ValueError,'OWNED_STOPPED'):
                    diagnostics.collect(Path(temp),target,Mock(),capture=capture)
                capture.assert_not_called()

    def test_a_log_timeout_preserves_partial_output_and_a_stopped_target(self):
        with tempfile.TemporaryDirectory() as temp:
            capture=Mock(side_effect=subprocess.TimeoutExpired('logs',2,output=b'partial diagnostic'))
            result=diagnostics.collect(Path(temp),self.target(),Mock(),capture=capture)
            self.assertEqual(result['status'],'DOCKER_LOG_CAPTURE_TIMEOUT')
            self.assertEqual((Path(temp)/'startup.log').read_bytes(),b'partial diagnostic')
            self.assertTrue(result['containerRetainedStopped'])


class RetainedStopTests(unittest.TestCase):
    def stop(self,docker,clock,**kwargs):
        with patch.object(guard,'inspect_target',side_effect=lambda client,_:client.inspect('owned')):
            return guard.stop_target(docker,{},'original',clock=clock,**kwargs)

    def test_fault_stop_confirms_exit_without_removing_its_logs(self):
        clock=Clock();docker=Docker(clock)
        result=self.stop(docker,clock,remove=False)
        self.assertTrue(result['stopConfirmed'])
        self.assertTrue(result['retainedStoppedTarget'])
        self.assertFalse(result['cleanupComplete'])
        self.assertIsNotNone(docker.info)
        self.assertNotIn('rm',[args[0] for args,_ in docker.calls])

    def test_competing_removal_is_success_only_after_fresh_confirmed_absence(self):
        clock=Clock();docker=Docker(clock);original=docker.call
        def call(*args,**kwargs):
            if args[0]=='rm':
                docker.info=None
                raise RuntimeError('other owner removed same ID')
            return original(*args,**kwargs)
        docker.call=call
        result=self.stop(docker,clock)
        self.assertTrue(result['cleanupComplete'])
        self.assertTrue(result['stopConfirmed'])


class RecoveryAdmissionTests(unittest.TestCase):
    def decision(self,packet):
        return {'version':1,'status':'owner-approved-one-cpu-build-recovery','scope':recovery.SCOPE,
            'reviewSha256':recovery.base.sha(packet),'acceptSourceQualificationSha256':packet['sourceReviewSha256'],
            'acceptSourceLimitation':recovery.cpu.LIMITATION,'maximumAttempts':1,'synthetic':False,
            'buildEnabled':True,'imageDownloadEnabled':False,'imageImportEnabled':False,'modelLaunchEnabled':False,
            'acceptStoppedFailureContainerRetention':True,'ownerMessage':'Synthetic fixture approval only'}

    def test_absent_recovery_approval_refuses_before_prior_evidence_process_or_reader(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(recovery,'APPROVAL',Path(temp)/'absent'), \
                patch.object(recovery,'previous') as prior,patch.object(recovery.first_build,'run') as run:
            with self.assertRaisesRegex(ValueError,'NOT_APPROVED'): recovery.run()
            prior.assert_not_called();run.assert_not_called()

    def test_scope_limits_retention_and_import_flags_are_strict(self):
        packet={'sourceReviewSha256':'c'*64}
        for key,value in (('imageImportEnabled',True),('imageDownloadEnabled',True),('modelLaunchEnabled',True),
                          ('maximumAttempts',True),('acceptStoppedFailureContainerRetention',False),('reviewSha256','0'*64)):
            with tempfile.TemporaryDirectory() as temp:
                decision=self.decision(packet);decision[key]=value;path=Path(temp)/'approval.json'
                path.write_text(json.dumps(decision))
                with patch.object(recovery,'APPROVAL',path),patch.object(recovery,'review',return_value=(recovery.base.sha(packet),packet)):
                    with self.assertRaisesRegex(ValueError,'SCOPE_OR_HASH'):recovery.authorize()

    def test_new_permit_binds_only_the_fixed_recovery_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);packet={'offlineDirectory':'unused','offlinePlanSha256':'a'*64,'liveNamespace':str(root/'new')}
            permit=recovery.Permit(recovery.base.sha(packet),recovery.base.encoded(packet).decode(),'b'*64)
            target=Mock(synthetic=False)
            with patch.object(recovery,'LIVE',root/'new'),patch.object(offline_target,'from_proposal',return_value=target):
                permit.target(target,root/'new')
                with self.assertRaisesRegex(ValueError,'namespace'):permit.target(target,root/'spent')

    def test_binary_evidence_is_static_and_matches_the_pinned_receipt(self):
        _,_,plan=recovery.base.selected()
        result=recovery.version_evidence(plan)
        self.assertTrue(result['literalMismatchConfirmed'])
        self.assertFalse(result['binaryExecutedDuringPreparation'])
        self.assertEqual(result['embeddedVersion'],'1.13.2.git.kitware.jobserver-pipe-1')

    def test_cancel_targets_only_the_new_session_without_requiring_new_start_authority(self):
        sys.path.insert(0,str(recovery.REPO))
        import local_worker
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=root/'sessions'/('a'*32);session.mkdir(parents=True)
            (root/'attempt.json').write_text(json.dumps({'sessionId':'a'*32}))
            (root/'state.json').write_text(json.dumps({'phase':'RUNNING'}))
            with patch.object(recovery,'LIVE',root),patch.object(sys,'argv',['local_worker.py','cancel-build-recovery']), \
                    patch.object(recovery,'authorize',side_effect=AssertionError('Stopping must not need start approval')), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(local_worker.main(),0)
            self.assertTrue((session/'cancel.request').exists())


if __name__=='__main__':unittest.main()
