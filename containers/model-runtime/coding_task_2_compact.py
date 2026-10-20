"""Offline compact task-2 request; preserve silence guard and failed history."""
import argparse
import functools
import hashlib
import json
from pathlib import Path

import coding_task_2_statement as prior

timing = prior.timing
statement = prior.statement

p = timing.p
task = timing.recovery.task
REPO, HERE = timing.REPO, timing.HERE
ROOT = REPO / '.runtime/strata-coding-2-compact-review'
WORKER = REPO / '.runtime/strata-coding-2-compact-worker'
LIVE = REPO / '.runtime/strata-coding-2-compact-model'
PREPARATION = REPO / '.runtime/strata-coding-2-compact-files'
REJECTED_SHA = '268602b8691a2d036f2c239f955eb1aa2a056b2fe24b5ab64936d27c8be0caad'
REJECTED = prior.ROOT / REJECTED_SHA
REJECTED_MANIFEST = '2d5084feb8d468cca11d011631b50b9b363c748ec4b96e1be97d60bf38e8cf74'
SCOPE = 'one-fresh-useful-task-2-compact-guard-same-safety-limits'
PROMPT = 'Python guard only: reject negative integer maximum with ValueError.'
REQUEST = {**task.REQUEST, 'messages': [{'role': 'user', 'content': PROMPT}]}
HELPERS = {'probe.py': 'bounded_read_statement.py', 'bounded_read_task.py': 'bounded_read_task.py',
           'coding_worker.py': 'coding_worker.py'}
_active = False


def silence_proof(verify=False):
    if p.build.tools.sha(REJECTED / 'execution-preservation.json') != REJECTED_MANIFEST:
        raise ValueError('REJECTED_MANIFEST_CHANGED')
    manifest = p.read(REJECTED / 'execution-preservation.json', 1048576)
    if p.build.tools.sha(REJECTED / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('REJECTED_RESULT_CHANGED')
    result = p.read(REJECTED / 'execution-result.json', 131072)
    if (result['status'] != 'USEFUL_TASK_2_STATEMENT_FAULT_CONFIRMED_STOPPED' or
            result['reviewSha256'] != REJECTED_SHA or result['operationApprovalConsumed'] is not True or
            result['modelAttemptConsumed'] is not True or result['codingPatchSucceeded'] is not False or
            result['modelState']['phase'] != 'FAULT' or result['modelState']['stopConfirmed'] is not True or
            result['apiResult']['status'] != 'FAULT' or
            result['apiResult']['requestsSubmitted'] != 1 or result['allFourHostProcessesExited'] is not True or
            result['modelState']['fault']['code'] != 'API_TEST_FAILED' or
            result['apiResult']['errorType'] != 'HTTPError' or
            result['apiResult']['error'] != 'HTTP Error 503: Service Unavailable' or
            result['patchApplied'] is not False):
        raise ValueError('REJECTED_COMPLETION_CHANGED')
    for key in ('independentModelState', 'independentWorkerState'):
        if result[key]['Running'] or result[key]['Pid'] != 0:
            raise ValueError('REJECTED_STOP_PROOF_CHANGED')
    expected = manifest['reviewEvidence']['owner-approved-decision.json']['sha256']
    if p.build.tools.sha(HERE / 'coding-task-2-statement-approval.json') != expected:
        raise ValueError('REJECTED_APPROVAL_CHANGED')
    if verify:
        for key in ('attempt', 'worker', 'reader', 'launcher', 'capacityProbe', 'preparation', 'taskBundle'):
            record = manifest[key]
            directory = Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()} != set(record['files']):
                raise ValueError('REJECTED_FILE_SET_CHANGED')
            for name, item in record['files'].items():
                path = directory / name
                p.build.tools.plain(path)
                if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                    raise ValueError('REJECTED_EVIDENCE_CHANGED')
        actual = {x.relative_to(REJECTED).as_posix() for x in REJECTED.rglob('*') if x.is_file()}
        if actual != set(manifest['reviewEvidence']) | {'execution-preservation.json'}:
            raise ValueError('REJECTED_REVIEW_FILE_SET_CHANGED')
        for name, item in manifest['reviewEvidence'].items():
            path = REJECTED / name
            p.build.tools.plain(path)
            if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                raise ValueError('REJECTED_REVIEW_EVIDENCE_CHANGED')
    return {'reviewSha256': REJECTED_SHA, 'preservationSha256': REJECTED_MANIFEST,
            'resultSha256': manifest['executionResultSha256'], 'previousAttemptReset': False,
            'previousApprovalReused': False}


