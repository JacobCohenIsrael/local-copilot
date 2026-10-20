"""Fixed useful task: insert a model-generated negative read-limit guard only."""
import ast
import hashlib
import textwrap

SELECTED = 'task_bundle.py'
SOURCE = 'containers/worker/task_bundle.py'
SOURCE_SHA256 = '33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d'
TASK = ('Only edit task_bundle.py: insert a guard at the start of bounded_read to '
        'raise ValueError when maximum < 0, before file access. Preserve all other bytes. '
        'Do not run commands or access other files.')
PROMPT = 'Return only Python: if maximum < 0 raise ValueError.'
MAX_CODE_BYTES = 128


def validate_original(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('SELECTED_REPOSITORY_SOURCE_CHANGED')


def guard_from_response(response):
    text = response['choices'][0]['message']['content'].strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines) < 3 or lines[0] not in ('```', '```python') or lines[-1] != '```':
            raise ValueError('CODE_FENCE_INVALID')
        text = textwrap.dedent('\n'.join(lines[1:-1])).strip()
    if not 1 <= len(text.encode('utf-8')) <= MAX_CODE_BYTES:
        raise ValueError('GENERATED_CODE_BUDGET')
    tree = ast.parse(text)
    expected = ast.parse('if maximum < 0: raise ValueError').body[0]
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.If):
        raise ValueError('UNEXPECTED_GUARD')
    node = tree.body[0]
    if (ast.dump(node.test) != ast.dump(expected.test) or node.orelse or
            len(node.body) != 1 or not isinstance(node.body[0], ast.Raise)):
        raise ValueError('UNEXPECTED_GUARD')
    raised = node.body[0]
    allowed = [ast.parse(code).body[0].exc for code in ('raise ValueError', 'raise ValueError()')]
    if raised.cause is not None or ast.dump(raised.exc) not in [ast.dump(x) for x in allowed]:
        raise ValueError('UNEXPECTED_GUARD')
    return text


def acceptance(data):
    """Execute only the selected trusted function with fake file access, offline."""
    tree = ast.parse(data)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'bounded_read']
    if len(functions) != 1:
        raise ValueError('BOUNDED_READ_FUNCTION_REQUIRED')
    accessed = []
    class Stream:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, size):
            accessed.append(('read', size))
            return b'abc' if size < 0 else b'abc'[:size]
    class FakePath:
        def __init__(self, path): accessed.append(('path', path))
        def open(self, mode):
            accessed.append(('open', mode))
            return Stream()
    scope = {'MAX_FILE_BYTES': 65536, 'plain': lambda path: accessed.append(('plain', path)),
             'Path': FakePath}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<bounded-read-acceptance>', 'exec'), scope)
    read = scope['bounded_read']
    for maximum in (-1, -2, -65536):
        accessed.clear()
        try: read('selected', maximum)
        except ValueError: pass
        else: raise ValueError('NEGATIVE_LIMIT_ACCEPTED')
        if accessed: raise ValueError('NEGATIVE_LIMIT_ACCESSED_FILE')
    for maximum, expected in ((3, b'abc'), (4, b'abc'), (65536, b'abc')):
        if read('selected', maximum) != expected: raise ValueError('VALID_READ_CHANGED')
    for maximum in (0, 1, 2):
        try: read('selected', maximum)
        except ValueError as error:
            if str(error) != 'FILE_BUDGET_EXCEEDED': raise
        else: raise ValueError('OVERSIZE_READ_ACCEPTED')
    return {'negativeLimitsRejectedBeforeAccess': True, 'validReadsUnchanged': True,
            'oversizeStillRejected': True, 'realFileAccess': False}


def replacement(response, original):
    validate_original(original)
    guard = guard_from_response(response)
    newline = '\r\n' if b'\r\n' in original else '\n'
    anchor = ('def bounded_read(path, maximum=MAX_FILE_BYTES):' + newline).encode()
    if original.count(anchor) != 1: raise ValueError('INSERTION_ANCHOR_CHANGED')
    inserted = textwrap.indent(guard, '    ').replace('\n', newline).encode() + newline.encode()
    updated = original.replace(anchor, anchor + inserted, 1)
    acceptance(updated)
    return updated


if __name__ == '__main__':
    import asyncio
    from pathlib import Path
    import coding_worker as worker
    original = Path('/input', SELECTED).read_bytes()
    validate_original(original)
    worker.SELECTED = SELECTED
    worker.TASK = TASK
    worker.STDOUT_LIMIT = 8192
    worker.STDERR_LIMIT = 4096
    worker.validate_original = validate_original
    worker.code_from_response = lambda response: replacement(response, original)
    raise SystemExit(asyncio.run(worker.run()))
