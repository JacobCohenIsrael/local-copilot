"""Generated Windows files and fake supervisors only; no hardware/model access."""
import ctypes as c
import errno
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

import first_api
import runtime_plan as plan
import runtime_record_io as record
import sensor_frame_io as frame
import verify_frame_access as fixture


@unittest.skipUnless(os.name=='nt','Windows file sharing contract')
class StateSharingTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def test_actual_parent_state_reader_accepts_completed_rename_without_retry(self):
        state={'version':1,'phase':'WAITING_BASELINE','fault':None}
        with fixture.published_frame(self.root,1,json.dumps(state).encode()) as path:
            directory=self.root/'states';directory.mkdir();target=directory/'state-0001.json'
            frame.checked(fixture.api().MoveFileExW(str(path),str(target),0))
            with self.assertRaises(PermissionError):plan.read(target)
            with patch.object(plan,'LIVE',self.root):self.assertEqual(first_api.read_state(),state)

    def test_open_reader_does_not_block_new_state_and_old_snapshot_stays_complete(self):
        record.publish(self.root,{'phase':'WAITING_BASELINE'})
        path=self.root/'states/state-0001.json'
        kernel=fixture.api()
        class Proxy:
            def __getattr__(self,name):return getattr(kernel,name)
            def ReadFile(self,*args):
                value=kernel.ReadFile(*args);record.publish(self_outer.root,{'phase':'ARMED'});return value
        self_outer=self
        with patch.object(frame,'api',return_value=Proxy()):
            self.assertEqual(record.read_json(path),{'phase':'WAITING_BASELINE'})
        self.assertEqual(record.latest(self.root),{'phase':'ARMED'})
        self.assertEqual(record.read_json(path),{'phase':'WAITING_BASELINE'})

    def test_active_writer_and_exclusive_holder_remain_errors(self):
        path=self.root/'state.json';path.write_text('{}');kernel=fixture.api()
        for access,share in ((0x40000000,7),(0x80000000,0)):
            handle=kernel.CreateFileW(str(path),access,share,None,3,0x80,None)
            self.assertNotEqual(handle,c.c_void_p(-1).value)
            try:
                with self.assertRaises(OSError) as error:record.read_json(path)
                self.assertEqual(error.exception.winerror,32)
            finally:frame.checked(kernel.CloseHandle(handle))

    def test_access_denied_is_not_retried_or_reopened_with_broader_sharing(self):
        path=self.root/'state.json';path.write_text('{}');kernel=Mock()
        def denied(*args):c.set_last_error(5);return c.c_void_p(-1).value
        kernel.CreateFileW.side_effect=denied
        with patch.object(frame,'api',return_value=kernel):
            with self.assertRaises(OSError) as error:record.read_json(path)
        self.assertEqual(error.exception.winerror,5);self.assertEqual(error.exception.filename,str(path))
        kernel.CreateFileW.assert_called_once();kernel.CloseHandle.assert_not_called()
        self.assertEqual(kernel.CreateFileW.call_args.args[1:3],(0x80000000,5))

    def test_budgets_malformed_data_and_hardlinks_fail_closed(self):
        path=self.root/'state.json';path.write_bytes(b'x'*(record.MAXIMUM+1))
        with self.assertRaisesRegex(ValueError,'budget'):record.read_json(path)
        for raw in (b'{invalid',b'[]'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):record.read_json(path)
        path.write_bytes(b'{}');os.link(path,self.root/'alias')
        with self.assertRaisesRegex(ValueError,'hard links'):record.read_json(path)

    def test_handle_identity_change_and_partial_read_are_rejected(self):
        path=self.root/'state.json';path.write_bytes(b'{}');kernel=fixture.api()
        for variant in ('identity','short'):
            class Proxy:
                def __getattr__(self,name):return getattr(kernel,name)
                def ReadFile(self,handle,buffer,size,count,unused):
                    value=kernel.ReadFile(handle,buffer,size,count,unused)
                    if variant=='short':c.cast(count,c.POINTER(c.c_ulong)).contents.value=1
                    return value
            original=record.identity
            calls=[0]
            def identity(*args):
                value=original(*args);calls[0]+=1
                return (*value[:-1],value[-1]+1) if variant=='identity' and calls[0]==2 else value
            with patch.object(frame,'api',return_value=Proxy()),patch.object(record,'identity',side_effect=identity):
                with self.assertRaisesRegex(ValueError,'changed during'):record.read_json(path)


class DiagnosticTests(unittest.TestCase):
    def test_parent_error_keeps_bounded_reason_stage_filename_and_traceback(self):
        try:
            error=PermissionError(errno.EACCES,'generated sharing conflict','C:/fixture/state.json')
            error.winerror=32
            raise error
        except PermissionError as error:result=first_api.error_record(error,'read_watch_state')
        self.assertEqual(result['operation'],'read_watch_state');self.assertEqual(result['errno'],13)
        self.assertEqual(result['winerror'],32);self.assertEqual(result['filename'],'C:/fixture/state.json')
        self.assertIn('generated sharing conflict',result['reason']);self.assertFalse(result['automaticRetry'])
        self.assertTrue(result['traceback']);self.assertLessEqual(len(result['traceback']),8)
        self.assertEqual(set(result['traceback'][0]),{'file','line','function'})
        result=first_api.error_record(ValueError('x'*10000),'fixture')
        self.assertEqual(len(result['reason']),1024)

    def test_existing_process_timeout_details_are_preserved(self):
        result=first_api.error_record(subprocess.TimeoutExpired(['fixed','inspect'],1.5),'fixture')
        self.assertEqual(result['command'],['fixed','inspect']);self.assertEqual(result['timeoutSeconds'],1.5)
        self.assertEqual(result['operation'],'fixture')


class JournalTests(unittest.TestCase):
    def test_budget_sequence_and_payload_never_overwrite_published_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertFalse(record.exists(root))
            for n in range(record.MAX_RECORDS):record.publish(root,{'sequence':n})
            first=(root/'states/state-0001.json').read_bytes()
            self.assertEqual(record.latest(root),{'sequence':15})
            with self.assertRaisesRegex(ValueError,'budget'):record.publish(root,{'sequence':16})
            self.assertEqual((root/'states/state-0001.json').read_bytes(),first)
            with self.assertRaisesRegex(ValueError,'budget'):record.publish(root,{'text':'x'*record.MAXIMUM})
            (root/'states/state-0002.json').rename(root/'states/wrong.json')
            with self.assertRaisesRegex(ValueError,'Unexpected'):record.latest(root)

    def test_pending_snapshot_is_not_observed_and_gaps_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'states').mkdir()
            (root/'states'/('pending-'+'a'*32+'.tmp')).write_text('{broken')
            self.assertFalse(record.exists(root))
            record.publish(root,{'phase':'WAITING_BASELINE'})
            self.assertEqual(record.latest(root),{'phase':'WAITING_BASELINE'})
            (root/'states/state-0001.json').rename(root/'states/state-0002.json')
            with self.assertRaisesRegex(ValueError,'sequence'):record.latest(root)


if __name__=='__main__':unittest.main()
