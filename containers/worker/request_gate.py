"""Offline request-budget state machine. No HTTP, process, model, or Docker calls."""
import argparse
from dataclasses import dataclass
import json
import math
import time


@dataclass(frozen=True)
class Limits:
    """Simulation limits only; not an owner-approved live policy."""
    calls: int = 2
    context_tokens: int = 8192
    context_reserve: int = 256
    task_tokens: int = 8192
    output_tokens: int = 512
    request_bytes: int = 65536
    response_bytes: int = 65536
    task_seconds: float = 60
    call_seconds: float = 15


class Rejected(ValueError):
    pass


def object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('NONFINITE_JSON_NUMBER')
    return number


class RequestGate:
    """Serialized, single-owner core; the future proxy must enforce transport stops.

    count_prompt must count the complete rendered model prompt, including tools
    and chat-template tokens. There is deliberately no default token counter.
    No admission in this module authorizes live execution.
    """
    def __init__(self, *, model, count_prompt, clock=time.monotonic):
        if not isinstance(model, str) or not model or not callable(count_prompt):
            raise ValueError('MODEL_AND_TOKEN_COUNTER_REQUIRED')
        self.limits = Limits()
        self.model = model
        self.count_prompt = count_prompt
        self.clock = clock
        self.started = self.last_time = self.clock()
        if type(self.started) not in (int, float) or not math.isfinite(self.started):
            raise ValueError('INVALID_CLOCK')
        self.state = 'READY'
        self.fault = None
        self.active = None
        self.calls = self.charged_tokens = 0
        self.events = []

    def _fault(self, code):
        if self.fault is None:
            self.fault = code
            self.state = 'FAULT'
            self.events.append({'event': 'FAULT', 'code': code})
        raise Rejected(self.fault)

    def check(self):
        """Must also be polled while the future transport is silent or blocked."""
        if self.fault:
            raise Rejected(self.fault)
        if self.state == 'COMPLETE':
            raise Rejected('TASK_CLOSED')
        now = self.clock()
        if (type(now) not in (int, float) or not math.isfinite(now) or
                now < self.last_time):
            self._fault('CLOCK_INVALID')
        self.last_time = now
        if now - self.started >= self.limits.task_seconds:
            self._fault('TASK_DEADLINE')
        if self.active and now >= self.active['deadline']:
            self._fault('CALL_DEADLINE')
        return now

    def admit(self, raw):
        self.check()
        if self.active:
            raise Rejected('CALL_ALREADY_ACTIVE')
        if self.calls >= self.limits.calls:
            self._fault('CALL_BUDGET')
        if not isinstance(raw, bytes) or len(raw) > self.limits.request_bytes:
            raise Rejected('REQUEST_BYTES')
        try:
            request = json.loads(raw.decode('utf-8'), object_pairs_hook=object_without_duplicates,
                                 parse_float=finite_float,
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError, RecursionError):
            raise Rejected('INVALID_JSON') from None
        allowed = {'model', 'messages', 'tools', 'tool_choice', 'stream', 'max_tokens',
                   'store', 'stream_options', 'max_completion_tokens'}
        if not isinstance(request, dict) or set(request) - allowed:
            raise Rejected('UNSUPPORTED_REQUEST_FIELDS')
        if request.get('model') != self.model:
            raise Rejected('MODEL_MISMATCH')
        messages = request.get('messages')
        if not isinstance(messages, list) or not 1 <= len(messages) <= 32:
            raise Rejected('INVALID_MESSAGES')
        for message in messages:
            if (not isinstance(message, dict) or
                    set(message) - {'role', 'content', 'tool_calls', 'tool_call_id', 'name'} or
                    message.get('role') not in ('system', 'user', 'assistant', 'tool') or
                    not (isinstance(message.get('content'), str) or
                         (message.get('role') == 'assistant' and message.get('content') is None
                          and isinstance(message.get('tool_calls'), list)))):
                raise Rejected('INVALID_MESSAGES')
        if 'tools' in request and (not isinstance(request['tools'], list) or len(request['tools']) > 8):
            raise Rejected('INVALID_TOOLS')
        if 'stream' in request and type(request['stream']) is not bool:
            raise Rejected('INVALID_STREAM')
        if 'store' in request and request['store'] is not False:
            raise Rejected('STORAGE_NOT_ALLOWED')
        if 'stream_options' in request and (request['stream_options'] != {'include_usage': True} or
                type(request['stream_options'].get('include_usage')) is not bool):
            raise Rejected('UNSUPPORTED_STREAM_OPTIONS')
        if 'max_tokens' in request and 'max_completion_tokens' in request:
            raise Rejected('AMBIGUOUS_OUTPUT_CAP')
        output_field = 'max_completion_tokens' if 'max_completion_tokens' in request else 'max_tokens'
        output = request.get(output_field, self.limits.output_tokens)
        if type(output) is not int or not 1 <= output <= self.limits.output_tokens:
            raise Rejected('OUTPUT_TOKEN_BUDGET')
        # Count the normalized request, including injected output cap and all tools.
        request[output_field] = output
        if len(json.dumps(request, separators=(',', ':')).encode('utf-8')) > self.limits.request_bytes:
            raise Rejected('REQUEST_BYTES')
        try:
            prompt = self.count_prompt(request)
        except Exception:
            self._fault('TOKEN_COUNTER_FAILED')
        now = self.check()  # Counter duration consumes task time too.
        if type(prompt) is not int or prompt < 1:
            self._fault('TOKEN_COUNT_INVALID')
        reserved = prompt + output
        if reserved + self.limits.context_reserve > self.limits.context_tokens:
            self._fault('CONTEXT_BUDGET')
        if self.charged_tokens + reserved > self.limits.task_tokens:
            self._fault('TASK_TOKEN_BUDGET')
        self.calls += 1
        self.charged_tokens += reserved
        self.active = {'id': self.calls, 'deadline': min(now + self.limits.call_seconds,
                                                      self.started + self.limits.task_seconds),
                       'responseBytes': 0}
        self.state = 'IN_FLIGHT'
        self.events.append({'event': 'ADMITTED_OFFLINE', 'callId': self.calls,
                            'promptTokens': prompt, 'reservedOutputTokens': output})
        return {'status': 'ADMITTED_OFFLINE', 'callId': self.calls, 'request': request,
                'deadline': self.active['deadline'], 'executionEnabled': False}

    def output(self, call_id, chunk):
        """Check raw response chunks BEFORE relaying them; includes stream framing."""
        self.check()
        self._active_call(call_id)
        if not isinstance(chunk, bytes):
            self._fault('INVALID_RESPONSE_BYTES')
        if self.active['responseBytes'] + len(chunk) > self.limits.response_bytes:
            self._fault('RESPONSE_BYTES')
        self.active['responseBytes'] += len(chunk)

    def _active_call(self, call_id):
        if type(call_id) is not int or not self.active or self.active['id'] != call_id:
            self._fault('CALL_ID_MISMATCH')

    def finish(self, call_id):
        self.check()
        self._active_call(call_id)
        self.events.append({'event': 'FINISHED_OFFLINE', 'callId': call_id,
                            'responseBytes': self.active['responseBytes']})
        self.active = None
        self.state = 'READY'
        # Never refund reserved tokens based on an untrusted backend usage field.

    def cancel(self):
        self._fault('CANCELLED')

    def backend_failed(self):
        self._fault('BACKEND_FAILURE')

    def close(self):
        self.check()
        if self.active:
            raise Rejected('CALL_ALREADY_ACTIVE')
        self.state = 'COMPLETE'

    def snapshot(self):
        return {'mode': 'offline-only', 'state': self.state, 'fault': self.fault,
                'calls': self.calls, 'chargedTokens': self.charged_tokens,
                'activeCall': self.active['id'] if self.active else None,
                'upstreamStopRequired': bool(self.fault and self.active),
                'events': [event.copy() for event in self.events],
                'executionEnabled': False, 'modelEnabled': False}


