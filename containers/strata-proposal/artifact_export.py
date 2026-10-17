"""Bounded output collection, with no container/model start authority or CLI.

A future admitted controller must supply a transport whose verify() checks its
pinned container, isolation, waiting state and active safety lease. Safety stops
always take priority over preserving output. Header checks never execute ELF.
"""
import hashlib
import os
from pathlib import Path
import re
import struct
import subprocess
import tarfile
import threading
import time
import uuid

import build_guard
import stage_build_tools as tools

ROOT = build_guard.base.ROOT / '.runtime/build-artifacts'
LIMITS = {'strata': 256 * 1024**2, 'libstrata_kq.so': 128 * 1024**2, 'BUILD.json': 16 * 1024}
PAYLOAD_LIMIT = sum(LIMITS.values())
WIRE_LIMIT = PAYLOAD_LIMIT + 64 * 1024
ROOT_LIMIT = 2 * 1024**3
SESSION_RESERVATION = WIRE_LIMIT + PAYLOAD_LIMIT + 16384
EXPORT_SECONDS = 20


def check_deadline(deadline, clock=time.monotonic):
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError('Artifact export deadline exceeded')
    return remaining


def capture_archive(container_id, output, deadline, *, clock=time.monotonic):
    """Run only fixed /bin/tar for the engine directory; bound streamed stdout.

    Killing this Docker client does not prove the container stopped. The future
    independent controller must still stop/confirm its worker on every failure.
    """
    if not re.fullmatch('[0-9a-f]{64}', container_id):
        raise ValueError('A full immutable container ID is required')
    check_deadline(deadline, clock)
    errors, diagnostic = [], bytearray()
    with Path(output).open('xb') as target:
        process = subprocess.Popen([build_guard.base.DOCKER, 'exec', '--user', '65532:65532',
                                    '--workdir', '/work', container_id, '/bin/tar', '-cf', '-', 'engine'],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        def drain():
            total = 0
            try:
                while True:
                    chunk = process.stdout.read1(min(65536, WIRE_LIMIT - total + 1))
                    if not chunk:
                        break
                    if total + len(chunk) > WIRE_LIMIT:
                        raise ValueError('Artifact archive exceeds wire limit')
                    target.write(chunk)
                    total += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            except BaseException as error:
                errors.append(error)
                process.kill()
        def drain_errors():
            try:
                while True:
                    chunk = process.stderr.read1(min(1024, 4096 - len(diagnostic) + 1))
                    if not chunk:
                        break
                    if len(diagnostic) + len(chunk) > 4096:
                        raise ValueError('Docker artifact diagnostic exceeds limit')
                    diagnostic.extend(chunk)
            except BaseException as error:
                errors.append(error)
                process.kill()
        reader = threading.Thread(target=drain, daemon=True)
        diagnostics = threading.Thread(target=drain_errors, daemon=True)
        reader.start()
        diagnostics.start()
        try:
            process.wait(timeout=check_deadline(deadline, clock))
            reader.join(timeout=check_deadline(deadline, clock))
            diagnostics.join(timeout=check_deadline(deadline, clock))
            if reader.is_alive() or diagnostics.is_alive():
                raise TimeoutError('Artifact copy stream did not close')
            if errors:
                raise errors[0]
            if process.returncode:
                raise ValueError('Docker artifact stream failed: ' + diagnostic.decode('utf-8', 'replace')[:4096])
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            reader.join(timeout=1)
            diagnostics.join(timeout=1)
            if reader.is_alive() or diagnostics.is_alive():
                # A host OS write stuck in the kernel is outside Python's deadline
                # guarantee. Keep it explicit; never promote this to successful export.
                raise TimeoutError('Artifact copy cleanup unconfirmed')
            process.stdout.close()
            process.stderr.close()


def acknowledge_export(container_id, deadline):
    """Fixed marker only. Caller must revalidate ownership and safety lease first.

    No shell, arbitrary paths/commands, root exec or model operations. Sending a
    marker is not confirmation of worker exit; the controller must confirm that.
    """
    if not re.fullmatch('[0-9a-f]{64}', container_id):
        raise ValueError('A full immutable container ID is required')
    subprocess.run([build_guard.base.DOCKER, 'exec', '--user', '65532:65532',
                    container_id, '/bin/touch', '/work/export.complete'],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True, timeout=check_deadline(deadline))


def validate_elf(header, name):
    if (len(header) < 64 or header[:7] != b'\x7fELF\x02\x01\x01' or
            struct.unpack_from('<H', header, 18)[0] != 62 or
            struct.unpack_from('<I', header, 20)[0] != 1 or
            struct.unpack_from('<H', header, 52)[0] != 64 or
            struct.unpack_from('<H', header, 16)[0] not in ((2, 3) if name == 'strata' else (3,))):
        raise ValueError('Unexpected ELF64 little-endian x86_64 header')


def unpack_archive(archive, destination, metadata_sha256, deadline, *, clock=time.monotonic):
    """Strict uncompressed tar reader. No extractall, extensions, links or modes.

    Only a root engine/ directory and the three fixed flat regular filenames are
    permitted. PAX/GNU extensions fail closed, before their data is interpreted.
    """
    tools.plain(archive)
    tools.plain(destination)
    if archive.stat().st_size > WIRE_LIMIT or archive.stat().st_size % 512:
        raise ValueError('Artifact archive size/alignment invalid')
    destination.mkdir()  # Must be new; never overwrite an existing output tree.
    rows, seen = [], set()
    total = 0
    with archive.open('rb') as stream:
        def read_exact(count):
            check_deadline(deadline, clock)
            data = stream.read(count)
            check_deadline(deadline, clock)
            if len(data) != count:
                raise ValueError('Truncated artifact archive')
            return data
        while True:
            block = read_exact(512)
            if block == bytes(512):
                if read_exact(512) != bytes(512):
                    raise ValueError('Invalid tar end marker')
                while True:
                    check_deadline(deadline, clock)
                    trailing = stream.read(65536)
                    if not trailing:
                        break
                    if any(trailing):
                        raise ValueError('Nonzero trailing archive data')
                break
            info = tarfile.TarInfo.frombuf(block, 'utf-8', 'strict')
            name = info.name.rstrip('/') if info.isdir() else info.name
            if name in seen or len(seen) >= 4:
                raise ValueError('Duplicate or excessive artifact headers')
            seen.add(name)
            if info.type == tarfile.DIRTYPE and name == 'engine' and info.size == 0 and not info.linkname:
                continue
            if (not name.startswith('engine/') or name[7:] not in LIMITS or
                    info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or info.linkname):
                raise ValueError('Unexpected artifact path or entry type')
            leaf = name[7:]
            if not 0 < info.size <= LIMITS[leaf] or total + info.size > PAYLOAD_LIMIT:
                raise ValueError('Artifact payload budget exceeded')
            tools.reserve(destination)
            digest, header = hashlib.sha256(), b''
            with (destination / leaf).open('xb') as output:
                os.chmod(destination / leaf, 0o600)  # Archive mode is never applied.
                remaining = info.size
                while remaining:
                    data = read_exact(min(65536, remaining))
                    if len(header) < 64:
                        header += data[:64 - len(header)]
                    digest.update(data)
                    output.write(data)
                    remaining -= len(data)
                output.flush()
                os.fsync(output.fileno())
            if any(read_exact((-info.size) % 512)):
                raise ValueError('Nonzero artifact padding')
            sha = digest.hexdigest()
            if leaf == 'BUILD.json':
                if sha != metadata_sha256:
                    raise ValueError('Build metadata differs from pinned input')
            else:
                validate_elf(header, leaf)
            total += info.size
            rows.append({'path': leaf, 'bytes': info.size, 'sha256': sha})
    if not {'engine/strata', 'engine/BUILD.json'} <= seen:
        raise ValueError('Missing required build artifacts')
    return rows


def root_usage():
    total = 0
    for count, path in enumerate(ROOT.rglob('*'), 1):
        if count > 1000:
            raise ValueError('Artifact namespace entry limit exceeded')
        tools.plain(path)
        if path.is_file():
            total += path.stat().st_size
            if total > ROOT_LIMIT:
                raise ValueError('Artifact namespace byte limit exceeded')
    return total


def collect(transport, *, container_id, plan_sha256, metadata_sha256, synthetic,
            deadline=None, clock=time.monotonic):
    """Collect then acknowledge through a controller-owned transport.

    transport.verify() must return True or raise, copy(path, deadline) must use
    bounded capture, acknowledge(deadline) writes only /work/export.complete.
    This function never starts/stops a container. Future controller integration
    must latch FAULT and trigger stopping if it raises, even if output was saved.
    """
    for value in (container_id, plan_sha256, metadata_sha256):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Expected full container/hash identities')
    if type(synthetic) is not bool:
        raise ValueError('Synthetic provenance must be explicit')
    end = min(deadline if deadline is not None else clock() + EXPORT_SECONDS, clock() + EXPORT_SECONDS)
    def verified():
        check_deadline(end, clock)
        if transport.verify() is not True:
            raise ValueError('Artifact target/lease verification failed')
        check_deadline(end, clock)
    tools.plain(ROOT)
    with build_guard.base.lock(ROOT / 'control'):
        if root_usage() + SESSION_RESERVATION > ROOT_LIMIT:
            raise ValueError('Artifact namespace lacks worst-case export capacity')
        tools.reserve(ROOT)
        session = ROOT / uuid.uuid4().hex
        session.mkdir()
        receipt = {'version': 1, 'state': 'EXPORT_PENDING', 'synthetic': synthetic,
                   'containerId': container_id, 'planSha256': plan_sha256,
                   'metadataSha256': metadata_sha256, 'acknowledged': False,
                   'acknowledgementAttempted': False,
                   'buildEnabled': False, 'modelLaunchEnabled': False}
        build_guard.base.atomic(session / 'result.json', receipt)
        try:
            verified()
            transport.copy(session / 'engine.tar', end)
            verified()
            receipt['files'] = unpack_archive(session / 'engine.tar', session / 'files', metadata_sha256, end, clock=clock)
            receipt['state'] = 'ARTIFACTS_SAVED_AWAITING_ACK'
            build_guard.base.atomic(session / 'result.json', receipt)
            verified()
            receipt['acknowledgementAttempted'] = True
            build_guard.base.atomic(session / 'result.json', receipt)
            check_deadline(end, clock)
            transport.acknowledge(end)
            check_deadline(end, clock)
            receipt.update(state='ARTIFACTS_SAVED_ACK_SENT', acknowledged=True)
            build_guard.base.atomic(session / 'result.json', receipt)
            return session, receipt
        except Exception as error:
            receipt.update(state='EXPORT_FAULT', error=type(error).__name__)
            build_guard.base.atomic(session / 'result.json', receipt)
            raise
