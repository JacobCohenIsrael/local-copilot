"""One synthetic task: prepare selected files, fake-only OpenCode edit, collect patch."""
import argparse
import base64
import json
from pathlib import Path
import uuid

import task_bundle as bundle
import verify_opencode

ROOT = Path(__file__).resolve().parents[2] / '.runtime' / 'bundle-rehearsals'
TASK = 'Only change example.py from VALUE = 1 to VALUE = 2. Do not run commands or access other files.'


def import_output(run_id, files):
    """Validate all output before writing ONLY the disposable bundle copy."""
    if bundle.collect(run_id)['changedFiles']:
        raise ValueError('PRISTINE_BUNDLE_REQUIRED')
    if not isinstance(files, dict) or set(files) != {'example.py'}:
        raise ValueError('UNEXPECTED_EXPORTED_PATH')
    encoded = files['example.py']
    if not isinstance(encoded, str) or len(encoded) > 4 * ((bundle.MAX_FILE_BYTES + 2) // 3):
        raise ValueError('EXPORTED_FILE_BUDGET')
    data = base64.b64decode(encoded, validate=True)
    if len(data) > bundle.MAX_FILE_BYTES:
        raise ValueError('EXPORTED_FILE_BUDGET')
    bundle.text_file(data)
    destination = bundle.plain(bundle.ROOT / run_id / 'workspace/example.py')
    destination.write_bytes(data)
    return bundle.collect(run_id)


def rehearse(artifact):
    ROOT.mkdir(parents=True, exist_ok=True)
    bundle.plain(ROOT, directory=True)
    directory = ROOT / uuid.uuid4().hex
    original = directory / 'original'
    original.mkdir(parents=True)
    (original / 'example.py').write_bytes(b'VALUE = 1\n')
    (original / 'unselected.txt').write_bytes(b'UNSELECTED SYNTHETIC FILE\n')
    fingerprints = {name: bundle.digest((original / name).read_bytes())
                    for name in ('example.py', 'unselected.txt')}
    result = {'mode': 'bundle-fake-only', 'status': 'PREPARING', 'fault': None,
              'runDirectory': str(directory), 'modelEnabled': False, 'strataContacted': False,
              'applied': False, 'patch': None, 'cleanupConfirmed': False}
    def save():
        # Each invocation owns a fresh directory; this record is never used to
        # reset/reuse a failed task or to authorize a live run.
        (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    save()
    try:
        prepared = bundle.prepare({'sourceRoot': str(original), 'files': ['example.py'], 'task': TASK})
        result.update({'bundleRunId': prepared['runId'], 'status': 'RUNNING'})
        save()
        worker = verify_opencode.run(artifact, fake=True, scenario='edit', bundle_id=prepared['runId'])
        result['workerReceipt'] = worker
        result['cleanupConfirmed'] = worker.get('cleanupConfirmed') is True
        if not result['cleanupConfirmed']:
            raise ValueError('WORKER_CLEANUP_UNCONFIRMED')
        probe = worker.get('probe', {})
        if (worker.get('containerExitCode') != 0 or worker.get('oomKilled') is not False or
                probe.get('compatibilityPassed') is not True or probe.get('bundleInputUsed') is not True or
                probe.get('timedOut') is not False or probe.get('modelEnabled') is not False or
                probe.get('strataContacted') is not False):
            raise ValueError('FAKE_WORKER_FAILED')
        collected = import_output(prepared['runId'], probe.get('outputFiles'))
        result.update({'status': 'PATCH_FOR_REVIEW', 'patch': collected['patch'],
                       'changedFiles': collected['changedFiles'], 'patchBytes': collected['patchBytes'],
                       'collected': collected})
        if (collected['changedFiles'] != ['example.py'] or
                bundle.bounded_read(bundle.ROOT / prepared['runId'] / 'workspace/example.py') != b'VALUE = 2\n'):
            raise ValueError('UNEXPECTED_SYNTHETIC_EDIT')
    except (Exception, KeyboardInterrupt) as error:
        result.update({'status': 'FAULT', 'fault': str(error) if isinstance(error, ValueError)
                       else type(error).__name__, 'patch': None})
        result.pop('collected', None)
    finally:
        result['originalUnchanged'] = all((original / name).is_file() and
            bundle.digest((original / name).read_bytes()) == digest for name, digest in fingerprints.items())
        if not result['originalUnchanged']:
            result.update({'status': 'FAULT', 'fault': result['fault'] or 'ORIGINAL_CHANGED', 'patch': None})
            result.pop('collected', None)
        save()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--execute-fake-only', action='store_true')
    args = parser.parse_args()
    if not args.execute_fake_only:
        parser.error('Execution requires --execute-fake-only; this command accepts no real project or model')
    result = rehearse(args.artifact)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'PATCH_FOR_REVIEW' else 3)
