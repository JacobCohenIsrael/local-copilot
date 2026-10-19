# First Strata Docker build: exact operation for approval

18 October 2026. Expected output: the Linux Strata executable, built for this
laptop's GPU architecture. No Strata model or GPU workload runs in this operation.

The owner approved normal Docker Desktop storage for the first test. This package
uses it to combine the remaining base-image import and CPU compilation into one
operation. The separate engine and disk rehearsals are deferred.

## What the approval covers

1. Check unchanged WSL limits and fresh disk space, using the existing cached
   Python image for the read-only guest-capacity probe. Establish the existing
   fresh CPU baseline through the administrator reader.
2. Rehash the already-downloaded CUDA blobs while writing a retained OCI archive
   of exactly **3,951,112,704 bytes** (about 3.95 GB). Send
   that file once to Docker Desktop using `docker image load --platform
   linux/amd64 --input <owned archive>`. No pull or registry download is used.
3. Verify the pinned manifest/platform and ordered layer identities. Stop the
   importer and reader. Only after successful verification and confirmed owned
   process stopping, authorize the exact linked CPU build from the same decision.
4. Recheck the build inputs, obtain a fresh guarded baseline, compile once and
   export the bounded artifact. Stop and remove the owned compiler container.
   Retain all results and faults; never retry automatically.

Entry point after approval: `python -B local_worker.py run-desktop-test`.
The prepared hidden administrator wrapper is
`.runtime/desktop-test-review/35f7e4b766ef0fd25c99de44428ab49bcca1a4a53254c4f384b96a6485163e78/run-desktop-reviewed.ps1`.
It has not run. Windows consent supplies access to the existing CPU reader.

## Unchanged limits and scope

- WSL: **1 CPU, 6 GiB RAM, no swap**; no settings change or restart.
- Admission: at or below **92 C for ten seconds**; stopping at **97 C**.
  Missing/stale readings and lost controller/worker leases also fault.
- Import helper: one logical CPU, 256 MiB, four processes in an owned Windows
  job; 30-minute work limit. Docker's shared daemon remains outside that job.
- Compiler: **1 CPU, 4 GiB, no additional swap, 128 processes, one compiler job,
  30 minutes**, network disabled and no GPU devices. Non-root, read-only root and
  inputs, no capabilities, no-new-privileges, no credentials/model/socket mounts.
  `/work` 2 GiB, `/tmp` 128 MiB and shared memory 16 MiB share the same 4 GiB cap.
  Target architecture 86; vision disabled. No apt/pip downloads.
- Preserve 20 GiB host free space; require the reviewed guest growth headroom
  plus 4 GiB reserve before importing. These are planning/monitoring limits,
  **not an enforced Docker storage quota**. The extra archive and Docker image
  content are retained. Compilation may run out of memory/space or time; that
  ends this attempt without enlarging limits.

## Limitations included in this approval

The ASUS CPU evidence is qualified for scoped acceptance; firmware refresh
latency and calibration are not independently guaranteed. Hardware throttle
status remains unknown. Accepting these limitations applies only to this import
and CPU build. Raw sensor evidence stays unchanged.

**Shared Docker cancellation:** stopping the owned import client does not prove
the shared daemon has stopped unpacking. Import does not have the compiler's
4-GiB memory cap or a hard disk quota. A fault blocks compilation and preserves
partial content and uncertainty. The supervisor has no authority to stop global
Docker/WSL automatically. The owner must explicitly accept this limitation for
the one import. Successful client exit is additionally checked for daemon unpack
errors and followed by exact image inspection.

## Exact frozen package and validation

- Combined review SHA256: `35f7e4b766ef0fd25c99de44428ab49bcca1a4a53254c4f384b96a6485163e78`.
- CPU build review SHA256: `d7faf479da04fcf795a165f4dc281fa364c181111396eeb396e29439c20b879f`.
- Source: pinned Strata 0.1.44.1, 6,001 files / 217,334,509 bytes verified against
  both source archives; 4,161 staged build-tool files verified. No source upgrade.
- CUDA manifest: `sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c`.
- Frozen helper files: 62; exact normalized copies,
  CPU review, storage decision and disabled approval template are beside the
  combined machine-readable `review.json`.
- **338 offline tests pass**, including 18 Desktop-path checks. Docker import,
  compiler, hardware and model are mocked/disabled in those tests. Manifest-ID
  and config-ID Docker image stores are both supported with pinned-content checks.
- The actual combined and CPU-build approvals are absent. Calling the live entry
  point without approval refuses before reader/process creation. Templates cannot
  enable execution. No new import, compilation or model has run.

All four prior image attempts, verified blobs, consumed native fault, never-started
container and bare attached disk remain preserved. Existing configurations stay
unchanged. Model execution requires a later concrete runtime package; this approval
does not cover model loading, a GPU test, new policy or larger resource limits.

## Done / left

- Done: one connected import-to-build workflow, offline tests and exact review.
- Next: approve and execute this combined operation to obtain Linux Strata.
- Then: obtain a short real Strata API answer, connect OpenCode for one disposable
  edit submitted by Codex, return its patch and confirm shutdown.
