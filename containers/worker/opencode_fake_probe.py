"""Container-only OpenCode compatibility test against owned loopback fake servers."""
import asyncio
import json
import os
from pathlib import Path
import signal
import difflib

from http_rehearsal import Rehearsal, body_length, close_writer, headers
from request_gate import RequestGate


def denial_kind(feedback, scenario):
    expected = {'deny-shell': ('Permission denied: shell',),
                'deny-external': ('Permission denied: external_directory', 'Permission denied: read'),
                'deny-file-write': ('Permission denied: edit',)}.get(scenario, ())
    for item in feedback:
        try:
            error = json.loads(item).get('error', {})
            if not isinstance(error, dict):
                continue
            if error.get('type') == 'permission.rejected' and error.get('message') in expected:
                return 'permission-denied'
            if (scenario == 'deny-shell' and error.get('type') == 'tool.execution' and
                    error.get('message', '').startswith('No tool named "shell" is currently available')):
                return 'tool-unavailable'
        except (ValueError, AttributeError):
            pass
    return None


class RecordingGate(RequestGate):
    def admit(self, raw):
        request = json.loads(raw)
        self.request_fields = sorted(request)[:24]
        self.request_summaries = getattr(self, 'request_summaries', [])
        if len(self.request_summaries) < 8:
            self.request_summaries.append({'fields': self.request_fields,
                'toolNames': [tool.get('function', {}).get('name') for tool in request.get('tools', [])]})
        return super().admit(raw)


class Fixture(Rehearsal):
    def __init__(self, scenario='reply'):
        super().__init__()
        self.scenario = scenario
        self.feedback = []
        self.secret_leaked = False

    async def fake(self, reader, writer):
        try:
            async with asyncio.timeout(1):
                _, fields = await headers(reader)
                request = json.loads(await reader.readexactly(body_length(fields, 65536)))
            self.fake_requests += 1
            self.fake_started.set()
            self.secret_leaked |= 'FAKE-PRIVATE-CONTENT-9371' in json.dumps(request)
            self.feedback.extend(message.get('content', '')[:512] for message in request['messages']
                                 if message.get('role') == 'tool')
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n')
            tool = None
            if self.fake_requests == 1:
                if self.scenario == 'edit':
                    tool = ('edit', {'path': '/tmp/workspace/example.py',
                                    'oldString': 'VALUE = 1', 'newString': 'VALUE = 2'})
                elif self.scenario == 'deny-shell':
                    tool = ('shell', {'command': 'printf blocked > /tmp/forbidden-shell-marker'})
                elif self.scenario == 'deny-external':
                    tool = ('read', {'path': '/tmp/outside/private.txt'})
                elif self.scenario == 'deny-file-write':
                    tool = ('write', {'path': '/tmp/workspace/other.py', 'content': 'UNAPPROVED = 1\n'})
            chunks = [({'role': 'assistant', 'content': 'synthetic OK'}, None), ({}, 'stop')]
            if tool:
                chunks = [({'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'fixture-tool-1',
                    'type': 'function', 'function': {'name': tool[0], 'arguments': json.dumps(tool[1])}}]}, None),
                    ({}, 'tool_calls')]
            for delta, finish in chunks:
                event = {'id': 'fake-completion', 'object': 'chat.completion.chunk', 'created': 1,
                         'model': request['model'], 'choices': [{'index': 0, 'delta': delta,
                                                               'finish_reason': finish}]}
                writer.write(b'data: ' + json.dumps(event).encode() + b'\n\n')
            writer.write(b'data: [DONE]\n\n')
            await writer.drain()
        finally:
            await close_writer(writer)


