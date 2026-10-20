"""One loopback API request; no external network, downloads or restart route."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

REQUEST = {'model': 'qwen3.8-flash-next-coder-iq1_m', 'messages': [
    {'role': 'user', 'content': 'Reply with READY. No explanation.'}],
    'max_tokens': 8, 'temperature': 0, 'stream': False, 'reasoning_effort': 'none'}
MAX_RESPONSE = 16384
REQUEST_SECONDS = 90


def qualify_environment(root=Path('/')):
    def read(name):
        raw=(root/name).read_text()
        if len(raw)>65536:raise ValueError('RUNTIME_QUALIFICATION_BUDGET')
        return raw
    quota,period=map(int,read('sys/fs/cgroup/cpu.max').split())
    memory=int(read('sys/fs/cgroup/memory.max'));swap=int(read('sys/fs/cgroup/memory.swap.max'))
    pids=int(read('sys/fs/cgroup/pids.max'))
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in read('proc/self/status').splitlines() if ':' in line}
    meminfo={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in read('proc/meminfo').splitlines() if ':' in line}
    interfaces=sorted(p.name for p in (root/'sys/class/net').iterdir())
    if (quota!=period or quota<=0 or memory!=4*1024**3 or swap!=0 or pids!=128 or
        os.getuid()!=65532 or int(status['CapEff'],16)!=0 or status['NoNewPrivs']!='1' or interfaces!=['lo'] or
        int(meminfo['SwapTotal'].split()[0])!=0 or not 4*1024**3<int(meminfo['MemTotal'].split()[0])*1024<=6*1024**3 or
        tuple(sys.version_info[:3])!=(3,13,15)):
        raise ValueError('RUNTIME_KERNEL_LIMITS_MISMATCH')
    return {'cpuQuota':1,'memoryBytes':memory,'swapBytes':swap,'pids':pids,'uid':65532,
        'effectiveCapabilities':0,'noNewPrivileges':True,'networkInterfaces':interfaces,
        'pythonVersion':'3.13.15','modelStartedDuringQualification':False}


class Leases:
    def __init__(self,start):self.start=start;self.last=start;self.sizes={};self.changed={}
    def check(self,now,sizes,request_deadline=None):
        if now<self.last:raise ValueError('CONTAINER_CLOCK_REGRESSION')
        self.last=now
        if now-self.start>=300:raise TimeoutError('CONTAINER_DEADLINE')
        if request_deadline is not None and now>=request_deadline:raise TimeoutError('REQUEST_DEADLINE')
        for name in ('controller.pulse','guard.pulse'):
            size=sizes[name]
            if type(size) is not int or not 0<size<=2048 or size<self.sizes.get(name,0):raise ValueError('HOST_LEASE_INVALID')
            if size>self.sizes.get(name,0):self.sizes[name]=size;self.changed[name]=now
            if now-self.changed[name]>2.5:raise TimeoutError('HOST_LEASE_EXPIRED')


def validate_response(response,maximum_output_tokens=8):
    if type(maximum_output_tokens) is not int or not 1<=maximum_output_tokens<=32:
        raise ValueError('OUTPUT_BUDGET_INVALID')
    if not isinstance(response, dict) or not isinstance(response.get('choices'), list) or len(response['choices']) != 1:
        raise ValueError('API_RESPONSE_SHAPE')
    choice = response['choices'][0]; message = choice.get('message', {}); usage = response.get('usage', {})
    if (message.get('role') != 'assistant' or not isinstance(message.get('content'), str) or
            not message['content'].strip() or choice.get('finish_reason') not in ('stop', 'length') or
            type(usage.get('completion_tokens')) is not int or not 1 <= usage['completion_tokens'] <= maximum_output_tokens or
            type(usage.get('prompt_tokens')) is not int or not 1 <= usage['prompt_tokens'] <= 512-maximum_output_tokens or
            type(usage.get('total_tokens')) is not int or
            usage['total_tokens'] != usage['completion_tokens'] + usage['prompt_tokens']):
        raise ValueError('API_RESPONSE_LIMIT_OR_EMPTY')
    return response


def shutdown(process):
    if process is not None:
        # Let the upstream server take its SIGTERM -> QUIT/close path first.
        try: process.terminate()
        except ProcessLookupError: pass
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        finally:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        process.wait(timeout=.5)


def main():
    # Failure of the host controller OR its independent guard ends the child
    # group locally, even when Docker control itself is unavailable.
    process = None; closed = threading.Event(); fault = []; start = time.monotonic()
    lease_gate = Leases(start); request_deadline = [None]

    def leases():
        try:
            while not closed.is_set():
                now = time.monotonic()
                lease_gate.check(now,{name:(Path('/control')/name).stat().st_size
                    for name in ('controller.pulse','guard.pulse')},request_deadline[0])
                log = Path('/work/engine.log')
                if log.exists() and log.stat().st_size > 1048576: raise ValueError('ENGINE_LOG_BUDGET')
                closed.wait(.1)
        except BaseException as error:
            fault.append(str(error)[:128])
            try: shutdown(process)
            finally: os._exit(70) # PID 1 exits even if group cleanup raises.

    def interrupted(*_): raise InterruptedError('HOST_STOP')
    signal.signal(signal.SIGTERM, interrupted)
    watcher = threading.Thread(target=leases, daemon=True); watcher.start()
    result = {'status': 'FAULT', 'modelStarted': False, 'requestsSubmitted': 0}
    try:
        result['runtimeQualification']=qualify_environment()
        print('RUNTIME_ENVIRONMENT_VERIFIED '+json.dumps(result['runtimeQualification']),flush=True)
        # Source dependencies/tokenizer are tested by the actual Linux startup;
        # this preparation never claims Windows imports qualify Linux binaries.
        process = subprocess.Popen([sys.executable, '-B', '/input/api_wrapper.py'], start_new_session=True)
        result.update(apiProcessStarted=True,modelStarted=None) # Startup may fail before the engine is spawned.
        ready_deadline = time.monotonic() + 180
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while time.monotonic() < ready_deadline:
            if process.poll() is not None: raise RuntimeError('API_EXIT_BEFORE_READY')
            try:
                with opener.open('http://127.0.0.1:8080/health', timeout=.5) as response:
                    health = response.read(4097)
                    if response.status == 200 and len(health) <= 4096:
                        result['modelStarted']=True;break # Upstream binds only after engine READY.
            except (OSError, urllib.error.URLError): pass
            time.sleep(.2)
        else: raise TimeoutError('API_STARTUP_DEADLINE')
        request_path=Path('/input/request.json')
        request_data=json.loads(request_path.read_bytes()) if request_path.exists() else REQUEST
        request = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
            data=json.dumps(request_data).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        result['requestsSubmitted'] = 1
        request_deadline[0] = time.monotonic() + REQUEST_SECONDS
        # Exactly one inference request, no retry on a socket/HTTP error.
        with opener.open(request, timeout=REQUEST_SECONDS) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if response.status != 200 or len(raw) > MAX_RESPONSE: raise ValueError('API_RESPONSE_BUDGET')
        answer = validate_response(json.loads(raw),request_data['max_tokens'])
        request_deadline[0] = None
        result.update(status='REAL_STRATA_API_ANSWER', response=answer)
    except BaseException as error:
        request_deadline[0] = None
        result.update(errorType=type(error).__name__, error=str(error)[:256])
    finally:
        raw = json.dumps(result).encode()
        if len(raw) > MAX_RESPONSE: raw = b'{"status":"FAULT","error":"RESULT_BUDGET"}'
        temporary=Path('/work/result.tmp'); temporary.write_bytes(raw); temporary.rename('/work/result.json')
        # Keep the result in bounded tmpfs until the host saved it. Continue
        # monitoring both leases while waiting; never extend the 300 s deadline.
        try:
            while not Path('/control/finish.request').exists() and not fault and time.monotonic()-start < 295:
                time.sleep(.1)
        finally:
            closed.set(); shutdown(process); watcher.join(timeout=.5)
    return 0 if result['status'] == 'REAL_STRATA_API_ANSWER' and not fault else 1


if __name__ == '__main__': raise SystemExit(main())
