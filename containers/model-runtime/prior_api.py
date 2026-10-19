"""Verify the consumed first API attempt from frozen evidence; never access Docker."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW_SHA = '62e923cdc2e135540231d4594bf82ea6011828f3b64bdb966e6ab63ba9fb9ae6'
FOLDER = REPO / '.runtime/model-api-review' / REVIEW_SHA
MANIFEST_SHA = 'e3481c7b5efbacdc418b761a9f84413fdc54422026f8281e36e9500f0877eed8'
SUPPLEMENT_SHA = '1e32f294234ee4ab22b0efc35973de426d238973408edb578b0d2a9b934d1f5d'
CONTAINER = 'f8b485a463ccc4bd65e5093140c2b26f2e64a68f5309e8b43a0cffc579bd9d48'
REPLAY = 'sessions/b778a58043f84cf99f48c5c6d56c3fa4/admission-replay.json'
SECOND_SHA = 'fc1d1d9c970ba58922483dd57aac625cef87fd4879d83fe0cf413a166ae04599'
SECOND_FOLDER = REPO / '.runtime/model-api-recovery-review' / SECOND_SHA
SECOND_MANIFEST_SHA = '1958b8f961e60ab2abe8884a416a12fa9f08a300c0580585bc1e31b1fdc71cdd'
SECOND_CONTAINER = 'bb32c325d280fb3c8ea2d4ffcfbf9d48f6c3df20b6af74c9b6ddf8082e75b8ca'
THIRD_SHA = 'fa9eeb3023db47bc8fd00a338979dabb13a0a8f16026e31c127d22d04a6c96b8'
THIRD_FOLDER = REPO / '.runtime/model-api-admission-review' / THIRD_SHA
THIRD_MANIFEST_SHA = '6eeb23d789f2ee67549c5c39fea1ab11dc9ee168245a192ab5ac2a169ef3fdc4'
THIRD_CONTAINER = 'bde071578cca6701809c592f2fe7ca90416260677f0ef579734c3b1a964c99c5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def proof():
    # Constants bind the inventories before any paths from them are trusted.
    if (digest(FOLDER / 'execution-preservation.json') != MANIFEST_SHA or
            digest(FOLDER / 'execution-preservation-supplement.json') != SUPPLEMENT_SHA):
        raise ValueError('PRIOR_API_MANIFEST_CHANGED')
    return {'reviewSha256': REVIEW_SHA, 'preservationSha256': MANIFEST_SHA,
            'supplementSha256': SUPPLEMENT_SHA,
            'resultSha256': digest(FOLDER / 'execution-result.json'),
            'retainedContainerId': CONTAINER, 'previousAttemptReset': False}


def verify(*, plain):
    result = proof()
    manifest = load(FOLDER / 'execution-preservation.json')
    supplement = load(FOLDER / 'execution-preservation-supplement.json')
    if (manifest['reviewSha256'] != REVIEW_SHA or supplement['parentManifestSha256'] != MANIFEST_SHA or
            manifest['executionResultSha256'] != result['resultSha256']):
        raise ValueError('PRIOR_API_RESULT_CHANGED')
    for key in ('attempt', 'reader', 'launcher', 'capacityProbe'):
        record = manifest[key]; directory = Path(record['directory'])
        entries = dict(record['files'])
        if key == 'attempt':
            path = directory / REPLAY
            if set(supplement['addedFiles']) != {str(path)}:
                raise ValueError('PRIOR_API_SUPPLEMENT_CHANGED')
            entries[REPLAY] = supplement['addedFiles'][str(path)]
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(entries):
            raise ValueError('PRIOR_API_FILE_SET_CHANGED')
        for name, item in entries.items():
            path = directory / name; plain(path)
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('PRIOR_API_EVIDENCE_CHANGED')
    for name, item in manifest['reviewEvidence'].items():
        path = FOLDER / name; plain(path)
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('PRIOR_API_REVIEW_CHANGED')
    packet = load(FOLDER / 'review.json')
    # The canonical packet hash is checked by the caller's existing encoder.
    for name, expected in packet['helperSha256'].items():
        path = FOLDER / 'helpers' / name; plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('PRIOR_API_FROZEN_HELPER_CHANGED')
    for name, expected in packet['inputSha256'].items():
        for path in (FOLDER / 'input' / name, Path(packet['packageDirectory']) / 'input' / name):
            plain(path)
            if digest(path) != expected:
                raise ValueError('PRIOR_API_INPUT_CHANGED')
    original_approval = REPO / 'containers/model-runtime/first-model-api-approval.json'
    if original_approval.read_bytes() != (FOLDER / 'owner-approval.json').read_bytes():
        raise ValueError('PRIOR_API_APPROVAL_CHANGED')
    saved = load(FOLDER / 'execution-result.json')
    if (saved['status'] != 'MODEL_API_ADMISSION_FAULT_NO_MODEL_STARTED' or
            saved['fault'] != {'code': 'BASELINE_NOT_MET'} or saved['containerId'] != CONTAINER or
            saved['stopConfirmed'] is not True or saved['containerStarted'] is not False or
            saved['modelStarted'] is not False or saved['requestsSubmitted'] != 0):
        raise ValueError('PRIOR_API_OUTCOME_CHANGED')
    return result


def second_proof():
    if digest(SECOND_FOLDER / 'execution-preservation.json') != SECOND_MANIFEST_SHA:
        raise ValueError('SECOND_API_MANIFEST_CHANGED')
    manifest = load(SECOND_FOLDER / 'execution-preservation.json')
    result_sha = digest(SECOND_FOLDER / 'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:
        raise ValueError('SECOND_API_RESULT_CHANGED')
    return {'reviewSha256': SECOND_SHA, 'preservationSha256': SECOND_MANIFEST_SHA,
            'resultSha256': result_sha, 'retainedContainerId': SECOND_CONTAINER,
            'previousAttemptReset': False}


def verify_second(*, plain):
    result = second_proof()
    manifest = load(SECOND_FOLDER / 'execution-preservation.json')
    if manifest['reviewSha256'] != SECOND_SHA:
        raise ValueError('SECOND_API_REVIEW_CHANGED')
    for key in ('attempt', 'reader', 'launcher', 'capacityProbe'):
        record = manifest[key]; directory = Path(record['directory'])
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('SECOND_API_FILE_SET_CHANGED')
        for name, item in record['files'].items():
            path = directory / name; plain(path)
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('SECOND_API_EVIDENCE_CHANGED')
    for name, item in manifest['reviewEvidence'].items():
        path = SECOND_FOLDER / name; plain(path)
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('SECOND_API_REVIEW_EVIDENCE_CHANGED')
    packet = load(SECOND_FOLDER / 'review.json')
    for name, expected in packet['helperSha256'].items():
        path = SECOND_FOLDER / 'helpers' / name; plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != expected:
            raise ValueError('SECOND_API_FROZEN_HELPER_CHANGED')
    for name, expected in packet['inputSha256'].items():
        for path in (SECOND_FOLDER / 'input' / name, Path(packet['packageDirectory']) / 'input' / name):
            plain(path)
            if digest(path) != expected:
                raise ValueError('SECOND_API_INPUT_CHANGED')
    original_approval = REPO / 'containers/model-runtime/model-api-2-approval.json'
    if original_approval.read_bytes() != (SECOND_FOLDER / 'owner-approval.json').read_bytes():
        raise ValueError('SECOND_API_APPROVAL_CHANGED')
    saved = load(SECOND_FOLDER / 'execution-result.json')
    if (saved['status'] != 'MODEL_API_ADMISSION_FAULT_NO_MODEL_STARTED' or
            saved['fault'] != {'code': 'BASELINE_NOT_MET'} or saved['containerId'] != SECOND_CONTAINER or
            saved['stopConfirmed'] is not True or saved['containerStarted'] is not False or
            saved['modelStarted'] is not False or saved['requestsSubmitted'] != 0 or
            saved['allFourHostProcessesExited'] is not True):
        raise ValueError('SECOND_API_OUTCOME_CHANGED')
    return result


def third_proof():
    if digest(THIRD_FOLDER/'execution-preservation.json') != THIRD_MANIFEST_SHA:
        raise ValueError('THIRD_API_MANIFEST_CHANGED')
    manifest = load(THIRD_FOLDER/'execution-preservation.json')
    result_sha = digest(THIRD_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:
        raise ValueError('THIRD_API_RESULT_CHANGED')
    return {'reviewSha256':THIRD_SHA,'preservationSha256':THIRD_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':THIRD_CONTAINER,'previousAttemptReset':False}


def verify_third(*, plain):
    result = third_proof(); manifest = load(THIRD_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256'] != THIRD_SHA:
        raise ValueError('THIRD_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record = manifest[key]; directory = Path(record['directory'])
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('THIRD_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path = directory/name; plain(path)
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('THIRD_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path = THIRD_FOLDER/name; plain(path)
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('THIRD_API_REVIEW_EVIDENCE_CHANGED')
    packet = load(THIRD_FOLDER/'review.json')
    for name,expected in packet['helperSha256'].items():
        path = THIRD_FOLDER/'helpers'/name; plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() != expected:
            raise ValueError('THIRD_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (THIRD_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path) != expected:
                raise ValueError('THIRD_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-3-approval.json').read_bytes() !=
            (THIRD_FOLDER/'owner-approval.json').read_bytes()):
        raise ValueError('THIRD_API_APPROVAL_CHANGED')
    saved = load(THIRD_FOLDER/'execution-result.json')
    if (saved['status'] != 'MODEL_API_ENGINE_ARGUMENT_REJECTION' or
            saved['fault'] != {'code':'API_TEST_FAILED'} or saved['containerId'] != THIRD_CONTAINER or
            saved['stopConfirmed'] is not True or saved['containerStarted'] is not True or
            saved['modelReady'] is not False or saved['requestsSubmitted'] != 0 or
            saved['engineExitCode'] != 2 or saved['allFourHostProcessesExited'] is not True):
        raise ValueError('THIRD_API_OUTCOME_CHANGED')
    return result

FOURTH_SHA = '29c70fec244b6f0f747dc60e39aab091387af43b55d5bc7708e2320ebc533bb2'
FOURTH_FOLDER = REPO / '.runtime/model-api-native-review' / FOURTH_SHA
FOURTH_MANIFEST_SHA = '9515d7896260b0ac430e636bd2e617bc5d5270a40b848533c7b2f54b93e0573d'
FOURTH_CONTAINER = '8257d6cfc5da92dcc687285f9c7e21a513031d60ba98a71f1df9210b22ae9dc4'

def fourth_proof():
    if digest(FOURTH_FOLDER/'execution-preservation.json') != FOURTH_MANIFEST_SHA:
        raise ValueError('FOURTH_API_MANIFEST_CHANGED')
    manifest = load(FOURTH_FOLDER/'execution-preservation.json')
    result_sha = digest(FOURTH_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:
        raise ValueError('FOURTH_API_RESULT_CHANGED')
    return {'reviewSha256':FOURTH_SHA,'preservationSha256':FOURTH_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':FOURTH_CONTAINER,'previousAttemptReset':False}


def verify_fourth(*, plain):
    result = fourth_proof(); manifest = load(FOURTH_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256'] != FOURTH_SHA:
        raise ValueError('FOURTH_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record = manifest[key]; directory = Path(record['directory'])
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise ValueError('FOURTH_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path = directory/name; plain(path)
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('FOURTH_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path = FOURTH_FOLDER/name; plain(path)
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('FOURTH_API_REVIEW_EVIDENCE_CHANGED')
    packet = load(FOURTH_FOLDER/'review.json')
    for name,expected in packet['helperSha256'].items():
        path = FOURTH_FOLDER/'helpers'/name; plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() != expected:
            raise ValueError('FOURTH_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (FOURTH_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path) != expected:
                raise ValueError('FOURTH_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-4-approval.json').read_bytes() !=
            (FOURTH_FOLDER/'owner-approval.json').read_bytes()):
        raise ValueError('FOURTH_API_APPROVAL_CHANGED')
    saved = load(FOURTH_FOLDER/'execution-result.json')
    if (saved['status'] != 'MODEL_API_READY_REQUEST_FAILED_ENGINE_SILENCE' or
            saved['fault'] != {'code':'API_TEST_FAILED'} or saved['containerId'] != FOURTH_CONTAINER or
            saved['stopConfirmed'] is not True or saved['containerStarted'] is not True or
            saved['modelReady'] is not True or saved['requestsSubmitted'] != 1 or
            saved['responseSucceeded'] is not False or saved['allFourHostProcessesExited'] is not True):
        raise ValueError('FOURTH_API_OUTCOME_CHANGED')
    return result


FIFTH_SHA = 'cbbcdf85aa9a72b6122fc1c30ecdaf89fe2ba0347ef5e17b73868cbcfcfaf38b'
FIFTH_FOLDER = REPO / '.runtime/model-api-timing-review' / FIFTH_SHA
FIFTH_MANIFEST_SHA = '5ef88755dad5b0c78122ca631a67ff1b73cadfe9bc9bc201eaa466c10ec4a2c2'
FIFTH_CONTAINER = '3eacfdda1f9f3a3965af96377a945fc410eed95b65797e510e8766ed4332624e'


def fifth_proof():
    if digest(FIFTH_FOLDER/'execution-preservation.json') != FIFTH_MANIFEST_SHA:
        raise ValueError('FIFTH_API_MANIFEST_CHANGED')
    manifest=load(FIFTH_FOLDER/'execution-preservation.json')
    result_sha=digest(FIFTH_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:raise ValueError('FIFTH_API_RESULT_CHANGED')
    return {'reviewSha256':FIFTH_SHA,'preservationSha256':FIFTH_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':FIFTH_CONTAINER,'previousAttemptReset':False}


def verify_fifth(*,plain):
    result=fifth_proof();manifest=load(FIFTH_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256']!=FIFTH_SHA:raise ValueError('FIFTH_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record=manifest[key];directory=Path(record['directory'])
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual!=set(record['files']):raise ValueError('FIFTH_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path=directory/name;plain(path)
            if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
                raise ValueError('FIFTH_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path=FIFTH_FOLDER/name;plain(path)
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('FIFTH_API_REVIEW_EVIDENCE_CHANGED')
    packet=load(FIFTH_FOLDER/'review.json')
    canonical=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest()!=FIFTH_SHA:raise ValueError('FIFTH_API_PACKET_CHANGED')
    for name,expected in packet['helperSha256'].items():
        path=FIFTH_FOLDER/'helpers'/name;plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('FIFTH_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (FIFTH_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path)!=expected:raise ValueError('FIFTH_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-5-approval.json').read_bytes()!=
            (FIFTH_FOLDER/'owner-approval.json').read_bytes()):raise ValueError('FIFTH_API_APPROVAL_CHANGED')
    for name,item in load(FIFTH_FOLDER/'prelaunch-result.json')['evidence'].items():
        path=REPO/name;plain(path)
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('FIFTH_API_CANCELED_LAUNCH_EVIDENCE_CHANGED')
    saved=load(FIFTH_FOLDER/'execution-result.json')
    if (saved['status']!='FIFTH_MODEL_API_TEST_STOPPED_WITHOUT_CONFIRMED_ANSWER' or
            saved['fault']!={'code':'CANCELLED'} or saved['parentError']['type']!='PermissionError' or
            saved['containerId']!=FIFTH_CONTAINER or saved['stopConfirmed'] is not True or
            saved['containerStarted'] is not False or saved['modelStarted'] is not False or
            saved['requestsSubmitted']!=0 or saved['responseSucceeded'] is not False or
            saved['allFourHostProcessesExited'] is not True):raise ValueError('FIFTH_API_OUTCOME_CHANGED')
    return result


SIXTH_SHA = '1f8494f279fb07c3c3ae2f62b39ba854e04fd1c915816696544416681d3c5b6a'
SIXTH_FOLDER = REPO / '.runtime/model-api-file-access-review' / SIXTH_SHA
SIXTH_MANIFEST_SHA = '7df84f76a54baa38441ca1718434674b910c0170cfbb802b499eeecec9a6039d'
SIXTH_CONTAINER = '564ce1f313db7d9aa6494072015c57caf58529651c8112ec403fc6bf436e46d1'


def sixth_proof():
    if digest(SIXTH_FOLDER/'execution-preservation.json') != SIXTH_MANIFEST_SHA:
        raise ValueError('SIXTH_API_MANIFEST_CHANGED')
    manifest=load(SIXTH_FOLDER/'execution-preservation.json')
    result_sha=digest(SIXTH_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:raise ValueError('SIXTH_API_RESULT_CHANGED')
    return {'reviewSha256':SIXTH_SHA,'preservationSha256':SIXTH_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':SIXTH_CONTAINER,'previousAttemptReset':False}


def verify_sixth(*,plain):
    result=sixth_proof();manifest=load(SIXTH_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256']!=SIXTH_SHA:raise ValueError('SIXTH_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record=manifest[key];directory=Path(record['directory'])
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual!=set(record['files']):raise ValueError('SIXTH_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path=directory/name;plain(path)
            if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
                raise ValueError('SIXTH_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path=SIXTH_FOLDER/name;plain(path)
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('SIXTH_API_REVIEW_EVIDENCE_CHANGED')
    packet=load(SIXTH_FOLDER/'review.json')
    canonical=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest()!=SIXTH_SHA:raise ValueError('SIXTH_API_PACKET_CHANGED')
    for name,expected in packet['helperSha256'].items():
        path=SIXTH_FOLDER/'helpers'/name;plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('SIXTH_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (SIXTH_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path)!=expected:raise ValueError('SIXTH_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-6-approval.json').read_bytes()!=
            (SIXTH_FOLDER/'owner-approval.json').read_bytes()):raise ValueError('SIXTH_API_APPROVAL_CHANGED')
    saved=load(SIXTH_FOLDER/'execution-result.json')
    if (saved['status']!='SIXTH_MODEL_API_TEST_BASELINE_NOT_MET' or
            saved['fault']!={'code':'BASELINE_NOT_MET'} or saved['parentError'] is not None or saved['noFileAccessErrorRecorded'] is not True or
            saved['containerId']!=SIXTH_CONTAINER or saved['stopConfirmed'] is not True or
            saved['containerStarted'] is not False or saved['modelStarted'] is not False or
            saved['requestsSubmitted']!=0 or saved['responseSucceeded'] is not False or
            saved['allFourHostProcessesExited'] is not True):raise ValueError('SIXTH_API_OUTCOME_CHANGED')
    return result


SEVENTH_SHA = '8d6239ba96a8ec346554470479c861315520ee63808781f5a3322cf5c75af3ed'
SEVENTH_FOLDER = REPO / '.runtime/model-api-94-admission-review' / SEVENTH_SHA
SEVENTH_MANIFEST_SHA = '46997b4ff1e1533eb0a66f240bb5b8a6253b952537df5298f13d0d84816ff9b1'
SEVENTH_CONTAINER = 'd279798aad898617df6b94a5012699cc4e136eb0bcc022682de46e2c2d28612b'


def seventh_proof():
    if digest(SEVENTH_FOLDER/'execution-preservation.json') != SEVENTH_MANIFEST_SHA:
        raise ValueError('SEVENTH_API_MANIFEST_CHANGED')
    manifest=load(SEVENTH_FOLDER/'execution-preservation.json')
    result_sha=digest(SEVENTH_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:raise ValueError('SEVENTH_API_RESULT_CHANGED')
    return {'reviewSha256':SEVENTH_SHA,'preservationSha256':SEVENTH_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':SEVENTH_CONTAINER,'previousAttemptReset':False}


def verify_seventh(*,plain):
    result=seventh_proof();manifest=load(SEVENTH_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256']!=SEVENTH_SHA:raise ValueError('SEVENTH_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record=manifest[key];directory=Path(record['directory'])
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual!=set(record['files']):raise ValueError('SEVENTH_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path=directory/name;plain(path)
            if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
                raise ValueError('SEVENTH_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path=SEVENTH_FOLDER/name;plain(path)
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('SEVENTH_API_REVIEW_EVIDENCE_CHANGED')
    packet=load(SEVENTH_FOLDER/'review.json')
    canonical=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest()!=SEVENTH_SHA:raise ValueError('SEVENTH_API_PACKET_CHANGED')
    for name,expected in packet['helperSha256'].items():
        path=SEVENTH_FOLDER/'helpers'/name;plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('SEVENTH_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (SEVENTH_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path)!=expected:raise ValueError('SEVENTH_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-7-approval.json').read_bytes()!=
            (SEVENTH_FOLDER/'owner-approval.json').read_bytes()):raise ValueError('SEVENTH_API_APPROVAL_CHANGED')
    saved=load(SEVENTH_FOLDER/'execution-result.json')
    if (saved['status']!='SEVENTH_MODEL_API_TEST_DOCKER_INSPECT_TIMEOUT' or
            saved['fault']!={'code':'MODEL_WATCH_ERROR'} or saved['watchError']['type']!='TimeoutExpired' or
            saved['containerId']!=SEVENTH_CONTAINER or saved['stopConfirmed'] is not True or
            saved['containerStarted'] is not True or saved['modelStarted'] is not None or
            saved['requestsSubmitted'] is not None or saved['responseSucceeded'] is not False or
            saved['admissionPassed'] is not True or saved['allFourHostProcessesExited'] is not True):
        raise ValueError('SEVENTH_API_OUTCOME_CHANGED')
    return result


EIGHTH_SHA = '5e7f1a40d21c24bd64fa495d8b821994def2e8e3c189318c3175b432de42b8d1'
EIGHTH_FOLDER = REPO / '.runtime/model-api-startup-review' / EIGHTH_SHA
EIGHTH_MANIFEST_SHA = '4f8e1671e9c02b07b63728e7922c0f41b849e0f2f6264970a9f5a11966d4e07c'
EIGHTH_CONTAINER = '2cb055083d4d0e4b5d4a76e38dac8d19fd077dccb076dc6ca20dbef434bad72e'


def eighth_proof():
    if digest(EIGHTH_FOLDER/'execution-preservation.json') != EIGHTH_MANIFEST_SHA:
        raise ValueError('EIGHTH_API_MANIFEST_CHANGED')
    manifest=load(EIGHTH_FOLDER/'execution-preservation.json')
    result_sha=digest(EIGHTH_FOLDER/'execution-result.json')
    if manifest['executionResultSha256'] != result_sha:raise ValueError('EIGHTH_API_RESULT_CHANGED')
    return {'reviewSha256':EIGHTH_SHA,'preservationSha256':EIGHTH_MANIFEST_SHA,
            'resultSha256':result_sha,'retainedContainerId':EIGHTH_CONTAINER,'previousAttemptReset':False}


def verify_eighth(*,plain):
    result=eighth_proof();manifest=load(EIGHTH_FOLDER/'execution-preservation.json')
    if manifest['reviewSha256']!=EIGHTH_SHA:raise ValueError('EIGHTH_API_REVIEW_CHANGED')
    for key in ('attempt','reader','launcher','capacityProbe'):
        record=manifest[key];directory=Path(record['directory'])
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if actual!=set(record['files']):raise ValueError('EIGHTH_API_FILE_SET_CHANGED')
        for name,item in record['files'].items():
            path=directory/name;plain(path)
            if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
                raise ValueError('EIGHTH_API_EVIDENCE_CHANGED')
    for name,item in manifest['reviewEvidence'].items():
        path=EIGHTH_FOLDER/name;plain(path)
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('EIGHTH_API_REVIEW_EVIDENCE_CHANGED')
    packet=load(EIGHTH_FOLDER/'review.json')
    canonical=json.dumps(packet,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest()!=EIGHTH_SHA:raise ValueError('EIGHTH_API_PACKET_CHANGED')
    for name,expected in packet['helperSha256'].items():
        path=EIGHTH_FOLDER/'helpers'/name;plain(path)
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('EIGHTH_API_FROZEN_HELPER_CHANGED')
    for name,expected in packet['inputSha256'].items():
        for path in (EIGHTH_FOLDER/'input'/name,Path(packet['packageDirectory'])/'input'/name):
            plain(path)
            if digest(path)!=expected:raise ValueError('EIGHTH_API_INPUT_CHANGED')
    if ((REPO/'containers/model-runtime/model-api-8-approval.json').read_bytes()!=
            (EIGHTH_FOLDER/'owner-approval.json').read_bytes()):raise ValueError('EIGHTH_API_APPROVAL_CHANGED')
    saved=load(EIGHTH_FOLDER/'execution-result.json')
    if (saved['status']!='EIGHTH_MODEL_API_TEST_FAILED' or
            saved['fault']!={'code':'BASELINE_NOT_MET'} or saved['watchError'] is not None or
            saved['parentError'] is not None or saved['containerId']!=EIGHTH_CONTAINER or
            saved['stopConfirmed'] is not True or saved['containerStatus']!='created' or
            saved['containerStarted'] is not False or saved['modelStarted'] is not False or
            saved['requestsSubmitted']!=0 or saved['responseSucceeded'] is not False or
            saved['admissionPassed'] is not False or saved['allFourHostProcessesExited'] is not True):
        raise ValueError('EIGHTH_API_OUTCOME_CHANGED')
    return result