async def run():
    signal.alarm(10)
    workspace = Path('/tmp/workspace')
    workspace.mkdir(parents=True)
    example = workspace / 'example.py'
    example.write_text('VALUE = 1\n')
    outside = Path('/tmp/outside/private.txt')
    outside.parent.mkdir()
    outside.write_text('FAKE-PRIVATE-CONTENT-9371\n')
    scenario = json.loads(Path('/input/scenario.json').read_text())['scenario']
    if scenario not in ('reply', 'edit', 'deny-shell', 'deny-external', 'deny-file-write'):
        raise ValueError('FIXED_SCENARIO_REQUIRED')
    rules = {'*': 'deny', 'read': {'*': 'deny', 'example.py': 'allow'},
             'edit': {'*': 'deny', 'example.py': 'allow'}, 'external_directory': 'deny'}
    async with Fixture(scenario) as session:
        session.gate = RecordingGate(model='synthetic-coder', count_prompt=lambda request: 80)
        port = session.proxy.sockets[0].getsockname()[1]
        config = {'model': 'strata/synthetic-coder', 'small_model': 'strata/synthetic-coder',
                  'enabled_providers': ['strata'], 'autoupdate': False, 'share': 'disabled',
                  'snapshot': False, 'formatter': False, 'lsp': False,
                  'plugin': [], 'mcp': {}, 'instructions': [], 'compaction': {'auto': False},
                  'permission': rules, 'default_agent': 'bounded',
                  'agent': {'title': {'disable': True},
                            'bounded': {'description': 'Fake-only compatibility test', 'mode': 'primary',
                                       'steps': 2, 'permission': rules}},
                  'provider': {'strata': {'npm': '@ai-sdk/openai-compatible',
                              'options': {'baseURL': f'http://127.0.0.1:{port}/v1', 'apiKey': session.token},
                              'models': {'synthetic-coder': {'name': 'Owned fake server',
                                                           'limit': {'context': 8192, 'output': 512}}}}}}
        env = {'PATH': os.environ['PATH'], 'LD_LIBRARY_PATH': '/input/libs', 'HOME': '/tmp/home',
               'XDG_CONFIG_HOME': '/tmp/config', 'XDG_DATA_HOME': '/tmp/data', 'XDG_CACHE_HOME': '/tmp/cache',
               'OPENCODE_CONFIG_CONTENT': json.dumps(config)}
        env.update({key: 'true' for key in ('OPENCODE_DISABLE_AUTOUPDATE', 'OPENCODE_DISABLE_MODELS_FETCH',
                   'OPENCODE_DISABLE_DEFAULT_PLUGINS', 'OPENCODE_DISABLE_LSP_DOWNLOAD',
                   'OPENCODE_DISABLE_AUTOCOMPACT', 'OPENCODE_DISABLE_CLAUDE_CODE')})
        process = await asyncio.create_subprocess_exec('/input/opencode', 'run', '--standalone', '--format', 'json',
                  '--model', 'strata/synthetic-coder', '--agent', 'bounded',
                  'Only change example.py from VALUE = 1 to VALUE = 2. Do not run commands or access other files.',
                  env=env, cwd=workspace,
                  stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 6)
        except asyncio.TimeoutError:
            timed_out = True
            process.kill()
            stdout, stderr = await process.communicate()
        request_fields = getattr(session.gate, 'request_fields', [])
        gate = session.gate.snapshot()
    leaked = session.secret_leaked or b'FAKE-PRIVATE-CONTENT-9371' in stdout or b'FAKE-PRIVATE-CONTENT-9371' in stderr
    stdout = stdout[:8192].decode(errors='replace').replace(session.token, '[redacted]')
    stderr = stderr[:4096].decode(errors='replace').replace(session.token, '[redacted]')
    feedback = '\n'.join(session.feedback)
    denied = denial_kind(session.feedback, scenario)
    changed = example.read_text() != 'VALUE = 1\n'
    scenario_passed = {'reply': not changed and session.fake_requests == 1,
                      'edit': example.read_text() == 'VALUE = 2\n',
                      'deny-shell': denied is not None and not changed and
                                    not Path('/tmp/forbidden-shell-marker').exists(),
                      'deny-external': denied == 'permission-denied' and not changed and not leaked,
                      'deny-file-write': denied == 'permission-denied' and not changed and
                                         not (workspace / 'other.py').exists()}[scenario]
    return {'mode': 'opencode-fake-only', 'exitCode': process.returncode, 'timedOut': timed_out,
            'scenario': scenario, 'scenarioPassed': scenario_passed,
            'stdout': stdout, 'stderr': stderr, 'requestFields': request_fields,
            'requestSummaries': getattr(session.gate, 'request_summaries', []), 'toolFeedback': feedback[:1024],
            'forbiddenMarkerCreated': Path('/tmp/forbidden-shell-marker').exists(),
            'fixtureSecretLeaked': leaked, 'denialKind': denied,
            'unlistedFileCreated': (workspace / 'other.py').exists(),
            'fakeRequests': session.fake_requests, 'gate': gate,
            'serversClosed': session.closed, 'handlerErrors': session.handler_errors,
            'workspaceChanged': changed,
            'patch': ''.join(difflib.unified_diff(['VALUE = 1\n'], example.read_text().splitlines(keepends=True),
                                                 fromfile='a/example.py', tofile='b/example.py')),
            'compatibilityPassed': process.returncode == 0 and not timed_out and
                session.fake_requests >= 1 and gate['fault'] is None and 'synthetic OK' in stdout and scenario_passed,
            'modelEnabled': False, 'strataContacted': False}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(run())))
