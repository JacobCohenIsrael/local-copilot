"""Generate a disabled, offline OpenCode configuration proposal. Never execute it."""
import argparse
import hashlib
import json
from pathlib import Path

import task_bundle as bundle

BLOCKED = {'.opencode', '.claude', 'agents.md', 'claude.md', 'opencode.json',
           'opencode.jsonc', '.env'}
BASE = 'docker.io/library/python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8'


def plan(run_id):
    # Reuse collection validation, including baseline hashes and output limits.
    result = bundle.collect(run_id)
    if result['changedFiles']:
        raise ValueError('PRISTINE_WORKSPACE_REQUIRED')
    manifest = bundle.read_json(bundle.ROOT / run_id / 'manifest.json')
    artifact = bundle.read_json(Path(__file__).with_name('opencode-lock.json'))
    names = list(manifest['files'])
    for name in names:
        if any(part.casefold() in BLOCKED or part.casefold().startswith('.env.')
               for part in name.split('/')):
            raise ValueError('WORKER_CONTROL_OR_SECRET_FILE')
    # OpenCode 2.0.26 authorizes internal files by location-relative resource.
    paths = {'*': 'deny', **{name: 'allow' for name in names}}
    permissions = {'*': 'deny', 'read': paths, 'edit': paths.copy(),
                   'external_directory': 'deny', 'doom_loop': 'deny'}
    config = {
        '$schema': 'https://opencode.ai/config.json',
        'enabled_providers': ['strata'], 'model': 'strata/VERIFY_SERVED_MODEL_ID',
        'small_model': 'strata/VERIFY_SERVED_MODEL_ID', 'default_agent': 'bounded',
        'autoupdate': False, 'snapshot': False, 'share': 'disabled',
        'formatter': False, 'lsp': False, 'plugin': [], 'mcp': {}, 'instructions': [],
        'compaction': {'auto': False}, 'permission': permissions,
        'provider': {'strata': {'npm': '@ai-sdk/openai-compatible',
                              'options': {'baseURL': 'http://request-gate:8081/v1'},
                              'models': {'VERIFY_SERVED_MODEL_ID': {
                                  'name': 'Strata (identity not verified)',
                                  'limit': {'context': 8192, 'output': 512}}}}},
        'agent': {'title': {'disable': True},
                  'bounded': {'description': 'One small supervised edit',
                              'mode': 'primary', 'steps': 2,
                              'permission': permissions.copy(),
                              'prompt': 'Edit only the explicitly supplied files. Do not delegate. '
                                        'Do not run commands. Stop after the requested small fix.'}}
    }
    environment = {name: 'true' for name in (
        'OPENCODE_DISABLE_AUTOUPDATE', 'OPENCODE_DISABLE_DEFAULT_PLUGINS',
        'OPENCODE_DISABLE_LSP_DOWNLOAD', 'OPENCODE_DISABLE_AUTOCOMPACT',
        'OPENCODE_DISABLE_CLAUDE_CODE', 'OPENCODE_DISABLE_MODELS_FETCH')}
    environment.update({'HOME': '/tmp/home', 'XDG_CONFIG_HOME': '/tmp/config',
                        'XDG_DATA_HOME': '/tmp/data', 'XDG_CACHE_HOME': '/tmp/cache',
                        'OPENCODE_CONFIG': '/input/opencode.json'})
    return {
        'version': 1, 'status': 'DISABLED_PROPOSAL', 'executionEnabled': False,
        'modelEnabled': False, 'runId': run_id,
        'manifestSha256': hashlib.sha256((bundle.ROOT / run_id / 'manifest.json').read_bytes()).hexdigest(),
        'opencode': {'versionCandidate': '2.0.26', 'linuxArtifactSha256': artifact['binarySha256'],
                     'package': artifact['package'],
                     'imageDigest': None, 'baseImage': BASE,
                     'argvTemplate': ['opencode', 'run', '--standalone', '--format', 'json', '--agent', 'bounded',
                                      '--model', 'strata/VERIFY_SERVED_MODEL_ID',
                                      '<bounded task text>'], 'workingDirectory': '/workspace'},
        'config': config, 'environment': environment,
        'containerCandidates': {'user': '65532:65532', 'cpus': 0.5, 'memoryBytes': 536870912,
                                'memorySwapBytes': 536870912, 'pids': 64,
                                'readonlyRoot': True, 'capDrop': ['ALL'],
                                'noNewPrivileges': True, 'gpuDevices': [], 'restart': 'no',
                                'ports': [], 'tmpfsBytes': 67108864,
                                'mounts': [{'source': str(bundle.ROOT / run_id / 'workspace'),
                                            'target': '/workspace', 'readOnly': False},
                                           {'source': 'generated config input only',
                                            'target': '/input', 'readOnly': True}],
                                'network': 'isolated worker-to-request-gate only; not created'},
        'unimplementedHardGates': ['verified Linux binary and runtime dependencies',
                                  'owner-approved live policy and engine build/runtime',
                                  'request gate with exact model tokenizer, input/output/call budgets',
                                  'network isolation: worker cannot bypass request gate or reach Internet',
                                  'deadline and bounded output capture, independent watchdog and cancellation',
                                  'scratch disk/write quotas while running; post-exit checks are insufficient',
                                  'verify effective config and denied tools in pinned OpenCode container'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(plan(args.run_id), ensure_ascii=True))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'REJECTED', 'error': str(error), 'executionEnabled': False}))
        raise SystemExit(2)
