# Next CPU-only Strata Docker build: timing adjustment

18 October 2026. **Ready for approval; no new build or reader has run.**
The objective is to export the Linux Strata executable so we can prepare a real
Docker API answer and one bounded coding task submitted by Codex.

## Exact change

For this one CPU build only, increase the allowed ASUS sensor query duration
from **1.0 to 1.5 seconds**. Increase the fixed build-ready file check's Docker
command timeout from **1.0 to 1.5 seconds** as well. The first change covers the
recorded 1.0943863-second query; the second gives the readiness check the same
small allowance under the one-CPU VM. Neither change guarantees build completion.
The previous parent timeout's exact command was not retained, so its cause is
not claimed as proven. Future parent timeout records include the command and bound.

The original reader, global CPU policy and existing configurations stay intact.
A mechanically checked reader variant changes only the query cutoff (plus its
comment); only the new exact CPU-build permit selects it. The original CIM call
timeout remains two seconds. All other routes retain their one-second query budget.
The variant has the same ASUS endpoint/decoding and raw unvalidated readings;
existing firmware-refresh/calibration and unknown-throttle limitations still apply.
The owner must accept that source limitation for this one scope again as part of
the exact operation decision; the earlier spent approvals grant no retry authority.

**The timing allowance is still bounded.** Sampling remains once per second;
freshness and controller/watchdog leases remain **2.5 seconds**. A query above
1.5 seconds, stale/missing data, reader exit, cancellation or temperature at least
97 C still stops and latches FAULT. A final buffered frame never makes an exited
reader acceptable. The controller now saves the precise reader exception reason,
operation, last sequence and exit code before stopping. No monitoring redesign.

## Unchanged limits and exact operation

- CPU admission **at or below 92 C for ten seconds**; stop **at or above 97 C**.
- WSL: **1 CPU, 6 GiB RAM, zero swap**. No Docker/WSL restart or settings change.
- Compiler: **1 CPU, 4 GiB RAM, no extra swap, 128 processes, one job,
  1,800-second build deadline**, one attempt. No GPU devices or model execution.
- Imported image `nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c`; inspect it, never pull/import/build
  an image. Use the pinned Strata source/tools, architecture 86 and no vision.
- Non-root, read-only root and inputs, all capabilities dropped,
  no-new-privileges, network none, no model/credential/Docker-socket mounts.
  Work tmpfs 2 GiB, temp 128 MiB and shared memory 16 MiB share the 4-GiB cap.
- Existing capacity admission, independent watchdog and five-second confirmed
  stop bound remain. Shared-Docker cancellation and CPU-source limitations remain.
- On success export the binary and build metadata, then confirm owned stopping
  and remove that successful owned compiler. On failure keep its container stopped
  and retain combined logs/exit/OOM diagnostics (64-KiB tail, two-second capture,
  two 1-MiB daemon log files). No automatic retry, reset or resource increase.

The exact command after approval is `python -B local_worker.py run-build-timing`.
Windows administrator consent is still needed for the same CPU source. The hidden
launcher `run-cpu-build-reviewed.ps1` is prepared beside this frozen review.
`cancel-build-timing` requests stopping only the new owned session, without start
approval; it cannot reset faults or start/remove historical containers.

New one-attempt namespace: `.runtime/cpu-build-timing-1`.
Review SHA256: `5201aa43ea96c130e96b1b89cd97c9d913919a86e6f14b748783aaa682005fc5`.
Offline plan SHA256: `8098cb7c5214a50f12a54f1e8a305931accd9a2f6445d82ee1ab22874fb350cb`.
Frozen package: `.runtime/cpu-build-timing-review/5201aa43ea96c130e96b1b89cd97c9d913919a86e6f14b748783aaa682005fc5/`.
The disabled approval template binds both timing values and this exact review.
The actual `cpu-build-timing-approval.json` is absent.

## Validation and preservation

**365 offline tests pass.** All 840 recorded frames pass the proposed query
budget; the old gate rejects the final 1.094-second query. Tests confirm unchanged
heat/staleness/throttle/lease faults, terminal-reader rejection and diagnostic
retention, exact reader selection, approval refusal, consumed-attempt refusal and
cancellation. Docker, readers and compiler are fake in these tests; the shell
fixtures use inert tools. No new real workload was used to test this adjustment.

The package freezes 66 helpers, all test results and
its new immutable shell inputs. Pinned source/tool receipts remain bound.
Both earlier CPU attempts, image attempts and raw readings were rechecked against
their preservation manifests. The previous failed compiler remains stopped and
untouched, with full logs retained. Existing blobs/imported image, attached bare
disk and unstarted private-engine container are preserved; no cleanup/reuse of
those objects is part of this operation.

After a successful binary export, the remaining functional work is a separately
reviewed model-runtime configuration, one real Strata answer in Docker, then a
Codex-submitted OpenCode edit with returned patch and confirmed shutdown. This
CPU approval does not approve model/GPU execution or model-runtime RAM changes.
