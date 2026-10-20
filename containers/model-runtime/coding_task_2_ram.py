"""Fresh task-2 scope with an explicit host-RAM job-readiness requirement."""
import argparse
import functools
import hashlib
import json
from pathlib import Path

import coding_task_2_compact as prior
import host_ram_readiness as readiness
import time

timing = prior.timing
statement = prior.statement

p = timing.p
task = timing.recovery.task
REPO, HERE = timing.REPO, timing.HERE
ROOT = REPO / '.runtime/strata-coding-2-ram-review'
WORKER = REPO / '.runtime/strata-coding-2-ram-worker'
LIVE = REPO / '.runtime/strata-coding-2-ram-model'
PREPARATION = REPO / '.runtime/strata-coding-2-ram-files'
REJECTED_SHA = '9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a'
REJECTED = prior.ROOT / REJECTED_SHA
REJECTED_MANIFEST = 'e03c7f983f591e1c53bc1124798d6ce27778d27f74465360b6f2b828278827c0'
SCOPE = 'one-fresh-useful-task-2-host-ram-readiness-same-safety-limits'
RAM_GATE = REPO / '.runtime/strata-coding-2-ram-readiness'
PROMPT = 'Python guard only: reject negative integer maximum with ValueError.'
REQUEST = {**task.REQUEST, 'messages': [{'role': 'user', 'content': PROMPT}]}
HELPERS = {'probe.py': 'bounded_read_statement.py', 'bounded_read_task.py': 'bounded_read_task.py',
           'coding_worker.py': 'coding_worker.py'}
_active = False


