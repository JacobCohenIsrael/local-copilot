# Approved image recovery: downloaded, verification interrupted

17 October 2026, 15:43:31-15:47:59 UTC, including preflight and baseline.
The owner approved one new acquisition/verification attempt under unchanged
limits, bound to review
`2f703f5a6b0b17eb9b2005a8d90275237532e9931cdb63ecbed116944c762c30`.
The receipt is `image-stage-recovery-approval.json`; the original approval and
failed attempt remain unchanged. No policy or production helper was edited.

## Outcome

- Authentication correction worked: all 12 auth observations were HTTP/1.1
  chunked without Content-Length. Accepted auth bodies totaled 65,771 bytes;
  no token/body/signed URL was retained in logs.
- All **12 pinned compressed blobs, 3,951,095,908 bytes**, passed exact size/hash
  checks and remain in the owned cache. Staging reports `STAGED_NOT_IMPORTED`.
- Expanded-stream verification began but did **not** complete. No successful
  worker result exists; the cached blobs are not a fully verified/import-ready
  image. No extra verification workload was run after stopping.
- Terminal state: **FAULT / SENSOR_FEED_ERROR**, CLI exit **3**. The worker
  subsequently reported `GUARD_PERMISSION_LOST` after the supervisor revoked
  permission. The consumed claim and fault remain latched; no retry or reset.
- Worker exit and reader shutdown are confirmed. Recorded worker stop time was
  about 0.024 seconds, an observation rather than a future timing guarantee.
- The approved ten-second baseline passed at sequence 28. Raw reader evidence
  contains 262 frames; 261 were consumed. Temperatures ranged 72-96 C, with
  zero raw frame errors, maximum query time 30.3 ms and maximum interval 1.03 s.
  The last raw frame is 95 C and still declares about 1,658 seconds of coverage.
  Unknown hardware throttle remained null and raw validation flags unchanged.
- The generic sensor-feed exception did not retain its underlying exception or
  reader exit code. These readings do not establish the exact failure cause;
  do not describe it as a measured overtemperature or a proven physical sensor
  failure. Investigate the adapter/reader lifecycle using preserved evidence.
- Docker inventory is empty and the pinned CUDA image remains absent. The
  cached read-only swap preflight exited and was removed; guest swap was zero.
  Import, compilation and model execution remained disabled throughout. No GPU,
  firmware, power, fan or existing Strata configuration changes occurred.

## Preserved evidence

Recovery session: **82dc1b816889471f98fd25ee8d31ea95**.
Fixed namespace: `.runtime/guarded-image-stage-recovery-1/`.

- `state.json`: final fault and positive stop confirmations; raw SHA256
  `dbad7dfedf8e18c58c3a58044f08c38e3dd71aa7ab9ebecf52d4870cb6417859`.
- `attempt.json`, `start.json`, `metrics.jsonl`, `auth-response-1.json` through
  `auth-response-12.json`, `worker-error.json`: immutable claim and observations.
- `data/state.json` and `data/cache/`: pinned compressed-blob verification
  receipts and retained bytes. No extraction output or completed stream receipt.
- Raw reader: `.runtime/compiler-guard/746421aeb6f34c85b7dcd3a837cda5f7/`.
- Swap/storage proof:
  `.runtime/image-storage/58cca59792fc46298ed19e6d2769b657/result.json`.
- Launcher invocation, completion, CLI output and observational summary:
  `.runtime/image-recovery/8de46ce61487484694d473faf9f9bb29/recovery-*.json`.

The original `.runtime/guarded-image-stage/` still has all 12 unchanged files,
verified by admission against its preserved tree hash. Its state SHA256 remains
`3729dbd7aa432cf22441b347e49a5036f9415cdd07c7e7c97d7755e2327e1ecc`.
Its 42 approved helper snapshots and original review/approval remain archived.

## Left

Diagnose the generic feed failure and test a correction offline, preserving both
attempts and their exact reviewed code. Then prepare a separate reviewed recovery
that can verify retained pinned blobs without silently reusing this consumed
approval or clearing either fault. Any new execution needs explicit approval.
Import still requires its own bounded disk/stop review; compilation and model
execution remain later milestones. No additional attempt is prepared or approved.

Later preparation update: offline feed corrections and a separately gated
retained-cache verification are now ready for approval in
[SENSOR_FEED_RECOVERY_REVIEW.md](SENSOR_FEED_RECOVERY_REVIEW.md). All 262 saved
frames replay cleanly; the historical underlying exception remains unproved.
Both faults, cache and exact reviewed code are preserved. No new live sensor
read, actual cache-body verification or execution attempt ran during preparation.
