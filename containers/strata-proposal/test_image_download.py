import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import image_download as downloads


def blob(payload):
    return downloads.Blob('sha256:' + hashlib.sha256(payload).hexdigest(), len(payload))


class Response(io.BytesIO):
    def __init__(self, payload, *, length=None, headers=None, status=200, on_read=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers if headers is not None else [('Content-Length', str(len(payload) if length is None else length))]
        self.on_read = on_read

    def getheaders(self):
        return self.headers

    def read1(self, count):
        data = super().read(count)
        if self.on_read:
            self.on_read()
        return data


class Source:
    def __init__(self, payloads):
        self.payloads = {blob(p): p for p in payloads}
        self.calls = []
        self.override = None

    def open(self, spec, _context):
        self.calls.append(spec)
        return self.override(spec) if self.override else Response(self.payloads[spec])


class Clock:
    value = 100

    def __call__(self):
        return self.value


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'stage'
        self.addCleanup(self.temp.cleanup)
        self.payloads = [b'synthetic-config', b'synthetic-layer' * 6000]
        self.blobs = [blob(p) for p in self.payloads]
        self.source = Source(self.payloads)
        self.limits = downloads.Limits(1024**2, 4 * 1024**2, 0, 10, 3)
        self.clock = Clock()

    def stage(self, *, guard=lambda: True):
        return downloads._stage(self.root, self.blobs, 'a' * 64, self.source,
                                self.limits, guard=guard, synthetic=True, clock=self.clock)

    def state(self):
        return json.loads((self.root / 'state.json').read_text())

    def test_complete_and_warm_cache_are_verified_without_redownload(self):
        directory, state = self.stage()
        self.assertEqual(state['state'], 'STAGED_NOT_IMPORTED')
        self.assertEqual(state['blobPayloadBytes'], sum(len(p) for p in self.payloads))
        self.assertEqual(len(self.source.calls), 2)
        self.assertTrue((directory / 'result.json').is_file())
        for spec in self.blobs:
            self.assertEqual(downloads.tools.sha(self.root / 'cache' / spec.digest[7:]), spec.digest[7:])
        self.source.calls.clear()
        _, second = self.stage()
        self.assertEqual(self.source.calls, [])
        self.assertTrue(all(r['cacheReused'] for r in second['blobs']))
        for flag in ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'):
            self.assertFalse(second[flag])

    def test_short_extra_and_bad_hash_fail_without_promoting_partial(self):
        for data in (b'short', self.payloads[0] + b'x', b'x' * len(self.payloads[0])):
            with tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'stage'
                self.source.override = lambda spec: Response(data, length=spec.size)
                with self.assertRaises(downloads.StageError):
                    self.stage()
                self.assertEqual(self.state()['state'], 'FAULT')
                self.assertEqual(list((self.root / 'cache').iterdir()), [])
                self.assertTrue(list((self.root / 'sessions').glob('*/*.partial')))
                before = len(self.source.calls)
                with self.assertRaisesRegex(downloads.StageError, 'LATCHED_FAULT'):
                    self.stage()
                self.assertEqual(len(self.source.calls), before)

    def test_bad_http_framing_fails_before_blob_body(self):
        headers = [[('Content-Length', str(self.blobs[0].size))] * 2,
                   [('Content-Length', str(self.blobs[0].size)), ('Transfer-Encoding', 'chunked')],
                   [('Content-Length', str(self.blobs[0].size)), ('Content-Encoding', 'gzip')],
                   [('Content-Length', '+16')], []]
        for values in headers:
            with tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder) / 'stage'
                response = Response(self.payloads[0], headers=values)
                self.source.override = lambda _: response
                with self.assertRaisesRegex(downloads.StageError, 'HTTP_'):
                    self.stage()
                self.assertEqual(self.state()['blobPayloadBytes'], 0)

    def test_corrupt_cache_latches_fault_without_refetch(self):
        self.stage()
        cache = self.root / 'cache' / self.blobs[0].digest[7:]
        cache.write_bytes(b'x' * self.blobs[0].size)
        self.source.calls.clear()
        with self.assertRaisesRegex(downloads.StageError, 'CACHE_CHANGED'):
            self.stage()
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.state()['fault']['code'], 'CACHE_CHANGED')

    def test_missing_previously_verified_cache_never_refetches(self):
        self.stage()
        (self.root / 'cache' / self.blobs[0].digest[7:]).unlink()
        self.source.calls.clear()
        with self.assertRaisesRegex(downloads.StageError, 'CACHE_CHANGED'):
            self.stage()
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.state()['state'], 'FAULT')

    def test_guard_loss_after_receive_prevents_cache_commit_and_charges_bytes(self):
        permission = {'allowed': True}
        self.source.override = lambda spec: Response(self.payloads[0], on_read=lambda: permission.update(allowed=False))
        with self.assertRaisesRegex(downloads.StageError, 'GUARD_PERMISSION_LOST'):
            self.stage(guard=lambda: permission['allowed'])
        self.assertEqual(self.state()['blobPayloadBytes'], self.blobs[0].size)
        self.assertEqual(list((self.root / 'cache').iterdir()), [])

    def test_per_blob_timeout_includes_returned_read_time(self):
        self.source.override = lambda spec: Response(self.payloads[0], on_read=lambda: setattr(self.clock, 'value', 104))
        with self.assertRaisesRegex(downloads.StageError, 'STAGING_DEADLINE'):
            self.stage()
        self.assertEqual(self.state()['state'], 'FAULT')

    def test_clock_regression_or_initial_guard_denial_starts_no_work(self):
        def reverse():
            self.clock.value = 99
            return True
        with self.assertRaisesRegex(downloads.StageError, 'CLOCK_INVALID'):
            self.stage(guard=reverse)
        self.assertFalse(self.root.exists())
        self.clock.value = 100
        with self.assertRaisesRegex(downloads.StageError, 'GUARD_PERMISSION_LOST'):
            self.stage(guard=lambda: False)
        self.assertEqual(self.source.calls, [])

    def test_namespace_and_disk_reserve_fail_before_source_open(self):
        self.limits = downloads.Limits(1024**2, downloads.RECEIPT_BYTES, 0, 10, 3)
        with self.assertRaisesRegex(downloads.StageError, 'NAMESPACE_BYTE_LIMIT'):
            self.stage()
        self.assertEqual(self.source.calls, [])
        self.root = Path(self.temp.name) / 'different'
        self.limits = downloads.Limits(1024**2, 4 * 1024**2, 1, 10, 3)
        with patch.object(downloads.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 0})()):
            with self.assertRaisesRegex(downloads.StageError, 'DISK_RESERVE_LOW'):
                self.stage()
        self.assertEqual(self.source.calls, [])

    def test_disk_loss_mid_transfer_retains_bounded_partial(self):
        available = {'bytes': 10 * 1024**2}
        def reserve(_):
            return type('Disk', (), {'free': available['bytes']})()
        def received():
            available['bytes'] = 0
        self.source.override = lambda spec: Response(self.payloads[0], on_read=received)
        with patch.object(downloads.shutil, 'disk_usage', side_effect=reserve):
            with self.assertRaisesRegex(downloads.StageError, 'DISK_RESERVE_LOW'):
                self.stage()
        self.assertFalse(list((self.root / 'cache').iterdir()))

    def test_interrupted_or_corrupt_journal_never_resumes(self):
        self.stage()
        state = self.state()
        state['state'] = 'STAGING'
        (self.root / 'state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(downloads.StageError, 'UNFINISHED_SESSION'):
            self.stage()
        (self.root / 'state.json').write_text('{')
        with self.assertRaises(ValueError):
            self.stage()

    def test_payload_budget_includes_registry_metadata(self):
        context = downloads.Context(downloads.Limits(5, 1024**2, 0, 10, 3), lambda: True, self.clock)
        context.charge(3, auth=True)
        with self.assertRaisesRegex(downloads.StageError, 'PAYLOAD_BUDGET_EXCEEDED'):
            context.charge(3)

    def test_hard_linked_cache_rejected_without_refetch(self):
        self.stage()
        cache = self.root / 'cache' / self.blobs[0].digest[7:]
        os.link(cache, self.root / 'extra-hard-link')
        self.source.calls.clear()
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.state()['state'], 'FAULT')

    def test_concurrent_writer_is_rejected_before_source_open(self):
        with downloads.tools.base.lock(self.root / 'control'):
            with self.assertRaises(downloads.tools.base.Busy):
                self.stage()
        self.assertEqual(self.source.calls, [])

    def test_expired_guard_check_never_opens_transport(self):
        def slow_guard():
            self.clock.value += 11
            return True
        with self.assertRaisesRegex(downloads.StageError, 'STAGING_DEADLINE'):
            self.stage(guard=slow_guard)
        self.assertEqual(self.source.calls, [])
        self.assertFalse(self.root.exists())

    def test_live_entry_rejected_before_network_or_directory_creation(self):
        with patch.object(downloads, 'RegistrySource') as source, patch.object(downloads, '_stage') as stage:
            with self.assertRaisesRegex(downloads.StageError, 'IMAGE_STAGING_NOT_APPROVED'):
                downloads.stage_pinned(approved=True)
            source.assert_not_called()
            stage.assert_not_called()


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.blob = blob(b'fake')
        self.auth = json.dumps({'token': 'synthetic.token'}).encode()
        self.context = downloads.Context(downloads.Limits(1024**2, 1024**2, 0, 10, 3), lambda: True)

    def source(self, events):
        calls = []
        class Opener:
            def open(_, request, *, timeout):
                calls.append((request.full_url, dict(request.header_items()), timeout))
                event = events.pop(0)
                if isinstance(event, BaseException):
                    raise event
                return event
        return downloads.RegistrySource([self.blob], opener=Opener()), calls

    def redirect(self, host='production.cloudflare.docker.com'):
        url = ('https://' + host + '/registry-v2/docker/registry/v2/blobs/sha256/' + self.blob.digest[7:9] +
               '/' + self.blob.digest[7:] + '/data?opaque=signed')
        return urllib.error.HTTPError('https://registry-1.docker.io', 307, 'redirect', {'Location': url}, io.BytesIO())

    def test_direct_registry_request_has_exact_scope_and_digest(self):
        source, calls = self.source([Response(self.auth), Response(b'fake')])
        with source.open(self.blob, self.context) as body:
            self.assertEqual(body.read(), b'fake')
        self.assertEqual(calls[0][0], 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:nvidia/cuda:pull')
        self.assertTrue(calls[1][0].endswith('/blobs/' + self.blob.digest))
        self.assertEqual(calls[1][1]['Authorization'], 'Bearer synthetic.token')
        self.assertTrue(all(0 < call[2] <= 5 for call in calls))

    def test_one_cdn_redirect_strips_bearer_credentials(self):
        source, calls = self.source([Response(self.auth), self.redirect(), Response(b'fake')])
        with source.open(self.blob, self.context):
            pass
        self.assertNotIn('Authorization', calls[2][1])
        self.assertEqual(len(calls), 3)

    def test_unapproved_redirect_and_second_redirect_fail_without_retry(self):
        for events in ([Response(self.auth), self.redirect('foreign.invalid')],
                       [Response(self.auth), self.redirect(), self.redirect()]):
            source, calls = self.source(list(events))
            with self.assertRaises(downloads.StageError):
                source.open(self.blob, self.context)
            self.assertLessEqual(len(calls), 3)

    def test_auth_failure_or_unlocked_blob_never_reaches_registry(self):
        source, calls = self.source([Response(b'not json')])
        with self.assertRaisesRegex(downloads.StageError, 'REGISTRY_REQUEST_FAILED'):
            source.open(self.blob, self.context)
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(downloads.StageError, 'BLOB_NOT_IN_LOCK'):
            source.open(blob(b'other'), self.context)
        self.assertEqual(len(calls), 1)

    def test_redirect_origin_protocol_path_and_digest_are_restricted(self):
        base = ('https://production.cloudflare.docker.com/registry-v2/docker/registry/v2/blobs/sha256/' +
                self.blob.digest[7:9] + '/' + self.blob.digest[7:] + '/data?opaque=signed')
        variants = [base.replace('https:', 'http:'), base.replace('https://', 'https://user@'),
                    base.replace('.com/', '.com:444/'), base + '#fragment',
                    base.replace(self.blob.digest[7:], '0' * 64),
                    base.replace('/registry-v2/', '/other/'),
                    base.replace('production.cloudflare.docker.com', 'production.cloudflare.docker.com.foreign.invalid')]
        for location in variants:
            error = urllib.error.HTTPError('https://registry-1.docker.io', 307, 'redirect', {'Location': location}, io.BytesIO())
            source, calls = self.source([Response(self.auth), error])
            with self.subTest(location=location), self.assertRaises(downloads.StageError):
                source.open(self.blob, self.context)
            self.assertEqual(len(calls), 2)

    def test_registry_errors_are_redacted_and_never_retried(self):
        secret = 'signed-url-and-bearer-must-not-be-logged'
        source, calls = self.source([Response(self.auth), urllib.error.URLError(secret)])
        with self.assertRaises(downloads.StageError) as raised:
            source.open(self.blob, self.context)
        self.assertEqual(len(calls), 2)
        self.assertNotIn(secret, str(raised.exception))


if __name__ == '__main__':
    unittest.main()