def ram_fault_proof(verify=False):
    if p.build.tools.sha(REJECTED / 'execution-preservation.json') != REJECTED_MANIFEST:
        raise ValueError('REJECTED_MANIFEST_CHANGED')
    manifest = p.read(REJECTED / 'execution-preservation.json', 1048576)
    if p.build.tools.sha(REJECTED / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('REJECTED_RESULT_CHANGED')
    result = p.read(REJECTED / 'execution-result.json', 131072)
    if (result['status'] != 'USEFUL_TASK_2_COMPACT_FAULT_CONFIRMED_STOPPED' or
            result['reviewSha256'] != REJECTED_SHA or result['operationApprovalConsumed'] is not True or
            result['modelAttemptConsumed'] is not True or result['codingPatchSucceeded'] is not False or
            result['modelState']['phase'] != 'FAULT' or result['modelState']['stopConfirmed'] is not True or
            result['apiResult'] is not None or result['allFourHostProcessesExited'] is not True or
            result['modelState']['fault']['code'] != 'HOST_RAM_HIGH' or
            result['totalConsumedModelAttempts'] != 14 or
            result['patchApplied'] is not False):
        raise ValueError('REJECTED_COMPLETION_CHANGED')
    for key in ('independentModelState', 'independentWorkerState'):
        if result[key]['Running'] or result[key]['Pid'] != 0:
            raise ValueError('REJECTED_STOP_PROOF_CHANGED')
    expected = manifest['reviewEvidence']['owner-approved-decision.json']['sha256']
    if p.build.tools.sha(HERE / 'coding-task-2-compact-approval.json') != expected:
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
    # Every existing limit, request and model/worker input stays fixed.
    # The additional job-readiness condition is separately bound and approved.
    for key in ('policy', 'configuration', 'requestTimingChange', 'fileAccessChange',
                'startupTargetChange', 'startupStatusChange', 'vmEnvelope', 'settings', 'modelFiles',
                'sourceLimitation', 'sourceReviewSha256', 'runtimeBundle', 'buildProof', 'sourceTree',
                'sourcePlan', 'limitations', 'startupSourceAudit', 'controls', 'modelLargeFileBinding'):
        if packet[key] != old[key]:
            raise ValueError('RAM_MUST_KEEP_REVIEWED_LIMITS_AND_INPUTS')
    if packet['request'] != REQUEST or packet['request'] != old['request']:
        raise ValueError('RAM_SCOPE_REQUEST_MUST_STAY_UNCHANGED')
    if packet.get('hostRamReadiness') != readiness.CONDITION:
        raise ValueError('RAM_READINESS_CONDITION_CHANGED')
    for key in ('host', 'environment', 'gpuRequests', 'image', 'imageId', 'alternateImageId', 'entrypoint', 'command'):
        if packet['contract'][key] != old['contract'][key]:
            raise ValueError('RAM_MODEL_CONTRACT_CHANGED')
    for key in ('task', 'selectedFile', 'repositoryFile', 'sourceSha256', 'workerEnvelope', 'modelCalls',
                'opencodeCalls', 'maximumModelOutputTokens', 'maximumGuardBytes', 'nativeToolCallingTested'):
        if packet['codingTask'][key] != old['codingTask'][key]:
            raise ValueError('RAM_FIXED_CODING_TASK_CHANGED')
    if (p.INPUT_SCRIPTS != timing.SCRIPTS or task.WORKER_HELPERS != HELPERS or
            timing.guest.REQUEST_SECONDS != 150):
        raise ValueError('RAM_SCOPED_HELPERS_CHANGED')
    inputs = Path(packet['packageDirectory']) / 'input'
    if set(packet['inputSha256']) != set(old['inputSha256']) or {x.name for x in inputs.iterdir()} != set(old['inputSha256']):
        raise ValueError('RAM_INPUT_SET_CHANGED')
    if p.read(inputs / 'request.json') != REQUEST or p.read(inputs / 'strata.json') != old['configuration']:
        raise ValueError('RAM_BAKED_REQUEST_OR_CONFIG_CHANGED')
    for name, source in timing.SCRIPTS.items():
        expected = hashlib.sha256((HERE / source).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if packet['inputSha256'][name] != old['inputSha256'][name] or p.build.tools.sha(inputs / name) != expected:
            raise ValueError('RAM_GUEST_INPUT_CHANGED')
    task.check_task(packet['codingTask'])


def activate():
    global _active
    if _active: return
    prior.activate()
    previous, proofs = p.previous, p.expected_proofs
    prepare_packet, authorize_packet = p.prepare, p.authorize
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.WORKER_HELPERS = dict(HELPERS)
    task.coding.WORKER_NAME = 'copilot-strata-coding-2-ram-worker-'
    task.coding.REQUEST = p.REQUEST = REQUEST
    original = task.coding.task_bundle.bounded_read(REPO / task.task_spec.SOURCE)
    task.task_spec.validate_original(original)
    task.coding.coding_worker.code_from_response = functools.partial(statement.replacement, original=original)
    p.LIVE = LIVE
    p.APPROVAL = HERE / 'coding-task-2-ram-approval.json'
    p.SCOPE = SCOPE
    p.previous = lambda: {**previous(), 'usefulTask2HostRamFault': ram_fault_proof(True)}
    p.expected_proofs = lambda: {**proofs(), 'usefulTask2HostRamFault': ram_fault_proof()}
    p.same_limits = same_limits
    def prepare_with_readiness(extra=None):
        if extra and 'hostRamReadiness' in extra: raise ValueError('RAM_READINESS_FIELD_COLLISION')
        return prepare_packet({**(extra or {}), 'hostRamReadiness': dict(readiness.CONDITION)})
    def owner_authorize():
        permit = authorize_packet()
        if p.read(p.APPROVAL, 16384).get('acceptHostRamReadiness') != readiness.CONDITION:
            raise ValueError('HOST_RAM_READINESS_NOT_APPROVED')
        return permit
    def admitted_authorize():
        permit = owner_authorize()
        record = p.read(RAM_GATE / 'result.json', 16384)
        observation = p.read(RAM_GATE / 'observation.json', 4096)
        expected = readiness.evaluate(observation, unix=observation['recordedAtUnix'])
        query = p.read(RAM_GATE / 'query-process.json', 4096)
        exited = p.read(RAM_GATE / 'query-exit.json', 4096)
        if (record.get('status') != 'READY_FOR_SINGLE_WORKLOAD' or
                record.get('reviewSha256') != permit.review_sha256 or
                record.get('approvalSha256') != permit.approval_sha256 or
                record.get('observationSha256') != p.sha(observation) or
                record.get('readiness') != expected or expected['ready'] is not True or
                exited.get('confirmedExited') is not True or exited.get('exitCode') != 0 or
                type(query.get('pid')) is not int or query['pid'] <= 0 or exited.get('pid') != query['pid']):
            raise ValueError('HOST_RAM_JOB_NOT_READY')
        return permit
    p.prepare = prepare_with_readiness
    p.authorize = admitted_authorize
    global _owner_authorize
    _owner_authorize = owner_authorize
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists() or RAM_GATE.exists(): raise ValueError('RAM_SCOPE_ALREADY_CONSUMED')
    return task.prepare()


def summary():
    activate()
    if RAM_GATE.exists():
        return {'status': 'ATTEMPT_CONSUMED', 'readinessDirectory': str(RAM_GATE),
                'modelLaunchEnabled': False, 'workerLaunchEnabled': False}
    return task.summary()


def run():
    activate()
    if RAM_GATE.exists() or WORKER.exists() or LIVE.exists():
        raise ValueError('RAM_SCOPE_ATTEMPT_CONSUMED')
    permit = _owner_authorize()  # Missing approval refuses before the RAM observation.
    RAM_GATE.mkdir(parents=True, exist_ok=False)
    task.coding.save(RAM_GATE / 'attempt.json', {'reviewSha256': permit.review_sha256,
                     'approvalSha256': permit.approval_sha256, 'automaticRetry': False})
    record = {'status': 'FAULT', 'reviewSha256': permit.review_sha256,
              'approvalSha256': permit.approval_sha256, 'operationApprovalConsumed': True,
              'modelStarted': False, 'workerStarted': False, 'automaticRetry': False}
    try:
        frame = readiness.read_once(RAM_GATE)
        task.coding.save(RAM_GATE / 'observation.json', frame)
        record['observationSha256'] = p.sha(frame)
        record['readiness'] = readiness.evaluate(frame, unix=time.time())
        record['status'] = 'READY_FOR_SINGLE_WORKLOAD' if record['readiness']['ready'] else 'NOT_READY'
    except Exception as error:
        record['error'] = {'type': type(error).__name__, 'message': str(error)[:512]}
    task.coding.save(RAM_GATE / 'result.json', record)
    if record['status'] != 'READY_FOR_SINGLE_WORKLOAD':
        raise ValueError('TASK_HOST_RAM_HEADROOM_NOT_READY')
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
