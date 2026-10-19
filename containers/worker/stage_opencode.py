"""Fetch/check one pinned Linux OpenCode package. Never install or execute it."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile
import time
import urllib.request
import uuid

import task_bundle

VERSION = '2.0.26'
PACKAGE = '@opencode/cli-linux-x64-baseline-musl'
METADATA = 'https://registry.npmjs.org/@opencode%2fcli-linux-x64-baseline-musl/' + VERSION
ARCHIVE = 'https://registry.npmjs.org/@opencode/cli-linux-x64-baseline-musl/-/cli-linux-x64-baseline-musl-' + VERSION + '.tgz'
INTEGRITY = 'sha512-Ywps7R3LgAUtJfyb15FVPUoLy9Q3Tt8b0DT2VmUjF1yKLwUM67Qu6l6qUNu+emXeVw2NHPMnnrLC2kOsqwt61g=='
ROOT = Path(__file__).resolve().parents[2] / '.runtime' / 'opencode-linux'
MAX_ARCHIVE = 96 * 1024 * 1024
MAX_EXPANDED = 224 * 1024 * 1024


def sha(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('DOWNLOAD_REDIRECT_DENIED')


def fetch(url, target, maximum):
    if url not in (METADATA, ARCHIVE):
        raise ValueError('FIXED_URL_REQUIRED')
    if target.exists():
        task_bundle.plain(target)
        if target.stat().st_size > maximum:
            raise ValueError('CACHED_DOWNLOAD_TOO_LARGE')
        return
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
    started = time.monotonic()
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(url, timeout=10) as response, temporary.open('xb') as stream:
        size = 0
        while chunk := response.read(65536):
            size += len(chunk)
            if size > maximum or time.monotonic() - started > 120:
                raise ValueError('DOWNLOAD_BUDGET')
            stream.write(chunk)
    temporary.rename(target)


def verify_archive(path):
    task_bundle.plain(path)
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('ARCHIVE_TOO_LARGE')
    expected = base64.b64decode(INTEGRITY.split('-', 1)[1], validate=True).hex()
    if sha(path, 'sha512') != expected:
        raise ValueError('PUBLISHED_SHA512_MISMATCH')


def unpack(archive, target):
    """Copy only two exact regular files; never use tar path extraction."""
    if target.exists():
        raise ValueError('NO_OVERWRITE')
    allowed = {'package/package.json': 'package.json', 'package/bin/opencode': 'staged/opencode'}
    seen, total = set(), 0
    with tarfile.open(archive, 'r|gz') as source:
        for index, member in enumerate(source):
            if index >= 8 or member.name in seen:
                raise ValueError('ARCHIVE_MEMBER_BUDGET_OR_DUPLICATE')
            seen.add(member.name)
            if member.isdir() and member.name in ('package', 'package/bin'):
                continue
            if member.name not in allowed or not member.isreg():
                raise ValueError('UNEXPECTED_OR_LINKED_MEMBER')
            total += member.size
            if (member.size < 0 or total > MAX_EXPANDED or
                    (member.name.endswith('.json') and member.size > 65536)):
                raise ValueError('EXPANDED_BUDGET')
            destination = target / allowed[member.name]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as data, destination.open('xb') as output:
                remaining = member.size
                while remaining:
                    chunk = data.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError('TRUNCATED_MEMBER')
                    output.write(chunk)
                    remaining -= len(chunk)
    if not set(allowed).issubset(seen):
        raise ValueError('MISSING_PACKAGE_FILES')
    package = json.loads((target / 'package.json').read_bytes())
    if (package.get('name') != PACKAGE or package.get('version') != VERSION or
            package.get('os') != ['linux'] or package.get('cpu') != ['x64']):
        raise ValueError('PACKAGE_IDENTITY_MISMATCH')
    binary = target / 'staged/opencode'
    with binary.open('rb') as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
        raise ValueError('NOT_LINUX_X64_ELF')
    return {'binarySha256': sha(binary), 'binaryBytes': binary.stat().st_size,
            'packageSha256': sha(target / 'package.json')}


def stage(download=False):
    ROOT.mkdir(parents=True, exist_ok=True)
    task_bundle.plain(ROOT, directory=True)
    metadata = ROOT / 'metadata-musl.json'
    archive = ROOT / ('opencode-musl-' + VERSION + '.tgz')
    if download:
        fetch(METADATA, metadata, 65536)
        fetch(ARCHIVE, archive, MAX_ARCHIVE)
    data = task_bundle.read_json(metadata)
    if (data.get('name') != PACKAGE or data.get('version') != VERSION or
            data.get('dist', {}).get('integrity') != INTEGRITY or
            data.get('dist', {}).get('tarball') != ARCHIVE):
        raise ValueError('REGISTRY_METADATA_MISMATCH')
    verify_archive(archive)
    target = ROOT / (VERSION + '-musl-' + uuid.uuid4().hex[:8])
    record = unpack(archive, target)
    manifest = {'version': 1, 'package': PACKAGE, 'packageVersion': VERSION,
                'registryMetadata': METADATA, 'archiveUrl': ARCHIVE,
                'publishedIntegrity': INTEGRITY, 'archiveSha256': sha(archive),
                'archiveBytes': archive.stat().st_size, **record,
                'artifactDirectory': str(target), 'executed': False,
                'modelEnabled': False, 'sourceSignatureVerified': False,
                'verification': 'TLS registry metadata plus pinned published SHA512; no signature verification'}
    (target / 'artifact.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    print(json.dumps(stage(args.download), indent=2))