def simulate(scenario):
    now = [0.0]
    prompt_tokens = 8000 if scenario == 'context-limit' else 80
    gate = RequestGate(model='synthetic-coder', count_prompt=lambda request: prompt_tokens,
                       clock=lambda: now[0])
    raw = json.dumps({'model': 'synthetic-coder',
                      'messages': [{'role': 'user', 'content': 'Simulated small edit.'}],
                      'stream': True}).encode()
    try:
        admitted = gate.admit(raw)
        if scenario == 'deadline':
            now[0] = 16
            gate.check()
        elif scenario == 'oversized-response':
            gate.output(admitted['callId'], b'x' * (gate.limits.response_bytes + 1))
        elif scenario == 'cancel':
            gate.cancel()
        else:
            gate.output(admitted['callId'], b'synthetic response')
            gate.finish(admitted['callId'])
            if scenario == 'call-limit':
                second = gate.admit(raw)
                gate.finish(second['callId'])
                gate.admit(raw)
            gate.close()
    except Rejected:
        pass
    return {**gate.snapshot(), 'scenario': scenario, 'tokenCounter': 'synthetic-fixed-count',
            'upstreamStarted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='success', choices=(
        'success', 'call-limit', 'context-limit', 'deadline', 'oversized-response', 'cancel'))
    args = parser.parse_args()
    result = simulate(args.scenario)
    print(json.dumps(result))
    raise SystemExit(3 if result['fault'] else 0)
