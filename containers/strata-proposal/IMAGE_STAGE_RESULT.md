# First approved image acquisition: stopped with a transport fault

17 October 2026, 14:48:24-14:48:39 UTC. The owner explicitly approved one
download/verification attempt under review
`861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323`, including
the image-scope CPU-source limitation and unknown throttle status. The recorded
decision is `image-stage-approval.json`. Import, compilation and model execution
remained disabled throughout.

## Outcome

- Final phase: **FAULT / IMAGE_WORKER_FAILED**, worker detail **HTTP_FRAMING_INVALID**.
- The single attempt is consumed and its fault/claim remain latched. No retry,
  reset, alternate downloader or new registry request followed the failure.
- The CPU baseline admitted the worker. Twelve real readings were
  **92,91,80,91,83,83,79,81,78,85,82,82 C**, spanning 11 seconds; the first ten
  seconds stayed at or below 92 C. Maximum observed query time was 47.6 ms.
- Hardware throttle stayed null. Raw reader validation flags were not changed.
  This brief observation does not establish calibrated hardware freshness or
  safety under sustained image/compilation/model work.
- The registry authentication response failed the framing check before any
  accepted authentication-body or blob bytes: both counters are **0**, no blobs
  were completed, and the cache is empty. These are accepted-body counters,
  not a measurement of TLS, headers or buffered wire traffic.
- Worker exit and CPU reader shutdown were confirmed. CLI exit code was **3**.
  Worker exit was already observable when cleanup checked it (about 0.0003 s
  from detection to confirmation); this is not a future stopping-time guarantee.
- The cached read-only swap/storage preflight completed and removed its fixture.
  Guest swap was zero; the reviewed Docker/WSL envelope passed. The pinned CUDA
  image remains absent and the final Docker inventory is empty.

## Retained evidence

The fixed live namespace remains `.runtime/guarded-image-stage/`:

- `attempt.json`: session **3487a42f960b47f887ddcada151a269a**, exact review hash.
- `state.json`: terminal fault and positive worker/reader stop confirmations.
  Raw SHA256: `3729dbd7aa432cf22441b347e49a5036f9415cdd07c7e7c97d7755e2327e1ecc`.
- `metrics.jsonl`, `worker-error.json` and `data/state.json`: real observations,
  framing rejection and zero accepted payload counts.
- Raw immutable CPU frames:
  `.runtime/compiler-guard/9fa838d2ad494e60850f63a3948b26fd/`.
- Fresh swap/storage proof:
  `.runtime/image-storage/f66b023abd464e22a39ab95f758ec43d/result.json`.
- Fixed administrator launcher invocation/completion and CLI output:
  `.runtime/guarded-image-launch/`.

The launcher ran the exact reviewed CLI once after Windows administrator
consent. The frozen helpers and review package were not changed during or after
the run. No bearer token, signed registry URL or authentication body was logged.

## Diagnosis and next work

The transport requests authentication before requesting a blob. Its current
`response_length` check requires HTTP 200, exactly one decimal Content-Length,
no Transfer-Encoding and absent/identity Content-Encoding. The zero auth-body
counter and empty blob list locate this rejection at the authentication response.
The check records a shared error code, not the response headers, so the exact
failed condition is **not known**. Missing length or transfer encoding are
possible explanations, not established observations.

Next, diagnose the precise authentication framing condition and implement/rehearse
compatible bounded handling, retaining fixed origins, byte ceilings, timeouts,
process supervision and redaction. This report makes no transport or policy
change. The consumed live state must be preserved; no second image attempt is
authorized by the first approval. Any proposed recovery needs its concrete
review and renewed authorization. Import/build/model remain separately disabled.

## Later diagnosis and prepared correction

The original report and failed namespace remain preserved. A later headers-only
diagnostic observed HTTP/1.1 chunked authentication without Content-Length,
reproducing the previous parser's rejection. It does not establish the unrecorded
historical headers. The bounded correction passes 213 proposal tests, 17 native
guarded cases and a small live authentication-only check with zero blob requests.
See [IMAGE_AUTH_RECOVERY_REVIEW.md](IMAGE_AUTH_RECOVERY_REVIEW.md) for the separate
unused successor awaiting approval. No second image attempt has run.
