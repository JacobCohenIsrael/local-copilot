"""Hash-bound first-build admission. Preparation cannot approve or start work."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time
import zipfile

import build_guard as guard
import build_policy_review as policy
import cpu_source_review as cpu
import image_plan
import offline_build_plan as offline
import stage_build_tools as tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / '.runtime/first-build-review'
LIVE = HERE.parents[1] / '.runtime/first-cpu-build'
APPROVAL = HERE / 'first-build-approval.json'  # Absent until an explicit human decision.


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def selected():
    pointer = json.loads(cpu.bounded(HERE / 'offline-build-candidate.json', 4096))
    directory = offline.ROOT / pointer['sessionId']
    return directory, pointer['planSha256'], offline.checked_proposal(directory, pointer['planSha256'])


def source_tree(plan):
    """Compare EVERY staged source file to its already-pinned ZIP; never extract.

    The earlier BUILD.json fingerprint covers only selected paths. Admission
    must also reject changed/extra/missing source outside that subset.
    """
    source = Path(plan['sourcePackage']) / 'input/source'
    manifest = json.loads(cpu.bounded(Path(plan['sourcePackage']) / 'build-manifest.json', 65536))
    if len(manifest['sources']) != 2:
        raise ValueError('Expected both pinned source archives')
    expected, total = {}, 0
    end = time.monotonic() + 120
    for index, row in enumerate(manifest['sources']):
        label = ('strata', 'llama')[index]
        archive = source.parents[2] / 'downloads' / (label + '-' + row['commit'] + '.zip')
        tools.plain(archive)
        if archive.stat().st_size != row['archiveBytes'] or tools.sha(archive) != row['archiveSha256']:
            raise ValueError('Pinned source archive changed')
        prefix = row['repository'].split('/')[1] + '-' + row['commit']
        with zipfile.ZipFile(archive) as stream:
            members = stream.infolist()
            if len(members) > 40000:
                raise ValueError('Source archive entry budget')
            for member in members:
                path = PurePosixPath(member.filename)
                if not path.parts or path.parts[0] != prefix or any(p in ('.', '..') for p in path.parts):
                    raise ValueError('Source archive path invalid')
                relative = PurePosixPath(*path.parts[1:])
                if member.is_dir() or not relative.parts or (index == 1 and relative.parts[:2] == ('tools', 'ui')):
                    continue
                if index == 1:
                    relative = PurePosixPath('third_party/llama.cpp') / relative
                name = relative.as_posix()
                total += member.file_size
                if name in expected or len(expected) >= 10000 or member.file_size > 32 * 1024**2 or total > 512 * 1024**2:
                    raise ValueError('Source tree budget/duplicate violation')
                target = source.joinpath(*relative.parts)
                tools.plain(target)
                if not target.is_file() or target.stat().st_size != member.file_size:
                    raise ValueError('Source file missing/size changed')
                digest = hashlib.sha256()
                with stream.open(member) as content:
                    copied = 0
                    while chunk := content.read(65536):
                        copied += len(chunk)
                        if copied > member.file_size or time.monotonic() > end:
                            raise ValueError('Source verification budget/deadline')
                        digest.update(chunk)
                if copied != member.file_size or tools.sha(target) != digest.hexdigest():
                    raise ValueError('Source differs from pinned archive')
                expected[name] = {'bytes': copied, 'sha256': digest.hexdigest()}
                time.sleep(.001)  # Yield between small files; no workload/stress loop.
    actual = set()
    for count, path in enumerate(source.rglob('*'), 1):
        if count > 20000 or time.monotonic() > end:
            raise ValueError('Source traversal budget/deadline')
        tools.plain(path)
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
        if len(actual) > 10000:
            raise ValueError('Source file budget')
    if actual != set(expected):
        raise ValueError('Extra/missing staged source file')
    return {'files': len(expected), 'bytes': total, 'treeSha256': sha(expected), 'verifiedAgainstPinnedArchives': True}


def helpers():
    paths = [p for root in (HERE, HERE.parent / 'worker') for p in root.glob('*.py')
             if not p.name.startswith('test_')]
    paths += [HERE / 'cpu_reader.ps1', HERE / 'cpu_build_reader.ps1', HERE.parent / 'lifecycle/supervisor.py', HERE.parents[1] / 'local_worker.py']
    return {p.relative_to(HERE.parents[1]).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted(paths)}


def material(*, selection=None, live_namespace=None, scope=None):
    directory, plan_sha, plan = selected() if selection is None else selection
    controls = policy.load_effective_controls()
    source_review = cpu.report()
    sources = source_tree(plan)
    tool_receipt = offline.verified_tools(plan['toolDirectory'])
    packet = {'version': 1, 'status': 'REVIEW_ONLY_NOT_APPROVED',
              'scope': controls['scope'] if scope is None else scope, 'offlineDirectory': str(directory), 'offlinePlanSha256': plan_sha,
              'sourceReview': source_review, 'sourceReviewSha256': sha(source_review), 'sourceTree': sources,
              'toolReceiptSha256': plan['toolReceiptSha256'], 'toolTreeFiles': len(tool_receipt['files']),
              'controls': controls['temperature'], 'resources': controls['resources'], 'stop': controls['stop'],
              'mutableFilesystems': plan['mutableFilesystems'], 'createArgs': plan['createArgs'],
              'proposedVmEnvelope': {'logicalProcessors': 1, 'maximumReportedMemoryBytes': 6 * 1024**3,
                    'guestSwapBytes': 0, 'settingsFile': str(Path.home() / '.wslconfig'),
                    'proposalSha256': tools.sha(HERE / 'wsl-build-limits.proposed'),
                    'requiresSeparatePolicyApprovalAndWslRestart': True},
              'helperSha256': helpers(), 'liveNamespace': str(LIVE if live_namespace is None else live_namespace), 'maximumAttempts': 1,
              'admissionWaitSeconds': 90, 'outerSeconds': 1910,
              'image': image_plan.metadata(), 'buildEnabled': False, 'modelLaunchEnabled': False,
              'imageDownloadEnabled': False, 'imageImportEnabled': False,
              'requiredBeforeExecution': ['Exact pinned image already available and verified',
                  'Explicit source acceptance and final first-build workload approval bound to this packet',
                  'Fresh CPU baseline, remaining reader coverage and independent watchdog lease',
                  'Fresh host/guest capacity check and all source/tool/helper identities unchanged'],
              'imagePreparationLimitation': 'Docker daemon image import is outside the compiler CPU/RAM/tmpfs caps; preparation remains a separate reviewed and approved operation.'}
    return packet


def prepare():
    packet = material()
    digest = sha(packet)
    tools.plain(ROOT)
    with guard.base.lock(ROOT / 'control'):
        destination = ROOT / digest
        destination.mkdir(exist_ok=True)
        path = destination / 'review.json'
        if path.exists() and json.loads(cpu.bounded(path, 65536)) != packet:
            raise ValueError('Review destination changed')
        guard.base.atomic(path, packet)
        guard.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return destination, packet


def review():
    pointer = json.loads(cpu.bounded(ROOT / 'candidate.json', 4096))
    digest = pointer['reviewSha256']
    if not guard.re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid first-build review pointer')
    packet = json.loads(cpu.bounded(ROOT / digest / 'review.json', 65536))
    if sha(packet) != digest or packet.get('status') != 'REVIEW_ONLY_NOT_APPROVED':
        raise ValueError('First-build review changed')
    if packet['helperSha256'] != helpers() or packet['sourceReviewSha256'] != sha(cpu.report()):
        raise ValueError('Review helpers/source qualification changed; prepare a new packet')
    _, current_sha, _ = selected()
    controls = policy.load_effective_controls()
    if (current_sha != packet['offlinePlanSha256'] or packet['controls'] != controls['temperature'] or
            packet['resources'] != controls['resources'] or packet['stop'] != controls['stop'] or
            packet['scope'] != controls['scope'] or
            packet['proposedVmEnvelope']['proposalSha256'] != tools.sha(HERE / 'wsl-build-limits.proposed')):
        raise ValueError('Reviewed proposal/controls changed')
    return digest, packet


def image_ready(docker, packet):
    identity = packet['image']
    rows = json.loads(docker.call('image', 'inspect', identity['image'], timeout=5))
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError('Pinned image inspection is not singular')
    # Classic Docker exposes the config digest as ID; containerd exposes the
    # manifest target. Both must still match the pinned content and diff-IDs.
    manifest_id = identity['image'].split('@', 1)[1]
    row = rows[0]
    valid_id = (row.get('Id') == identity['configDigest'] or
                (row.get('Id') == manifest_id and row.get('Descriptor', {}).get('digest') == manifest_id))
    if (not valid_id or
            rows[0].get('Os') != 'linux' or rows[0].get('Architecture') != 'amd64' or
            identity['image'] not in rows[0].get('RepoDigests', []) or
            rows[0].get('RootFS', {}).get('Layers') != ['sha256:' + r['expandedSha256'] for r in identity['layers']]):
        raise ValueError('Pinned image content/platform/diff-ID identity mismatch')
    return rows[0]['Id']


def vm_ready(docker, packet):
    """Read-only proof of the reviewed VM cap; never changes daemon settings."""
    data = json.loads(docker.call('info', '--format', '{{json .}}', timeout=5))
    limits = packet['proposedVmEnvelope']
    if (type(data.get('NCPU')) is not int or data['NCPU'] != limits['logicalProcessors'] or
            type(data.get('MemTotal')) is not int or not 4 * 1024**3 < data['MemTotal'] <= limits['maximumReportedMemoryBytes']):
        raise ValueError('REVIEWED_DOCKER_WSL_RESOURCE_CAPS_NOT_ACTIVE')
    return {'logicalProcessors': data['NCPU'], 'reportedMemoryBytes': data['MemTotal']}


@dataclass(frozen=True)
class Permit:
    review_sha256: str
    packet_json: str
    approval_sha256: str

    @property
    def packet(self):
        return json.loads(self.packet_json)

    @property
    def live_namespace(self):
        return LIVE

    def target(self, target, namespace):
        import offline_target
        packet = self.packet
        expected = offline_target.from_proposal(packet['offlineDirectory'], packet['offlinePlanSha256'], target.container_id)
        if (self.review_sha256 != sha(packet) or target.synthetic or target != expected or Path(namespace).absolute() != self.live_namespace or
                packet['liveNamespace'] != str(self.live_namespace)):
            raise ValueError('First-build permit target/namespace mismatch')

    def qualify(self, frame):
        if (frame.get('version') != 1 or frame.get('synthetic') is not False or frame.get('validatedCpuSensor') is not False or
                frame.get('cpuThermalThrottling') is not None or
                frame.get('source') != self.packet['controls']['source']):
            raise ValueError('Source permit cannot qualify a different or synthetic channel')
        return {**frame, 'rawValidatedCpuSensor': False, 'validatedCpuSensor': True,
                'sourceQualification': self.packet['sourceReviewSha256']}


def authorize():
    digest, packet = review()
    if not APPROVAL.exists():
        raise ValueError('FINAL_FIRST_BUILD_WORKLOAD_NOT_APPROVED')
    raw = cpu.bounded(APPROVAL, 8192)
    decision = json.loads(raw)
    if (decision.get('version') != 1 or decision.get('status') != 'owner-approved-one-cpu-build' or
            decision.get('reviewSha256') != digest or decision.get('scope') != packet['scope'] or
            decision.get('synthetic') is not False or
            decision.get('buildEnabled') is not True or
            decision.get('acceptSourceQualificationSha256') != packet['sourceReviewSha256'] or
            decision.get('acceptSourceLimitation') != cpu.LIMITATION or
            decision.get('maximumAttempts') != 1 or type(decision.get('maximumAttempts')) is not int or
            not isinstance(decision.get('ownerMessage'), str) or not decision['ownerMessage'].strip() or
            any(decision.get(k) is not False for k in ('modelLaunchEnabled', 'imageDownloadEnabled', 'imageImportEnabled'))):
        raise ValueError('First-build approval scope/hash/source acceptance invalid')
    return Permit(digest, encoded(packet).decode(), hashlib.sha256(raw).hexdigest())


def summary(*, check_environment=False):
    if not (ROOT / 'candidate.json').exists():
        return {'status': 'NOT_PREPARED', 'buildEnabled': False, 'modelLaunchEnabled': False}
    try:
        digest, packet = review()
    except (ValueError, OSError, KeyError):
        return {'status': 'STALE_REVIEW_REPREPARE_REQUIRED', 'buildEnabled': False, 'modelLaunchEnabled': False}
    blockers = []
    try:
        authorize()
        accepted = True
    except ValueError:
        accepted = False
        blockers.append('SOURCE_ACCEPTANCE_AND_WORKLOAD_APPROVAL_REQUIRED')
    image_status = 'RECHECK_REQUIRED_BEFORE_EXECUTION'
    if check_environment:
        try:
            vm_ready(guard.base.Docker(), packet)
        except Exception:
            blockers.append('REVIEWED_DOCKER_WSL_RESOURCE_CAPS_NOT_ACTIVE')
        try:
            image_ready(guard.base.Docker(), packet)
            image_status = 'VERIFIED_PRESENT'
        except subprocess.CalledProcessError as error:
            image_status = 'ABSENT' if 'No such image' in (error.stderr or '') else 'INSPECTION_UNCONFIRMED'
        except Exception:
            image_status = 'INSPECTION_UNCONFIRMED'
        if image_status != 'VERIFIED_PRESENT':
            blockers.append('PINNED_CUDA_IMAGE_' + image_status)
    reserve = 20 * 1024**3 + 1024**3
    free = shutil.disk_usage(HERE.parents[1]).free
    if free < reserve:
        blockers.append('HOST_EXPORT_CAPACITY_LOW')
    if any((LIVE / name).exists() for name in ('attempt.json', 'state.json', 'emergency.json')):
        blockers.append('FIRST_BUILD_ATTEMPT_ALREADY_CONSUMED')
    return {'status': 'PREPARED_BLOCKED' if blockers else 'REQUIRES_FRESH_RUNTIME_ADMISSION',
            'reviewSha256': digest, 'reviewFile': str(ROOT / digest / 'review.json'),
            'cpuSourceReview': packet['sourceReview']['status'], 'sourceAcceptanceApproved': accepted,
            'allSourceFilesVerifiedAtPreparation': packet['sourceTree']['files'],
            'allToolFilesVerifiedAtPreparation': packet['toolTreeFiles'],
            'productionController': 'CONNECTED_BEHIND_HASH_BOUND_ONE_ATTEMPT_ADMISSION',
            'proposedVmEnvelope': packet['proposedVmEnvelope'],
            'imageReadiness': image_status, 'hostFreeBytesObserved': free,
            'freshReaderBaselineAndCoverageRequired': True, 'freshGuestCapacityRequired': True,
            'blockers': blockers, 'buildEnabled': False, 'modelLaunchEnabled': False,
            'imageDownloadEnabled': False, 'imageImportEnabled': False}
