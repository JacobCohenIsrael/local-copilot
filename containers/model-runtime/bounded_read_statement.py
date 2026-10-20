"""Task-2 correction: demand a completed, single-statement model answer."""
import bounded_read_task as spec

PROMPT = ('Python only, one line, no function or markdown. Validate integer maximum: '
          'raise ValueError when it is negative.')


def guard_from_response(response):
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('MODEL_OUTPUT_INCOMPLETE')
    text = choice['message']['content'].strip()
    if len(text.splitlines()) != 1 or '`' in text:
        raise ValueError('SINGLE_PYTHON_STATEMENT_REQUIRED')
    return spec.guard_from_response(response)


def replacement(response, original):
    guard_from_response(response)
    return spec.replacement(response, original)


if __name__ == '__main__':
    import asyncio
    from pathlib import Path
    import coding_worker as worker
    original = Path('/input', spec.SELECTED).read_bytes()
    spec.validate_original(original)
    worker.SELECTED = spec.SELECTED
    worker.TASK = spec.TASK
    worker.STDOUT_LIMIT = 8192
    worker.STDERR_LIMIT = 4096
    worker.validate_original = spec.validate_original
    worker.code_from_response = lambda response: replacement(response, original)
    raise SystemExit(asyncio.run(worker.run()))
