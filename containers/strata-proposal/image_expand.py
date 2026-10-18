"""Bounded gzip/diff-ID verification kernel; no extraction or live entry point."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import zlib

import image_download as downloads


@dataclass(frozen=True)
class Layer:
    blob: downloads.Blob
    expanded_sha256: str

    def __post_init__(self):
        if (not isinstance(self.blob, downloads.Blob) or
                not isinstance(self.expanded_sha256, str) or
                not re.fullmatch('[0-9a-f]{64}', self.expanded_sha256)):
            raise downloads.StageError('LAYER_DESCRIPTOR_INVALID')


@dataclass(frozen=True)
class Limits:
    layer_bytes: int
    total_bytes: int

    def __post_init__(self):
        if (any(type(n) is not int or n <= 0 for n in (self.layer_bytes, self.total_bytes)) or
                self.layer_bytes > self.total_bytes):
            raise downloads.StageError('EXPANSION_LIMITS_INVALID')


def _layer(path, spec, maximum, context):
    """Hash one gzip member with <=64 KiB output per inflate call.

    No tar parsing/extraction: stream bytes do not bound Docker disk allocation
    (for example sparse files). Concatenated members/trailing bytes fail closed;
    compatibility with the actual pinned layers is still untested.
    """
    downloads.tools.plain(path)
    if not path.is_file() or path.stat().st_size != spec.blob.size:
        raise downloads.StageError('CACHE_CHANGED')
    compressed, expanded = hashlib.sha256(), hashlib.sha256()
    copied = emitted = 0
    inflater = zlib.decompressobj(31)
    with path.open('rb') as stream:
        while True:
            data = downloads.read_chunk(stream, min(downloads.CHUNK, spec.blob.size - copied + 1), context)
            if not data:
                break
            copied += len(data)
            if copied > spec.blob.size:
                raise downloads.StageError('CACHE_CHANGED')
            compressed.update(data)
            if inflater.eof:
                raise downloads.StageError('GZIP_TRAILING_DATA')
            pending = data
            while True:
                context.check()
                output_limit = min(downloads.CHUNK, maximum - emitted + 1)
                try:
                    output = inflater.decompress(pending, output_limit)
                except zlib.error:
                    raise downloads.StageError('GZIP_INVALID') from None
                context.check()
                emitted += len(output)
                if emitted > maximum:
                    raise downloads.StageError('EXPANDED_BYTE_LIMIT')
                expanded.update(output)
                if inflater.unused_data:
                    raise downloads.StageError('GZIP_TRAILING_DATA')
                pending = inflater.unconsumed_tail
                # A full output buffer can leave output inside zlib even when
                # all input was consumed. Drain it only through capped calls.
                if inflater.eof or (not pending and len(output) < output_limit):
                    break
    if copied != spec.blob.size or 'sha256:' + compressed.hexdigest() != spec.blob.digest:
        raise downloads.StageError('CACHE_CHANGED')
    if not inflater.eof:
        raise downloads.StageError('GZIP_TRUNCATED')
    if expanded.hexdigest() != spec.expanded_sha256:
        raise downloads.StageError('DIFF_ID_MISMATCH')
    context.check()
    return {'digest': spec.blob.digest, 'compressedBytes': copied,
            'expandedBytes': emitted, 'expandedSha256': expanded.hexdigest()}


def _verify(cache, layers, limits, context):
    """Internal kernel. Admission, writer lock and fault journal belong to caller.

    Caller must supervise this process independently: checks cannot interrupt
    blocked OS reads or guarantee a physical thermal cutoff. Never writes tar
    output; expected descriptors come from the reviewed, pinned image identity.
    """
    if (not 1 <= len(layers) <= 64 or any(not isinstance(row, Layer) for row in layers) or
            len({row.blob.digest for row in layers}) != len(layers)):
        raise downloads.StageError('LAYER_CONTRACT_INVALID')
    context.check()
    rows, total = [], 0
    for spec in layers:
        context.begin_blob()
        row = _layer(Path(cache) / spec.blob.digest[7:], spec,
                     min(limits.layer_bytes, limits.total_bytes - total), context)
        total += row['expandedBytes']
        rows.append(row)
    context.check()
    return {'status': 'STREAMS_VERIFIED_NOT_IMPORTED', 'layers': rows,
            'expandedBytes': total, 'extracted': False, 'dockerDiskUsageBounded': False}
