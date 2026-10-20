"""Offline preparation and separately approved execution of one useful fixed task."""
import argparse
import functools
import hashlib
import json
from pathlib import Path
import shutil
import uuid

import coding_task as coding
import bounded_read_task as task_spec

p = coding.p
HERE = coding.HERE
REPO = coding.REPO
ROOT = REPO / '.runtime/strata-coding-2-review'
WORKER = REPO / '.runtime/strata-coding-2-worker'
PREPARATION = REPO / '.runtime/strata-coding-2-preparation'
PILOT = coding.ROOT / '256f8be8d82772d044da1964b3d65286975d5c33dd8789b7684ab7936ca3477f'
PILOT_MANIFEST = '2d98e87203e1bfabecbdc303e0b6eaf0c225fd1154a49459d4802f95bffdb23a'
REQUEST = {**coding.REQUEST, 'messages': [{'role': 'user', 'content': task_spec.PROMPT}]}
ENVELOPE = {'cpus': .5, 'memoryMiB': 512, 'swapMiB': 0, 'tmpMiB': 64,
            'deadlineSeconds': 410, 'leaseSeconds': 2.5, 'network': 'none', 'gpu': False}
WORKER_HELPERS = {'probe.py': 'bounded_read_task.py', 'coding_worker.py': 'coding_worker.py'}
MAXIMUM_OUTPUT_TOKENS = 32
_active = False


def pilot_proof(verify=False):
    if p.build.tools.sha(PILOT / 'execution-preservation.json') != PILOT_MANIFEST:
        raise ValueError('PILOT_MANIFEST_CHANGED')
    manifest = p.read(PILOT / 'execution-preservation.json', 1048576)
    if p.build.tools.sha(PILOT / 'execution-result.json') != manifest['executionResultSha256']:
        raise ValueError('PILOT_RESULT_CHANGED')
    result = p.read(PILOT / 'execution-result.json', 65536)
    if (result['status'] != 'REAL_STRATA_OPENCODE_PATCH_CONFIRMED_STOPPED' or
            result.get('workerStopConfirmed') is not True or result.get('allFourHostProcessesExited') is not True):
        raise ValueError('PILOT_SUCCESS_UNCONFIRMED')
    if verify:
        for key in ('attempt', 'worker', 'reader', 'launcher', 'capacityProbe'):
            record = manifest[key]
            directory = Path(record['directory'])
            if {x.relative_to(directory).as_posix() for x in directory.rglob('*') if x.is_file()} != set(record['files']):
                raise ValueError('PILOT_EVIDENCE_FILE_SET_CHANGED')
            for name, item in record['files'].items():
                path = directory / name
                p.build.tools.plain(path)
                if path.stat().st_size != item['bytes'] or p.build.tools.sha(path) != item['sha256']:
                    raise ValueError('PILOT_EVIDENCE_CHANGED')
        for name, item in manifest['reviewEvidence'].items():
            if p.build.tools.sha(PILOT / name) != item['sha256']:
                raise ValueError('PILOT_REVIEW_EVIDENCE_CHANGED')
        for name, expected in p.read(PILOT / 'review.json')['helperSha256'].items():
            raw = (PILOT / 'helpers' / name).read_bytes().replace(b'\r\n', b'\n')
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('PILOT_FROZEN_HELPER_CHANGED')
    return {'reviewSha256': result['reviewSha256'], 'preservationSha256': PILOT_MANIFEST,
            'resultSha256': manifest['executionResultSha256'], 'previousAttemptReset': False}


def check_task(task):
    original = Path(task['originalDirectory'])
    source = Path(task['workerInput'])
    if original.parent.parent != PREPARATION or source.parent != original.parent:
        raise ValueError('CODING_PREPARATION_PATH')
    for directory in (original, source): p.build.tools.plain(directory)
    if (task['task'] != task_spec.TASK or task['selectedFile'] != task_spec.SELECTED or
            task['repositoryFile'] != task_spec.SOURCE or task['sourceSha256'] != task_spec.SOURCE_SHA256 or
            task['workerEnvelope'] != ENVELOPE or task['modelCalls'] != 1 or task['opencodeCalls'] != 2 or
            task['maximumModelOutputTokens'] != MAXIMUM_OUTPUT_TOKENS or task['maximumGuardBytes'] != 128 or
            task['nativeToolCallingTested'] is not False):
        raise ValueError('FIXED_USEFUL_TASK_CHANGED')
    bundle = coding.task_bundle
    task_spec.validate_original(bundle.bounded_read(REPO / task_spec.SOURCE))
    task_spec.validate_original(bundle.bounded_read(original / task_spec.SELECTED))
    task_spec.validate_original(bundle.bounded_read(source / task_spec.SELECTED))
    collected = bundle.collect(task['bundleRunId'])
    manifest = bundle.read_json(bundle.ROOT / task['bundleRunId'] / 'manifest.json')
    if (collected['changedFiles'] or manifest['files'] != {task_spec.SELECTED: task_spec.SOURCE_SHA256} or
            manifest['task'] != task_spec.TASK):
        raise ValueError('CODING_BUNDLE_CHANGED')
    if set(task['workerFiles']) != {x.relative_to(source).as_posix() for x in source.rglob('*') if x.is_file()}:
        raise ValueError('WORKER_FILE_SET_CHANGED')
    for name, digest in task['workerFiles'].items():
        path = source / name
        p.build.tools.plain(path)
        if p.build.tools.sha(path) != digest: raise ValueError('WORKER_INPUT_CHANGED')
    for staged, repository in WORKER_HELPERS.items():
        if (source / staged).read_bytes() != (HERE / repository).read_bytes():
            raise ValueError('WORKER_HELPER_CHANGED')
    if task['workerFiles']['opencode'] != bundle.read_json(HERE.parent / 'worker/opencode-lock.json')['binarySha256']:
        raise ValueError('OPENCODE_IDENTITY_CHANGED')


