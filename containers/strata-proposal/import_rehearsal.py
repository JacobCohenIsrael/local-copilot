"""Tiny in-memory archive/transport rehearsal. No engine, sensor or disk mount.

These cases prove the stream contract only, not a real filesystem quota or
daemon shutdown. Native store/daemon proof remains a separate admission gate.
"""
import errno
import gzip
import hashlib
import io
import json
import tarfile
import uuid

import import_plan as plan
import oci_archive as archive


def fixture():
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        data = b'harmless synthetic OCI import fixture\n'
        header = tarfile.TarInfo('fixture.txt')
        header.size = len(data)
        tar.addfile(header, io.BytesIO(data))
    expanded = layer.getvalue()
    packed = gzip.compress(expanded, mtime=0)
    def encoded(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    def sha(raw):
        return hashlib.sha256(raw).hexdigest()
    config = encoded({'architecture': 'amd64', 'os': 'linux',
                      'rootfs': {'type': 'layers', 'diff_ids': ['sha256:' + sha(expanded)]}})
    manifest = encoded({'schemaVersion': 2,
        'mediaType': 'application/vnd.docker.distribution.manifest.v2+json',
        'config': {'mediaType': 'application/vnd.docker.container.image.v1+json',
                   'size': len(config), 'digest': 'sha256:' + sha(config)},
        'layers': [{'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip',
                    'size': len(packed), 'digest': 'sha256:' + sha(packed)}]})
    rows = archive.members(manifest, config, expected_manifest=sha(manifest))
    return rows, {sha(config): config, sha(packed): packed}


class Sink:
    """Fault-injectable memory pipe; no claim of real disk enforcement."""
    def __init__(self, *, capacity, partial=65536):
        self.capacity, self.partial, self.data = capacity, partial, bytearray()

    def write(self, raw):
        if len(self.data) >= self.capacity:
            raise OSError(errno.ENOSPC, 'synthetic disk full')
        count = min(len(raw), self.partial, self.capacity - len(self.data))
        self.data.extend(raw[:count])
        return count


def exercise():
    rows, blobs = fixture()
    exact = archive.archive_bytes(rows)
    cases = []
    for name in ('success', 'disk-full', 'guard-permission-lost',
                 'bad-hash', 'short-input', 'extra-input', 'pipe-closed'):
        source = dict(blobs)
        key = rows[-1].sha256
        if name == 'bad-hash':
            source[key] = b'X' + source[key][1:]
        elif name == 'short-input':
            source[key] = source[key][:-1]
        elif name == 'extra-input':
            source[key] += b'X'
        sink = Sink(capacity=exact if name != 'disk-full' else 1024, partial=7)
        calls = 0
        def guard():
            nonlocal calls
            calls += 1
            return not (name == 'guard-permission-lost' and calls > 8)
        class Closed:
            def write(self, raw):
                raise BrokenPipeError('synthetic disconnected daemon')
        try:
            result = archive.stream(rows, lambda sha: io.BytesIO(source[sha]),
                                    Closed() if name == 'pipe-closed' else sink,
                                    guard=guard, maximum_bytes=exact)
            if name != 'success':
                raise AssertionError('Injected fault was ignored: ' + name)
            with tarfile.open(fileobj=io.BytesIO(sink.data), mode='r:') as tar:
                if tar.getnames() != [r.name for r in rows]:
                    raise AssertionError('Archive member identity changed')
                for row in rows:
                    if hashlib.sha256(tar.extractfile(row.name).read()).hexdigest() != row.sha256:
                        raise AssertionError('Archive content changed')
            cases.append({'case': name, 'result': result['status'], 'archiveBytes': len(sink.data)})
        except (ValueError, OSError) as error:
            if name == 'success':
                raise
            cases.append({'case': name, 'result': 'REJECTED', 'error': type(error).__name__,
                          'bytesAccepted': len(sink.data)})
    return {'status': 'PASS_TRANSPORT_ONLY', 'synthetic': True, 'cases': cases,
            'caseCount': len(cases), 'nativeDiskQuotaProven': False,
            'nativeDaemonShutdownProven': False, 'hardwareRead': False,
            'realCacheBodiesRead': False, 'imageDownloadEnabled': False,
            'imageImportEnabled': False, 'buildEnabled': False, 'modelLaunchEnabled': False}


def rehearse():
    result = exercise()
    directory = plan.REPO / '.runtime/import-rehearsals' / uuid.uuid4().hex
    plan.tools.plain(directory)
    directory.mkdir(parents=True)
    plan.tools.base.atomic(directory / 'result.json', result)
    return {**result, 'resultFile': str(directory / 'result.json')}
