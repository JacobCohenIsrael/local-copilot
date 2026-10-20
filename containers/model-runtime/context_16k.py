"""One reviewed 16K allocation/coding probe; not a full-window capacity claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import coding_task_2_ram30 as prior
import context_16k_guest as guest

p, task = prior.p, prior.task
REPO, HERE = prior.REPO, prior.HERE
ROOT = REPO / '.runtime/strata-context-16k-review'
LIVE = REPO / '.runtime/strata-context-16k-model'
WORKER = REPO / '.runtime/strata-context-16k-worker'
PREPARATION = REPO / '.runtime/strata-context-16k-files'
SCOPE = 'one-16k-context-allocation-task-2-64-output-no-readiness'
PREVIOUS_SHA = '4b1d0a4a15eec7f180a13d52ce23c68b4d2860fbe903960c645cfabc27937875'
PREVIOUS = prior.ROOT / PREVIOUS_SHA
PREVIOUS_MANIFEST = 'ee0da137ccc41fa58afa3a7734c79741d4d9e1631bd92d97739939d037136da2'
REQUEST = {**prior.REQUEST, 'max_tokens': guest.OUTPUT_TOKENS}
SCRIPTS = {'api_wrapper.py':'api_wrapper.py', 'container_test.py':'context_16k_guest.py',
           'container_test_base.py':'container_test.py'}
PROBE = {'configuredContextTokens':16384, 'outputTokens':64, 'previousOutputTokens':32,
         'actualPromptTokensExpected':23, 'marginTokens':8,
         'kind':'allocation-and-small-coding-request', 'fullWindowCapacityTest':False,
         'fullWindowCapacityEstablishedBySuccess':False, 'automaticNextAttempt':False,
         'searchStartTokens':16384, 'goalTokens':65536, 'automaticRetry':False}
_active = False


def previous_proof(verify=False):
    if p.build.tools.sha(PREVIOUS / 'execution-preservation.json') != PREVIOUS_MANIFEST:
        raise ValueError('RAM30_MANIFEST_CHANGED')
    manifest = p.read(PREVIOUS / 'execution-preservation.json',1048576)
    if p.build.tools.sha(PREVIOUS / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('RAM30_RESULT_CHANGED')
    result = p.read(PREVIOUS / 'execution-result.json',131072)
    if (result['status'] != 'USEFUL_TASK_2_RAM30_FAULT_CONFIRMED_STOPPED' or
            result['reviewSha256'] != PREVIOUS_SHA or result['totalConsumedModelAttempts'] != 15 or
            result['operationApprovalConsumed'] is not True or result['modelAttemptConsumed'] is not True or
            result['modelState']['phase'] != 'COMPLETE' or result['modelState']['stopConfirmed'] is not True or
            result['apiResult']['requestsSubmitted'] != 1 or
            result['apiResult']['response']['choices'][0]['finish_reason'] != 'length' or
            result['integration']['error']['reason'] != 'MODEL_OUTPUT_INCOMPLETE' or
            result['codingPatchSucceeded'] is not False or result['patchApplied'] is not False or
            result['allFourHostProcessesExited'] is not True):
        raise ValueError('RAM30_COMPLETION_CHANGED')
    for key in ('independentModelState','independentWorkerState'):
        if result[key]['Running'] or result[key]['Pid'] != 0: raise ValueError('RAM30_STOP_CHANGED')
    if p.build.tools.sha(HERE / 'coding-task-2-ram30-approval.json') != manifest['reviewEvidence']['owner-approved-decision.json']['sha256']:
        raise ValueError('RAM30_APPROVAL_CHANGED')
    if verify:
        for key in ('attempt','worker','reader','launcher','capacityProbe','preparation','taskBundle'):
            record = manifest[key]; directory = Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()} != set(record['files']):
                raise ValueError('RAM30_FILE_SET_CHANGED')
            for name,item in record['files'].items():
                path = directory / name; p.build.tools.plain(path)
                if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                    raise ValueError('RAM30_EVIDENCE_CHANGED')
        if {x.relative_to(PREVIOUS).as_posix() for x in PREVIOUS.rglob('*') if x.is_file()} != set(manifest['reviewEvidence']) | {'execution-preservation.json'}:
            raise ValueError('RAM30_REVIEW_SET_CHANGED')
        for name,item in manifest['reviewEvidence'].items():
            path = PREVIOUS / name; p.build.tools.plain(path)
            if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                raise ValueError('RAM30_REVIEW_CHANGED')
    return {'reviewSha256':PREVIOUS_SHA, 'preservationSha256':PREVIOUS_MANIFEST,
            'resultSha256':manifest['executionResultSha256'], 'previousApprovalReused':False,
            'previousAttemptReset':False}


def larger_context(cfg):
    cfg = copy.deepcopy(cfg)
    args = cfg['args']
    if args.count('--max-context') != 1: raise ValueError('CONTEXT_ARGUMENT_REQUIRED')
    args[args.index('--max-context')+1] = str(guest.CONTEXT_TOKENS)
    return cfg


def same_limits(packet):
    old = p.read(PREVIOUS / 'review.json',131072)
    for key in ('policy','requestTimingChange','fileAccessChange','startupTargetChange','startupStatusChange',
                'vmEnvelope','settings','modelFiles','sourceLimitation','sourceReviewSha256','runtimeBundle',
                'buildProof','sourceTree','sourcePlan','limitations','controls','modelLargeFileBinding'):
        if packet[key] != old[key]: raise ValueError('CONTEXT_PROBE_OTHER_LIMIT_CHANGED')
    if packet['configuration'] != larger_context(old['configuration']) or packet['request'] != REQUEST:
        raise ValueError('ONLY_16K_CONTEXT_64_OUTPUT_CHANGES_ALLOWED')
    if {**packet['request'],'max_tokens':32} != old['request']:
        raise ValueError('CONTEXT_PROBE_PROMPT_CHANGED')
    if packet.get('contextProbe') != PROBE or 'hostRamReadiness' in packet:
        raise ValueError('CONTEXT_PROBE_CLAIM_OR_READINESS_CHANGED')
    audit = copy.deepcopy(old['startupSourceAudit'])
    args = audit['engineCommand']; args[args.index('--max-context')+1] = '16384'
    if packet['startupSourceAudit'] != audit: raise ValueError('CONTEXT_SOURCE_AUDIT_CHANGED')
    for key in ('host','environment','gpuRequests','image','imageId','alternateImageId','entrypoint','command'):
        if packet['contract'][key] != old['contract'][key]: raise ValueError('CONTEXT_MODEL_CONTRACT_CHANGED')
    for key in ('task','selectedFile','repositoryFile','sourceSha256','workerEnvelope','modelCalls','opencodeCalls',
                'maximumGuardBytes','nativeToolCallingTested'):
        if packet['codingTask'][key] != old['codingTask'][key]: raise ValueError('CONTEXT_CODING_TASK_CHANGED')
    if packet['codingTask']['maximumModelOutputTokens'] != 64 or task.MAXIMUM_OUTPUT_TOKENS != 64:
        raise ValueError('CONTEXT_OUTPUT_64_REQUIRED')
    if p.INPUT_SCRIPTS != SCRIPTS or task.WORKER_HELPERS != prior.HELPERS:
        raise ValueError('CONTEXT_SCOPED_HELPERS_CHANGED')
    inputs = Path(packet['packageDirectory']) / 'input'
    if set(packet['inputSha256']) != set(SCRIPTS) | {'request.json','strata.json'}:
        raise ValueError('CONTEXT_INPUT_SET_CHANGED')
    if {x.name for x in inputs.iterdir()} != set(packet['inputSha256']): raise ValueError('CONTEXT_INPUT_SET_CHANGED')
    if p.read(inputs/'request.json') != REQUEST or p.read(inputs/'strata.json') != packet['configuration']:
        raise ValueError('CONTEXT_BAKED_INPUT_CHANGED')
    for name,source in SCRIPTS.items():
        expected = hashlib.sha256((HERE/source).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if packet['inputSha256'][name] != expected or p.build.tools.sha(inputs/name) != expected:
            raise ValueError('CONTEXT_GUEST_CHANGED')
    task.check_task(packet['codingTask'])


def activate():
    global _active
    if _active: return
    prior.activate()
    old_previous, old_proofs, old_config, old_prepare = p.previous, p.expected_proofs, p.config, p.prepare
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.MAXIMUM_OUTPUT_TOKENS = 64
    task.coding.WORKER_NAME = 'copilot-strata-context-16k-worker-'
    task.coding.REQUEST = p.REQUEST = REQUEST
    task.coding.first_api.validate_response = guest.validate_response
    p.LIVE, p.APPROVAL, p.SCOPE = LIVE, HERE/'context-16k-approval.json', SCOPE
    p.INPUT_SCRIPTS = dict(SCRIPTS)
    p.config = lambda: larger_context(old_config())
    p.previous = lambda: {**old_previous(),'usefulTask2Ram30Output':previous_proof(True)}
    p.expected_proofs = lambda: {**old_proofs(),'usefulTask2Ram30Output':previous_proof()}
    p.prepare = lambda extra=None: old_prepare({**(extra or {}),'contextProbe':dict(PROBE)})
    p.same_limits = same_limits
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists(): raise ValueError('CONTEXT_SCOPE_ALREADY_CONSUMED')
    return task.prepare()


def summary():
    activate()
    return task.summary()


def run():
    activate()
    return task.coding.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['prepare','review','run'])
    parser.add_argument('--watch',action='store_true')
    options = parser.parse_args()
    if not options.watch and options.command is None: parser.error('command required')
    activate()
    if options.watch: task.coding.first_api.watch()
    else:
        result = prepare() if options.command=='prepare' else summary() if options.command=='review' else run()
        print(json.dumps(result,indent=2),flush=True)
        if options.command=='run' and result['status']!='REAL_STRATA_CODING_PATCH_FOR_REVIEW': raise SystemExit(3)
