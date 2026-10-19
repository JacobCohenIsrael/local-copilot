"""Use the pinned upstream API with automatic engine reload/retry disabled."""
import sys
from pathlib import Path
import threading
import time


def main():
    sys.path[:0] = ['/source', '/source/tools', '/runtime/site']
    from serve import server
    # Upstream needs a seekable native log for its startup diagnostics. Mirror
    # it to bounded Docker logs so stopping the tmpfs does not erase failures.
    def mirror():
        position = 0
        while position < 1048576:
            try:
                with Path('/work/engine.log').open('rb') as stream:
                    stream.seek(position); chunk = stream.read(min(16384,1048576-position))
                if chunk:
                    sys.stderr.buffer.write(chunk);sys.stderr.buffer.flush();position+=len(chunk)
            except OSError: pass
            time.sleep(.1)
    threading.Thread(target=mirror,daemon=True).start()
    server.START_RETRIES = 0
    original = server.popen
    launches = 0

    def spawn(what, args, **kwargs):
        nonlocal launches
        if what == 'the Strata engine':
            launches += 1
            if launches > 1: raise server.EngineDied('Automatic engine reload is disabled for this one test')
        return original(what, args, **kwargs)

    def no_restart(self, *args, **kwargs):
        raise server.EngineDied('Automatic engine restart is disabled for this one test')

    server.popen = spawn
    server.StrataEngine.restart = no_restart
    sys.argv = ['server.py', '--engine', 'strata', '--config', '/input/strata.json',
                '--host', '127.0.0.1', '--port', '8080']
    raise SystemExit(server.main())


if __name__ == '__main__': main()
