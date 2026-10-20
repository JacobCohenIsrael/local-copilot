"""Separate offline review and single-use approval for manual Docker chat."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'model-runtime'))
import runtime_plan as base
import runtime_safety as safety
from protocol import LIMITS

ROOT = REPO / '.runtime/strata-manual-chat-review'
LIVE = REPO / '.runtime/strata-manual-chat-session'
APPROVAL = HERE / 'approval.json'
SCOPE = 'one-manual-strata-session-16k-512-input-up-to-4096-output-150s-300s-no-readiness'
BASELINE = REPO / '.runtime/strata-coding-2-ram30-review/4b1d0a4a15eec7f180a13d52ce23c68b4d2860fbe903960c645cfabc27937875'
BASELINE_MANIFEST = 'ee0da137ccc41fa58afa3a7734c79741d4d9e1631bd92d97739939d037136da2'
POLICY = {**safety.POLICY, 'ramStopMiB': 30720}
GUEST = {'guest.py': HERE / 'guest.py', 'protocol.py': HERE / 'protocol.py',
         'wrapper.py': HERE / 'wrapper.py', 'bridge.py': HERE / 'bridge.py',
         'api_wrapper.py': base.HERE / 'api_wrapper.py',
         'container_test.py': base.HERE / 'container_test.py'}


def read(path, maximum=262144):
    base.build.tools.plain(Path(path))
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('RECORD_BYTES')
    return json.loads(raw)


def write(path, value):
    path = Path(path)
    base.build.tools.plain(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def sources():
    paths = set(base.helpers()) | {p.relative_to(REPO).as_posix()
            for p in HERE.iterdir() if p.suffix in ('.py', '.ps1')}
    return {relative: base.build.tools.sha(REPO / relative) for relative in sorted(paths)}


def baseline():
    if base.build.tools.sha(BASELINE / 'execution-preservation.json') != BASELINE_MANIFEST:
        raise ValueError('PRESERVED_RAM30_CHANGED')
    manifest = read(BASELINE / 'execution-preservation.json', 1048576)
    packet = read(BASELINE / 'review.json')
    item = manifest['reviewEvidence']['review.json']
    if base.build.tools.sha(BASELINE / 'review.json') != item['sha256']:
        raise ValueError('BASELINE_REVIEW_CHANGED')
    if packet['policy'] != POLICY:
        raise ValueError('MANUAL_SAFETY_MUST_MATCH_RAM30')
    return packet


def configuration():
    cfg = copy.deepcopy(baseline()['configuration'])
    args = cfg['args']
    args[args.index('--max-context') + 1] = str(LIMITS['contextTokens'])
    return cfg


def launch(package, source, old):
    # Reuse the exact existing resource/isolation builder in this process only.
    previous = base.LIVE
    try:
        base.LIVE = LIVE
        args, contract = base.launch(package, Path(old['buildProof']['artifactDirectory']),
                                    Path(old['runtimeBundle']['directory']), source)
    finally:
        base.LIVE = previous
    name = 'copilot-strata-manual-' + package.name
    args[args.index('--name') + 1] = name
    label = 'local-copilot.kind=first-strata-api'
    args[args.index(label)] = 'local-copilot.kind=strata-manual-chat'
    args[-1] = '/input/guest.py'
    contract['name'] = name
    contract['labels']['local-copilot.kind'] = 'strata-manual-chat'
    contract['command'] = ['-B', '/input/guest.py']
    if contract['host'] != old['contract']['host']:
        raise ValueError('RESOURCE_OR_ISOLATION_DRIFT')
    return args, contract


def source_path(old, *, full=False):
    p = old['sourcePlan']
    path = Path(p['directory']) / 'offline-plan.json'
    if base.build.tools.sha(path) != p['sha256']:
        raise ValueError('SOURCE_PLAN_CHANGED')
    source = read(path, 2 * 1024**2)
    result = Path(source['sourcePackage']) / 'input/source'
    base.build.tools.plain(result)
    if full:
        checked = base.build.offline.checked_proposal(p['directory'], p['sha256'])
        if base.build.source_tree(checked) != old['sourceTree']:
            raise ValueError('PINNED_SOURCE_CHANGED')
    # The expensive complete archive comparison belongs before live helpers;
    # ARMED reauthorization must never block controller pulses for that scan.
    return result


def verify_inputs(packet):
    old = baseline()
    if (base.preserved_build() != old['buildProof'] or base.bundle() != old['runtimeBundle'] or
            base.model_identities() != old['modelFiles']):
        raise ValueError('INSTALLED_INPUT_CHANGED')
    source_path(old, full=True)
    for key, path in [('wslSha256', Path.home() / '.wslconfig'),
                      ('desktopSha256', Path.home() / 'AppData/Roaming/Docker/settings-store.json')]:
        if base.build.tools.sha(path) != old['settings'][key]:
            raise ValueError('WSL_OR_DOCKER_SETTINGS_CHANGED')
    if packet['settings'] != old['settings']:
        raise ValueError('SETTINGS_BINDING_CHANGED')


def prepare():
    if LIVE.exists():
        raise ValueError('MANUAL_SESSION_ALREADY_CLAIMED_NO_RETRY')
    old = baseline()
    source = source_path(old)
    package = ROOT / 'packages' / uuid.uuid4().hex
    inputs = package / 'input'
    inputs.mkdir(parents=True)
    for name, path in GUEST.items():
        (inputs / name).write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    write(inputs / 'strata.json', configuration())
    args, contract = launch(package, source, old)
    packet = dict(version=1, scope=SCOPE, status='OFFLINE_READY_FOR_REVIEW', maximumAttempts=1,
        modelLaunchEnabled=False, workerLaunchEnabled=False, policy=POLICY, limits=LIMITS,
        packageDirectory=str(package), liveNamespace=str(LIVE), configuration=configuration(),
        createArgs=args, contract=contract, helperSha256=sources(),
        inputSha256={p.name: base.build.tools.sha(p) for p in inputs.iterdir()},
        baselineManifestSha256=BASELINE_MANIFEST, settings=old['settings'],
        sourceLimitation=old['sourceLimitation'], sourceReviewSha256=old['sourceReviewSha256'],
        controls=old['controls'], limitations=old['limitations'],
        startupAudit=base.native_iq_startup.check(configuration(), source))
    verify_inputs(packet)
    digest = base.sha(packet)
    folder = ROOT / digest
    folder.mkdir(parents=True)
    write(folder / 'review.json', packet)
    for relative in packet['helperSha256']:
        path = REPO / relative
        if base.build.tools.sha(path) != packet['helperSha256'][relative]:
            raise ValueError('MANUAL_HELPER_CHANGED_DURING_PREPARATION')
        target = folder / 'helpers' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    write(folder / 'approval.template.json', dict(version=1, status='NOT_APPROVED', scope=SCOPE,
        reviewSha256=digest, maximumAttempts=1, acceptPolicySha256=base.sha(POLICY),
        acceptLimits=LIMITS, acceptSourceLimitation=old['sourceLimitation'],
        acceptLimitations=old['limitations'], ownerMessage='', modelLaunchEnabled=False,
        workerLaunchEnabled=False, synthetic=False))
    # New immutable review packets; candidate is only a convenience pointer.
    base.build.tools.base.atomic(ROOT / 'candidate.json', {'reviewSha256': digest})
    return dict(status='OFFLINE_READY_FOR_REVIEW', reviewSha256=digest,
                reviewFile=str(folder / 'review.json'), modelLaunchEnabled=False)


def review():
    digest = read(ROOT / 'candidate.json')['reviewSha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('MANUAL_REVIEW_ID')
    packet = read(ROOT / digest / 'review.json')
    old = baseline()
    package = Path(packet['packageDirectory'])
    if package.parent != ROOT / 'packages' or not re.fullmatch('[0-9a-f]{32}', package.name):
        raise ValueError('MANUAL_PACKAGE_PATH')
    args, contract = launch(package, source_path(old), old)
    if (base.sha(packet) != digest or packet['scope'] != SCOPE or packet['policy'] != POLICY or
            packet['limits'] != LIMITS or packet['maximumAttempts'] != 1 or
            packet['liveNamespace'] != str(LIVE) or packet['configuration'] != configuration() or
            packet['modelLaunchEnabled'] is not False or packet['workerLaunchEnabled'] is not False or
            packet['helperSha256'] != sources() or packet['createArgs'] != args or
            base.sha(packet['contract']) != base.sha(contract)):
        raise ValueError('MANUAL_REVIEW_STALE')
    inputs = package / 'input'
    if {p.name for p in inputs.iterdir()} != set(GUEST) | {'strata.json'}:
        raise ValueError('MANUAL_INPUT_SET')
    for name, expected in packet['inputSha256'].items():
        if base.build.tools.sha(inputs / name) != expected:
            raise ValueError('MANUAL_INPUT_CHANGED')
    for name, original in GUEST.items():
        if (inputs / name).read_bytes() != original.read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('MANUAL_GUEST_CHANGED')
    if read(inputs / 'strata.json') != configuration():
        raise ValueError('MANUAL_CONFIG_CHANGED')
    return digest, packet


class Permit(base.Permit):
    @property
    def live_namespace(self):
        return LIVE


def authorize():
    # Approval absence checked before any review/identity/live operation.
    if not APPROVAL.exists():
        raise ValueError('MANUAL_CHAT_NOT_APPROVED')
    digest, packet = review()
    decision = read(APPROVAL, 16384)
    if (type(decision.get('version')) is not int or decision.get('version') != 1 or
            decision.get('status') != 'owner-approved-one-manual-chat-session' or
            decision.get('scope') != SCOPE or decision.get('reviewSha256') != digest or
            type(decision.get('maximumAttempts')) is not int or decision['maximumAttempts'] != 1 or
            decision.get('acceptPolicySha256') != base.sha(POLICY) or decision.get('acceptLimits') != LIMITS or
            decision.get('acceptSourceLimitation') != packet['sourceLimitation'] or
            decision.get('acceptLimitations') != packet['limitations'] or
            decision.get('modelLaunchEnabled') is not True or decision.get('workerLaunchEnabled') is not False or
            decision.get('synthetic') is not False or not isinstance(decision.get('ownerMessage'), str) or
            not decision['ownerMessage'].strip()):
        raise ValueError('MANUAL_CHAT_APPROVAL_INVALID')
    return Permit(digest, base.build.encoded(packet).decode(), base.sha(decision))
