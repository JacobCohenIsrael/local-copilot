# Authentication correction and one new image attempt

17 October 2026. **Approved and consumed.** All pinned blobs downloaded, then
stream verification stopped on SENSOR_FEED_ERROR. Worker/reader shutdown is
confirmed; no retry. See [IMAGE_RECOVERY_RESULT.md](IMAGE_RECOVERY_RESULT.md).
Import, compilation and model execution remain disabled. The first failed
attempt is preserved, still FAULT, and cannot be reset or reused. The preparation
record below describes the exact operation before its one approved execution.

## Diagnosis and correction

A single fixed-endpoint authentication-header diagnostic observed **HTTP/1.1
200, Transfer-Encoding: chunked, no Content-Length**, with no content encoding.
It did not read a token body or request a blob. The previous parser rejects
exactly that format because it requires Content-Length on every response.
The original failed request did not retain its headers, so we cannot claim its
historical headers were identical; the current observation reproduces its error.

The correction separates small authentication responses from pinned blob data.
Auth accepts either its previous exact Content-Length form or HTTP/1.1 chunked
with no Content-Length. Python's HTTP client decodes the chunk framing; retained
decoded auth data remains capped at **256 KiB**. At most one extra decoded byte
detects overflow and is charged to the shared accepted-body budget. Blob responses
still require one exact Content-Length and their pinned size/hash. No compressed,
unframed, duplicate, conflicting or stacked transfer encoding was enabled.

Chunked HTTP is defined by [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3);
the transport uses Python's [HTTP client](https://docs.python.org/3.13/library/http.client.html).
It relies on that parser's handling of chunk syntax; it does not implement a new
HTTP decoder. TLS verification, fixed origins, request deadlines, body budgets,
process ownership, liveness checks and redaction remain in place.

After offline tests, one separately bounded **authentication-only diagnostic**
verified the correction against the live endpoint: 5,481 decoded bytes, token
syntax valid, token discarded, **zero blob requests**. That diagnostic used an
owned one-processor/128-MiB process, an eight-second cooperative/ten-second outer
deadline and no real sensor or GPU load. It is not a second image attempt.
Only categorical framing and counts were saved; no token/body/signed URL was kept.
Future image attempts also retain these redacted framing categories so a failure
can identify the protocol condition without exposing credentials.

Diagnostic/check receipts:
`.runtime/image-recovery/8de46ce61487484694d473faf9f9bb29/auth-headers.json` and
`auth-correction-check.json` in the same directory. Both hashes are bound in the
new review package. No real image blob has been requested by this work.

## Preservation and recovery admission

The previous namespace `.runtime/guarded-image-stage/`, session
**3487a42f960b47f887ddcada151a269a**, remains untouched and stopped in FAULT.
All **12 files** have the same tree SHA256:
`7b9ab387a0207c681a8d073e9892f45cf97bdf3c995e7aae2392441c841c0581`.
The prior approval and exact 42 approved helper files/review were archived before
editing. Their hashes are checked again by the new admission path. Original raw
CPU frames and prior evidence remain in their existing locations.

Preservation record:
`.runtime/image-recovery/8de46ce61487484694d473faf9f9bb29/preservation.json`, SHA256
`aac617524754554fc5160c8051c9a298173fe73010d286409a5f1ca326e007d4`.
Changing/removing/adding/linking old evidence or changing its archived code denies
recovery. A confirmed stopped predecessor is mandatory; no unresolved worker is
waived. The old empty cache is not reused or deleted.

The proposed successor is fixed at **`.runtime/guarded-image-stage-recovery-1/`**,
with **one new attempt**. There is no arbitrary namespace option, reset operation,
automatic retry, or automatic creation of another successor. It needs a separate
`image-stage-recovery-approval.json` receipt bound to the new exact review and the
failed session. That receipt is absent. Copying the old approval cannot authorize
it; the disabled new template is documentation, not authority.

## Exact new operation

Review SHA256:
**`2f703f5a6b0b17eb9b2005a8d90275237532e9931cdb63ecbed116944c762c30`**.
Machine-readable package:
`.runtime/guarded-image-review/2f703f5a6b0b17eb9b2005a8d90275237532e9931cdb63ecbed116944c762c30/review.json`.

