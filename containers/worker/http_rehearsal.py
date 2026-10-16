"""Bounded loopback HTTP proxy rehearsal. The upstream is always our own fake."""
import argparse
import asyncio
import hmac
import json
import secrets
import time

from request_gate import Rejected, RequestGate

HEADER_BYTES = 8192
IO_SECONDS = 1.0


async def close_writer(writer):
    if writer is not None:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 0.2)
        except (OSError, asyncio.TimeoutError):
            pass


async def headers(reader):
    raw = await reader.readuntil(b'\r\n\r\n')
    if len(raw) > HEADER_BYTES:
        raise ValueError('HEADERS_TOO_LARGE')
    lines = raw.decode('ascii').split('\r\n')
    fields = {}
    for line in lines[1:-2]:
        name, value = line.split(':', 1)
        if name != name.strip() or not name or name.lower() in fields:
            raise ValueError('INVALID_HEADERS')
        fields[name.lower()] = value.strip()
    return lines[0], fields


def body_length(fields, maximum):
    if 'transfer-encoding' in fields or 'expect' in fields:
        raise ValueError('UNSUPPORTED_FRAMING')
    value = fields.get('content-length', '')
    if not value.isascii() or not value.isdecimal() or len(value) > 8:
        raise ValueError('CONTENT_LENGTH_REQUIRED')
    length = int(value)
    if length > maximum:
        raise ValueError('REQUEST_BYTES')
    return length


