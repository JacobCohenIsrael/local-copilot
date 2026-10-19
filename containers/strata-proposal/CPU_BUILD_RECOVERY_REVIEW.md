# CPU-only Strata build recovery: exact operation for approval

18 October 2026. Expected output: Linux Strata built for architecture 86, using
the **already-imported pinned CUDA image**. No download, image import, image build,
model loading, GPU workload, machine-setting change or automatic retry is included.

## Diagnosis and correction

The hash-pinned Ninja ELF contains `1.13.2.git.kitware.jobserver-pipe-1`; the old
shell script required exactly `1.13.2`. An inert shell fixture reproduces exit 1
before configure using that output. The corrected script accepts only the exact
pinned suffix and reaches configure/build/export with shell stubs. A wrong version
and missing executable now produce named failure messages and a stage/line/exit.
The CMake version check also consumes its full output, avoiding a head/pipefail
race. No actual Linux tool or compiler was executed to obtain these results.

The cached final image metadata layer confirms GCC, G++, build-essential and
CUDA nvcc are installed. Only that 89,735-byte compressed metadata layer was
read for this check; no large CUDA stream was expanded. A missing-compiler claim
is unsupported. The original container's exact failing line is still unknown
because its logs were removed. The matching version defect is fixed; the new
attempt must still establish native compatibility and resource fit.

## Connected logging and preserved evidence

On a real build fault, confirm stopping within the existing bound **before**
reading logs. Keep the failed container stopped; its bounded daemon logs remain.
After stopping the watchdog/reader, save a 64-KiB combined stdout/stderr tail,
exit/runtime/OOM details and the parent error. Log capture has a two-second
timeout; a failure preserves the stopped container and a diagnostic error.
Do not remove failed containers automatically. Successful artifact export still
removes its owned container. Confirmed concurrent removal is handled by fresh
immutable-ID inspection rather than falsely reporting a cleanup failure.

The original import and build namespaces, both raw reader sessions, spent
approvals, original shell input, and all 62 original approved helpers are
unchanged. The existing 3.95-GB OCI archive is retained without rehashing its body.
The new attempt uses `.runtime/cpu-build-recovery-1`; the old fault is never reset.
The private engine, its retained disk and unstarted capsule remain deferred.

## Exact approved limits to retain

- Existing WSL policy: **1 CPU, 6 GiB RAM, no swap**; no restart or settings edit.
- CPU admission <=92 C for ten seconds, stopping >=97 C, existing source/freshness
  checks and independent watchdog. Firmware freshness/calibration are not
  independently guaranteed; hardware throttle remains unknown and raw readings
  stay unchanged. The scoped source acceptance is included in this workload.
- Compiler: **1 CPU, 4 GiB RAM, no additional swap, 128 processes, one job,
  1,800 seconds**, one attempt. No GPU devices; architecture 86, no vision build.
- Read-only root/source/tools, non-root user, all capabilities dropped,
  no-new-privileges, network none, no credentials/model/Docker-socket mounts.
  `/work` 2 GiB, `/tmp` 128 MiB, shared memory 16 MiB share the same 4-GiB cap.
  Existing disk admission and five-second stop confirmation remain required.
- Failed container daemon logs remain capped at two 1-MiB files; the local
  diagnostic tail is at most 64 KiB. OOM/space/time failures end the attempt
  without enlarging limits or retrying. Retained stopped-container evidence is
  explicitly part of this review, not an automatic cleanup/reset authorization.

## Frozen package and next operation

Review SHA256: `b01b440e575209bb8c2fb629b18a0c4703301d5272acd950db2714b0f310ffc6`.
Offline plan SHA256: `1e134c63e155cf4c995d01d1c70458a28aa2537eb360a3c6447bd7b80d9c56e9`.
The package binds 64 helper files, 6,001 source files and
4,161 staged tool files. Original attempts were checked against their preservation
manifest. **353 offline tests pass**, including shell-only reproduction and
connected failed-start retention tests. Docker/sensors/compiler/model are mocked
or disabled; native shell fixtures contain only stubs.

After exact approval, `python -B local_worker.py run-build-recovery` uses the
existing guarded admission, creates one restricted compiler, compiles and exports
the artifact, then confirms owned stopping. The prepared hidden administrator
wrapper for the CPU reader is `run-cpu-build-reviewed.ps1` beside the frozen JSON
review under `.runtime/cpu-build-recovery-review/b01b440e575209bb8c2fb629b18a0c4703301d5272acd950db2714b0f310ffc6/`.
`cancel-build-recovery` requests stopping in this fixed new namespace, even when
start approval is unavailable; it cannot reset a terminal fault or target the old attempt.

The actual `cpu-build-recovery-approval.json` is **absent**; its template is
disabled. No new attempt, reader, container or compiler has run. The CLI refuses
without approval before live access. All earlier approvals are spent and cannot
authorize this new attempt. Model execution remains disabled after a successful
build; a later concrete runtime scope is required.