This is still **one acquisition and compressed/expanded-stream verification of
the same pinned Linux amd64 CUDA blobs**, with no import/execution:

| Control | Unchanged limit |
| --- | --- |
| Image | `nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c` |
| Locked bytes | 3,951,095,908 bytes, about 3.95 GB |
| Accepted HTTP bodies | 5 GiB shared by auth and blob bodies, not a TLS/wire-byte cap |
| New staging namespace | 7,918,969,032 bytes including partials/receipts; 4 MiB supervisor reserve |
| Host disk reserve | 20 GiB checked throughout copying; not a physical reservation |
| Expanded stream | 16 GiB total/per layer, <=64-KiB output chunks, no tar extraction/output |
| Staging process | One logical processor, 128 MiB committed memory, one process |
| CPU baseline | <=92 C for ten seconds; wait at most 90 seconds |
| Stop | >=97 C, any known throttling or source/monitor/controller failure |
| Unknown throttle | Remains null under the already accepted image-only exception |
| Work time | 1,800 seconds shared by acquisition and verification; <=600 s/blob |
| Reader and leases | 1,920 samples with coverage checks; monitor/controller 2.5 s, worker progress 7.5 s |
| Shutdown | Cooperative cancellation, then owned job termination; five-second worker exit-confirmation budget |
| Attempts | One newly approved attempt, including a failed baseline/setup after claiming; no reset/retry |

The preceding failed namespace and code archive remain additionally retained.
They contain no image payload, and their fixed contents are separately hash-bound.
Windows paging, existing D:\AI/configuration and firmware/power/fan settings are
unchanged. The previously approved temporary WSL limits remain active.

The earlier image-scope source limitation and unknown-throttle acceptance remain
recorded. Their source/thermal hashes are unchanged; this request is for a new
attempt under corrected code, not another decision on those numeric/source limits.
Firmware freshness/calibration and a physical cutoff are still not guaranteed.
Fresh live source/baseline/coverage, WSL/swap and disk checks are still mandatory.

## Verification and operation

**213 proposal tests pass**, including real HTTP chunk decoding over generated
in-memory responses, overflow/accounting, malformed/truncated/framing conflicts,
cancellation/deadline interruption, redaction, old evidence tampering and refusal
to reuse the old approval. **17 native guarded cases pass**, including chunked
authentication success, malformed chunks without blob promotion and shutdown
during a blocked auth read. They use tiny generated data, no external network,
real CPU sensor, actual image bytes or GPU. Fixture timings are shortened; real
baseline values remain covered by deterministic real-format checks.

Native evidence:
`.runtime/guarded-image-rehearsals/1f48e7371fb0465e829cc5bf70f59104/result.json`.
No new image attempt, import, compilation or model run occurred while preparing
this correction. The earlier full supervisor rehearsal remains preserved as prior
evidence; it was not rerun for this transport-only correction.

`python -B local_worker.py review-image` reports the new unused candidate and the
preserved prior FAULT. `run-image` refuses the absent new approval before any
reader/worker/connection/live claim. Once explicitly approved it uses the same
guarded CLI and requires Windows administrator consent for the ASUS reader.
The fixed, not-yet-executed recovery launcher is prepared under the preservation
directory as `run-recovery-approved.ps1`; it verifies this exact candidate and
Python binary before invoking the CLI once. `cancel-image` targets only the new
owned active attempt. Import/build/model still require their own later approvals.

Final admission checks: the real `run-image` entry point returned
`IMAGE_STAGING_NOT_APPROVED` (exit 3) with the new approval absent and created no
successor namespace. The original state and approval raw hashes are unchanged.
Read-only Docker inspection confirms the approved resource envelope, no remaining
containers and no pinned CUDA image. The prepared launcher parses successfully
but has not run. The disabled first-build packet is refreshed to
`b03888655b150cc20e807eedfc50be092cd1c0f94fb0f818379beda03f354a92`;
its build-source/workload approval remains absent. `git diff --check` passes.
