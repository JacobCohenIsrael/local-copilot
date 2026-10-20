"""Fresh review for the same fixed task; never reuse the consumed worker scope."""
import argparse
from pathlib import Path
import json

import coding_task_2 as task

p = task.p
REPO = task.REPO
HERE = task.HERE
ROOT = REPO / '.runtime/strata-coding-2-recovery-review'
WORKER = REPO / '.runtime/strata-coding-2-recovery-worker'
LIVE = REPO / '.runtime/strata-coding-2-recovery-model'
PREPARATION = REPO / '.runtime/strata-coding-2-recovery-files'
FAILED_SHA = '549cb02957572957e23f1cc8346803ee3bbb3bef1c924bdf6ff2e64ef4d161e8'
FAILED = task.ROOT / FAILED_SHA
FAILED_MANIFEST = '7a8838a0f40b4af513b2dfb03a4e6caee03797ccdf2978dfbe221eb5a8f35354'
SCOPE = 'one-fresh-useful-task-2-after-docker-unavailable-same-limits'
_active = False


def failed_proof(verify=False):
    if p.build.tools.sha(FAILED / 'execution-preservation.json') != FAILED_MANIFEST:
        raise ValueError('FAILED_CODING_MANIFEST_CHANGED')
    manifest = p.read(FAILED / 'execution-preservation.json', 1048576)
    if p.build.tools.sha(FAILED / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('FAILED_CODING_RESULT_CHANGED')
    result = p.read(FAILED / 'execution-result.json', 65536)
    if (result['reviewSha256'] != FAILED_SHA or result['status'] != 'USEFUL_CODING_TASK_2_FAULT_BEFORE_CONTAINER_CREATION' or
            result['operationApprovalConsumed'] is not True or result['workerAttemptConsumed'] is not True or
            result['workerStarted'] is not False or result['modelStarted'] is not False or
            result['patch'] is not None or result['ownedHostProcessesIndependentlyConfirmedExited'] is not True):
        raise ValueError('FAILED_CODING_SCOPE_CHANGED')
    approval = HERE / 'coding-task-2-approval.json'
    if p.build.tools.sha(approval) != result['approvalSha256']:
        raise ValueError('FAILED_CODING_APPROVAL_CHANGED')
    if verify:
        for key in ('worker', 'launcher', 'preparation', 'taskBundle'):
            record = manifest[key]
            directory = Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()} != set(record['files']):
                raise ValueError('FAILED_CODING_FILE_SET_CHANGED')
            for name, item in record['files'].items():
                path = directory / name
                p.build.tools.plain(path)
                if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                    raise ValueError('FAILED_CODING_EVIDENCE_CHANGED')
        actual = {x.relative_to(FAILED).as_posix() for x in FAILED.rglob('*') if x.is_file()}
        if actual != set(manifest['reviewEvidence']) | {'execution-preservation.json'}:
            raise ValueError('FAILED_CODING_REVIEW_FILE_SET_CHANGED')
        for name, item in manifest['reviewEvidence'].items():
            path = FAILED / name
            p.build.tools.plain(path)
            if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                raise ValueError('FAILED_CODING_REVIEW_EVIDENCE_CHANGED')
    return {'reviewSha256': FAILED_SHA, 'preservationSha256': FAILED_MANIFEST,
            'resultSha256': manifest['executionResultSha256'], 'approvalSha256': result['approvalSha256'],
            'previousAttemptReset': False, 'previousApprovalReused': False}


def same_limits(packet):
    task.coding.same_limits(packet)
    old = p.read(FAILED / 'review.json', 131072)
    for key in ('policy', 'request', 'configuration', 'requestTimingChange', 'fileAccessChange',
                'startupTargetChange', 'startupStatusChange', 'vmEnvelope', 'settings', 'modelFiles',
                'sourceLimitation', 'sourceReviewSha256', 'runtimeBundle', 'buildProof', 'sourceTree', 'sourcePlan', 'limitations'):
        if packet[key] != old[key]:
            raise ValueError('RECOVERY_MUST_KEEP_REVIEWED_LIMITS_AND_INPUTS')
    for key in ('task', 'selectedFile', 'repositoryFile', 'sourceSha256', 'workerEnvelope', 'modelCalls',
                'opencodeCalls', 'maximumModelOutputTokens', 'maximumGuardBytes', 'nativeToolCallingTested'):
        if packet['codingTask'][key] != old['codingTask'][key]:
            raise ValueError('RECOVERY_MUST_KEEP_FIXED_CODING_TASK')


def activate():
    global _active
    if _active: return
    task.activate()
    previous, proofs = p.previous, p.expected_proofs
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.coding.WORKER_NAME = 'copilot-strata-coding-2-recovery-worker-'
    p.LIVE = LIVE
    p.APPROVAL = HERE / 'coding-task-2-recovery-approval.json'
    p.SCOPE = SCOPE
    p.previous = lambda: {**previous(), 'usefulTask2Failed': failed_proof(True)}
    p.expected_proofs = lambda: {**proofs(), 'usefulTask2Failed': failed_proof()}
    p.same_limits = same_limits
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists(): raise ValueError('RECOVERY_SCOPE_ALREADY_CONSUMED')
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
