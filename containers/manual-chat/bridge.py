"""Fixed Docker-exec mailbox protocol. No shell, host port or writable bind."""
import base64
import json
from pathlib import Path
import sys

from protocol import LIMITS, validate_request

WORK = Path('/work')


def submit(sequence, encoded):
    if type(sequence) is not int or not 1 <= sequence <= LIMITS['requests'] or len(encoded) > 12000:
        raise ValueError('MAILBOX_BUDGET')
    status = json.loads((WORK / 'chat.json').read_bytes())
    if status['phase'] != 'READY' or status['sequence'] != sequence - 1:
        raise ValueError('MAILBOX_NOT_READY')
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > LIMITS['requestBytes']:
        raise ValueError('REQUEST_BYTES')
    validate_request(json.loads(raw))
    path = WORK / f'request-{sequence}.json'
    with path.with_suffix('.tmp').open('xb') as stream:
        stream.write(raw)
    path.with_suffix('.tmp').rename(path)


if __name__ == '__main__':
    if sys.argv[1:] == ['snapshot']:
        path = WORK / 'chat.json'
        raw = path.read_bytes() if path.exists() else b'{"phase":"STARTING","sequence":0}'
        if len(raw) > 131072:
            raise ValueError('SNAPSHOT_BYTES')
        sys.stdout.buffer.write(raw)
    elif len(sys.argv) == 4 and sys.argv[1] == 'submit':
        submit(int(sys.argv[2]), sys.argv[3])
    else:
        raise ValueError('BRIDGE_COMMAND')
