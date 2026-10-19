"""Source-bound native-IQ argument checks; no engine, model or GPU execution."""
import ast
import hashlib
from pathlib import Path

CPP_SHA = 'fd85d08db152867dfe9a36afaee584b643bd26ddd70d791f9ef95ca47ab940c7'
SERVER_SHA = '6c45c639e28a873b854606719d9ce2bb2e0df666f105164e78e2735878b9aa8f'


def check(cfg, source):
    source = Path(source)
    cpp_raw = (source/'src/program/generate.cpp').read_bytes()
    server_raw = (source/'serve/server.py').read_bytes()
    if (hashlib.sha256(cpp_raw).hexdigest() != CPP_SHA or
            hashlib.sha256(server_raw).hexdigest() != SERVER_SHA):
        raise ValueError('NATIVE_IQ_PINNED_SOURCE_CHANGED')
    cpp = cpp_raw.decode('utf-8')
    for required in ('o.native_preset.empty() || o.spec < 2 || o.keep_canonical',
            'if (o.spec < 2 || o.prefill_chunk <= 0 ||',
            'const bool use_mtp = !o.mtp.empty();',
            'int T = use_mtp ? S_mtp : 1;',
            'if (o.suffix_draft > 0 && !first_window)', 'int lookup_chain = 0;'):
        if required not in cpp:
            raise ValueError('NATIVE_IQ_SOURCE_CONTRACT_CHANGED')
    args = cfg['args']
    def value(flag):
        if args.count(flag) != 1 or args.index(flag)+1 >= len(args):
            raise ValueError('NATIVE_IQ_REQUIRED_ARGUMENT_'+flag)
        return args[args.index(flag)+1]
    if int(value('--spec')) < 2:
        raise ValueError('NATIVE_IQ_SPEC_BELOW_TWO')
    if int(value('--prefill')) <= 0 or not value('--native'):
        raise ValueError('NATIVE_IQ_NATIVE_OR_PREFILL_REQUIRED')
    if (value('--spec') != '2' or value('--suffix-draft') != '0' or
            any(x in args for x in ('--mtp','--lookup-chain','--keep-canonical','--batch','--batch-mtp')) or
            'vision' in cfg or 'expert_profile_save' in cfg or 'parallel' in cfg):
        raise ValueError('NATIVE_IQ_MINIMAL_STARTUP_ONLY')
    # Execute only these pinned, pure argument functions, not module imports,
    # StrataEngine, CUDA checks, or any top-level upstream initialization.
    names = {'gpu_list','layer_split_of','engine_args','parallel_args','learned_profile_args','engine_silence_s'}
    selected = [node for node in ast.parse(server_raw).body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != names:
        raise ValueError('NATIVE_IQ_ARGUMENT_BUILDER_CHANGED')
    builtins = {'bool':bool,'dict':dict,'int':int,'str':str,'list':list,'tuple':tuple,
                'len':len,'isinstance':isinstance,'float':float,'ValueError':ValueError}
    namespace = {'__builtins__':builtins}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(source/'serve/server.py'),'exec'),namespace)
    forwarded = namespace['engine_args'](cfg)
    silence = namespace['engine_silence_s'](cfg)
    if silence != 75:
        raise ValueError('BOUNDED_ENGINE_SILENCE_75_REQUIRED')
    if forwarded != args:
        raise ValueError('NATIVE_IQ_UPSTREAM_ARGUMENT_REWRITE')
    return {'status':'OFFLINE_PINNED_SOURCE_ARGUMENTS_VERIFIED','cppSha256':CPP_SHA,
            'serverSha256':SERVER_SHA,'specWindow':2,'mtpEnabled':False,'suffixDraft':0,
            'engineSilenceSeconds':silence,'upstreamArgsUnchanged':True,'engineCommand':[cfg['exe'],'--serve',*forwarded],
            'nativeEngineExecuted':False,'modelReadinessProven':False}
