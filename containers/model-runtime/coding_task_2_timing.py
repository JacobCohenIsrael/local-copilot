"""Offline review of one task-2 successor with only its request deadline changed."""
import argparse
import hashlib
import json
from pathlib import Path

import coding_task_2_recovery as recovery
import container_test_150 as guest

p = recovery.p
REPO, HERE = recovery.REPO, recovery.HERE
ROOT = REPO / '.runtime/strata-coding-2-timing-review'
WORKER = REPO / '.runtime/strata-coding-2-timing-worker'
LIVE = REPO / '.runtime/strata-coding-2-timing-model'
PREPARATION = REPO / '.runtime/strata-coding-2-timing-files'
TIMEOUT_SHA = '55ef192ab57dde085aab4dd8840b7a765e019507f1ba96782eedd09bfcae8059'
TIMEOUT = recovery.ROOT / TIMEOUT_SHA
TIMEOUT_MANIFEST = 'ed524dcb61a59b10da3120c35d3d119fd46a5cb3ee8ff45a8e1629e9aa1d4c29'
SCOPE = 'one-fresh-useful-task-2-request-150s-all-other-limits-unchanged'
SCRIPTS = {'api_wrapper.py':'api_wrapper.py', 'container_test.py':'container_test_150.py',
           'container_test_base.py':'container_test.py'}
TIMING = {'setting':'engine_silence_s','from':30,'to':75,'hardRequestDeadlineSeconds':150}
_active = False


def timeout_proof(verify=False):
    if p.build.tools.sha(TIMEOUT / 'execution-preservation.json') != TIMEOUT_MANIFEST:
        raise ValueError('TIMEOUT_MANIFEST_CHANGED')
    manifest = p.read(TIMEOUT / 'execution-preservation.json', 1048576)
    if p.build.tools.sha(TIMEOUT / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('TIMEOUT_RESULT_CHANGED')
    result = p.read(TIMEOUT / 'execution-result.json', 131072)
    if (result['status'] != 'USEFUL_TASK_2_RECOVERY_FAULT_CONFIRMED_STOPPED' or
            result['reviewSha256'] != TIMEOUT_SHA or result['operationApprovalConsumed'] is not True or
            result['modelAttemptConsumed'] is not True or result['codingPatchSucceeded'] is not False or
            result['modelState']['phase'] != 'FAULT' or result['modelState']['stopConfirmed'] is not True or
            result['apiResult']['errorType'] != 'TimeoutError' or result['apiResult']['requestsSubmitted'] != 1 or
            result['allFourHostProcessesExited'] is not True):
        raise ValueError('TIMEOUT_COMPLETION_CHANGED')
    for key in ('independentModelState', 'independentWorkerState'):
        if result[key]['Running'] or result[key]['Pid'] != 0:
            raise ValueError('TIMEOUT_STOP_PROOF_CHANGED')
    expected = manifest['reviewEvidence']['owner-approved-decision.json']['sha256']
    if p.build.tools.sha(HERE / 'coding-task-2-recovery-approval.json') != expected:
        raise ValueError('TIMEOUT_APPROVAL_CHANGED')
    if verify:
        for key in ('attempt', 'worker', 'reader', 'launcher', 'capacityProbe', 'preparation', 'taskBundle'):
            record = manifest[key]
            directory = Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()} != set(record['files']):
                raise ValueError('TIMEOUT_FILE_SET_CHANGED')
            for name, item in record['files'].items():
                path = directory / name
                p.build.tools.plain(path)
                if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                    raise ValueError('TIMEOUT_EVIDENCE_CHANGED')
        actual = {x.relative_to(TIMEOUT).as_posix() for x in TIMEOUT.rglob('*') if x.is_file()}
        if actual != set(manifest['reviewEvidence']) | {'execution-preservation.json'}:
            raise ValueError('TIMEOUT_REVIEW_FILE_SET_CHANGED')
        for name, item in manifest['reviewEvidence'].items():
            path = TIMEOUT / name
            p.build.tools.plain(path)
            if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                raise ValueError('TIMEOUT_REVIEW_EVIDENCE_CHANGED')
    return {'reviewSha256':TIMEOUT_SHA, 'preservationSha256':TIMEOUT_MANIFEST,
            'resultSha256':manifest['executionResultSha256'], 'previousAttemptReset':False,
            'previousApprovalReused':False}


def same_limits(packet):
    old = p.read(TIMEOUT / 'review.json', 131072)
    if packet['requestTimingChange'] != TIMING or guest.REQUEST_SECONDS != 150:
        raise ValueError('ONLY_REQUEST_DEADLINE_150_ALLOWED')
    # Check every inherited invariant with only the expressly reviewed field
    # restored for the old comparison; the original packet is never mutated.
    recovery.same_limits({**packet, 'requestTimingChange':old['requestTimingChange']})
    if {**old['requestTimingChange'], 'hardRequestDeadlineSeconds':150} != TIMING:
        raise ValueError('OTHER_TIMING_CHANGE_FORBIDDEN')
    if p.INPUT_SCRIPTS != SCRIPTS:
        raise ValueError('TIMED_GUEST_SOURCES_CHANGED')
    inputs = Path(packet['packageDirectory']) / 'input'
    expected_names = set(SCRIPTS) | {'strata.json', 'request.json'}
    if set(packet['inputSha256']) != expected_names or {x.name for x in inputs.iterdir()} != expected_names:
        raise ValueError('TIMED_GUEST_INPUT_SET_CHANGED')
    for name, source in SCRIPTS.items():
        expected = hashlib.sha256((HERE / source).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if packet['inputSha256'][name] != expected or p.build.tools.sha(inputs / name) != expected:
            raise ValueError('TIMED_GUEST_INPUT_CHANGED')


def activate():
    global _active
    if _active: return
    recovery.activate()
    previous, proofs = p.previous, p.expected_proofs
    task = recovery.task
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.coding.WORKER_NAME = 'copilot-strata-coding-2-timing-worker-'
    p.LIVE = LIVE
    p.APPROVAL = HERE / 'coding-task-2-timing-approval.json'
    p.SCOPE = SCOPE
    p.INPUT_SCRIPTS = dict(SCRIPTS)
    p.REQUEST_TIMING_CHANGE = dict(TIMING)
    p.previous = lambda: {**previous(), 'usefulTask2Timeout':timeout_proof(True)}
    p.expected_proofs = lambda: {**proofs(), 'usefulTask2Timeout':timeout_proof()}
    p.same_limits = same_limits
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists(): raise ValueError('TIMING_SCOPE_ALREADY_CONSUMED')
    return recovery.task.prepare()


def summary():
    activate()
    return recovery.task.summary()


def run():
    activate()
    return recovery.task.coding.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['prepare', 'review', 'run'])
    parser.add_argument('--watch', action='store_true')
    options = parser.parse_args()
    if not options.watch and options.command is None: parser.error('command required')
    activate()
    if options.watch: recovery.task.coding.first_api.watch()
    else:
        result = prepare() if options.command == 'prepare' else summary() if options.command == 'review' else run()
        print(json.dumps(result, indent=2), flush=True)
        if options.command == 'run' and result['status'] != 'REAL_STRATA_CODING_PATCH_FOR_REVIEW': raise SystemExit(3)
