"""Stage pinned Alpine C++ libraries as files only; never install APK packages."""
import argparse
import hashlib
import json
import tarfile
import urllib.request

import stage_opencode as stage
import task_bundle

ROOT = stage.ROOT / 'alpine-runtime'
PACKAGES = (
    ('libstdc++-15.2.0-r5.apk', '14c987b556f5385a5db18376e788c75f37d85321b8dc1920d926ea7daac1d6f6',
     'usr/lib/libstdc++.so.6.0.34', 'libstdc++.so.6'),
    ('libgcc-15.2.0-r5.apk', '393dcd32629f06d7d85409c272d142d0c082772d10b87ef55ee82f47de3be637',
     'usr/lib/libgcc_s.so.1', 'libgcc_s.so.1'),
)


def prepare(download=False):
    ROOT.mkdir(parents=True, exist_ok=True)
    task_bundle.plain(ROOT, directory=True)
    target = ROOT / 'staged'
    target.mkdir(exist_ok=True)
    task_bundle.plain(target, directory=True)
    records = []
    for filename, expected, member_name, output_name in PACKAGES:
        path = ROOT / filename
        url = 'https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/' + filename
        if download and not path.exists():
            with urllib.request.build_opener(stage.NoRedirect()).open(url, timeout=10) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('RUNTIME_DOWNLOAD_BUDGET_OR_HASH')
            with path.open('xb') as output:
                output.write(data)
        task_bundle.plain(path)
        if path.stat().st_size > 4 * 1024 * 1024 or stage.sha(path) != expected:
            raise ValueError('RUNTIME_PACKAGE_HASH')
        library = None
        # APK v2 contains concatenated tar streams. Ignore zero blocks, but
        # never extract member paths, symlinks, install scripts or metadata.
        with tarfile.open(path, 'r:gz', ignore_zeros=True) as archive:
            for index, member in enumerate(archive):
                if index > 64:
                    raise ValueError('RUNTIME_MEMBER_BUDGET')
                if member.name == member_name:
                    if library is not None or not member.isreg() or not 0 < member.size <= 4 * 1024 * 1024:
                        raise ValueError('RUNTIME_LIBRARY_SHAPE')
                    library = archive.extractfile(member).read(member.size)
                    if len(library) != member.size or not library.startswith(b'\x7fELF\x02\x01'):
                        raise ValueError('RUNTIME_LIBRARY_ELF')
        if library is None:
            raise ValueError('RUNTIME_LIBRARY_MISSING')
        destination = target / output_name
        digest = hashlib.sha256(library).hexdigest()
        if destination.exists():
            task_bundle.plain(destination)
            if stage.sha(destination) != digest:
                raise ValueError('STAGED_RUNTIME_CHANGED')
        else:
            with destination.open('xb') as output:
                output.write(library)
        records.append({'url': url, 'packageSha256': expected, 'library': output_name,
                        'librarySha256': digest, 'libraryBytes': len(library)})
    manifest = {'libraries': records, 'installed': False, 'executed': False,
                'signatureVerified': False,
                'origin': 'Official Alpine HTTPS downloads, SHA256 pinned after initial inspection'}
    (ROOT / 'runtime.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return target, manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    target, result = prepare(args.download)
    print(json.dumps({'directory': str(target), **result}, indent=2))
