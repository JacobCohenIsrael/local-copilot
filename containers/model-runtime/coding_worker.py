"""Container-only one-file OpenCode adapter; awaits this task's live Strata answer."""
import asyncio,base64,hashlib,json,os,signal,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

MAX_REQUEST=65536
MODEL='qwen3.8-flash-next-coder-iq1_m'
TASK='Only change example.py from VALUE = 1 to VALUE = 2. Do not run commands or access other files.'

def code_from_response(response):
    text=response['choices'][0]['message']['content'].strip()
    if text.startswith('```'):
        lines=text.splitlines()
        if len(lines)<3 or lines[-1]!='```':raise ValueError('CODE_FENCE_INVALID')
        text='\n'.join(lines[1:-1]).strip()
    data=(text+'\n').encode('utf-8')
    if not 1<=len(data)<=128:raise ValueError('GENERATED_CODE_BUDGET')
    import ast
    tree=ast.parse(data)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.Assign):raise ValueError('UNEXPECTED_CODE')
    node=tree.body[0]
    if (len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name) or node.targets[0].id!='VALUE' or
            not isinstance(node.value,ast.Constant) or type(node.value.value) is not int or node.value.value!=2):
        raise ValueError('TASK_NOT_SOLVED')
    return data

async def run():
    bridge=Path('/bridge');work=Path('/tmp/workspace');work.mkdir()
    original=Path('/input/example.py').read_bytes()
    if original!=b'VALUE = 1\n':raise ValueError('FIXED_SELECTED_FILE_REQUIRED')
    (work/'example.py').write_bytes(original)
    started=time.monotonic();closed=threading.Event();process=[None];requests=[];answer_used=[]
    def terminate():
        child=process[0]
        if child is not None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
    def watchdog():
        previous=0;changed=time.monotonic()
        while not closed.wait(.1):
            try:
                now=time.monotonic();size=(bridge/'worker.pulse').stat().st_size
                if size>previous:changed=now
                if (size<previous or not 0<size<=2048 or now-changed>2.5 or now-started>=410 or
                        (bridge/'cancel.worker').exists()):raise ValueError('WORKER_LEASE_OR_DEADLINE')
                previous=size
            except BaseException:
                terminate();os._exit(70)
    threading.Thread(target=watchdog,daemon=True).start()
    token=os.urandom(24).hex()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            try:
                if self.path!='/v1/chat/completions' or self.headers.get('Authorization')!='Bearer '+token:
                    raise ValueError('UNAUTHORIZED_REQUEST')
                if self.headers.get('Transfer-Encoding') or not self.headers.get('Content-Length','').isdigit():
                    raise ValueError('REQUEST_FRAMING')
                size=int(self.headers['Content-Length'])
                if not 0<size<=MAX_REQUEST:raise ValueError('REQUEST_BUDGET')
                raw=self.rfile.read(size);req=json.loads(raw)
                if req.get('model')!=MODEL or len(requests)>=2:raise ValueError('MODEL_OR_CALL_BUDGET')
                requests.append(req)
                if len(requests)==1:
                    if ('edit' not in [t.get('function',{}).get('name') for t in req.get('tools',[])] or
                            TASK not in json.dumps(req.get('messages',[]))):raise ValueError('TASK_OR_EDIT_TOOL_MISSING')
                    Path('/tmp/request.pending').write_bytes(raw)
                    Path('/tmp/request.pending').rename('/tmp/request.json')
                    while not (bridge/'answer.json').exists():time.sleep(.1)
                    record=json.loads((bridge/'answer.json').read_bytes())
                    code=code_from_response(record['response'])
                    answer_used.append({'responseSha256':record['responseSha256'],
                        'codeSha256':hashlib.sha256(code).hexdigest(),'code':base64.b64encode(code).decode()})
                    delta={'role':'assistant','tool_calls':[{'index':0,'id':'live-strata-edit-1','type':'function',
                        'function':{'name':'edit','arguments':json.dumps({'path':'/tmp/workspace/example.py',
                            'oldString':original.decode(),'newString':code.decode()})}}]}
                    finish='tool_calls'
                else:
                    feedback=[m for m in req.get('messages',[]) if m.get('role')=='tool']
                    if not feedback or (work/'example.py').read_bytes()!=base64.b64decode(answer_used[0]['code']):
                        raise ValueError('REAL_EDIT_NOT_APPLIED')
                    delta={'role':'assistant','content':'Applied the Strata-generated replacement.'};finish='stop'
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Connection','close');self.end_headers()
                for chunk,end in ((delta,None),({},finish)):
                    event={'id':'strata-task','object':'chat.completion.chunk','model':MODEL,
                        'choices':[{'index':0,'delta':chunk,'finish_reason':end}]}
                    self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n')
                self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
            except BaseException as error:
                Path('/tmp/adapter-error.json').write_text(json.dumps({'error':str(error)[:512]}))
                try:self.send_error(502)
                except OSError:pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    rules={'*':'deny','read':{'*':'deny','example.py':'allow'},'edit':{'*':'deny','example.py':'allow'},
        'external_directory':'deny'}
    config={'model':'strata/'+MODEL,'small_model':'strata/'+MODEL,'enabled_providers':['strata'],
        'autoupdate':False,'share':'disabled','snapshot':False,'formatter':False,'lsp':False,'plugin':[],
        'mcp':{},'instructions':[],'compaction':{'auto':False},'permission':rules,'default_agent':'bounded',
        'agent':{'title':{'disable':True},'bounded':{'description':'One bounded real Strata edit',
            'mode':'primary','steps':2,'permission':rules}},
        'provider':{'strata':{'npm':'@ai-sdk/openai-compatible','options':{
            'baseURL':f'http://127.0.0.1:{server.server_port}/v1','apiKey':token},
            'models':{MODEL:{'name':'Strata one-file adapter','limit':{'context':8192,'output':512}}}}}}
    env={'PATH':os.environ['PATH'],'LD_LIBRARY_PATH':'/input/libs','HOME':'/tmp/home',
        'XDG_CONFIG_HOME':'/tmp/config','XDG_DATA_HOME':'/tmp/data','XDG_CACHE_HOME':'/tmp/cache',
        'OPENCODE_CONFIG_CONTENT':json.dumps(config)}
    env.update({key:'true' for key in ('OPENCODE_DISABLE_AUTOUPDATE','OPENCODE_DISABLE_MODELS_FETCH',
        'OPENCODE_DISABLE_DEFAULT_PLUGINS','OPENCODE_DISABLE_LSP_DOWNLOAD','OPENCODE_DISABLE_AUTOCOMPACT',
        'OPENCODE_DISABLE_CLAUDE_CODE')})
    result={'status':'FAULT','adapter':'live-one-file-code-to-edit','liveModelConnection':'host-brokered',
        'localAcknowledgement':True,'modelToolCallingTested':False}
    try:
        child=await asyncio.create_subprocess_exec('/input/opencode','run','--standalone','--format','json',
            '--model','strata/'+MODEL,'--agent','bounded',TASK,cwd=work,env=env,start_new_session=True,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        process[0]=child
        async def read_bound(stream,maximum):
            chunks=[];total=0
            while True:
                value=await stream.read(min(4096,maximum+1-total))
                if not value:return b''.join(chunks)
                total+=len(value)
                if total>maximum:raise ValueError('OPENCODE_OUTPUT_BUDGET')
                chunks.append(value)
        stdout,stderr,_=await asyncio.wait_for(asyncio.gather(read_bound(child.stdout,16384),
            read_bound(child.stderr,8192),child.wait()),400)
        generated=base64.b64decode(answer_used[0]['code']) if len(answer_used)==1 else None
        actual=(work/'example.py').read_bytes()
        if child.returncode!=0 or len(requests)!=2 or actual!=generated or (Path('/tmp/adapter-error.json').exists()):
            raise ValueError('OPENCODE_EDIT_FAILED')
        result.update(status='REAL_STRATA_CODE_APPLIED',exitCode=child.returncode,requests=len(requests),
            modelRequests=1,answerUsed=answer_used[0],outputFiles={'example.py':base64.b64encode(actual).decode()},
            stdout=stdout.decode(errors='replace').replace(token,'[redacted]'),
            stderr=stderr.decode(errors='replace').replace(token,'[redacted]'))
    except BaseException as error:
        terminate();result['error']=str(error)[:512]
        if Path('/tmp/adapter-error.json').exists():result['adapterError']=json.loads(Path('/tmp/adapter-error.json').read_text())
    finally:
        Path('/tmp/result.pending').write_text(json.dumps(result))
        Path('/tmp/result.pending').rename('/tmp/result.json')
        while not (bridge/'finish.worker').exists() and not (bridge/'cancel.worker').exists():time.sleep(.1)
        closed.set();server.shutdown();terminate()
    return 0 if result['status']=='REAL_STRATA_CODE_APPLIED' else 1

if __name__=='__main__':raise SystemExit(asyncio.run(run()))
