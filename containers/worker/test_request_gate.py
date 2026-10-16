import json
import math
import unittest

from request_gate import Limits, Rejected, RequestGate, simulate


class RequestGateTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.tokens = 80
        self.seen = []
        self.gate = RequestGate(model='test-model', count_prompt=self.count,
                                clock=lambda: self.now)

    def count(self, request):
        self.seen.append(request)
        return self.tokens

    def body(self, **changes):
        request = {'model': 'test-model', 'messages': [{'role': 'user', 'content': 'private task'}],
                   'stream': True}
        request.update(changes)
        return json.dumps(request).encode()

    def one_call(self):
        admitted = self.gate.admit(self.body())
        self.gate.output(admitted['callId'], b'response')
        self.gate.finish(admitted['callId'])
        return admitted

    def test_complete_call_caps_output_without_logging_content(self):
        tools = [{'type': 'function', 'function': {'name': 'edit', 'parameters': {'type': 'object'}}}]
        admitted = self.gate.admit(self.body(tools=tools))
        self.assertEqual(admitted['request']['max_tokens'], Limits().output_tokens)
        self.assertEqual(self.seen[0]['tools'], tools)
        self.assertEqual(self.seen[0]['messages'][0]['content'], 'private task')
        self.gate.output(admitted['callId'], b'synthetic response')
        self.gate.finish(admitted['callId'])
        self.gate.close()
        state = self.gate.snapshot()
        self.assertEqual(state['state'], 'COMPLETE')
        self.assertEqual(state['chargedTokens'], self.tokens + Limits().output_tokens)
        self.assertNotIn('private task', json.dumps(state))
        self.assertFalse(state['executionEnabled'])
        self.now = Limits().task_seconds + 1
        with self.assertRaisesRegex(Rejected, 'TASK_CLOSED'):
            self.gate.admit(self.body())
        self.assertEqual(self.gate.state, 'COMPLETE')

    def test_bad_request_does_not_consume_calls(self):
        cases = [self.body(model='other'), self.body(max_tokens=True), self.body(max_tokens=0),
                 self.body(max_tokens=513), self.body(max_completion_tokens=True),
                 self.body(max_completion_tokens=513), self.body(max_tokens=10, max_completion_tokens=10),
                 self.body(stream='true'), self.body(store=True), self.body(store='false'),
                 self.body(stream_options={'include_usage': 1}),
                 self.body(stream_options={'include_usage': True, 'other': True}),
                 self.body(stream_options=None), self.body(messages=[]), self.body(tools={}),
                 self.body(messages=[{'role': 'user', 'content': [{'type': 'image_url'}]}]),
                 b'{"model":"test-model","model":"other"}',
                 b'{"tools":[NaN]}', b'{"tools":[1e999]}', b'[]', b'\xff', b'not json']
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(Rejected):
                self.gate.admit(raw)
            self.assertEqual(self.gate.calls, 0)
            self.assertEqual(self.gate.state, 'READY')
        self.assertEqual(self.seen, [])

    def test_oversized_request_never_reaches_counter(self):
        with self.assertRaisesRegex(Rejected, 'REQUEST_BYTES'):
            self.gate.admit(b'x' * (Limits().request_bytes + 1))
        self.assertEqual(self.seen, [])
        base = json.dumps({'model': 'test-model', 'messages': [{'role': 'user', 'content': ''}]},
                          separators=(',', ':'))
        raw = base.replace('"content":""', '"content":"' +
                           'x' * (Limits().request_bytes - len(base.encode())) + '"').encode()
        self.assertEqual(len(raw), Limits().request_bytes)
        with self.assertRaisesRegex(Rejected, 'REQUEST_BYTES'):
            self.gate.admit(raw)  # Injecting max_tokens also has to fit.
        self.assertEqual(self.seen, [])

    def test_tool_history_is_passed_to_trusted_counter(self):
        messages = [{'role': 'assistant', 'content': None,
                     'tool_calls': [{'id': 'call1', 'type': 'function',
                                     'function': {'name': 'read', 'arguments': '{"path":"x.py"}'}}]},
                    {'role': 'tool', 'content': 'file text', 'tool_call_id': 'call1'}]
        admitted = self.gate.admit(self.body(messages=messages, max_completion_tokens=128,
                                  store=False, stream_options={'include_usage': True}))
        self.assertEqual(admitted['request']['max_completion_tokens'], 128)
        self.assertNotIn('max_tokens', admitted['request'])
        self.assertEqual(self.seen[0]['messages'], messages)
        self.assertEqual(self.gate.charged_tokens, self.tokens + 128)

    def test_context_boundary_and_reserve(self):
        limits = Limits()
        self.tokens = limits.context_tokens - limits.context_reserve - limits.output_tokens
        self.one_call()  # Exactly fits including the safety reserve.
        other = RequestGate(model='test-model', count_prompt=lambda request: self.tokens + 1)
        with self.assertRaisesRegex(Rejected, 'CONTEXT_BUDGET'):
            other.admit(self.body())
        self.assertEqual(other.calls, 0)
        self.assertEqual(other.snapshot()['state'], 'FAULT')

    def test_cumulative_token_reservation_is_not_refunded(self):
        self.tokens = 4000
        self.one_call()
        with self.assertRaisesRegex(Rejected, 'TASK_TOKEN_BUDGET'):
            self.gate.admit(self.body())
        self.assertEqual(self.gate.calls, 1)
        self.assertEqual(self.gate.charged_tokens, 4512)
        self.assertFalse(self.gate.snapshot()['upstreamStopRequired'])

    def test_calls_are_bounded_and_not_parallel(self):
        first = self.gate.admit(self.body())
        with self.assertRaisesRegex(Rejected, 'CALL_ALREADY_ACTIVE'):
            self.gate.admit(self.body())
        self.assertEqual(self.gate.calls, 1)
        self.assertIsNone(self.gate.fault)
        self.gate.finish(first['callId'])
        self.one_call()
        with self.assertRaisesRegex(Rejected, 'CALL_BUDGET'):
            self.gate.admit(self.body())
        self.assertEqual(self.gate.calls, 2)
        self.assertLessEqual(len(self.gate.events), 5)

    def test_call_deadline_trips_without_receiving_a_chunk(self):
        self.gate.admit(self.body())
        self.now = Limits().call_seconds
        with self.assertRaisesRegex(Rejected, 'CALL_DEADLINE'):
            self.gate.check()
        self.assertTrue(self.gate.snapshot()['upstreamStopRequired'])

    def test_task_deadline_and_counter_time(self):
        self.now = Limits().task_seconds
        with self.assertRaisesRegex(Rejected, 'TASK_DEADLINE'):
            self.gate.admit(self.body())
        self.assertEqual(self.gate.calls, 0)
        self.now = 0
        def slow_counter(request):
            self.now = Limits().task_seconds
            return 1
        other = RequestGate(model='test-model', count_prompt=slow_counter, clock=lambda: self.now)
        with self.assertRaisesRegex(Rejected, 'TASK_DEADLINE'):
            other.admit(self.body())
        self.assertEqual(other.calls, 0)

    def test_clock_regression_or_invalid_number_faults(self):
        for invalid in [-1, math.nan, math.inf, True]:
            self.now = 0
            gate = RequestGate(model='test-model', count_prompt=self.count, clock=lambda: self.now)
            self.now = invalid
            with self.subTest(value=invalid), self.assertRaisesRegex(Rejected, 'CLOCK_INVALID'):
                gate.check()

    def test_token_counter_failure_and_invalid_values_fail_closed(self):
        for invalid in [True, 0, -1, 2.5, None]:
            gate = RequestGate(model='test-model', count_prompt=lambda request: invalid)
            with self.subTest(value=invalid), self.assertRaisesRegex(Rejected, 'TOKEN_COUNT_INVALID'):
                gate.admit(self.body())
            self.assertEqual(gate.calls, 0)
        def broken(request):
            raise RuntimeError('sensitive tokenizer details')
        gate = RequestGate(model='test-model', count_prompt=broken)
        with self.assertRaisesRegex(Rejected, 'TOKEN_COUNTER_FAILED'):
            gate.admit(self.body())
        self.assertNotIn('sensitive', json.dumps(gate.snapshot()))
        with self.assertRaisesRegex(ValueError, 'TOKEN_COUNTER_REQUIRED'):
            RequestGate(model='test-model', count_prompt=None)

    def test_response_limit_checks_bytes_before_relay(self):
        admitted = self.gate.admit(self.body())
        call = admitted['callId']
        self.gate.output(call, b'x' * (Limits().response_bytes - 1))
        self.gate.output(call, b'x')
        with self.assertRaisesRegex(Rejected, 'RESPONSE_BYTES'):
            self.gate.output(call, b'x')
        self.assertEqual(self.gate.active['responseBytes'], Limits().response_bytes)
        self.assertTrue(self.gate.snapshot()['upstreamStopRequired'])

    def test_cancel_latches_first_fault_and_blocks_further_activity(self):
        admitted = self.gate.admit(self.body())
        operations = [self.gate.cancel, self.gate.backend_failed,
                      lambda: self.gate.finish(admitted['callId']),
                      lambda: self.gate.admit(self.body()), self.gate.close]
        for operation in operations:
            with self.assertRaisesRegex(Rejected, 'CANCELLED'):
                operation()
        self.assertEqual(len([event for event in self.gate.events if event['event'] == 'FAULT']), 1)

    def test_stale_completion_cannot_finish_new_call(self):
        first = self.one_call()
        self.gate.admit(self.body())
        with self.assertRaisesRegex(Rejected, 'CALL_ID_MISMATCH'):
            self.gate.finish(first['callId'])
        self.assertTrue(self.gate.snapshot()['upstreamStopRequired'])
        other = RequestGate(model='test-model', count_prompt=self.count)
        other.admit(self.body())
        with self.assertRaisesRegex(Rejected, 'BACKEND_FAILURE'):
            other.backend_failed()
        self.assertTrue(other.snapshot()['upstreamStopRequired'])

    def test_scenarios_are_explicitly_offline(self):
        expected = {'success': None, 'call-limit': 'CALL_BUDGET', 'context-limit': 'CONTEXT_BUDGET',
                    'deadline': 'CALL_DEADLINE', 'oversized-response': 'RESPONSE_BYTES',
                    'cancel': 'CANCELLED'}
        for scenario, fault in expected.items():
            result = simulate(scenario)
            self.assertEqual(result['fault'], fault)
            self.assertFalse(result['upstreamStarted'])
            self.assertFalse(result['modelEnabled'])
            self.assertEqual(result['tokenCounter'], 'synthetic-fixed-count')


if __name__ == '__main__':
    unittest.main()