def activate():
    global _active
    if _active: return
    coding.activate()
    coding.ROOT = p.ROOT = ROOT
    coding.WORKER = WORKER
    coding.WORKER_NAME = 'copilot-strata-coding-2-worker-'
    p.LIVE = REPO / '.runtime/strata-coding-2-model'
    p.APPROVAL = HERE / 'coding-task-2-approval.json'
    p.SCOPE = 'one-useful-negative-read-limit-guard-strata-opencode-patch'
    coding.REQUEST = p.REQUEST = REQUEST
    p.previous = lambda: {**coding._original_previous(), 'ninth': coding.ninth_proof(True), 'codingPilot': pilot_proof(True)}
    p.expected_proofs = lambda: {**coding._original_proofs(), 'ninth': coding.ninth_proof(), 'codingPilot': pilot_proof()}
    coding.check_task = check_task
    original = coding.task_bundle.bounded_read(REPO / task_spec.SOURCE)
    task_spec.validate_original(original)
    coding.coding_worker.TASK = task_spec.TASK
    coding.coding_worker.code_from_response = functools.partial(task_spec.replacement, original=original)
    coding.first_api.WATCH_ENTRYPOINT = Path(__file__).resolve()
    _active = True


def prepare():
    activate()
    base = PREPARATION / uuid.uuid4().hex
    original = base / 'original'
    source = base / 'worker-input'
    original.mkdir(parents=True)
    source.mkdir()
    data = coding.task_bundle.bounded_read(REPO / task_spec.SOURCE)
    task_spec.validate_original(data)
    (original / task_spec.SELECTED).write_bytes(data)
    (original / 'unselected.txt').write_bytes(b'UNSELECTED; MUST NOT ENTER WORKER\n')
    prepared = coding.task_bundle.prepare({'sourceRoot': str(original), 'files': [task_spec.SELECTED], 'task': task_spec.TASK})
    artifact = coding.verify_opencode.artifact(REPO / '.runtime/opencode-linux/2.0.26-musl-44f176ba')
    shutil.copyfile(artifact / 'staged/opencode', source / 'opencode')
    for staged, repository in WORKER_HELPERS.items():
        shutil.copyfile(HERE / repository, source / staged)
    (source / task_spec.SELECTED).write_bytes(data)
    libraries = REPO / '.runtime/opencode-linux/alpine-runtime'
    runtime = coding.task_bundle.read_json(libraries / 'runtime.json')
    (source / 'libs').mkdir()
    for item in runtime['libraries']:
        path = libraries / 'staged' / item['library']
        if p.build.tools.sha(path) != item['librarySha256']: raise ValueError('PINNED_WORKER_LIBRARY_CHANGED')
        shutil.copyfile(path, source / 'libs' / path.name)
    task = {'task': task_spec.TASK, 'selectedFile': task_spec.SELECTED, 'repositoryFile': task_spec.SOURCE,
            'sourceSha256': task_spec.SOURCE_SHA256, 'bundleRunId': prepared['runId'],
            'originalDirectory': str(original), 'workerInput': str(source),
            'workerFiles': {x.relative_to(source).as_posix(): p.build.tools.sha(x)
                            for x in sorted(source.rglob('*')) if x.is_file()},
            'workerEnvelope': ENVELOPE, 'modelCalls': 1, 'opencodeCalls': 2,
            'maximumModelOutputTokens': MAXIMUM_OUTPUT_TOKENS, 'maximumGuardBytes': 128, 'nativeToolCallingTested': False}
    folder, packet = p.prepare({'codingTask': task})
    return {'reviewSha256': p.sha(packet), 'reviewFile': str(folder / 'review.json'),
            'modelLaunchEnabled': False, 'workerLaunchEnabled': False}


def summary():
    # A worker failure can consume this operation before a model namespace exists.
    if WORKER.exists():
        return {'status': 'ATTEMPT_CONSUMED', 'workerAttemptDirectory': str(WORKER),
                'integrationResultFile': str(WORKER / 'integration-result.json'),
                'modelLaunchEnabled': False, 'workerLaunchEnabled': False}
    return p.summary()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['prepare', 'review', 'run'])
    parser.add_argument('--watch', action='store_true')
    options = parser.parse_args()
    if not options.watch and options.command is None: parser.error('command required')
    activate()
    if options.watch: coding.first_api.watch()
    else:
        result = prepare() if options.command == 'prepare' else summary() if options.command == 'review' else coding.run()
        print(json.dumps(result, indent=2), flush=True)
        if options.command == 'run' and result['status'] != 'REAL_STRATA_CODING_PATCH_FOR_REVIEW': raise SystemExit(3)
