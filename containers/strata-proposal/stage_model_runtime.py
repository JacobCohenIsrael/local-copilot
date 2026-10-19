"""Stage hash-pinned portable Python and API wheels; never execute staged code."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tarfile
import time
import urllib.request
import zipfile

import stage_build_tools as tools

ROOT = tools.HERE.parents[1] / '.runtime/model-runtime-inputs'
PACKAGES = {'jinja2': '3.1.6', 'markupsafe': '3.0.3', 'regex': '2026.9.10'}


def metadata():
    rows = json.loads((tools.HERE.parent / 'model-runtime/runtime-dependencies.lock.json').read_text())
    if len(rows)!=4:raise ValueError('RUNTIME_DEPENDENCY_SET')
    for row in rows:
        if (safe(row['name'])!=row['name'] or '/' in row['name'] or
                not re.fullmatch('[0-9a-f]{64}',row['sha256']) or
                type(row['bytes']) is not int or not 0<row['bytes']<=40*1024**2 or
                not row['url'].startswith(('https://github.com/astral-sh/python-build-standalone/releases/download/',
                                          'https://files.pythonhosted.org/packages/'))):
            raise ValueError('RUNTIME_DEPENDENCY_LOCK')
    if sum(r['bytes'] for r in rows) > 48 * 1024**2: raise ValueError('RUNTIME_DOWNLOAD_BUDGET')
    target = ROOT / 'downloads.lock.json'
    ROOT.mkdir(exist_ok=True)
    if target.exists():
        if json.loads(target.read_text())!=rows:raise ValueError('RUNTIME_DOWNLOAD_LOCK_CHANGED')
    else:
        with target.open('x', encoding='utf-8') as out: json.dump(rows, out, indent=2)
    return rows


def safe(name):
    path = PurePosixPath(name)
    if (path.is_absolute() or not path.parts or '\\' in name or
            any(p in ('.', '..') or ':' in p or p.endswith((' ', '.')) or
                p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
                for p in path.parts)):
        raise ValueError('RUNTIME_ARCHIVE_PATH')
    return path.as_posix()


def fetch(row):
    cache = ROOT / 'downloads'; cache.mkdir(exist_ok=True)
    target = cache / row['name']; tools.plain(target)
    if target.exists():
        if target.stat().st_size != row['bytes'] or tools.sha(target) != row['sha256']:
            raise ValueError('RUNTIME_CACHED_DOWNLOAD_CHANGED')
        return target
    partial = target.with_suffix(target.suffix + '.part'); started = time.monotonic()
    with urllib.request.urlopen(row['url'], timeout=15) as response, partial.open('xb') as output:
        count = 0
        while chunk := response.read(65536):
            count += len(chunk)
            if count > row['bytes'] or time.monotonic() - started > 90:
                raise ValueError('RUNTIME_DOWNLOAD_LIMIT')
            output.write(chunk)
    if partial.stat().st_size != row['bytes'] or tools.sha(partial) != row['sha256']:
        raise ValueError('RUNTIME_DOWNLOAD_HASH')
    partial.rename(target)
    return target


def extract_python(archive, destination):
    """Flatten only in-archive file links; never create Windows symlinks."""
    with tarfile.open(archive, 'r:gz') as source:
        members = {}; folded = set(); total = 0
        for item in source:
            name = safe(item.name)
            if not name.startswith('python/') and name != 'python': raise ValueError('RUNTIME_PYTHON_PREFIX')
            # Non-interactive API execution does not use terminal descriptions;
            # the official archive contains case-distinct terminal names that
            # cannot coexist on this Windows volume. Omit that data subtree.
            if name == 'python/share/terminfo' or name.startswith('python/share/terminfo/'): continue
            if name.casefold() in folded or len(members) >= 12000: raise ValueError('RUNTIME_ARCHIVE_COLLISION')
            folded.add(name.casefold()); members[name] = item
            if not (item.isfile() or item.isdir() or item.issym() or item.islnk()): raise ValueError('RUNTIME_ARCHIVE_TYPE')
            total += item.size
            if item.size > 64*1024**2 or total > 256*1024**2: raise ValueError('RUNTIME_EXPANSION_LIMIT')
        resolved = {}
        for name,item in members.items():
            if item.isdir(): continue
            actual = item; seen = {name}
            while actual.issym() or actual.islnk():
                target = safe(posixpath.normpath(posixpath.join(posixpath.dirname(actual.name),actual.linkname))
                              if actual.issym() else actual.linkname)
                if target in seen or target not in members or len(seen)>8: raise ValueError('RUNTIME_LINK_ESCAPE')
                seen.add(target); actual=members[target]
            if not actual.isfile(): raise ValueError('RUNTIME_LINK_NOT_FILE')
            resolved[name] = actual
        if sum(item.size for item in resolved.values()) > 384*1024**2: raise ValueError('RUNTIME_FLATTENED_LIMIT')
        destination.mkdir()
        for name,item in resolved.items():
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
            with source.extractfile(item) as data,target.open('xb') as output:shutil.copyfileobj(data,output,65536)


def extract_wheels(archives, destination):
    destination.mkdir(); seen=set(); total=0
    for archive in archives:
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                name=safe(item.filename)
                if item.is_dir():continue
                if name.casefold() in seen or len(seen)>=6000:raise ValueError('RUNTIME_WHEEL_COLLISION')
                seen.add(name.casefold());total+=item.file_size
                if item.file_size>16*1024**2 or total>32*1024**2 or (item.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('RUNTIME_WHEEL_LIMIT')
                target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
                with source.open(item) as data,target.open('xb') as output:shutil.copyfileobj(data,output,65536)


def stage():
    rows=metadata()
    archives=[fetch(row) for row in rows]
    destination=ROOT/'bundle'
    if destination.exists():raise ValueError('RUNTIME_BUNDLE_ALREADY_EXISTS')
    extract_python(archives[0],destination)
    extract_wheels(archives[1:],destination/'site')
    files={p.relative_to(destination).as_posix():{'bytes':p.stat().st_size,'sha256':tools.sha(p)}
           for p in sorted(destination.rglob('*')) if p.is_file()}
    result={'status':'STAGED_NOT_EXECUTED','directory':str(destination),'downloads':rows,'files':files,
            'omittedDataSubtree':'python/share/terminfo (case aliases, unused by non-interactive API)',
            'linuxCodeExecuted':False,'containerStarted':False,'modelStarted':False}
    with (ROOT/'bundle-receipt.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    return {'status':result['status'],'files':len(files),'bytes':sum(p['bytes'] for p in files.values())}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['metadata','stage'])
    args=parser.parse_args();print(json.dumps(metadata() if args.command=='metadata' else stage(),indent=2))
