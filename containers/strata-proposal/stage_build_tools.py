"""Stage pinned Linux tool bytes only. Never install or execute downloaded code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

from build_guard import base

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / '.runtime/build-tools'
DOWNLOAD_LIMIT = 64 * 1024 * 1024
EXPANDED_LIMIT = 256 * 1024 * 1024
FILE_LIMIT = 10000
FILE_BYTES = 64 * 1024 * 1024
RESERVE_BYTES = 20 * 1024**3
ROOT_BYTES_LIMIT = 512 * 1024**2


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def plain(path):
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('Tool paths must not contain links')
    if path.exists() and path.is_file() and path.stat().st_nlink != 1:
        raise ValueError('Tool files must not have hard links')


def reserve(path):
    if shutil.disk_usage(path).free < RESERVE_BYTES:
        raise ValueError('Host staging disk reserve below 20 GiB')


def root_usage():
    total = 0
    for count, path in enumerate(ROOT.rglob('*'), 1):
        if count > 25000:
            raise ValueError('Combined tool staging entry budget exceeded')
        plain(path)
        if path.is_file():
            total += path.stat().st_size
            if total > ROOT_BYTES_LIMIT:
                raise ValueError('Combined tool staging byte budget exceeded')
    return total


def lock():
    raw = (HERE / 'build-tools.lock.json').read_bytes().replace(b'\r\n', b'\n')
    data = json.loads(raw)
    tools = data['tools']
    if data['version'] != 1 or [(t['name'], t['version']) for t in tools] != [('cmake', '4.4.3'), ('ninja', '1.13.2')]:
        raise ValueError('Unexpected compiler-tool lock')
    for item in tools:
        url = urllib.parse.urlsplit(item['url'])
        if (url.scheme != 'https' or url.netloc != 'files.pythonhosted.org' or url.query or url.fragment or
                not url.path.startswith('/packages/') or url.path.rsplit('/', 1)[-1] != item['filename'] or
                not re.fullmatch(r'[A-Za-z0-9_.-]+\.whl', item['filename']) or
                type(item['bytes']) is not int or not 0 < item['bytes'] <= DOWNLOAD_LIMIT or
                not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('Invalid locked artifact')
    if sum(t['bytes'] for t in tools) > DOWNLOAD_LIMIT:
        raise ValueError('Combined tool download limit exceeded')
    return tools, hashlib.sha256(raw).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Compiler-tool downloads do not follow redirects')


def copy_payload(response, output, item, *, clock=time.monotonic):
    """Bound accepted body bytes; transport/TLS overhead is not counted."""
    started = clock()
    total = 0
    digest = hashlib.sha256()
    while True:
        if clock() - started > 120:
            raise TimeoutError('Tool payload deadline exceeded')
        read = getattr(response, 'read1', response.read)
        chunk = read(min(65536, item['bytes'] - total + 1))
        if clock() - started > 120:
            raise TimeoutError('Tool payload deadline exceeded')
        if not chunk:
            break
        total += len(chunk)
        if total > item['bytes'] or total > DOWNLOAD_LIMIT:
            raise ValueError('Tool payload exceeds locked byte count')
        output.write(chunk)
        digest.update(chunk)
    if total != item['bytes'] or digest.hexdigest() != item['sha256']:
        raise ValueError('Tool payload size/hash mismatch')


def download(item, target):
    plain(target)
    if target.exists():
        if target.stat().st_size != item['bytes'] or sha(target) != item['sha256']:
            raise ValueError('Cached tool changed; refusing reuse or overwrite')
        return
    reserve(target.parent)
    partial = target.with_suffix('.part')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(item['url'], timeout=5) as response, partial.open('xb') as output:
        if int(response.headers.get('Content-Length', '-1')) != item['bytes']:
            raise ValueError('Tool Content-Length differs from lock')
        copy_payload(response, output, item)
    reserve(target.parent)
    partial.rename(target)


def unpack(archives, destination, *, expanded_limit=EXPANDED_LIMIT):
    """Validate every archive path before creating the destination tree."""
    if destination.exists():
        raise ValueError('Tool staging never overwrites an existing tree')
    selected, seen, mapped = [], set(), set()
    total = count = 0
    for name, archive in archives:
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                count += 1
                parts = PurePosixPath(member.filename).parts
                mode = member.external_attr >> 16
                if (count > FILE_LIMIT or not parts or PurePosixPath(member.filename).is_absolute() or
                        any(p in ('.', '..') or ':' in p or '\\' in p or p.endswith((' ', '.')) for p in parts) or
                        stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ValueError('Unsafe or oversized tool archive')
                for part in parts:
                    if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
                        raise ValueError('Reserved tool path')
                key = (name, member.filename.casefold())
                if key in seen:
                    raise ValueError('Duplicate/case-aliased tool archive path')
                seen.add(key)
                if member.is_dir():
                    continue
                total += member.file_size
                if member.file_size > FILE_BYTES or total > expanded_limit:
                    raise ValueError('Expanded tool budget exceeded')
                if parts[:2] == (name, 'data'):
                    relative = Path(name, *parts[2:])
                elif name == 'ninja' and member.filename == 'ninja-1.13.2.data/scripts/ninja':
                    relative = Path('ninja/bin/ninja')
                elif parts[0].endswith('.dist-info') and 'licenses' in parts[1:]:
                    relative = Path('licenses', name, *parts[1:])
                else:
                    continue  # Never install/import package wrappers or metadata.
                if relative.as_posix().casefold() in mapped:
                    raise ValueError('Aliased tool destination')
                mapped.add(relative.as_posix().casefold())
                selected.append((archive, member.filename, relative, member.file_size))
    destination.mkdir(parents=True)
    records = []
    for archive, member, relative, size in selected:
        reserve(destination)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as source, source.open(member) as data, target.open('xb') as output:
            copied = 0
            while chunk := data.read(min(65536, size - copied + 1)):
                copied += len(chunk)
                if copied > size:
                    raise ValueError('Tool member exceeds declared size')
                output.write(chunk)
            if copied != size:
                raise ValueError('Short tool member')
        records.append({'path': relative.as_posix(), 'bytes': size, 'sha256': sha(target)})
    for name in ('cmake', 'ninja'):
        binary = destination / name / 'bin' / name
        with binary.open('rb') as stream:
            header = stream.read(20)
        if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
            raise ValueError('Expected Linux x86-64 ELF tool')
    return records


def _stage_locked(fetch=False):
    plain(ROOT)
    tools, lock_sha = lock()
    # Reserve worst-case new files/receipt before writing. Count failed sessions
    # too, so repeated attempts cannot grow this namespace without a bound.
    if root_usage() + DOWNLOAD_LIMIT + EXPANDED_LIMIT + 2 * 1024**2 > ROOT_BYTES_LIMIT:
        raise ValueError('Combined staging budget cannot cover another attempt; preserve/review existing sessions')
    downloads = ROOT / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    reserve(downloads)
    archives = []
    for item in tools:
        path = downloads / item['filename']
        if fetch:
            download(item, path)
        plain(path)
        if not path.is_file() or path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('Verified tool archive missing; --download-tools stages bytes only')
        archives.append((item['name'], path))
    session = ROOT / uuid.uuid4().hex
    records = unpack(archives, session / 'tools')
    receipt = {'version': 1, 'status': 'staged-not-executed', 'lockSha256': lock_sha,
               'archives': tools, 'files': records, 'expandedBytes': sum(r['bytes'] for r in records),
               'lockedDownloadBytes': sum(t['bytes'] for t in tools),
               'buildEnabled': False, 'modelLaunchEnabled': False, 'toolsExecuted': False}
    encoded = json.dumps(receipt, indent=2).encode('utf-8')
    if len(encoded) > 2 * 1024**2:
        raise ValueError('Tool receipt exceeds reserved metadata budget')
    (session / 'tools.json').write_bytes(encoded)
    print(json.dumps({'directory': str(session), 'files': len(records),
        'expandedBytes': receipt['expandedBytes'], 'lockedDownloadBytes': receipt['lockedDownloadBytes'],
        'toolsExecuted': False, 'buildEnabled': False}))
    return session


def stage(fetch=False):
    plain(ROOT)
    with base.lock(ROOT / 'control'):
        return _stage_locked(fetch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-tools', action='store_true')
    stage(parser.parse_args().download_tools)
