"""One 16K-context request, small input, up to 4K output; finite deadlines."""
CONTEXT_TOKENS=16384
OUTPUT_TOKENS=4096
INPUT_BUDGET=512
MARGIN_TOKENS=8
RESPONSE_BYTES=262144
REQUEST_SECONDS=150


def validate_response(response,maximum_output_tokens=OUTPUT_TOKENS):
    if type(maximum_output_tokens) is not int or maximum_output_tokens!=OUTPUT_TOKENS:
        raise ValueError('OUTPUT_BUDGET_INVALID')
    if not isinstance(response,dict) or not isinstance(response.get('choices'),list) or len(response['choices'])!=1:
        raise ValueError('API_RESPONSE_SHAPE')
    choice=response['choices'][0]
    if not isinstance(choice,dict):raise ValueError('API_RESPONSE_SHAPE')
    message,usage=choice.get('message'),response.get('usage')
    if not isinstance(message,dict) or not isinstance(usage,dict):raise ValueError('API_RESPONSE_SHAPE')
    if (message.get('role')!='assistant' or not isinstance(message.get('content'),str) or
            not message['content'].strip() or choice.get('finish_reason') not in ('stop','length') or
            type(usage.get('completion_tokens')) is not int or not 1<=usage['completion_tokens']<=OUTPUT_TOKENS or
            type(usage.get('prompt_tokens')) is not int or not 1<=usage['prompt_tokens']<=INPUT_BUDGET or
            type(usage.get('total_tokens')) is not int or
            usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']):
        raise ValueError('API_RESPONSE_LIMIT_OR_EMPTY')
    return response


def main():
    import container_test_base as base
    base.REQUEST_SECONDS=REQUEST_SECONDS
    base.MAX_RESPONSE=RESPONSE_BYTES
    base.validate_response=validate_response
    return base.main()


if __name__=='__main__':raise SystemExit(main())