def same_limits(packet):
    old = p.read(REJECTED / 'review.json', 131072)
    # This scope shortens only the prompt. Strict response admission stays fixed.
    # Compare
    # every inherited safety/input invariant directly to the latest live review.
    for key in ('policy', 'configuration', 'requestTimingChange', 'fileAccessChange',
                'startupTargetChange', 'startupStatusChange', 'vmEnvelope', 'settings', 'modelFiles',
                'sourceLimitation', 'sourceReviewSha256', 'runtimeBundle', 'buildProof', 'sourceTree',
                'sourcePlan', 'limitations', 'startupSourceAudit', 'controls', 'modelLargeFileBinding'):
        if packet[key] != old[key]:
            raise ValueError('COMPACT_MUST_KEEP_REVIEWED_LIMITS_AND_INPUTS')
    if packet['request'] != REQUEST or {**packet['request'], 'messages': old['request']['messages']} != old['request']:
        raise ValueError('ONLY_REVIEWED_COMPACT_PROMPT_CHANGE_ALLOWED')
    for key in ('host', 'environment', 'gpuRequests', 'image', 'imageId', 'alternateImageId', 'entrypoint', 'command'):
        if packet['contract'][key] != old['contract'][key]:
            raise ValueError('COMPACT_MODEL_CONTRACT_CHANGED')
    for key in ('task', 'selectedFile', 'repositoryFile', 'sourceSha256', 'workerEnvelope', 'modelCalls',
                'opencodeCalls', 'maximumModelOutputTokens', 'maximumGuardBytes', 'nativeToolCallingTested'):
        if packet['codingTask'][key] != old['codingTask'][key]:
            raise ValueError('COMPACT_FIXED_CODING_TASK_CHANGED')
    if (p.INPUT_SCRIPTS != timing.SCRIPTS or task.WORKER_HELPERS != HELPERS or
            timing.guest.REQUEST_SECONDS != 150):
        raise ValueError('COMPACT_SCOPED_HELPERS_CHANGED')
    inputs = Path(packet['packageDirectory']) / 'input'
    if set(packet['inputSha256']) != set(old['inputSha256']) or {x.name for x in inputs.iterdir()} != set(old['inputSha256']):
        raise ValueError('COMPACT_INPUT_SET_CHANGED')
    if p.read(inputs / 'request.json') != REQUEST or p.read(inputs / 'strata.json') != old['configuration']:
        raise ValueError('COMPACT_BAKED_REQUEST_OR_CONFIG_CHANGED')
    for name, source in timing.SCRIPTS.items():
        expected = hashlib.sha256((HERE / source).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if packet['inputSha256'][name] != old['inputSha256'][name] or p.build.tools.sha(inputs / name) != expected:
            raise ValueError('COMPACT_GUEST_INPUT_CHANGED')
    task.check_task(packet['codingTask'])


def activate():
    global _active
    if _active: return
    prior.activate()
    previous, proofs = p.previous, p.expected_proofs
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.WORKER_HELPERS = dict(HELPERS)
    task.coding.WORKER_NAME = 'copilot-strata-coding-2-compact-worker-'
    task.coding.REQUEST = p.REQUEST = REQUEST
    original = task.coding.task_bundle.bounded_read(REPO / task.task_spec.SOURCE)
    task.task_spec.validate_original(original)
    task.coding.coding_worker.code_from_response = functools.partial(statement.replacement, original=original)
    p.LIVE = LIVE
    p.APPROVAL = HERE / 'coding-task-2-compact-approval.json'
    p.SCOPE = SCOPE
    p.previous = lambda: {**previous(), 'usefulTask2EngineSilence': silence_proof(True)}
    p.expected_proofs = lambda: {**proofs(), 'usefulTask2EngineSilence': silence_proof()}
    p.same_limits = same_limits
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists(): raise ValueError('COMPACT_SCOPE_ALREADY_CONSUMED')
    return task.prepare()


def summary():
    activate()
    return task.summary()


def run():
    activate()
    return task.coding.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['prepare', 'review', 'run'])
    parser.add_argument('--watch', action='store_true')
    options = parser.parse_args()
    if not options.watch and options.command is None: parser.error('command required')
    activate()
    if options.watch: task.coding.first_api.watch()
    else:
        result = prepare() if options.command == 'prepare' else summary() if options.command == 'review' else run()
        print(json.dumps(result, indent=2), flush=True)
        if options.command == 'run' and result['status'] != 'REAL_STRATA_CODING_PATCH_FOR_REVIEW': raise SystemExit(3)
