"""Manual chat budgets and stream admission. Pure Python; no live access."""
import json
import unicodedata

LIMITS = dict(contextTokens=16384, inputTokens=512, outputTokens=4096,
              contextMargin=8, requests=3, requestSeconds=150,
              startupSeconds=180, modelSeconds=300, outerSeconds=410,
              requestBytes=8192, replyBytes=98304, streamBytes=524288)
MODEL = 'qwen3.8-flash-next-coder-iq1_m'


def request(messages, output=4096):
    if type(output) is not int or not 1 <= output <= LIMITS['outputTokens']:
        raise ValueError('OUTPUT_BUDGET')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 5:
        raise ValueError('MESSAGE_COUNT')
    for index, message in enumerate(messages):
        if (not isinstance(message, dict) or set(message) != {'role', 'content'} or
                message['role'] != ('user' if index % 2 == 0 else 'assistant') or
                not isinstance(message['content'], str) or not message['content'].strip()):
            raise ValueError('TEXT_MESSAGES_ONLY')
    if len(messages) % 2 != 1:
        raise ValueError('USER_TURN_REQUIRED')
    result = dict(model=MODEL, messages=messages, max_tokens=output, temperature=0,
                  stream=True, return_progress=True, reasoning_effort='none')
    if len(json.dumps(result).encode()) > LIMITS['requestBytes']:
        raise ValueError('REQUEST_BYTES')
    return result


def validate_request(value):
    if not isinstance(value, dict) or value != request(value.get('messages'), value.get('max_tokens')):
        raise ValueError('REQUEST_CONTRACT')
    return value


def admit_prompt(ids, output):
    if (type(output) is not int or not 1 <= output <= LIMITS['outputTokens'] or
            not 1 <= len(ids) <= LIMITS['inputTokens'] or
            len(ids) + output + LIMITS['contextMargin'] > LIMITS['contextTokens']):
        raise ValueError('MANUAL_PROMPT_TOKEN_BUDGET_512_INCLUDING_TEMPLATE_AND_HISTORY')


def terminal(text):
    """Keep model/user text from issuing terminal escape/control commands."""
    return ''.join(c for c in text if c in '\n\t' or not unicodedata.category(c).startswith('C'))


class Stream:
    def __init__(self, output):
        self.output = output
        self.text = ''
        self.progress = None
        self.finish = None
        self.usage = None
        self.bytes = 0
        self.done = False

    def feed(self, line):
        self.bytes += len(line)
        if self.bytes > LIMITS['streamBytes'] or len(line) > 65536:
            raise ValueError('STREAM_BYTES')
        if not line.startswith(b'data:'):
            return  # SSE keepalives are transport activity, never native progress.
        data = line[5:].strip()
        if data == b'[DONE]':
            self.done = True
            return
        if self.done or self.finish is not None:
            raise ValueError('STREAM_AFTER_FINISH')
        value = json.loads(data)
        if 'error' in value:
            raise ValueError('API_STREAM_ERROR')
        choices = value.get('choices')
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError('STREAM_SHAPE')
        choice = choices[0]
        delta = choice.get('delta', {})
        if not isinstance(delta, dict) or delta.get('tool_calls') or delta.get('reasoning_content'):
            raise ValueError('TEXT_REPLY_ONLY')
        text = delta.get('content') or ''
        if not isinstance(text, str):
            raise ValueError('TEXT_REPLY_ONLY')
        self.text += text
        if len(self.text.encode()) > LIMITS['replyBytes']:
            raise ValueError('REPLY_BYTES')
        if 'prompt_progress' in value:
            p = value['prompt_progress']
            if (not isinstance(p, dict) or any(type(p.get(k)) is not int for k in ('processed', 'total')) or
                    not 0 <= p['processed'] <= p['total'] <= LIMITS['inputTokens']):
                raise ValueError('PROMPT_PROGRESS')
            self.progress = dict(processed=p['processed'], total=p['total'])
        if choice.get('finish_reason') is not None:
            self.finish, self.usage = choice['finish_reason'], value.get('usage')
            u = self.usage
            if (self.finish not in ('stop', 'length') or not isinstance(u, dict) or
                    type(u.get('prompt_tokens')) is not int or not 1 <= u['prompt_tokens'] <= LIMITS['inputTokens'] or
                    type(u.get('completion_tokens')) is not int or not 0 <= u['completion_tokens'] <= self.output or
                    type(u.get('total_tokens')) is not int or
                    u['total_tokens'] != u['prompt_tokens'] + u['completion_tokens']):
                raise ValueError('FINAL_USAGE_OR_FINISH')

    def result(self):
        if not self.done or self.finish is None or not self.text.strip():
            raise ValueError('INCOMPLETE_STREAM')
        return dict(text=self.text, finish=self.finish, usage=self.usage,
                    truncated=self.finish == 'length')
