"""Fresh task-2 scope: owner-approved 30 GiB RAM stop; readiness deferred."""
import argparse
import functools
import hashlib
import json
from pathlib import Path

import coding_task_2_compact as prior
import coding_task_2_ram as history

timing = prior.timing
statement = prior.statement

p = timing.p
task = timing.recovery.task
REPO, HERE = timing.REPO, timing.HERE
ROOT = REPO / '.runtime/strata-coding-2-ram30-review'
WORKER = REPO / '.runtime/strata-coding-2-ram30-worker'
LIVE = REPO / '.runtime/strata-coding-2-ram30-model'
PREPARATION = REPO / '.runtime/strata-coding-2-ram30-files'
REJECTED_SHA = '9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a'
REJECTED = prior.ROOT / REJECTED_SHA
REJECTED_MANIFEST = 'e03c7f983f591e1c53bc1124798d6ce27778d27f74465360b6f2b828278827c0'
SCOPE = 'one-fresh-useful-task-2-30gib-host-ram-stop-no-readiness'
RAM_STOP_MIB = 30720
DEFERRED = history.ROOT / 'ef7fe198b880eedb015cf92949ba15ae04fb8109f32610a00570ab78a094ef01'
DEFERRED_MANIFEST = '1a8727abf13ed83d8476789ef7641ebadd7ec709fc9dcb4d4a2b4eaceb14f526'
PROMPT = 'Python guard only: reject negative integer maximum with ValueError.'
REQUEST = {**task.REQUEST, 'messages': [{'role': 'user', 'content': PROMPT}]}
HELPERS = {'probe.py': 'bounded_read_statement.py', 'bounded_read_task.py': 'bounded_read_task.py',
           'coding_worker.py': 'coding_worker.py'}
_active = False


def deferred_proof(verify=False):
    manifest_path = DEFERRED / 'preparation-preservation.json'
    if p.build.tools.sha(manifest_path) != DEFERRED_MANIFEST:
        raise ValueError('DEFERRED_PREPARATION_CHANGED')
    manifest = p.read(manifest_path, 1048576)
    if verify:
        actual = {x.relative_to(DEFERRED).as_posix() for x in DEFERRED.rglob('*') if x.is_file()}
        if actual != set(manifest['files']) | {'preparation-preservation.json'}:
            raise ValueError('DEFERRED_FILE_SET_CHANGED')
        for name, item in manifest['files'].items():
            path = DEFERRED / name
            p.build.tools.plain(path)
            if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                raise ValueError('DEFERRED_EVIDENCE_CHANGED')
    return {'reviewSha256': manifest['reviewSha256'], 'preservationSha256': DEFERRED_MANIFEST,
            'status': 'DEFERRED_UNRUN_PREPARATION', 'readinessEnabled': False}


def same_limits(packet):
    old = p.read(REJECTED / 'review.json', 131072)
    # Only the owner-approved used-host-RAM stop changes from 28 to 30 GiB.
    if packet['policy'] != {**old['policy'], 'ramStopMiB': RAM_STOP_MIB}:
        raise ValueError('ONLY_30GIB_HOST_RAM_STOP_CHANGE_ALLOWED')
    for key in ('configuration', 'requestTimingChange', 'fileAccessChange',
                'startupTargetChange', 'startupStatusChange', 'vmEnvelope', 'settings', 'modelFiles',
                'sourceLimitation', 'sourceReviewSha256', 'runtimeBundle', 'buildProof', 'sourceTree',
                'sourcePlan', 'limitations', 'startupSourceAudit', 'controls', 'modelLargeFileBinding'):
        if packet[key] != old[key]:
            raise ValueError('RAM_MUST_KEEP_REVIEWED_LIMITS_AND_INPUTS')
    if packet['request'] != REQUEST or packet['request'] != old['request']:
        raise ValueError('RAM_SCOPE_REQUEST_MUST_STAY_UNCHANGED')
    if 'hostRamReadiness' in packet:
        raise ValueError('RAM_READINESS_DEFERRED')
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
    task.ROOT = task.coding.ROOT = p.ROOT = ROOT
    task.WORKER = task.coding.WORKER = WORKER
    task.PREPARATION = PREPARATION
    task.WORKER_HELPERS = dict(HELPERS)
    task.coding.WORKER_NAME = 'copilot-strata-coding-2-ram30-worker-'
    task.coding.REQUEST = p.REQUEST = REQUEST
    original = task.coding.task_bundle.bounded_read(REPO / task.task_spec.SOURCE)
    task.task_spec.validate_original(original)
    task.coding.coding_worker.code_from_response = functools.partial(statement.replacement, original=original)
    p.LIVE = LIVE
    p.APPROVAL = HERE / 'coding-task-2-ram30-approval.json'
    p.SCOPE = SCOPE
    # Assign a scoped copy: historical/default policies retain 28 GiB. Both
    # controller and independent --watch process activate this exact module.
    p.safety.POLICY = {**p.safety.POLICY, 'ramStopMiB': RAM_STOP_MIB}
    p.previous = lambda: {**previous(), 'usefulTask2HostRamFault': history.ram_fault_proof(True),
                          'deferredReadinessPreparation': deferred_proof(True)}
    p.expected_proofs = lambda: {**proofs(), 'usefulTask2HostRamFault': history.ram_fault_proof(),
                                 'deferredReadinessPreparation': deferred_proof()}
    p.same_limits = same_limits
    task.coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    if WORKER.exists() or LIVE.exists(): raise ValueError('RAM_SCOPE_ALREADY_CONSUMED')
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
