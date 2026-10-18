"""Bounded blob acquisition and registry transport; exact approval gates live work.

No image import, container launch, automatic retry, reset or credential-file access.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import image_plan as images
import stage_build_tools as tools

CHUNK = 65536
RECEIPT_BYTES = 128 * 1024
ENTRY_LIMIT = 4096
AUTH_BYTES = images.METADATA_LIMIT
CDN_HOSTS = frozenset({'production.cloudflare.docker.com', 'production.cloudfront.docker.com',
    'docker-images-prod.6aa30f8b08e16409b46e0173d6de2f56.r2.cloudflarestorage.com'})


class StageError(ValueError):
    def __init__(self, code):
        if not re.fullmatch('[A-Z_]{1,80}', code):
            code = 'STAGING_ERROR'
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Blob:
    digest: str
    size: int

    def __post_init__(self):
        if (not isinstance(self.digest, str) or not re.fullmatch('sha256:[0-9a-f]{64}', self.digest) or
                type(self.size) is not int or not 0 < self.size <= 3 * images.GIB):
            raise StageError('BLOB_DESCRIPTOR_INVALID')


@dataclass(frozen=True)
class Limits:
    payload_bytes: int
    namespace_bytes: int
    free_reserve_bytes: int
    session_seconds: float
    blob_seconds: float

    def __post_init__(self):
        if (any(type(n) is not int or n < 0 for n in
                (self.payload_bytes, self.namespace_bytes, self.free_reserve_bytes)) or
                self.payload_bytes <= 0 or self.namespace_bytes < RECEIPT_BYTES or
                any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0
                    for n in (self.session_seconds, self.blob_seconds))):
            raise StageError('STAGING_LIMITS_INVALID')


class Context:
    def __init__(self, limits, guard, clock=time.monotonic):
        self.limits, self.guard, self.clock = limits, guard, clock
        now = clock()
        if not math.isfinite(now):
            raise StageError('CLOCK_INVALID')
        self.last, self.end, self.blob_end = now, now + limits.session_seconds, now + limits.session_seconds
        self.blob_bytes, self.auth_bytes = 0, 0

    def check(self):
        now = self.clock()
        if not math.isfinite(now) or now < self.last:
            raise StageError('CLOCK_INVALID')
        self.last = now
        if now >= min(self.end, self.blob_end):
            raise StageError('STAGING_DEADLINE')
        try:
            allowed = self.guard()
        except StageError:
            raise
        except Exception:
            raise StageError('GUARD_ERROR') from None
        if allowed is not True:
            raise StageError('GUARD_PERMISSION_LOST')
        after = self.clock()
        if not math.isfinite(after) or after < self.last:
            raise StageError('CLOCK_INVALID')
        self.last = after
        if after >= min(self.end, self.blob_end):
            raise StageError('STAGING_DEADLINE')
        return min(self.end, self.blob_end) - after

    def begin_blob(self):
        self.blob_end = self.end
        self.check()
        self.blob_end = min(self.end, self.clock() + self.limits.blob_seconds)

    def charge(self, count, *, auth=False):
        if auth:
            self.auth_bytes += count
        else:
            self.blob_bytes += count
        if self.blob_bytes + self.auth_bytes > self.limits.payload_bytes:
            raise StageError('PAYLOAD_BUDGET_EXCEEDED')


def framing_fields(response):
    """Validate header envelope before reading any decoded response-body bytes."""
    headers = response.getheaders()
    if (len(headers) > 100 or any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers) or
            sum(len(k) + len(v) for k, v in headers) > 8192):
        raise StageError('HTTP_HEADERS_INVALID')
    lengths = [v for k, v in headers if k.lower() == 'content-length']
    transfers = [v.strip().lower() for k, v in headers if k.lower() == 'transfer-encoding']
    encodings = [v.strip().lower() for k, v in headers if k.lower() == 'content-encoding']
    if response.status != 200 or encodings not in ([], ['identity']):
        raise StageError('HTTP_FRAMING_INVALID')
    return lengths, transfers


def declared_length(lengths, maximum):
    if len(lengths) != 1 or not re.fullmatch('[0-9]{1,12}', lengths[0]):
        raise StageError('HTTP_FRAMING_INVALID')
    size = int(lengths[0])
    if not 0 < size <= maximum:
        raise StageError('HTTP_LENGTH_INVALID')
    return size


def response_length(response, maximum):
    # Blobs still require one exact length and no Transfer-Encoding.
    lengths, transfers = framing_fields(response)
    if transfers:
        raise StageError('HTTP_FRAMING_INVALID')
    return declared_length(lengths, maximum)


def auth_response_length(response):
    """Only auth may use HTTP/1.1 chunked with NO Content-Length.

    http.client decodes chunks; the caller bounds retained decoded bytes and
    charges every byte (including one possible overflow-detection byte).
    Close-delimited, compressed, duplicate/conflicting/stacked framing fails.
    """
    lengths, transfers = framing_fields(response)
    if transfers:
        if lengths or transfers != ['chunked'] or getattr(response, 'version', None) != 11:
            raise StageError('HTTP_FRAMING_INVALID')
        return None
    return declared_length(lengths, AUTH_BYTES)


def auth_framing_summary(response):
    """Categorical diagnostics only: no raw headers, URLs, body or bearer token."""
    headers = response.getheaders()
    lengths = [v for k, v in headers[:101] if k.lower() == 'content-length']
    transfers = [v.strip().lower() for k, v in headers[:101] if k.lower() == 'transfer-encoding']
    encodings = [v.strip().lower() for k, v in headers[:101] if k.lower() == 'content-encoding']
    return {'status': response.status if type(response.status) is int else None,
            'httpVersion': getattr(response, 'version', None) if getattr(response, 'version', None) in (10, 11) else None,
            'headerCount': len(headers), 'contentLengthCount': len(lengths),
            'declaredBytes': int(lengths[0]) if len(lengths) == 1 and re.fullmatch('[0-9]{1,12}', lengths[0]) else None,
            'transferEncoding': 'absent' if not transfers else 'chunked' if transfers == ['chunked'] else 'other',
            'contentEncoding': 'absent' if not encodings else 'identity' if encodings == ['identity'] else 'other'}


def read_auth(response, context):
    size = auth_response_length(response)
    maximum = AUTH_BYTES if size is None else size
    payload = bytearray()
    while True:
        chunk = read_chunk(response, min(CHUNK, maximum - len(payload) + 1), context, charge=True)
        if len(payload) + len(chunk) > maximum:
            raise StageError('AUTH_BODY_LIMIT' if size is None else 'AUTH_LENGTH_MISMATCH')
        if not chunk:
            break
        payload.extend(chunk)
    if size is not None and len(payload) != size:
        raise StageError('AUTH_LENGTH_MISMATCH')
    return payload


def read_chunk(body, count, context, *, charge=None):
    context.check()
    try:
        chunk = getattr(body, 'read1', body.read)(count)
    except StageError:
        raise
    except Exception:
        raise StageError('TRANSPORT_READ_FAILED') from None
    if not isinstance(chunk, bytes) or len(chunk) > count:
        raise StageError('TRANSPORT_READ_INVALID')
    if charge is not None:
        context.charge(len(chunk), auth=charge)
    context.check()
    return chunk


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class RegistrySource:
    """Fixed anonymous Docker Hub scope; no bearer tokens or signed URLs logged."""
    def __init__(self, blobs, opener=None, on_auth_headers=None):
        self.allowed = frozenset(blobs)
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.on_auth_headers = on_auth_headers or (lambda summary: None)

    def _get(self, url, context, headers=None):
        remaining = context.check()
        request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity', **(headers or {})})
        return self.opener.open(request, timeout=min(5, remaining))

    def open(self, blob, context):
        if blob not in self.allowed:
            raise StageError('BLOB_NOT_IN_LOCK')
        try:
            auth_url = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:nvidia/cuda:pull'
            with self._get(auth_url, context) as response:
                self.on_auth_headers(auth_framing_summary(response))
                payload = read_auth(response, context)
                token = json.loads(payload)['token']
                if (not isinstance(token, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,16384}', token)):
                    raise StageError('AUTH_RESPONSE_INVALID')
            url = 'https://registry-1.docker.io/v2/nvidia/cuda/blobs/' + blob.digest
            try:
                return self._get(url, context, {'Authorization': 'Bearer ' + token})
            except urllib.error.HTTPError as error:
                try:
                    if error.code != 307:
                        raise StageError('REGISTRY_REQUEST_FAILED') from None
                    location = error.headers.get('Location', '')
                finally:
                    error.close()
                parsed = urllib.parse.urlsplit(location)
                if (len(location) > 16384 or parsed.scheme != 'https' or parsed.hostname not in CDN_HOSTS or
                        parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment or
                        parsed.path != '/registry-v2/docker/registry/v2/blobs/sha256/' +
                            blob.digest[7:9] + '/' + blob.digest[7:] + '/data'):
                    raise StageError('REGISTRY_REDIRECT_REJECTED')
                # Exactly one redirect; anonymous signed CDN request only.
                return self._get(location, context)
        except StageError:
            raise
        except Exception as error:
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            raise StageError('REGISTRY_REQUEST_FAILED') from None


def plain_usage(root):
    count, total = 0, 0
    for path in root.rglob('*'):
        count += 1
        if count > ENTRY_LIMIT:
            raise StageError('NAMESPACE_ENTRY_LIMIT')
        tools.plain(path)
        if path.is_file():
            total += path.stat().st_size
    return count, total


def reserve_disk(path, limits, remaining):
    if shutil.disk_usage(path).free < limits.free_reserve_bytes + remaining:
        raise StageError('DISK_RESERVE_LOW')


def verify_cached(path, blob, context):
    tools.plain(path)
    if not path.is_file() or path.stat().st_size != blob.size:
        raise StageError('CACHE_CHANGED')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := read_chunk(stream, CHUNK, context):
            digest.update(chunk)
    if 'sha256:' + digest.hexdigest() != blob.digest:
        raise StageError('CACHE_CHANGED')


def _stage(root, blobs, identity_sha, source, limits, *, guard, synthetic, clock=time.monotonic):
    """Internal acquisition kernel. Caller owns transport admission and supervision.

    This code cannot make a blocked OS read/fsync obey a Python deadline. A live
    caller still needs independently supervised process lifetime/cancellation.
    """
    root = Path(root).absolute()
    if (type(synthetic) is not bool or not re.fullmatch('[0-9a-f]{64}', identity_sha) or
            not 1 <= len(blobs) <= 65 or len(set(blobs)) != len(blobs) or
            len({b.digest for b in blobs}) != len(blobs) or
            sum(b.size for b in blobs) > limits.payload_bytes):
        raise StageError('STAGING_CONTRACT_INVALID')
    context = Context(limits, guard, clock)
    context.check()
    tools.plain(root)
    with tools.base.lock(root / 'control'):
        state_file = root / 'state.json'
        previous = None
        if state_file.exists():
            previous = json.loads(images.read_metadata(state_file))
            if (previous.get('version') != 1 or previous.get('identitySha256') != identity_sha or
                    previous.get('synthetic') is not synthetic or previous.get('state') != 'STAGED_NOT_IMPORTED' or
                    previous.get('fault') is not None or any(previous.get(k) is not False for k in
                        ('imageDownloadEnabled', 'imageImportEnabled', 'buildEnabled', 'modelLaunchEnabled'))):
                raise StageError('LATCHED_FAULT_OR_UNFINISHED_SESSION')
        session = root / 'sessions' / uuid.uuid4().hex
        cache = root / 'cache'
        state = {'version': 1, 'state': 'STAGING', 'identitySha256': identity_sha, 'synthetic': synthetic,
                 'sessionId': session.name, 'fault': None, 'blobs': [], 'blobPayloadBytes': 0, 'authPayloadBytes': 0,
                 'imageDownloadEnabled': False, 'imageImportEnabled': False,
                 'buildEnabled': False, 'modelLaunchEnabled': False}
        def save():
            encoded = json.dumps(state, sort_keys=True).encode()
            if len(encoded) > RECEIPT_BYTES:
                raise StageError('RECEIPT_LIMIT')
            tools.base.atomic(state_file, state)
            if session.exists():
                tools.base.atomic(session / 'result.json', state)
        try:
            if previous is not None:
                expected = sorted((b.digest, b.size) for b in blobs)
                recorded = previous.get('blobs')
                if (not isinstance(recorded, list) or len(recorded) != len(blobs) or
                        any(not isinstance(row, dict) for row in recorded) or
                        sorted((row.get('digest', ''), row.get('bytes', -1)) for row in recorded) != expected or
                        any(not (cache / b.digest[7:]).is_file() for b in blobs)):
                    raise StageError('CACHE_CHANGED')
            # Reserve a full attempt even on a warm cache. Failed partials,
            # completed blobs and previous receipts all count; no auto deletion.
            needed = sum(b.size for b in blobs) + 3 * RECEIPT_BYTES
            count, used = plain_usage(root)
            if count + len(blobs) + 8 > ENTRY_LIMIT:
                raise StageError('NAMESPACE_ENTRY_LIMIT')
            if used + needed > limits.namespace_bytes:
                raise StageError('NAMESPACE_BYTE_LIMIT')
            reserve_disk(root, limits, needed)
            session.mkdir(parents=True)
            cache.mkdir(exist_ok=True)
            save()
            for blob in blobs:
                context.begin_blob()
                target = cache / blob.digest[7:]
                if target.exists():
                    verify_cached(target, blob, context)
                    state['blobs'].append({'digest': blob.digest, 'bytes': blob.size, 'cacheReused': True})
                    save()
                    context.check()
                    continue
                partial = session / (blob.digest[7:] + '.partial')
                digest, copied = hashlib.sha256(), 0
                with source.open(blob, context) as response:
                    context.check()
                    if response_length(response, blob.size) != blob.size:
                        raise StageError('BLOB_LENGTH_MISMATCH')
                    with partial.open('xb') as output:
                        while True:
                            reserve_disk(root, limits, blob.size - copied)
                            chunk = read_chunk(response, min(CHUNK, blob.size - copied + 1), context, charge=False)
                            if copied + len(chunk) > blob.size:
                                raise StageError('BLOB_LENGTH_MISMATCH')
                            if not chunk:
                                break
                            reserve_disk(root, limits, blob.size - copied)
                            output.write(chunk)
                            digest.update(chunk)
                            copied += len(chunk)
                        if copied != blob.size or 'sha256:' + digest.hexdigest() != blob.digest:
                            raise StageError('BLOB_HASH_OR_LENGTH_MISMATCH')
                        output.flush()
                        os.fsync(output.fileno())
                context.check()
                tools.plain(target)
                if target.exists():
                    raise StageError('CACHE_DESTINATION_EXISTS')
                # Same-filesystem rename under the namespace writer lock. Both
                # paths are fixed digest leaves inside this owned namespace.
                partial.rename(target)
                state['blobs'].append({'digest': blob.digest, 'bytes': copied, 'cacheReused': False})
                state.update(blobPayloadBytes=context.blob_bytes, authPayloadBytes=context.auth_bytes)
                save()
                context.check()
            context.check()
            state['state'] = 'STAGED_NOT_IMPORTED'
            save()
            context.check()
            return session, state
        except BaseException as error:
            state.update(state='FAULT', fault={'code': error.code if isinstance(error, StageError) else 'STAGING_ERROR'},
                         blobPayloadBytes=context.blob_bytes, authPayloadBytes=context.auth_bytes)
            try:
                save()
            except Exception:
                pass  # Failed persistence is never success; original error still escapes.
            raise


def prepared_contract(identity=None):
    identity = images.metadata() if identity is None else identity
    return {'status': 'IMPLEMENTED_APPROVAL_GATED',
            'blobCount': len(identity['layers']) + 1,
            'kernel': 'image_download._stage', 'transport': 'image_download.RegistrySource',
            'implementationSha256': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
            'pinnedBlobBytes': identity['lockedBlobBytes'],
            'authBodyAllowanceBytes': (len(identity['layers']) + 1) * AUTH_BYTES,
            'namespaceLimitBytesProposed': images.storage_budget(identity)['hostStageBytes'],
            'expandedStreamVerification': {
                'kernel': 'image_expand._verify', 'status': 'SYNTHETIC_VALIDATION_ONLY',
                'maxOutputChunkBytes': CHUNK, 'actualPinnedLayersVerified': False,
                'dockerDiskUsageBounded': False},
            'processSupervision': {
                'rehearsal': 'verify_image_stage.py', 'status': 'CONNECTED_APPROVAL_GATED',
                'productionConnected': True, 'supervisorDeathCovered': True,
                'ownership': 'windows-job-kill-on-close', 'singleLogicalProcessorEnforced': True},
            'helperSha256': {name: hashlib.sha256((images.HERE / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                             for name in ('image_expand.py', 'image_stage.py', 'image_admission.py', 'verify_image_stage.py', 'windows_job.py')},
            'liveApprovalBridgeConnected': True, 'independentDownloadProcessGuardConnected': True,
            'imageDownloadEnabled': False, 'imageImportEnabled': False}


def stage_pinned(*args, **kwargs):
    if args or kwargs:
        raise StageError('IMAGE_STAGING_NOT_APPROVED')  # No enable/bypass options.
    import image_stage
    return image_stage.run()  # Rejects missing exact approval before any side effect.
