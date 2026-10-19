"""On-disk stager rehearsal with fixed tiny bytes; no network or Docker calls."""
import argparse
import hashlib
import io
import json
import uuid

import image_download as downloads

ROOT = downloads.images.HERE.parents[1] / '.runtime/image-blob-rehearsals'
ROOT_LIMIT = 32 * 1024**2
SUITE_RESERVATION = 4 * 1024**2
PAYLOADS = (b'{"synthetic":true,"kind":"config"}', b'fixed synthetic compressed-layer placeholder')
BLOBS = tuple(downloads.Blob('sha256:' + hashlib.sha256(data).hexdigest(), len(data)) for data in PAYLOADS)
IDENTITY = hashlib.sha256(b'fixed-image-stager-rehearsal-v1').hexdigest()


class Body(io.BytesIO):
    status = 200

    def __init__(self, payload, length):
        super().__init__(payload)
        self.length = length

    def getheaders(self):
        return [('Content-Length', str(self.length))]


class SyntheticSource:
    def __init__(self, scenario):
        self.scenario, self.calls = scenario, 0

    def open(self, spec, _context):
        self.calls += 1
        data = PAYLOADS[BLOBS.index(spec)]
        if self.scenario == 'wrong-hash':
            data = b'x' * len(data)
        if self.scenario == 'extra-byte':
            data += b'x'
        return Body(data, spec.size)


def verify():
    downloads.tools.plain(ROOT)
    with downloads.tools.base.lock(ROOT / 'control'):
        entries, used = downloads.plain_usage(ROOT)
        if entries + 80 > downloads.ENTRY_LIMIT or used + SUITE_RESERVATION > ROOT_LIMIT:
            raise downloads.StageError('REHEARSAL_NAMESPACE_FULL')
        directory = ROOT / uuid.uuid4().hex
        directory.mkdir()
        limits = downloads.Limits(65536, 1024**2, 0, 5, 2)
        result = {'version': 1, 'passed': False, 'synthetic': True, 'networkUsed': False,
                  'realImageLayersDownloaded': False, 'imageImported': False,
                  'compilerStarted': False, 'modelStarted': False, 'cases': []}
        try:
            for scenario in ('success', 'wrong-hash', 'extra-byte'):
                source = SyntheticSource(scenario)
                root = directory / scenario
                row = {'scenario': scenario, 'passed': False}
                result['cases'].append(row)
                try:
                    _, state = downloads._stage(root, BLOBS, IDENTITY, source, limits,
                                                guard=lambda: True, synthetic=True)
                    if scenario != 'success':
                        raise AssertionError('Invalid synthetic blob accepted')
                    row['stagedBytes'] = state['blobPayloadBytes']
                    row['firstSourceCalls'] = source.calls
                    source.calls = 0
                    _, state = downloads._stage(root, BLOBS, IDENTITY, source, limits,
                                                guard=lambda: True, synthetic=True)
                    if source.calls or not all(r['cacheReused'] for r in state['blobs']):
                        raise AssertionError('Warm cache unexpectedly fetched bytes')
                    row.update(cacheVerifiedWithoutRefetch=True, passed=True)
                except downloads.StageError as error:
                    if scenario == 'success':
                        raise
                    expected = 'BLOB_HASH_OR_LENGTH_MISMATCH' if scenario == 'wrong-hash' else 'BLOB_LENGTH_MISMATCH'
                    if error.code != expected:
                        raise
                    state = json.loads((root / 'state.json').read_text())
                    if state['state'] != 'FAULT' or not list((root / 'sessions').glob('*/*.partial')):
                        raise AssertionError('Failure evidence was not retained')
                    before = source.calls
                    try:
                        downloads._stage(root, BLOBS, IDENTITY, source, limits, guard=lambda: True, synthetic=True)
                    except downloads.StageError as retry:
                        if retry.code != 'LATCHED_FAULT_OR_UNFINISHED_SESSION' or source.calls != before:
                            raise
                    else:
                        raise AssertionError('Fault incorrectly allowed restart')
                    row.update(fault=expected, restartRejected=True, partialRetained=True, passed=True)
            result['passed'] = all(row['passed'] for row in result['cases'])
        finally:
            downloads.tools.base.atomic(directory / 'result.json', result)
        print(json.dumps({'directory': str(directory), **result}, indent=2))
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-only', action='store_true', required=True)
    parser.parse_args()
    verify()
