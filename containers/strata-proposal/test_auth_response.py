import http.client
import io
import json
from pathlib import Path
import tempfile
import unittest

import image_download as download
from test_image_download import Response, blob


def wire(payload, *, ending=b'0\r\n\r\n', chunk=None, extra_headers=b''):
    class Socket:
        def makefile(self, _mode):
            encoded = chunk if chunk is not None else (f'{len(payload):x}\r\n'.encode() + payload + b'\r\n' + ending)
            return io.BytesIO(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n' + extra_headers + b'\r\n' + encoded)
    response = http.client.HTTPResponse(Socket())
    response.begin()
    return response


class AuthResponseTests(unittest.TestCase):
    def context(self, *, guard=lambda: True, payload=1024**2, clock=None):
        return download.Context(download.Limits(payload, 1024**2, 0, 10, 5), guard,
                                **({'clock': clock} if clock else {}))

    def source(self, auth, context=None, observations=None):
        payload = b'fixture-blob'
        spec = blob(payload)
        calls = []
        class Opener:
            def open(self, request, *, timeout):
                calls.append(request.full_url)
                return auth if len(calls) == 1 else Response(payload)
        return (download.RegistrySource([spec], opener=Opener(),
                    on_auth_headers=(observations.append if observations is not None else None)),
                spec, context or self.context(), calls)

    def test_observed_chunked_auth_works_with_real_http_decoder_without_weakening_blobs(self):
        token = json.dumps({'token': 'synthetic.token'}).encode()
        observations = []
        source, spec, context, calls = self.source(wire(token), observations=observations)
        with source.open(spec, context) as body:
            self.assertEqual(body.read(), b'fixture-blob')
        self.assertEqual(context.auth_bytes, len(token))
        self.assertEqual(len(calls), 2)
        self.assertEqual(observations[0]['transferEncoding'], 'chunked')
        self.assertEqual(observations[0]['contentLengthCount'], 0)
        self.assertNotIn('synthetic.token', json.dumps(observations))
        with wire(b'fixture-blob') as response:
            with self.assertRaisesRegex(ValueError, 'HTTP_FRAMING_INVALID'):
                download.response_length(response, spec.size)

    def test_content_length_auth_remains_compatible(self):
        payload = b'{"token":"synthetic.token"}'
        source, spec, context, calls = self.source(Response(payload))
        with source.open(spec, context):
            pass
        self.assertEqual(context.auth_bytes, len(payload))
        self.assertEqual(len(calls), 2)

    def test_conflicting_duplicate_compressed_and_unframed_auth_are_rejected_before_body(self):
        cases = [[], [('Content-Length', '1'), ('Transfer-Encoding', 'chunked')],
                 [('Transfer-Encoding', 'chunked'), ('Transfer-Encoding', 'chunked')],
                 [('Transfer-Encoding', 'gzip, chunked')], [('Transfer-Encoding', 'gzip')],
                 [('Transfer-Encoding', 'chunked'), ('Content-Encoding', 'gzip')],
                 [('Content-Length', '1'), ('Content-Length', '1')], [('Content-Length', '-1')],
                 [('Content-Length', str(download.AUTH_BYTES + 1))]]
        for headers in cases:
            response = Response(b'x', headers=headers)
            response.version = 11
            source, spec, context, calls = self.source(response)
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                source.open(spec, context)
            self.assertEqual(context.auth_bytes, 0)
            self.assertEqual(len(calls), 1)

    def test_auth_requires_http11_for_chunking_and_success_status(self):
        for status, version in ((200, 10), (200, None), (401, 11), (204, 11)):
            response = Response(b'x', headers=[('Transfer-Encoding', 'chunked')], status=status)
            response.version = version
            source, spec, _, calls = self.source(response)
            with self.assertRaises(ValueError):
                source.open(spec, self.context())
            self.assertEqual(len(calls), 1)

    def test_decoded_auth_body_cap_counts_overflow_probe_without_retaining_it(self):
        context = self.context()
        with wire(b'x' * download.AUTH_BYTES) as response:
            self.assertEqual(len(download.read_auth(response, context)), download.AUTH_BYTES)
        self.assertEqual(context.auth_bytes, download.AUTH_BYTES)
        context = self.context()
        with wire(b'x' * (download.AUTH_BYTES + 20)) as response:
            with self.assertRaisesRegex(ValueError, 'AUTH_BODY_LIMIT'):
                download.read_auth(response, context)
        self.assertEqual(context.auth_bytes, download.AUTH_BYTES + 1)

    def test_truncated_invalid_and_unterminated_wire_fail_before_blob_request(self):
        token = b'{"token":"synthetic.token"}'
        variants = [wire(token, ending=b''), wire(token, chunk=b'xx\r\n' + token + b'\r\n0\r\n\r\n'),
                    wire(token, chunk=b'ffff\r\n' + token)]
        for response in variants:
            source, spec, context, calls = self.source(response)
            with self.assertRaisesRegex(ValueError, 'TRANSPORT_READ_FAILED'):
                source.open(spec, context)
            self.assertEqual(len(calls), 1)

    def test_shared_payload_budget_and_cancel_still_apply_inside_chunked_auth(self):
        token = b'{"token":"synthetic.token"}'
        context = self.context(payload=5)
        source, spec, _, calls = self.source(wire(token), context)
        with self.assertRaisesRegex(ValueError, 'PAYLOAD_BUDGET_EXCEEDED'):
            source.open(spec, context)
        self.assertEqual(len(calls), 1)
        allowed = [True]
        response = wire(token)
        read = response.read1
        def cancel(count):
            data = read(count)
            allowed[0] = False
            return data
        response.read1 = cancel
        source, spec, context, calls = self.source(response, self.context(guard=lambda: allowed[0]))
        with self.assertRaisesRegex(ValueError, 'GUARD_PERMISSION_LOST'):
            source.open(spec, context)
        self.assertEqual(len(calls), 1)

    def test_deadline_during_decoding_prevents_registry_request(self):
        now = [0.0]
        response = wire(b'{"token":"synthetic.token"}')
        read = response.read1
        def expire(count):
            data = read(count)
            now[0] = 20
            return data
        response.read1 = expire
        source, spec, context, calls = self.source(response, self.context(clock=lambda: now[0]))
        with self.assertRaisesRegex(ValueError, 'STAGING_DEADLINE'):
            source.open(spec, context)
        self.assertEqual(len(calls), 1)

    def test_framing_observations_do_not_log_raw_values_urls_or_token(self):
        secret = 'sensitive-url-token-or-header-value'
        response = Response(b'', headers=[('Transfer-Encoding', secret), ('Set-Cookie', secret),
                           ('Authorization', secret), ('Content-Encoding', secret)])
        record = download.auth_framing_summary(response)
        self.assertNotIn(secret, json.dumps(record))
        self.assertEqual(record['transferEncoding'], 'other')
        self.assertEqual(record['contentEncoding'], 'other')

    def test_header_envelope_is_still_bounded(self):
        for headers in ([('Transfer-Encoding', 'chunked')] * 101,
                        [('Transfer-Encoding', 'chunked'), ('X-Long', 'x' * 8192)]):
            response = Response(b'x', headers=headers)
            response.version = 11
            source, spec, context, calls = self.source(response)
            with self.assertRaisesRegex(ValueError, 'HTTP_HEADERS_INVALID'):
                source.open(spec, context)
            self.assertEqual(len(calls), 1)
            self.assertEqual(context.auth_bytes, 0)

    def test_chunk_extensions_and_multiple_chunks_use_decoded_body_budget(self):
        token = b'{"token":"synthetic.token"}'
        parts = [token[:3], token[3:]]
        encoded = b''.join(f'{len(p):x};fixture=yes\r\n'.encode() + p + b'\r\n' for p in parts)
        response = wire(token, chunk=encoded + b'0\r\nX-Trailer: ignored\r\n\r\n')
        context = self.context()
        self.assertEqual(download.read_auth(response, context), token)
        self.assertEqual(context.auth_bytes, len(token))


if __name__ == '__main__':
    unittest.main()
