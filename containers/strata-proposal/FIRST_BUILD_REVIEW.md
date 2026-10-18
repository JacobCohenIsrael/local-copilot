# CPU-source and first-build admission review

17 October 2026. Build review/preparation only: no compilation, engine, model or
GPU load has run. Three prior image attempts remain preserved in FAULT. The
corrected fourth attempt completed all compressed/expanded verification and
stopped cleanly; see IMAGE_VERIFICATION_SUCCESS.md. Import is still disabled and
the CUDA image is not present in Docker. No further execution is approved.
The temporary WSL2 resource policy remains applied and verified.

## Result and exact package

The snapshot below is preserved history and is disabled/stale after the sample
access/heartbeat helper corrections. Refresh its exact helper binding when
verification/import prerequisites are ready. See SAMPLE_ACCESS_RECOVERY_REVIEW.md
for the currently prepared image verification; no compiler approval is present.

The CPU source is qualified for an explicit owner acceptance decision for one
monitored CPU-only build. The production controller, fixed one-attempt state,
reader adapter, emergency stopping and bounded exporter are connected behind
hash-bound admission. They are implemented, not authorized to execute.

Review SHA256:
`a587cd09a408fd2053a18a6dc263aced51d789b57d2254999f605ee97b9650c3`.
Machine-readable package:
`.runtime/first-build-review/a587cd09a408fd2053a18a6dc263aced51d789b57d2254999f605ee97b9650c3/review.json`.
Earlier packets are preserved. This revision binds the corrected feed diagnostics
and cache-verification admission; it changes no compiler controls
or source/workload approval. All source/tool bytes were rechecked.

Offline successor:
`.runtime/offline-build/c47d018e42244443a72bf166081da9c4/offline-plan.json`,
SHA256 `c6e632e6d21f02c70f0e27b37190afa0e221a9c083501a8dac7b85e33f0dc9a0`.
The earlier 836b14c7 plan and its inputs remain intact. The selected revision
publishes the ready record atomically so the controller cannot mistake an
in-progress write for corrupt completion. No compiler inputs were executed.

## CPU-source decision

Evidence is bound to reader SHA256
`e8a3db7155b4ef177344d12bc1326f02f5da16ea9bab0a71066a97bb0c67b90d`:

- Ten real passive readings span 8.996 s with 0.974-1.020 s intervals,
  7.69-31.35 ms returned query times, no query error and confirmed reader stop.
- Values were 95,87,81,77,74,75,75,78,75,78 C. The owner's Armoury values were
  78,73,67,82,93,95 C. The ranges overlap; they are not timestamp-paired.
- G-Helper's public ASUS implementation independently names endpoint 0x00120094
  as CPU temperature and uses DSTS minus 65536. Its inert source snapshot is
  hash-bound in the review; no code or driver from it was installed/executed.
- Source/sequence/query/age checks, remaining reader coverage, cancellation and
  monitor/controller loss are tested. No more manual comparison is required
  unless new evidence reveals a discrepancy.

The limitation requiring explicit acceptance is:

> Firmware refresh latency and calibration are not independently guaranteed;
> acceptance is for one monitored CPU-only build, never model runtime.

This is a practical qualification with a recorded limitation, not manufacturer
calibration or a guaranteed hardware refresh bound. Software can detect missing
or stale delivered frames, but the ASUS status exposes no independent firmware
timestamp. A fresh wrapper timestamp alone cannot prove hardware freshness.
Hardware throttle stays null; the previously approved CPU-build-only exception
already covers that unknown. It is never converted into "not throttling".

Raw reader frames still contain validatedCpuSensor=false. Only a valid,
scope-bound first-build permit can qualify a copy for the CPU-build gate; the
original frame and its unknown channel remain unchanged. No permit is present.
The acceptance cannot be reused for image preparation or model runtime.

## Build admission and controls

Existing approvals stay unchanged: <=92 C for ten seconds before admission,
trigger stopping at >=97 C; one CPU, 4 GiB RAM, no additional container swap,
128 processes, one compiler job, 1,800 seconds and no retry. No second approval
of these existing numeric controls is requested here.

The exact workload and filesystem profile still require final approval. Root,
source/tools/metadata are read-only; network is none, user is 65532:65532, all
capabilities are dropped, no-new-privileges is set, runc is explicit and GPU
devices are absent. Mutable tmpfs limits are /work 2 GiB, /tmp 128 MiB and
/dev/shm 16 MiB, sharing the same 4 GiB memory limit. Build fit is unknown:
OOM/ENOSPC must fail without retries or larger limits. No model data, credentials
or Docker socket is mounted. D:\AI and existing configurations are untouched.

Admission now checks every staged source file against both pinned archives:
**6,001 files / 217,334,509 bytes**, source-tree SHA256
`63e03fb04ab51bdd169ab2e2ec0939160a26be39ac9c8903e7760d7b4dfdb251`.
Changed, extra, missing and linked source is rejected, including files outside
the earlier BUILD.json subset. All 4,161 staged tool files are rechecked too.

The approved path will:

1. Reject missing/mismatched approval before starting a reader or container.
   Recheck the exact review, controls, helper hashes, full source/tool trees,
   pinned image/config/platform/ordered diff IDs, VM envelope, disk and swap.
