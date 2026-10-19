import asyncio
import json
import unittest

from http_rehearsal import Rehearsal, demonstrate, headers, close_writer


class HTTPRehearsalTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_request_is_capped_and_cleanup_is_confirmed(self):
        async with Rehearsal() as session:
            status, body = await session.call()
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['choices'][0]['message']['content'], 'synthetic OK')
            self.assertEqual(session.last_fake_request['max_tokens'], 512)
            self.assertEqual(session.gate.calls, 1)
            self.assertEqual(session.gate.charged_tokens, 592)
            self.assertEqual(session.gate.state, 'READY')
        self.assertTrue(session.snapshot()['cleanupConfirmed'])
        self.assertEqual(session.snapshot()['handlerErrors'], 0)
        self.assertFalse(session.snapshot()['strataContacted'])

    async def test_fragmented_stream_is_reassembled_and_terminated(self):
        async with Rehearsal('stream') as session:
            status, body = await session.call()
            self.assertEqual(status, 200)
            self.assertIn(b'"synthetic OK"', body)
            self.assertTrue(body.endswith(b'data: [DONE]\n\n'))
            self.assertEqual(body.count(b'[DONE]'), 1)
            self.assertEqual(session.gate.state, 'READY')

    async def test_missing_or_extra_terminal_data_faults(self):
        for mode in ('truncated', 'trailing'):
            async with Rehearsal(mode) as session:
                _, body = await session.call()
                self.assertNotIn(b'[DONE]', body)
                self.assertEqual(session.gate.fault, 'BACKEND_FAILURE')
                self.assertEqual(session.fake_stop_requests, 1)
            self.assertTrue(session.snapshot()['cleanupConfirmed'])

    async def test_wrong_authentication_never_reaches_backend(self):
        async with Rehearsal() as session:
            status, _ = await session.call(token='wrong-token')
            self.assertEqual(status, 401)
            self.assertEqual(session.fake_requests, 0)
            self.assertEqual(session.gate.calls, 0)
            self.assertIsNone(session.gate.fault)

    async def test_budget_exhaustion_blocks_third_backend_request(self):
        async with Rehearsal() as session:
            await session.call()
            await session.call()
            status, body = await session.call()
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(body)['error'], 'CALL_BUDGET')
            self.assertEqual(session.fake_requests, 2)
            self.assertEqual(session.gate.fault, 'CALL_BUDGET')

    async def test_disallowed_model_is_rejected_before_forwarding(self):
        async with Rehearsal() as session:
            raw = json.dumps({'model': 'other', 'messages': [{'role': 'user', 'content': 'x'}]}).encode()
            status, _ = await session.call(raw)
            self.assertEqual(status, 409)
            self.assertEqual(session.fake_requests, 0)
            self.assertIsNone(session.gate.fault)

    async def test_parallel_http_request_is_rejected_without_stopping_first(self):
        async with Rehearsal('silent') as session:
            pending = asyncio.create_task(session.call())
            await asyncio.wait_for(session.fake_started.wait(), 1)
            status, body = await session.call()
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(body)['error'], 'CALL_ALREADY_ACTIVE')
            self.assertEqual(session.fake_requests, 1)
            self.assertEqual(session.fake_stop_requests, 0)
            self.assertIsNone(session.gate.fault)
            await session.trip(session.gate.cancel)
            await pending

    async def test_incomplete_request_body_times_out_before_admission(self):
        async with Rehearsal() as session:
            reader, writer = await asyncio.open_connection(
                '127.0.0.1', session.proxy.sockets[0].getsockname()[1])
            try:
                writer.write(f'POST /v1/chat/completions HTTP/1.1\r\n'
                             f'Authorization: Bearer {session.token}\r\n'
                             f'Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{{'.encode())
                await writer.drain()
                first, _ = await asyncio.wait_for(headers(reader), 2)
                self.assertIn(' 400 ', first)
                self.assertEqual(session.gate.calls, 0)
                self.assertEqual(session.fake_requests, 0)
            finally:
                await close_writer(writer)

    async def test_oversized_response_is_stopped_before_relay(self):
        async with Rehearsal('oversized') as session:
            status, body = await session.call()
            self.assertEqual(status, 502)
            self.assertNotIn(b'xxxxx', body)
            self.assertEqual(session.gate.fault, 'RESPONSE_BYTES')
            self.assertEqual(session.fake_stop_requests, 1)

    async def test_silent_backend_hits_accelerated_deadline_and_fault_latches(self):
        async with Rehearsal('silent', clock_rate=100) as session:
            status, _ = await session.call()
            self.assertEqual(status, 502)
            self.assertEqual(session.gate.fault, 'CALL_DEADLINE')
            status, _ = await session.call()
            self.assertEqual(status, 409)
            self.assertEqual(session.fake_requests, 1)
        self.assertTrue(session.snapshot()['cleanupConfirmed'])

    async def test_explicit_cancellation_stops_owned_fake_job(self):
        async with Rehearsal('silent') as session:
            pending = asyncio.create_task(session.call())
            await asyncio.wait_for(session.fake_started.wait(), 1)
            await session.trip(session.gate.cancel)
            status, _ = await pending
            self.assertEqual(status, 502)
            self.assertEqual(session.gate.fault, 'CANCELLED')
            self.assertFalse(session.backends)

    async def test_client_disconnect_cancels_without_waiting_for_call_timeout(self):
        async with Rehearsal('silent') as session:
            pending = asyncio.create_task(session.call())
            await asyncio.wait_for(session.fake_started.wait(), 1)
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
            async with asyncio.timeout(1):
                while session.gate.fault is None or session.backends:
                    await asyncio.sleep(0.01)
            self.assertEqual(session.gate.fault, 'CANCELLED')
            self.assertEqual(session.fake_stop_requests, 1)

    async def test_backend_error_is_sanitized(self):
        async with Rehearsal('backend-error') as session:
            status, body = await session.call()
            self.assertEqual(status, 502)
            self.assertNotIn(b'private', body)
            self.assertEqual(session.gate.fault, 'BACKEND_FAILURE')

    async def test_http_framing_and_route_rejections(self):
        for extra, route in [('Content-Length: 0\r\nContent-Length: 0\r\n', '/v1/chat/completions'),
                             ('Transfer-Encoding: chunked\r\n', '/v1/chat/completions'),
                             ('Content-Length: 65537\r\n', '/v1/chat/completions'),
                             ('Content-Length: 0\r\n', '/not-allowed')]:
            async with Rehearsal() as session:
                reader, writer = await asyncio.open_connection(
                    '127.0.0.1', session.proxy.sockets[0].getsockname()[1])
                try:
                    writer.write(f'POST {route} HTTP/1.1\r\nAuthorization: Bearer {session.token}\r\n'
                                 f'Content-Type: application/json\r\n{extra}\r\n'.encode())
                    await writer.drain()
                    first, _ = await asyncio.wait_for(headers(reader), 1)
                    self.assertIn(' 400 ', first)
                    self.assertEqual(session.fake_requests, 0)
                finally:
                    await close_writer(writer)

    async def test_context_exit_cleans_up_an_active_rehearsal(self):
        async with Rehearsal('silent') as session:
            pending = asyncio.create_task(session.call())
            await asyncio.wait_for(session.fake_started.wait(), 1)
            port = session.proxy.sockets[0].getsockname()[1]
        await asyncio.gather(pending, return_exceptions=True)
        self.assertTrue(session.snapshot()['cleanupConfirmed'])
        with self.assertRaises(OSError):
            await asyncio.open_connection('127.0.0.1', port)

    async def test_cli_demonstration_marks_all_work_as_fake(self):
        result = await demonstrate('stream')
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(result['mode'], 'http-fake-backend-only')
        self.assertFalse(result['executionEnabled'])
        self.assertFalse(result['modelEnabled'])
        self.assertTrue(result['cleanupConfirmed'])
        self.assertEqual(result['handlerErrors'], 0)
        self.assertNotIn('Bearer', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
