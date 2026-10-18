import ctypes as c
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cpu_feed
import sensor_frame_io as io
import verify_frame_access as fixture


@unittest.skipUnless(os.name=='nt','Windows native sharing contract')
class FrameReadTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name)

    def test_visible_complete_frame_under_delete_handle_reads_without_retry(self):
        raw=json.dumps(fixture.generated(1,0)).encode()
        with fixture.published_frame(self.directory,1,raw) as path:
            with self.assertRaises(PermissionError):
                path.read_bytes()
            self.assertEqual(io.read(path),raw)

    def test_feed_reads_held_publication_without_tolerating_a_real_writer(self):
        session=self.directory/('a'*32)
        session.mkdir()
        with patch.object(cpu_feed,'ROOT',self.directory):
            feed=cpu_feed.Feed(session)
        feed.synthetic=True
        raw=json.dumps(fixture.generated(1,0)).encode()
        with fixture.published_frame(session,1,raw):
            self.assertEqual(feed.poll()['sequence'],1)
        self.assertEqual(feed.sequence,1)

    def test_existing_writer_or_exclusive_reader_still_fails(self):
        path=self.directory/'sample.json'
        path.write_bytes(b'{}')
        kernel=fixture.api()
        for access,share in [(0x40000000,7),(0x80000000,0)]:
            handle=kernel.CreateFileW(str(path),access,share,None,3,0x80,None)
            self.assertNotEqual(handle,c.c_void_p(-1).value)
            try:
                with self.assertRaises(OSError) as caught:
                    io.read(path)
                self.assertEqual(caught.exception.winerror,32)
            finally:
                io.checked(kernel.CloseHandle(handle))

    def test_same_handle_checks_reject_path_replacement_after_read(self):
        path=self.directory/'sample.json'
        path.write_bytes(b'{}')
        replacement=self.directory/'replacement'
        replacement.write_bytes(b'[]')
        moved=self.directory/'moved-old'
        kernel=fixture.api()
        class Proxy:
            def __getattr__(self,name):
                return getattr(kernel,name)
            def ReadFile(self,*args):
                result=kernel.ReadFile(*args)
                io.checked(kernel.MoveFileExW(str(path),str(moved),0))
                os.rename(replacement,path)
                return result
        with patch.object(io,'api',return_value=Proxy()):
            with self.assertRaisesRegex(ValueError,'changed during'):
                io.read(path)

    def test_oversize_and_hardlinked_frames_are_rejected(self):
        path=self.directory/'sample.json'
        path.write_bytes(b'x'*4097)
        with self.assertRaisesRegex(ValueError,'budget'):
            io.read(path)
        path.write_bytes(b'{}')
        os.link(path,self.directory/'alias')
        with self.assertRaisesRegex(ValueError,'hard links'):
            io.read(path)

    def test_native_open_preserves_access_denial_without_retry_or_chmod(self):
        path=self.directory/'sample.json'
        path.write_bytes(b'{}')
        kernel=Mock()
        def denied(*args):
            c.set_last_error(5)
            return c.c_void_p(-1).value
        kernel.CreateFileW.side_effect=denied
        with patch.object(io,'api',return_value=kernel):
            with self.assertRaises(OSError) as caught:
                io.read(path)
        self.assertEqual(caught.exception.winerror,5)
        kernel.CreateFileW.assert_called_once()
        args=kernel.CreateFileW.call_args.args
        self.assertEqual(args[1],0x80000000)
        self.assertEqual(args[2],5)
        self.assertEqual(args[4],3)
        kernel.CloseHandle.assert_not_called()

    def test_malformed_held_publication_faults_without_consuming_frame(self):
        session=self.directory/('a'*32)
        session.mkdir()
        with patch.object(cpu_feed,'ROOT',self.directory):
            feed=cpu_feed.Feed(session)
        feed.synthetic=True
        monitor=cpu_feed.Monitor(feed)
        with fixture.published_frame(session,1,b'{invalid'):
            self.assertEqual(monitor.poll()['fault'],'SENSOR_FEED_ERROR')
        self.assertEqual(feed.sequence,0)
        self.assertIsNone(feed.received)
        self.assertEqual(monitor.last_error['reason'],'READER_FRAME_JSON')

    def test_stale_held_publication_does_not_refresh_age_checks(self):
        session=self.directory/('a'*32)
        session.mkdir()
        with patch.object(cpu_feed,'ROOT',self.directory):
            feed=cpu_feed.Feed(session)
        feed.synthetic=True
        monitor=cpu_feed.Monitor(feed,unix=lambda:1010)
        with fixture.published_frame(session,1,json.dumps(fixture.generated(1,0)).encode()):
            self.assertEqual(monitor.poll()['fault'],'SENSOR_STALE')


if __name__=='__main__':
    unittest.main()
