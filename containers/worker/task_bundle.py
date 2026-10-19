"""Offline intake/patch boundary. No subprocess, Docker, HTTP, or model calls."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

ROOT = Path(__file__).resolve().parents[2] / '.runtime' / 'worker-bundles'
MAX_FILES = 8
MAX_FILE_BYTES = 65536
MAX_TOTAL_BYTES = 131072
MAX_PATCH_BYTES = 65536
MAX_TASK_CHARS = 4000
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)


def safe_path(name):
    if not isinstance(name, str) or not name or len(name) > 200:
        raise ValueError('INVALID_PATH')
    parts = name.split('/')
    if any(not p or p in ('.', '..') or p.endswith((' ', '.')) or
           any(ord(c) < 32 or c in '<>:"\\|?*' for c in p) or
           RESERVED.match(p) or p.lower() in ('.git', '.agents', '.codex')
           for p in parts):
        raise ValueError('INVALID_PATH')
    return PurePosixPath(name)


def plain(path, directory=False):
    """Reject links/junctions in every existing ancestor, including on Windows."""
    path = Path(path).absolute()
    for node in reversed((path, *path.parents)):
        info = node.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('LINK_OR_REPARSE_POINT')
        if node != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError('INVALID_ANCESTOR')
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('NOT_DIRECTORY')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('NOT_SINGLE_LINK_FILE')
    return path


def bounded_read(path, maximum=MAX_FILE_BYTES):
    plain(path)
    with Path(path).open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('FILE_BUDGET_EXCEEDED')
    return data


def text_file(data):
    text = data.decode('utf-8')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
        raise ValueError('TEXT_FILES_ONLY')
    return text


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(bounded_read(path, MAX_TOTAL_BYTES).decode('utf-8'))


def prepare(request):
    if not isinstance(request, dict) or set(request) != {'sourceRoot', 'files', 'task'}:
        raise ValueError('INVALID_REQUEST_FIELDS')
    if not isinstance(request['sourceRoot'], str) or not Path(request['sourceRoot']).is_absolute():
        raise ValueError('ABSOLUTE_SOURCE_ROOT_REQUIRED')
    source = plain(request['sourceRoot'], directory=True)
    task = request['task']
    files = request['files']
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS:
        raise ValueError('TASK_BUDGET_EXCEEDED')
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError('FILE_COUNT_EXCEEDED')
    names = [str(safe_path(name)) for name in files]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('DUPLICATE_PATH')
    # Validate and bound all input before creating a session.
    content = {name: bounded_read(source / name) for name in names}
    if sum(map(len, content.values())) > MAX_TOTAL_BYTES:
        raise ValueError('TOTAL_BUDGET_EXCEEDED')
    for data in content.values():
        text_file(data)
    ROOT.mkdir(parents=True, exist_ok=True)
    plain(ROOT, directory=True)
    session = ROOT / uuid.uuid4().hex
    session.mkdir()
    manifest = {'version': 1, 'mode': 'offline-only', 'runId': session.name,
                'task': task, 'files': {name: digest(data) for name, data in content.items()},
                'limits': {'files': MAX_FILES, 'fileBytes': MAX_FILE_BYTES,
                           'totalBytes': MAX_TOTAL_BYTES, 'patchBytes': MAX_PATCH_BYTES,
                           'taskCharacters': MAX_TASK_CHARS},
                'modelEnabled': False, 'executionEnabled': False}
    for area in ('baseline', 'workspace'):
        for name, data in content.items():
            target = session / area / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    (session / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'status': 'PREPARED_OFFLINE', 'runId': session.name,
            'workspace': str(session / 'workspace'), 'fileCount': len(content),
            'inputBytes': sum(map(len, content.values())), 'modelEnabled': False,
            'executionEnabled': False}


def collect(run_id):
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('INVALID_RUN_ID')
    session = plain(ROOT / run_id, directory=True)
    manifest = read_json(session / 'manifest.json')
    files = manifest['files']
    if (manifest.get('version') != 1 or manifest.get('runId') != run_id or
            manifest.get('mode') != 'offline-only' or
            manifest.get('modelEnabled') is not False or
            manifest.get('executionEnabled') is not False or
            not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES):
        raise ValueError('INVALID_MANIFEST')
    names = [str(safe_path(name)) for name in files]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('INVALID_MANIFEST')
    workspace = plain(session / 'workspace', directory=True)
    # Traverse only expected directories; stop at the first unexpected entry.
    expected_dirs = {str(parent) for name in names for parent in PurePosixPath(name).parents
                     if str(parent) != '.'}
    pending = [workspace]
    while pending:
        folder = pending.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                node = Path(entry.path)
                relative = node.relative_to(workspace).as_posix()
                if relative in expected_dirs:
                    plain(node, directory=True)
                    pending.append(node)
                elif relative in files:
                    plain(node)
                else:
                    raise ValueError('UNEXPECTED_OUTPUT_PATH')
    patches, changed = [], []
    total = patch_bytes = 0
    for name in names:
        before = bounded_read(session / 'baseline' / name)
        if digest(before) != files[name]:
            raise ValueError('BASELINE_CHANGED')
        target = workspace / name
        # Missing approved files represent deletion. A broken link is rejected above.
        after = bounded_read(target) if target.exists() else b''
        total += len(after)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('TOTAL_BUDGET_EXCEEDED')
        old, new = text_file(before), text_file(after)
        if before == after and target.exists():
            continue
        changed.append(name)
        quote = lambda path: json.dumps(path, ensure_ascii=False)
        header = 'diff --git ' + quote('a/' + name) + ' ' + quote('b/' + name) + '\n'
        if not target.exists():
            header += 'deleted file mode 100644\n'
        patch_bytes += len(header.encode('utf-8'))
        patches.append(header)
        # Preserve the unified-diff marker for lines lacking a final newline.
        for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                         fromfile=quote('a/' + name),
                                         tofile=quote('b/' + name) if target.exists() else '/dev/null'):
            if not line.endswith('\n'):
                line += '\n\\ No newline at end of file\n'
            patch_bytes += len(line.encode('utf-8'))
            if patch_bytes > MAX_PATCH_BYTES:
                raise ValueError('PATCH_BUDGET_EXCEEDED')
            patches.append(line)
        if patch_bytes > MAX_PATCH_BYTES:
            raise ValueError('PATCH_BUDGET_EXCEEDED')
    return {'status': 'PATCH_FOR_REVIEW', 'mode': 'offline-only', 'runId': run_id,
            'codingPerformed': False, 'changedFiles': changed, 'outputBytes': total,
            'patchBytes': patch_bytes, 'patch': ''.join(patches), 'applied': False,
            'modelEnabled': False, 'executionEnabled': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare').add_argument('--request', required=True)
    sub.add_parser('collect').add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        result = prepare(read_json(args.request)) if args.command == 'prepare' else collect(args.run_id)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'REJECTED', 'error': str(error), 'applied': False,
                          'modelEnabled': False, 'executionEnabled': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