async def reply(writer, status, body, content_type='application/json'):
    writer.write(f'HTTP/1.1 {status} Rehearsal\r\nContent-Type: {content_type}\r\n'
                 f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'.encode() + body)
    await asyncio.wait_for(writer.drain(), IO_SECONDS)


async def error_reply(writer, status, body):
    try:
        await reply(writer, status, body)
    except (OSError, asyncio.TimeoutError):
        pass  # The peer may already have disconnected; owned cleanup still runs.


class SSE:
    """Narrow fixture protocol: JSON data frames followed by one terminal marker."""
    def __init__(self):
        self.buffer = b''
        self.terminal = None

    def feed(self, chunk):
        self.buffer += chunk
        ready = []
        while b'\n\n' in self.buffer:
            frame, self.buffer = self.buffer.split(b'\n\n', 1)
            if len(frame) > 4096 or self.terminal is not None or not frame.startswith(b'data: '):
                raise ValueError('INVALID_SSE')
            data = frame[6:]
            if data == b'[DONE]':
                self.terminal = frame + b'\n\n'
            else:
                if not isinstance(json.loads(data), dict):
                    raise ValueError('INVALID_SSE')
                ready.append(frame + b'\n\n')
        if len(self.buffer) > 4096:
            raise ValueError('SSE_FRAME_TOO_LARGE')
        return ready

    def finish(self):
        if self.buffer or self.terminal is None:
            raise ValueError('INCOMPLETE_SSE')
        return self.terminal  # Withheld until EOF confirms no trailing data.


class Rehearsal:
    MODES = ('json', 'stream', 'silent', 'oversized', 'backend-error', 'truncated', 'trailing')

    def __init__(self, mode='json', *, clock_rate=1):
        if mode not in self.MODES or clock_rate not in (1, 100):
            raise ValueError('FIXED_FAKE_SCENARIO_REQUIRED')
        self.mode = mode
        self.clock_rate = clock_rate
        start = time.monotonic()
        self.gate = RequestGate(model='synthetic-coder', count_prompt=lambda request: 80,
                                clock=lambda: (time.monotonic() - start) * clock_rate)
        self.token = secrets.token_hex(24)
        self.lock = asyncio.Lock()
        self.stop_lock = asyncio.Lock()
        self.clients = set()
        self.backends = set()
        self.fake_started = asyncio.Event()
        self.fake_requests = self.fake_stop_requests = 0
        self.last_fake_request = None
        self.upstream_writer = None
        self.stop_requested = False
        self.closed = False
        self.handler_errors = 0

    def spawn(self, group, handler, reader, writer):
        if len(group) >= 4:
            writer.close()
            return
        task = asyncio.create_task(handler(reader, writer))
        group.add(task)
        def completed(task):
            group.discard(task)
            if not task.cancelled() and task.exception() is not None:
                self.handler_errors += 1
        task.add_done_callback(completed)

    async def __aenter__(self):
        self.backend = await asyncio.start_server(
            lambda r, w: self.spawn(self.backends, self.fake, r, w), '127.0.0.1', 0,
            limit=HEADER_BYTES)
        try:
            self.proxy = await asyncio.start_server(
                lambda r, w: self.spawn(self.clients, self.client, r, w), '127.0.0.1', 0,
                limit=HEADER_BYTES)
        except BaseException:
            self.backend.close()
            await self.backend.wait_closed()
            raise
        self.watchdog = asyncio.create_task(self.watch())
        return self

    async def __aexit__(self, *args):
        for server in (self.proxy, self.backend):
            server.close()
        self.watchdog.cancel()
        await asyncio.gather(self.watchdog, return_exceptions=True)
        tasks = list(self.clients | self.backends)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close_writer(self.upstream_writer)
        for server in (self.proxy, self.backend):
            await asyncio.wait_for(server.wait_closed(), 1)
        self.closed = True

    async def stop_fake(self):
        async with self.stop_lock:
            if self.stop_requested:
                return
            self.stop_requested = True
            self.fake_stop_requests += 1
            await close_writer(self.upstream_writer)
            # Explicitly stop only fake tasks owned by this fixture. Closing a
            # socket alone is NOT proof that a real inference engine stopped.
            tasks = list(self.backends)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def trip(self, operation):
        async with self.lock:
            try:
                operation()
            except Rejected:
                pass
        await self.stop_fake()

    async def watch(self):
        while True:
            await asyncio.sleep(0.02)
            async with self.lock:
                try:
                    self.gate.check()
                except Rejected:
                    pass
                fault = self.gate.fault
            if fault:
                await self.stop_fake()

    async def fake(self, reader, writer):
        try:
            async with asyncio.timeout(IO_SECONDS):
                _, fields = await headers(reader)
                raw = await reader.readexactly(body_length(fields, 65536))
            self.last_fake_request = json.loads(raw)
            self.fake_requests += 1
            self.fake_started.set()
            if self.mode == 'silent':
                await asyncio.Event().wait()
            elif self.mode == 'backend-error':
                await reply(writer, 503, b'private fake backend error')
            elif self.mode == 'oversized':
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                             b'Content-Length: 65537\r\nConnection: close\r\n\r\n')
                await writer.drain()
            elif self.mode == 'json':
                await reply(writer, 200, json.dumps({'choices': [{'message': {
                    'role': 'assistant', 'content': 'synthetic OK'}, 'finish_reason': 'stop'}]}).encode())
            else:
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n'
                             b'Connection: close\r\n\r\n')
                frame = b'data: {"choices":[{"delta":{"content":"synthetic OK"}}]}\n\n'
                # Fragment an event across TCP writes to exercise buffering.
                for offset in range(0, len(frame), 7):
                    writer.write(frame[offset:offset + 7])
                    await writer.drain()
                    await asyncio.sleep(0.001)
                if self.mode != 'truncated':
                    writer.write(b'data: [DONE]\n\n')
                if self.mode == 'trailing':
                    writer.write(frame)
                await writer.drain()
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        finally:
            await close_writer(writer)

    async def client(self, reader, writer):
        sent = False
        relay = disconnected = None
        admitted = None
        try:
            async with asyncio.timeout(IO_SECONDS):
                first, fields = await headers(reader)
                if first != 'POST /v1/chat/completions HTTP/1.1':
                    raise ValueError('ROUTE_DENIED')
                if not hmac.compare_digest(fields.get('authorization', ''), 'Bearer ' + self.token):
                    await reply(writer, 401, b'{"error":"UNAUTHORIZED"}')
                    return
                if fields.get('content-type') != 'application/json':
                    raise ValueError('CONTENT_TYPE_REQUIRED')
                raw = await reader.readexactly(body_length(fields, self.gate.limits.request_bytes))
            async with self.lock:
                admitted = self.gate.admit(raw)
            relay = asyncio.create_task(self.relay(admitted, writer))
            disconnected = asyncio.create_task(reader.read(1))
            done, _ = await asyncio.wait((relay, disconnected), return_when=asyncio.FIRST_COMPLETED)
            if disconnected in done and not relay.done():
                await self.trip(self.gate.cancel)
                relay.cancel()
            else:
                sent = await relay
        except Rejected as error:
            if self.gate.fault:
                await self.stop_fake()
            if not sent:
                await error_reply(writer, 409, json.dumps({'error': str(error)}).encode())
        except (ValueError, asyncio.LimitOverrunError, asyncio.IncompleteReadError, asyncio.TimeoutError):
            if admitted is None:
                await error_reply(writer, 400, b'{"error":"INVALID_HTTP_REQUEST"}')
            else:
                await self.trip(self.gate.backend_failed)
        except OSError:
            if admitted is not None:
                await self.trip(self.gate.cancel)
        finally:
            for task in (relay, disconnected):
                if task is not None:
                    task.cancel()
            await asyncio.gather(*(t for t in (relay, disconnected) if t is not None),
                                 return_exceptions=True)
            await close_writer(writer)

    async def relay(self, admitted, client_writer):
        sent = False
        upstream = None
        try:
            port = self.backend.sockets[0].getsockname()[1]
            async with asyncio.timeout(IO_SECONDS):
                reader, upstream = await asyncio.open_connection('127.0.0.1', port, limit=HEADER_BYTES)
                self.upstream_writer = upstream
                raw = json.dumps(admitted['request'], separators=(',', ':')).encode()
                upstream.write(f'POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                               f'Content-Type: application/json\r\nContent-Length: {len(raw)}\r\n'
                               f'Connection: close\r\n\r\n'.encode() + raw)
                await upstream.drain()
                first, fields = await headers(reader)
            stream = admitted['request'].get('stream', False)
            content_type = 'text/event-stream' if stream else 'application/json'
            if first.split(' ', 2)[:2] != ['HTTP/1.1', '200'] or fields.get('content-type') != content_type:
                raise ValueError('BACKEND_PROTOCOL')
            if 'transfer-encoding' in fields or 'content-encoding' in fields:
                raise ValueError('BACKEND_FRAMING')
            length = None
            if 'content-length' in fields:
                length = body_length(fields, 99999999)
                if length > self.gate.limits.response_bytes:
                    async with self.lock:
                        self.gate._fault('RESPONSE_BYTES')
            sse = SSE() if stream else None
            body = bytearray()
            while True:
                async with self.lock:
                    self.gate.check()
                chunk = await reader.read(4096)  # Watchdog closes this during silent faults.
                if not chunk:
                    break
                async with self.lock:
                    self.gate.output(admitted['callId'], chunk)
                if sse:
                    frames = sse.feed(chunk)
                    if not sent:
                        client_writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n'
                                            b'Connection: close\r\n\r\n')
                        sent = True
                    for frame in frames:
                        client_writer.write(frame)
                    await asyncio.wait_for(client_writer.drain(), IO_SECONDS)
                else:
                    body.extend(chunk)
            if length is not None and self.gate.active['responseBytes'] != length:
                raise ValueError('TRUNCATED_BODY')
            terminal = sse.finish() if sse else None
            if not sse and not isinstance(json.loads(body), dict):
                raise ValueError('INVALID_JSON_RESPONSE')
            async with self.lock:
                self.gate.finish(admitted['callId'])
            if sse:
                client_writer.write(terminal)
                await asyncio.wait_for(client_writer.drain(), IO_SECONDS)
            else:
                await reply(client_writer, 200, bytes(body))
            return True
        except (Rejected, ValueError, OSError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError, asyncio.TimeoutError):
            await self.trip(self.gate.backend_failed)
            if not sent:
                await error_reply(client_writer, 502, b'{"error":"FAKE_UPSTREAM_STOPPED"}')
            return True
        finally:
            await close_writer(upstream)

    async def call(self, raw=None, *, token=None):
        """Test client; no user-selectable destination."""
        port = self.proxy.sockets[0].getsockname()[1]
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            '127.0.0.1', port, limit=HEADER_BYTES), IO_SECONDS)
        try:
            if raw is None:
                raw = json.dumps({'model': 'synthetic-coder', 'messages': [{'role': 'user',
                    'content': 'Fake task only.'}], 'stream': self.mode in ('stream', 'truncated', 'trailing')}).encode()
            auth = self.token if token is None else token
            writer.write(f'POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                         f'Authorization: Bearer {auth}\r\nContent-Type: application/json\r\n'
                         f'Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n'.encode() + raw)
            await writer.drain()
            async with asyncio.timeout(3):
                first, _ = await headers(reader)
                body = bytearray()
                while chunk := await reader.read(4096):
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise ValueError('TEST_CLIENT_RESPONSE_LIMIT')
            return int(first.split()[1]), bytes(body)
        finally:
            await close_writer(writer)

    def snapshot(self):
        return {**self.gate.snapshot(), 'mode': 'http-fake-backend-only',
                'tokenCounter': 'synthetic-fixed-count', 'clockRate': self.clock_rate,
                'fakeRequests': self.fake_requests, 'fakeStopRequests': self.fake_stop_requests,
                'serversClosed': self.closed,
                'cleanupConfirmed': self.closed and not self.clients and not self.backends,
                'handlerErrors': self.handler_errors, 'strataContacted': False}


async def demonstrate(scenario):
    mode = {'success': 'json', 'call-limit': 'json', 'timeout': 'silent',
            'oversized-response': 'oversized', 'cancel': 'silent'}.get(scenario, scenario)
    async with Rehearsal(mode, clock_rate=100 if scenario == 'timeout' else 1) as session:
        if scenario == 'cancel':
            pending = asyncio.create_task(session.call())
            await asyncio.wait_for(session.fake_started.wait(), 1)
            await session.trip(session.gate.cancel)
            status, body = await pending
        else:
            status, body = await session.call()
            if scenario == 'call-limit':
                await session.call()
                status, body = await session.call()
        if session.gate.fault is None:
            session.gate.close()
    return {**session.snapshot(), 'scenario': scenario, 'httpStatus': status,
            'clientResponseBytes': len(body)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('success', 'stream', 'call-limit', 'timeout',
                        'oversized-response', 'cancel', 'truncated', 'trailing', 'backend-error'),
                        default='success')
    args = parser.parse_args()
    result = asyncio.run(demonstrate(args.scenario))
    print(json.dumps(result))
    raise SystemExit(3 if result['fault'] else 0)
