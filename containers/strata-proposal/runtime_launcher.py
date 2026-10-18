"""Fixed-command launcher inside the admitted capsule, never a shell wrapper."""
import json
import os
from pathlib import Path
import sys


def command(name, manifest):
    if name not in manifest['commands']:
        raise ValueError('RUNTIME_COMMAND_NOT_ALLOWED')
    executable = '/exec/' + manifest['commands'][name]
    # All selected commands have a PT_INTERP; the static shim is the exception.
    if name in manifest['staticCommands']:
        return [executable]
    return ['/exec/' + manifest['loader'], '--library-path', '/exec/lib', executable]


def main():
    manifest = json.loads(Path('/control/runtime.json').read_text())
    if sys.platform != 'linux' or not Path('/exec/.qualified').is_file():
        raise ValueError('RUNTIME_NOT_ADMITTED')
    argv = command(sys.argv[1], manifest) + sys.argv[2:]
    os.execv(argv[0], argv)


if __name__ == '__main__':
    main()
