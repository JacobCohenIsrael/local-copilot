"""Read-only compiler readiness report. No Docker, telemetry or workload calls."""
import json
import hashlib
import re
from pathlib import Path

import build_guard
import build_policy_review as policy

HERE = Path(__file__).resolve().parent


def offline_summary():
    pointer = HERE / 'offline-build-candidate.json'
    if not pointer.exists():
        return {'status': 'NOT_PREPARED', 'buildEnabled': False}
    import offline_build_plan
    candidate = json.loads(pointer.read_text())
    if (candidate.get('version') != 1 or candidate.get('status') != 'proposal-not-approved' or
            not isinstance(candidate.get('sessionId'), str) or not re.fullmatch('[0-9a-f]{32}', candidate['sessionId']) or
            candidate.get('buildEnabled') is not False or candidate.get('modelLaunchEnabled') is not False):
        raise ValueError('Offline candidate must remain an unapproved proposal')
    directory = offline_build_plan.ROOT / candidate['sessionId']
    plan = offline_build_plan.checked_proposal(directory, candidate['planSha256'])
    return {'status': 'PREPARED_NOT_APPROVED', 'directory': str(directory),
            'planSha256': candidate['planSha256'], 'compilerNetwork': plan['compilerNetwork'],
            'rootReadOnly': plan['rootReadOnly'], 'mutableFilesystems': plan['mutableFilesystems'],
            'toolDownloadBytes': plan['lockedToolDownloadBytes'], 'toolExpandedBytes': plan['toolExpandedBytes'],
            'fullToolTreeRecheckBeforeStartRequired': True,
            'imageCompatibilityVerified': False, 'artifactExporterConnected': False,
            'artifactCollector': {'implementation': 'artifact_export.collect',
                                  'liveControllerConnected': False,
                                  'startAuthority': False},
            'controllerIntegration': {
                'status': 'SYNTHETIC_REHEARSAL_ONLY', 'startAuthority': False,
                'liveCpuFeedConnected': False,
                'helperSha256': {name: build_guard.digest(HERE / name) for name in (
                    'offline_target.py', 'controller_session.py', 'controller_rehearsal.py',
                    'artifact_export.py', 'build_guard.py')}},
            'buildEnabled': False, 'remainingGates': plan['remainingGates']}


def report():
    controls = policy.load_effective_controls()
    candidate = json.loads((HERE / 'build-candidate.json').read_text())
    if (candidate.get('version') != 1 or candidate.get('status') != 'prepared-not-approved' or
            not isinstance(candidate.get('packageId'), str) or not re.fullmatch('[0-9a-f]{8}', candidate['packageId']) or
            any(candidate.get(key) is not False for key in ('buildEnabled', 'modelLaunchEnabled'))):
        raise ValueError('Candidate must be a disabled prepared source package')
    package = build_guard.PACKAGE.parent / candidate['packageId']
    if build_guard.digest(package / 'build-manifest.json') != candidate.get('manifestSha256'):
        raise ValueError('Candidate build manifest changed')
    contract = build_guard.plan(package)  # Verifies command and input hashes, never runs Docker.
    resources = controls['resources']
    if (resources['cpuQuota'] != contract['cpuQuota'] or
            resources['memoryBytes'] != contract['memoryBytes'] or
            resources['swapBytes'] != contract['swapBytes'] or resources['pids'] != contract['pids'] or
            resources['gpuDevices'] != [] or resources['compilerJobs'] != 1 or
            resources['automaticRetry'] is not False):
        raise ValueError('Prepared compiler resources differ from approved CPU-only controls')
    helpers = {}
    blockers = []
    for name in ('compile.sh', 'bounded_build.py'):
        # Staged Linux helpers use LF even when the host checkout uses CRLF.
        staged = build_guard.digest(package / 'input' / name)
        current = hashlib.sha256((HERE / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        helpers[name] = {'preparedSha256': staged, 'currentSha256': current, 'matches': staged == current}
    if not all(item['matches'] for item in helpers.values()):
        blockers.append('BUILD_PACKAGE_OUTDATED')
    # No evidence for these gates has been validated or authorized. This report
    # cannot promote an observation/config field into approval or start authority.
    blockers.extend(['CPU_SOURCE_VALIDATION_PENDING', 'LIVE_CONTROLLER_NOT_CONNECTED',
                     'DEPENDENCY_AND_DISK_BUDGETS_PENDING', 'FINAL_BUILD_WORKLOAD_NOT_APPROVED'])
    return {'version': 1, 'status': 'BUILD_BLOCKED',
            'buildEnabled': False, 'modelLaunchEnabled': False,
            'approvedCpuControls': controls['temperature'],
            'unknownThrottleException': 'approved-cpu-only-build-only',
            'preparedManifestSha256': contract['buildManifestSha256'],
            'candidatePackage': str(package), 'finalWorkloadApproved': False,
            'readerSha256': contract['readerSha256'], 'helpers': helpers,
            'blockers': blockers,
            'thermalReadinessGate': 'build_policy_review.CpuBuildReadinessGate',
            'thermalGateIsStartAuthority': False,
            'historicalNetworkedRecipeIsExecutionCandidate': False,
            'offlineSuccessorProposal': offline_summary(),
            'note': 'Historical samples and successful dummy rehearsals do not authorize compilation.'}


if __name__ == '__main__':
    print(json.dumps(report(), indent=2))