2. Claim the one attempt in fixed `.runtime/first-cpu-build/`. A failed,
   unfinished or completed attempt cannot reset/restart automatically.
3. Create the compiler without starting it. A separate guard owns the fixed
   reader, establishes a fresh baseline and requires full remaining coverage.
   Admission waits at most 90 s; failure consumes this attempt without compiling.
4. Start once only while that independent guard is progressing. Reader and
   controller leases remain bounded; monitoring continues through export.
5. Save/hash only the bounded named artifacts before acknowledging export.
   Confirm compiler exit and removal. The engine is never run as a build check.

The parent's emergency stop precedes waiting for a stuck guard. Stop uses the
frozen target rather than rereading approval files; unconfirmed stopping stays
unresolved. Reader ownership has a Windows kill-on-close job, one reader at a
time and combined retained-evidence admission limits. Host/driver/daemon or
blocked OS I/O can still defeat software intervention; no physical cutoff is
promised. A first real build remains an explicitly approved bounded trial.

## Docker/WSL resource policy: applied and verified

Before the approved change, read-only inspection found:

- The pinned CUDA image is absent; no pull/load/import was attempted.
- Docker reports 24 logical CPUs and 16,569,262,080 bytes RAM (~15.4 GiB).
- A refreshed read-only cached-image probe reports 4 GiB guest swap. It completed
  successfully and its container was removed; no image download or build ran.
  Evidence: `.runtime/image-storage/1d7296a94da441619a0c4752ec117c7b/result.json`.
- `C:\Users\yaki_\.wslconfig` does not exist. No Docker containers were running
  in the inventory; the subsequent dummy-test containers were all removed.

Image import is a daemon operation outside the compiler's container quotas.
To constrain that prerequisite, the proposed temporary WSL file is
`wsl-build-limits.proposed` in this directory:

```ini
[wsl2]
processors=1
memory=6GB
swap=0
```

The VM gets at most one logical CPU and 6 GiB RAM, with guest swap disabled;
the builder retains its separate 4 GiB limit. The extra VM allowance is for
Linux/Docker overhead, not more compiler memory. This does not bound host power
or guarantee temperatures. Verify the actual daemon/guest values after restart;
the first-build gate refuses the current uncapped envelope.

This separate policy decision is now approved. The file is global to WSL 2,
so other WSL distributions are affected and applying it required
stopping/restarting Docker/WSL. See [Microsoft's scope/restart
documentation](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) and
[Docker's WSL resource guidance](https://docs.docker.com/desktop/features/wsl/).
The owner explicitly approved this exact policy and restart. Prior absence was
recorded, the exact file was exclusively created, Docker was stopped, WSL shut
down and Docker restarted. Effective values are **one CPU, 6,215,266,304 usable
memory bytes and zero guest swap**. The cached-image read-only probe exited 0
and was removed. Verification is saved under
`.runtime/wsl-policy/8c26adaaf9a447df9af27319745e14d4/verification.json`.
Rollback restores recorded absence, with another restart; remove only the exact
file created by this operation if its hash is unchanged. Preserve owner edits.

Approving this VM policy authorizes neither image transfer/import nor compilation
nor model work. Image preparation still needs its concrete execution review,
live monitoring/source acceptance for that scope, fresh capacity and separately
approved budgets. Do not silently extend the CPU-build source/throttle decision
to image work. No image pull or import command is implemented by the build runner.
See [SENSOR_FEED_RECOVERY_REVIEW.md](SENSOR_FEED_RECOVERY_REVIEW.md) for the next exact
scope and tested guarded staging operation ready for approval. The earlier image
attempt is consumed; existing image-source/policy acceptance remains recorded.
Do not ask for WSL policy
approval again. Fresh actual resource checks still apply before live work.

## Validation and operator entry points

232 proposal tests pass. Eighteen build-admission checks cover source evidence, complete tree
verification, approval scope/tampering, the real-mode controller with mock frames,
the full mocked start/export protocol, guard-exit race and VM limits. An additional
status check detects configuration drift and keeps saved observations distinct
from live workload authority. The connected image milestone adds 17 checks and
23 native synthetic cases (six cache-verification plus 17 shared guard). The earlier passing full supervisor rehearsal remains
preserved; it was not rerun for the transport-only correction. See its review.
Native sleeping/fake-output controller cases passed again; hot and lost-lease
stops during blocked export confirmed exit in 1.63/1.58 s and removed the targets.
Evidence: `.runtime/offline-controller-rehearsals/46839ff23e0f42b1b9119bfe07999b7d/result.json`.
The production-format tests use mock telemetry and Docker; they are not real
sensor qualification, compilation or performance evidence.

From the project root:

```powershell
python -B local_worker.py review-build --check-environment
```

This inspects image/daemon metadata only. `prepare-build` regenerates the
disabled package and rechecks inputs. After all prerequisites and explicit final
workload/source acceptance, `run-build` is the one-attempt entry point from an
administrator shell; `cancel-build` signals only that owned build. The final
approval file is absent and must be recorded only from an explicit owner decision
binding this exact package. Do not edit enable flags to bypass the review.
