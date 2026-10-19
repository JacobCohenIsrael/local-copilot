"""Stage a closed ELF runtime from Docker's installed ISO, without execution.

Only named commands and their ELF interpreter/DT_NEEDED closure are copied.
No image, installer, package manager or network API is used.
"""
import hashlib
import json
import os
import shutil
from pathlib import Path, PurePosixPath
import stat
import struct
import uuid

import stage_build_tools as tools

ISO = Path('C:/Program Files/Docker/Docker/resources/docker-desktop.iso')
ROOT = tools.HERE.parents[1] / '.runtime/isolated-runtime'
LIMIT = 256 * 1024**2
COMMANDS = {'dockerd': '/usr/bin/dockerd', 'containerd': '/usr/bin/containerd',
    'containerd-shim-runc-v2': '/usr/bin/containerd-shim-runc-v2', 'runc': '/usr/bin/runc',
    'mkfs.ext4': '/usr/sbin/mkfs.ext4', 'mount': '/usr/bin/mount', 'umount': '/usr/bin/umount'}


class Iso:
    def __init__(self, path):
        tools.plain(Path(path))
        self.file = Path(path).open('rb')
        self.before = os.fstat(self.file.fileno())
        self.metadata_bytes = 0
        pvd = self.read(16 * 2048, 2048)
        if pvd[:7] != b'\x01CD001\x01':
            raise ValueError('RUNTIME_ISO_FORMAT')
        self.root = self.record(pvd[156:156 + pvd[156]])
        self.directories = {}

    def close(self):
        self.file.close()

    def read(self, offset, size, *, body=False):
        if type(size) is not int or not 0 <= size <= 131072 or not 0 <= offset <= self.before.st_size - size:
            raise ValueError('RUNTIME_ISO_READ_LIMIT')
        if not body:
            self.metadata_bytes += size
            if self.metadata_bytes > 16 * 1024**2:
                raise ValueError('RUNTIME_ISO_METADATA_LIMIT')
        self.file.seek(offset)
        raw = self.file.read(size)
        if len(raw) != size:
            raise ValueError('RUNTIME_ISO_CHANGED')
        return raw

    def record(self, raw):
        if len(raw) < 34 or len(raw) != raw[0] or raw[25] & 0x80:
            raise ValueError('RUNTIME_ISO_RECORD')
        extent, size = int.from_bytes(raw[2:6], 'little'), int.from_bytes(raw[10:14], 'little')
        if (raw[2:6] != raw[6:10][::-1] or raw[10:14] != raw[14:18][::-1] or
                extent * 2048 + size > self.before.st_size):
            raise ValueError('RUNTIME_ISO_RECORD')
        length = raw[32]
        name = raw[33:33 + length].decode('ascii').split(';')[0].rstrip('.').lower()
        attrs = raw[33 + length + (length % 2 == 0):]
        mode, link, nm = None, [], None
        while len(attrs) >= 4:
            sig, n = attrs[:2], attrs[2]
            if n < 4 or n > len(attrs):
                raise ValueError('RUNTIME_ROCKRIDGE_RECORD')
            value = attrs[4:n]
            if sig == b'NM':
                if not value or value[0] != 0 or nm is not None:
                    raise ValueError('RUNTIME_ROCKRIDGE_NAME')
                nm = value[1:].decode('utf-8')
            elif sig == b'PX':
                mode = int.from_bytes(value[:4], 'little')
            elif sig == b'SL':
                if not value or value[0] != 0:
                    raise ValueError('RUNTIME_ROCKRIDGE_LINK')
                value = value[1:]
                while value:
                    if len(value) < 2 or value[1] > len(value) - 2:
                        raise ValueError('RUNTIME_ROCKRIDGE_LINK')
                    flags, size_part = value[0], value[1]
                    part = value[2:2 + size_part]
                    value = value[2 + size_part:]
                    if flags == 8:
                        link.append('')
                    elif flags == 4:
                        link.append('..')
                    elif flags == 2:
                        link.append('.')
                    elif flags == 0:
                        link.append(part.decode('utf-8'))
                    else:
                        raise ValueError('RUNTIME_ROCKRIDGE_LINK')
            elif sig == b'CE':
                # Selected short runtime names must not depend on unparsed CE.
                # Most CE records here are irrelevant deep documentation paths.
                pass
            attrs = attrs[n:]
        return {'name': nm if nm is not None else name, 'extent': extent, 'bytes': size,
                'directory': bool(raw[25] & 2), 'link': '/'.join(link) if link else None,
                'mode': mode}

    def entries(self, directory):
        key = (directory['extent'], directory['bytes'])
        if key in self.directories:
            return self.directories[key]
        if not directory['directory'] or directory['bytes'] > 131072:
            raise ValueError('RUNTIME_ISO_DIRECTORY_LIMIT')
        raw = self.read(directory['extent'] * 2048, directory['bytes'])
        rows, offset = {}, 0
        while offset < len(raw):
            size = raw[offset]
            if not size:
                offset = (offset // 2048 + 1) * 2048
                continue
            record = self.record(raw[offset:offset + size])
            offset += size
            if record['name'] in ('\0', '\1'):
                continue
            if record['name'] in rows or '/' in record['name'] or record['name'] in ('.', '..'):
                raise ValueError('RUNTIME_ISO_DUPLICATE_NAME')
            rows[record['name']] = record
        self.directories[key] = rows
        return rows

    def resolve(self, name, *, links=0):
        parts, done, node = list(PurePosixPath(name).parts[1:]), [], self.root
        while parts:
            part = parts.pop(0)
            if part in ('', '.'):
                continue
            if part == '..':
                if not done:
                    raise ValueError('RUNTIME_ISO_LINK_ESCAPE')
                return self.resolve('/' + '/'.join(done[:-1] + parts), links=links)
            node = self.entries(node)[part]
            if node['link'] is not None:
                links += 1
                if links > 16:
                    raise ValueError('RUNTIME_ISO_LINK_LIMIT')
                target = node['link']
                parts = list(PurePosixPath(target).parts[(1 if target.startswith('/') else 0):]) + parts
                if target.startswith('/'):
                    done = []
                parts = done + parts
                done, node = [], self.root
                continue
            done.append(part)
        return node

    def elf(self, row):
        base = row['extent'] * 2048
        head = self.read(base, min(row['bytes'], 64))
        if len(head) < 64 or head[:6] != b'\x7fELF\x02\x01' or int.from_bytes(head[18:20], 'little') != 62:
            raise ValueError('RUNTIME_EXPECTED_AMD64_ELF')
        offset, width, count = struct.unpack_from('<Q', head, 32)[0], struct.unpack_from('<H', head, 54)[0], struct.unpack_from('<H', head, 56)[0]
        if width != 56 or not 1 <= count <= 64 or offset + width * count > row['bytes']:
            raise ValueError('RUNTIME_ELF_HEADERS')
        headers = self.read(base + offset, width * count)
        segments, interpreter, dynamic = [], None, []
        for index in range(count):
            kind, flags, off, vaddr, _, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', headers, index * width)
            if off + filesz > row['bytes']:
                raise ValueError('RUNTIME_ELF_SEGMENT')
            if kind == 1:
                segments.append((vaddr, off, filesz))
            elif kind == 3:
                if filesz > 256:
                    raise ValueError('RUNTIME_ELF_INTERPRETER')
                interpreter = self.read(base + off, filesz).rstrip(b'\0').decode('ascii')
            elif kind == 2:
                if filesz > 65536 or filesz % 16:
                    raise ValueError('RUNTIME_ELF_DYNAMIC_LIMIT')
                raw = self.read(base + off, filesz)
                dynamic = [struct.unpack_from('<qQ', raw, i) for i in range(0, len(raw), 16)]
        needed = [value for tag, value in dynamic if tag == 1]
        strings, stringsize = next((v for t, v in dynamic if t == 5), None), next((v for t, v in dynamic if t == 10), 0)
        names = []
        if needed:
            mapping = [(off + strings - va, n - (strings - va)) for va, off, n in segments if strings is not None and va <= strings < va + n]
            if len(mapping) != 1 or not 0 < stringsize <= min(131072, mapping[0][1]):
                raise ValueError('RUNTIME_ELF_STRING_TABLE')
            table = self.read(base + mapping[0][0], stringsize)
            for at in needed:
                end = table.find(b'\0', at)
                if not 0 <= at < end <= len(table):
                    raise ValueError('RUNTIME_ELF_LIBRARY_NAME')
                name = table[at:end].decode('ascii')
                if '/' in name or name in ('.', '..'):
                    raise ValueError('RUNTIME_ELF_LIBRARY_NAME')
                names.append(name)
        return {'interpreter': interpreter, 'needed': names}

    def unchanged(self):
        after = os.fstat(self.file.fileno())
        if any(getattr(after, key) != getattr(self.before, key)
               for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
            raise ValueError('RUNTIME_ISO_CHANGED')


def closure(iso):
    files, commands, pending, libraries, interpreters = {}, {}, [], {}, set()
    for name, source in COMMANDS.items():
        row = iso.resolve(source)
        files['elf/' + name] = row
        commands[name] = 'elf/' + name
        pending.append(row)
    seen = set()
    while pending:
        row = pending.pop()
        key = (row['extent'], row['bytes'])
        if key in seen:
            continue
        seen.add(key)
        elf = iso.elf(row)
        if elf['interpreter']:
            interpreters.add(elf['interpreter'])
        names = [*elf['needed'], *([PurePosixPath(elf['interpreter']).name] if elf['interpreter'] else [])]
        for name in names:
            if name in libraries:
                continue
            matches = []
            for root in ('/usr/lib/x86_64-linux-gnu', '/usr/lib64', '/usr/lib', '/lib/x86_64-linux-gnu', '/lib64'):
                try:
                    target = iso.resolve(root + '/' + name)
                except KeyError:
                    continue
                if target not in matches:
                    matches.append(target)
            # Different aliases to the same extent are harmless; different
            # versions are ambiguous and require a fresh explicit qualifier.
            distinct = {(r['extent'], r['bytes']) for r in matches}
            if len(distinct) != 1:
                raise ValueError('RUNTIME_LIBRARY_MISSING_OR_AMBIGUOUS:' + name)
            libraries[name] = matches[0]
            files['lib/' + name] = matches[0]
            pending.append(matches[0])
        if len(files) > 96 or sum(r['bytes'] for r in files.values()) > LIMIT:
            raise ValueError('RUNTIME_CLOSURE_LIMIT')
    if len(interpreters) != 1:
        raise ValueError('RUNTIME_INTERPRETER_AMBIGUOUS')
    return files, commands, 'lib/' + PurePosixPath(next(iter(interpreters))).name


def stage():
    tools.plain(ROOT)
    tools.reserve(tools.HERE)
    if shutil.disk_usage(tools.HERE).free < tools.RESERVE_BYTES + LIMIT:
        raise ValueError('RUNTIME_HOST_RESERVE')
    total, entries = 0, 0
    for path in ROOT.rglob('*'):
        tools.plain(path)
        entries += 1
        if path.is_file():
            total += path.stat().st_size
        if entries > 1024 or total + LIMIT > 512 * 1024**2:
            raise ValueError('RUNTIME_RETAINED_STAGING_BUDGET')
    iso = Iso(ISO)
    directory = ROOT / uuid.uuid4().hex
    try:
        selected, commands, loader = closure(iso)
        directory.mkdir(parents=True, exist_ok=False)
        files, identities = {}, {}
        for relative, row in selected.items():
            target = directory / relative
            target.parent.mkdir(exist_ok=True)
            digest, remaining, offset = hashlib.sha256(), row['bytes'], row['extent'] * 2048
            with target.open('xb') as output:
                while remaining:
                    raw = iso.read(offset, min(65536, remaining), body=True)
                    output.write(raw)
                    digest.update(raw)
                    remaining, offset = remaining - len(raw), offset + len(raw)
            info = target.stat()
            files[relative] = {'bytes': row['bytes'], 'sha256': digest.hexdigest()}
            identities[relative] = {'bytes': info.st_size, 'fileId': info.st_ino, 'mtimeNs': info.st_mtime_ns}
        for source, relative in ((tools.HERE / 'runtime_launcher.py', 'launcher.py'),):
            raw = source.read_bytes().replace(b'\r\n', b'\n')
            (directory / relative).write_bytes(raw)
            info = (directory / relative).stat()
            files[relative] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            identities[relative] = {'bytes': info.st_size, 'fileId': info.st_ino, 'mtimeNs': info.st_mtime_ns}
        iso.unchanged()
        for name in commands:
            raw = ('#!/usr/local/bin/python3\nimport os,sys\nos.execv(sys.executable, [sys.executable,"-I","-B",'
                   '"/exec/launcher.py",' + repr(name) + ',*sys.argv[1:]])\n').encode()
            relative = 'bin/' + name
            (directory / 'bin').mkdir(exist_ok=True)
            (directory / relative).write_bytes(raw)
            info = (directory / relative).stat()
            files[relative] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            identities[relative] = {'bytes': info.st_size, 'fileId': info.st_ino, 'mtimeNs': info.st_mtime_ns}
        manifest = {'version': 1, 'status': 'ELF_CLOSURE_STAGED_NOT_EXECUTED', 'files': files,
            'commands': commands, 'loader': loader, 'bytes': sum(r['bytes'] for r in files.values()),
            'staticCommands': [name for name, rel in commands.items() if iso.elf(selected[rel])['interpreter'] is None],
            'source': {'path': str(ISO), 'bytes': iso.before.st_size, 'fileId': iso.before.st_ino,
                       'mtimeNs': iso.before.st_mtime_ns}, 'identities': identities,
            'nativeCompatibilityProven': False, 'networkRequests': 0}
        iso.unchanged()
        tools.base.atomic(directory / 'runtime.json', manifest)
        tools.base.atomic(ROOT / 'candidate.json', {'directory': directory.name, 'manifestSha256': tools.sha(directory / 'runtime.json')})
        return directory, manifest
    finally:
        iso.close()


def review():
    def read(path, limit):
        tools.plain(path)
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('RUNTIME_MANIFEST_BYTE_LIMIT')
        return json.loads(raw)
    pointer = read(ROOT / 'candidate.json', 4096)
    if len(pointer['directory']) != 32 or uuid.UUID(hex=pointer['directory']).hex != pointer['directory']:
        raise ValueError('RUNTIME_DIRECTORY_INVALID')
    directory = ROOT / pointer['directory']
    tools.plain(directory)
    if tools.sha(directory / 'runtime.json') != pointer['manifestSha256']:
        raise ValueError('RUNTIME_MANIFEST_CHANGED')
    manifest = read(directory / 'runtime.json', 65536)
    if set(manifest['files']) != set(manifest['identities']) or len(manifest['files']) > 96:
        raise ValueError('RUNTIME_MANIFEST_COVERAGE')
    for relative, expected in manifest['identities'].items():
        if PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts or '\\' in relative:
            raise ValueError('RUNTIME_MANIFEST_PATH')
        path = directory / relative
        tools.plain(path)
        actual = path.stat()
        if {'bytes': actual.st_size, 'fileId': actual.st_ino, 'mtimeNs': actual.st_mtime_ns} != expected:
            raise ValueError('RUNTIME_STAGE_METADATA_CHANGED')
    if manifest['status'] != 'ELF_CLOSURE_STAGED_NOT_EXECUTED' or manifest['bytes'] > LIMIT:
        raise ValueError('RUNTIME_NOT_QUALIFIED_OFFLINE')
    actual_files = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if actual_files != {*manifest['files'], 'runtime.json'}:
        raise ValueError('RUNTIME_STAGE_EXTRA_FILES')
    return directory, manifest, pointer['manifestSha256']
