"""Bounded OCI archive producer. No Docker, extraction, network or subprocess API.

The caller owns the sink, its deadline and independent cancellation. A blocking
sink MUST be supervised outside this function; a Python callback cannot unblock
a pipe write. This is a transport primitive, never workload admission.
"""
from dataclasses import dataclass
import hashlib
import io
import json
import re
import tarfile

CHUNK = 64 * 1024
METADATA_MAX = 256 * 1024
MAX_INPUT = 5 * 1024**3


@dataclass(frozen=True)
class Member:
    name: str
    size: int
    sha256: str
    inline: bytes | None = None


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def members(manifest_raw, config_raw, *, expected_manifest, image_name=None):
    """Build descriptors from small pinned metadata; never open a layer body."""
    import image_plan
    if any(type(raw) is not bytes or len(raw) > METADATA_MAX for raw in (manifest_raw, config_raw)):
        raise ValueError('OCI_METADATA_INVALID')
    image = image_plan.metadata(manifest_raw, config_raw, expected_sha=expected_manifest)
    manifest = json.loads(manifest_raw)
    annotations = {'org.opencontainers.image.ref.name': 'local-copilot/cuda-base:' + expected_manifest[:16]}
    if image_name is not None:
        if image_name != 'docker.io/nvidia/cuda@sha256:' + expected_manifest:
            raise ValueError('OCI_IMAGE_NAME_INVALID')
        annotations = {'io.containerd.image.name': image_name, 'org.opencontainers.image.ref.name': image_name}
    index = _json({'schemaVersion': 2, 'manifests': [{
        'mediaType': manifest['mediaType'], 'digest': 'sha256:' + expected_manifest,
        'size': len(manifest_raw), 'platform': {'os': 'linux', 'architecture': 'amd64'},
        'annotations': annotations}]})
    def inline(name, body):
        return Member(name, len(body), hashlib.sha256(body).hexdigest(), body)
    result = [inline('oci-layout', _json({'imageLayoutVersion': '1.0.0'})),
              inline('index.json', index),
              inline('blobs/sha256/' + expected_manifest, manifest_raw),
              Member('blobs/sha256/' + image['configDigest'][7:], image['configBytes'], image['configDigest'][7:])]
    result.extend(Member('blobs/sha256/' + row['digest'][7:], row['bytes'], row['digest'][7:])
                  for row in image['layers'])
    validate(result)
    return tuple(result)


def validate(rows):
    if not 5 <= len(rows) <= 68 or len({r.name for r in rows}) != len(rows):
        raise ValueError('OCI_MEMBER_SET_INVALID')
    if rows[0].name != 'oci-layout' or rows[1].name != 'index.json':
        raise ValueError('OCI_MEMBER_SET_INVALID')
    for row in rows:
        if (not (row.name in ('oci-layout', 'index.json') or
                 re.fullmatch(r'blobs/sha256/[0-9a-f]{64}', row.name)) or
                not re.fullmatch('[0-9a-f]{64}', row.sha256) or
                (row.name.startswith('blobs/') and row.name[-64:] != row.sha256) or
                type(row.size) is not int or not 0 < row.size <= MAX_INPUT or
                (row.inline is not None and (type(row.inline) is not bytes or
                 len(row.inline) != row.size or len(row.inline) > METADATA_MAX or
                 hashlib.sha256(row.inline).hexdigest() != row.sha256))):
            raise ValueError('OCI_MEMBER_INVALID')
    if sum(r.size for r in rows) > MAX_INPUT + 3 * METADATA_MAX:
        raise ValueError('OCI_INPUT_LIMIT')


def archive_bytes(rows):
    validate(rows)
    return 1024 + sum(512 + ((r.size + 511) // 512) * 512 for r in rows)


def stream(rows, open_blob, sink, *, guard, maximum_bytes):
    """Stream immutable declared members, including hashes, with no full archive.

    open_blob receives only a validated SHA256. Production must supply a bounded,
    no-reparse, read-only cache adapter and recheck identity afterwards. No live
    adapter is wired here. A hash failure invalidates the entire attempt, even
    though a prefix may already have reached the private daemon.
    """
    expected = archive_bytes(rows)
    if type(maximum_bytes) is not int or maximum_bytes != expected:
        raise ValueError('OCI_OUTPUT_LIMIT')
    written = 0
    def check():
        if guard() is not True:
            raise ValueError('OCI_GUARD_LOST')
    def write(raw):
        nonlocal written
        view = memoryview(raw)
        while view:
            check()
            if written + len(view) > maximum_bytes:
                raise ValueError('OCI_OUTPUT_LIMIT')
            count = sink.write(view)
            if type(count) is not int or not 0 < count <= len(view):
                raise ValueError('OCI_SINK_FAILED')
            written += count
            view = view[count:]
            check()
    for row in rows:
        check()
        header = tarfile.TarInfo(row.name)
        header.size, header.mode, header.mtime = row.size, 0o444, 0
        write(header.tobuf(format=tarfile.USTAR_FORMAT))
        digest, received = hashlib.sha256(), 0
        with (io.BytesIO(row.inline) if row.inline is not None else open_blob(row.sha256)) as source:
            while received < row.size:
                check()
                raw = source.read(min(CHUNK, row.size - received))
                check()
                if type(raw) is not bytes or not 0 < len(raw) <= min(CHUNK, row.size - received):
                    raise ValueError('OCI_BLOB_SIZE_CHANGED')
                received += len(raw)
                digest.update(raw)
                write(raw)
            check()
            if source.read(1) != b'':
                raise ValueError('OCI_BLOB_SIZE_CHANGED')
        if digest.hexdigest() != row.sha256:
            raise ValueError('OCI_BLOB_HASH_CHANGED')
        write(b'\0' * ((-row.size) % 512))
    write(b'\0' * 1024)
    if written != expected:
        raise ValueError('OCI_OUTPUT_SIZE_CHANGED')
    return {'status': 'OCI_ARCHIVE_STREAMED', 'archiveBytes': written,
            'members': len(rows), 'inputBytes': sum(r.size for r in rows),
            'networkRequests': 0, 'extracted': False}
