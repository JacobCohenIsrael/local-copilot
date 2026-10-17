# Pinned Linux Strata build proposal

This directory contains disabled build preparation. No compiler or model has
been started. The owner approved CPU-only controls and an unknown-throttle
exception, but not a build workload; see `BUILD_POLICY_REVIEW.md`. The 92 C
start / 97 C stop revision is approved; do not ask for that decision again.
`build-proposal.json` has both build and model launch disabled. The
Dockerfile is named `.proposed`; its default entrypoint refuses execution even
if a future owner-approved build succeeds. No launch command or live thermal
policy is supplied while required CPU telemetry is missing.

## Offline compiler successor ג€” 17 October

The historical apt/pip recipe is no longer an execution candidate. Its source
package remains a read-only input to the offline successor, recorded in
`offline-build-candidate.json`. The successor is prepared but unapproved; it
has no build-start command or live controller admission. Existing CPU controls remain
92 C start / 97 C stop, one CPU, 4 GiB RAM, no extra swap or GPU, one job and a
30-minute deadline. Proposed filesystem changes need final manifest review.

`stage_build_tools.py` downloaded the exact Linux CMake 4.4.3 and Ninja 1.13.2
artifacts pinned in `build-tools.lock.json`, verified their published SHA256,
validated archive paths and extracted native binaries/data and licenses only.
No Python wrappers were installed/imported; no downloaded tool was run.
Archive bytes: **30,415,348**; staged bytes: **76,349,964**, 4,161 files.
Receipt: `.runtime/build-tools/ec73930b8fe5475296d70e1eacb4b065/tools.json`.
Origin/hash verification uses official PyPI HTTPS metadata, not independent
code signing. Linux loader/library compatibility is not yet tested.

Staging limits are enforced in code: 64 MiB accepted archive payload total,
256 MiB expanded archive data, 64 MiB/file, 10,000 archive entries and a 2 MiB
receipt. Redirects, extra bytes, wrong hashes, path/link/alias violations and
cache tampering fail closed. A process lock and a worst-case 512 MiB combined
namespace budget include failed attempts. No automatic cleanup/retry can hide
an error. The 20 GiB host free-space check is made before/after downloads and
before extraction files; it is not a physical reservation against other apps.
The payload deadline is 120 seconds with five-second socket timeouts; a blocking
read/system call can outlast a deadline check. Wire/TLS overhead is not counted
as accepted payload. Partial bytes remain for investigation, never execution.

`offline_build_plan.py` prepared
`.runtime/offline-build/836b14c728b047e695b24a48e6bf35fb/offline-plan.json`.
The script configures/builds only the engine with staged CMake/Ninja and the
base image's compiler/CUDA toolkit. It performs no apt/pip/setup/model operation.
Missing tools/source fail rather than downloading replacements. The source
fingerprint and BUILD.json were generated without importing upstream setup.py.
Exact image/source/receipt/script hashes and the resource/command profile are
checked by the read-only preflight. Full tool-tree verification occurred during
preparation and must be repeated before any eventual start.

The proposed profile has network=none, read-only root and read-only source,
tool and metadata mounts. It drops capabilities and uses a non-root user.
Writable locations are explicitly capped: /work **2 GiB**, /tmp **128 MiB**,
/dev/shm **16 MiB**; Docker JSON logs rotate at 1 MiB/two files. These tmpfs
limits share the existing 4 GiB memory cap and provide no extra RAM. A real
compile may fail with OOM/ENOSPC; that must stop without automatic retries or
cap increases. CUDA base-image files, loader compatibility and compiler resource
fit remain untested. Image-layer storage and Windows/VM paging are separate
from these compiler filesystem limits.
See [Docker tmpfs documentation](https://docs.docker.com/engine/storage/tmpfs/)
for memory/swap accounting, and [CMake FetchContent](https://cmake.org/cmake/help/v4.0/module/FetchContent.html)
for the additional disconnected-source configure setting. Network=none provides
the container network restriction independently of CMake's setting.

`verify_offline_quota.py --execute` used only the cached Python image, 0.5 CPU,
64 MiB/no extra swap, 16 processes, no GPU/network and a four-second inner alarm.
The fixture wrote exactly **65,536 bytes** before ENOSPC, proved read-only root,
and parsed the offline shell script without executing it. It exited successfully
and removal was confirmed. Evidence:
`.runtime/offline-quota/27b244a65d3f4ebcb58459c9f89be342/result.json`.
**89 proposal tests passed** after the controller-connection step.
This scaled fixture proves the mechanism, not that
the real compiler fits or that its image/guard/controller is ready.

tmpfs output disappears at stop. The draft waits after build completion for
export acknowledgement within the same 30-minute deadline. The collector and
controller connection below are implemented and rehearsed
with synthetic data; the live-build entry point remains disabled.
No build may start until that connection, validated CPU telemetry, independent
watchdog, bounded image staging/VM capacity and final owner approval are ready.
No CUDA image was pulled, no compiler/model was launched, and no device settings
were changed in this step.

## Bounded artifact collection — synthetic validation only

`artifact_export.py` accepts only regular `strata`, optional `libstrata_kq.so`,
and `BUILD.json` under the fixed engine directory. Proposed maximum sizes are
256 MiB, 128 MiB and 16 KiB respectively; the uncompressed transfer gets another
64 KiB for tar headers/padding. It rejects links, traversal, duplicate/extra files,
compressed input, sparse files, extended tar headers and malformed/truncated data.
These are proposed build-output limits, not an approved live-policy revision.

Collected bytes are SHA256-recorded; BUILD.json must exactly match the pinned
input hash. ELF64/little-endian/x86_64 headers are checked without executing any
file. This does not prove linkage, compiler provenance, completeness of runtime
libraries or that an engine can run. Archive modes are ignored and no exported
file is launched or installed. New outputs never overwrite earlier attempts.

Docker's normal copy API cannot read tmpfs here, as confirmed by the failed
synthetic attempts and [Docker's documented corner cases](https://docs.docker.com/reference/cli/docker/container/cp/#corner-cases).
The successful route uses only fixed non-root commands: `/bin/tar` streams the
fixed engine directory and `/bin/touch` sends the fixed export-complete marker.
No shell or caller-supplied container command/path is accepted. The immutable
container ID must be supplied by the future controller. Its transport must
recheck identity/isolation, waiting state and active safety lease before copy,
after copy and before acknowledgement. The native fixture verifies its own
identity/resource profile; it does not validate the future live CPU feed.

The copy drains stdout in chunks to a capped file, with at most 4 KiB diagnostics;
it never buffers an entire archive in memory. A shared export deadline is at
most 20 seconds and must also fit inside the original build deadline. The host
namespace `.runtime/build-artifacts` has a 2 GiB combined budget and 1,000-entry
cap under a process lock, reserving worst-case archive + expanded files + receipt
space before each attempt. Failed attempts remain and count against the budget;
there is no retry, deletion or automatic limit increase. A 20 GiB free-space
check is inherited from tool staging; it cannot reserve capacity against other
applications. Blocking OS I/O and bounded client cleanup can outlast a deadline
check. Killing the Docker client alone does not confirm the container/tar exited.
The independent controller must always retain stop authority during export.

The collector writes and flushes files and a structured receipt before sending
acknowledgement. Export failure is journaled as `EXPORT_FAULT`, with any saved
files retained and no automatic acknowledgement. An attempted acknowledgement
may have reached the worker even if its reply is lost; the receipt distinguishes
attempted from confirmed. The future controller must latch global FAULT and
trigger/confirm stopping on export failure, timeout or lost lease. A saved-output
receipt is not global FAULT state or confirmation of worker exit. Safety stopping
must take priority over preserving output; never delay it to finish collection.

`verify_artifact_export.py --execute-synthetic-only` used the cached Python image
with 0.5 CPU, 64 MiB RAM/no extra swap, 16 processes, a 64 KiB tmpfs and a ten-second
inner alarm. Network/GPU access was absent. The success case saved **176 bytes**
of metadata and fake ELF headers, observed acknowledgement and confirmed exit 0.
The mismatched-metadata case rejected export, observed no acknowledgement and was
removed. Both removals were confirmed. No fake ELF file was executed. Evidence:
`.runtime/artifact-export-rehearsals/2a1c94a7c3d44fa8b43febcaf68a03ce/result.json`.
The earlier failed copy-API attempts are retained, with cleanup confirmed.

Nineteen synthetic unit tests cover archive/identity/lease/deadline/size failures,
fixed commands, bounded stdout/diagnostics and acknowledgement ordering. The
proposal suite now totals 89 passing tests. The collector has no start CLI/authority;
`build_preflight.py` still reports `artifactExporterConnected=false` because the
real CPU feed and production admission remain disabled. CUDA-image tar/touch availability, GNU tar header
compatibility, full-size throughput and real compiler output remain untested.
The frozen offline plan and both existing owner-approval receipts are unchanged.

## Controller connection — synthetic-only admission

`offline_target.py` now freezes the current offline proposal's target identity,
command, image reference, read-only mounts, non-root identity, resource caps,
network/GPU isolation and log/tmpfs profile. It never creates or starts a worker.
The stop path accepts this frozen matcher so emergency stopping does not depend
on rereading mutable approval/source files. Existing guard behavior is unchanged
when no matcher is supplied. The actual CUDA-image inspection remains untested.

`controller_session.py` connects the readiness gate, persistent session state,
collector and confirmed stop/removal. Its single writer must hold the namespace
lock. The actual 92 C / ten-second baseline, 97 C stop trigger and unknown-throttle
exception are resolved from the existing approval receipts; no policy is changed.
Fault state is saved before Docker stop/kill. Sensor silence, cancelled work,
lost controller lease, unexpected exit, OOM, identity mismatch, export failure,
clock regression or mismatched wall/monotonic progress prevent success. A clock
jump/resume gap cannot be hidden by a freshly wrapped sensor timestamp.

The collector requires an independently progressing watchdog heartbeat and an
EXPORTING state bound to its container and plan hashes. It rechecks permission
after the inspect call and before acknowledgement. A successful collector receipt
alone cannot complete a session: the watchdog also requires the matching receipt,
exit code zero, no OOM and confirmed removal. First faults survive later events;
a new invocation refuses saved FAULT, corrupt or unfinished state. There is no
reset endpoint. Journal-write failures still attempt stopping and remain explicit;
a failed disk cannot guarantee durable fault persistence. Docker/host failure can
leave STOP_UNCONFIRMED; software does not provide a physical thermal cutoff.

`controller_rehearsal.py --watch-synthetic-only <owned-session>` is a separate
host process and only accepts fixed fake-output source/metadata in its owned
rehearsal namespace. It independently polls sensors/leases and stops the worker
while output collection is blocked. This is synthetic telemetry, including the
97 C event: no GPU/CPU heating, real sensor read, compiler or model is involved.
Both Session and GuardedExport explicitly reject the production target. The
watchdog does not create or start containers; only the synthetic verifier starts
its fixed harmless fixture after ARMED. The older dummy guard CLI is preserved.

`verify_controller_session.py --execute-synthetic-only` passed three native cases:

| Case | Observed result |
| --- | --- |
| Normal export | 176 fake bytes saved; acknowledgement, exit 0 and removal confirmed |
| Synthetic 97 C during blocked export | FAULT CPU_HOT; independent stop confirmed in 1.55 s; removal and restart rejection confirmed |
| Missing controller heartbeat during blocked export | FAULT CONTROLLER_LEASE_EXPIRED; independent stop confirmed in 1.56 s; removal and restart rejection confirmed |

Each case uses the cached Python image, 0.5 CPU, 64 MiB/no extra swap, 16 processes,
64 KiB tmpfs, read-only root/input, no network/GPU, a ten-second worker alarm after
start and a 35-second outer rehearsal deadline. The ten-second cool baseline
runs in real elapsed time using synthetic samples. Separate fault namespaces
isolate the test cases; they are not a mechanism for resetting future live FAULT.
A live deployment must use one fixed state namespace and an explicitly reviewed
recovery procedure. Rehearsal evidence:
`.runtime/offline-controller-rehearsals/89d484304f1d4241a6bbb33b1ffdb094/result.json`.

Seventeen new synthetic unit tests include clock gaps, lost leases, failed fault
journals, outages, changed identities, stop ordering without approval-file access,
and faults racing export inspection. Total: 89 proposal tests pass. Read-only
preflight includes the connection's source hashes but retains all live admission
blockers. The offline plan, reader, model/configuration files and owner-approval
receipts are unchanged. Full tool-tree rechecking, CPU-source validation/coverage,
CUDA image staging/capacity/compatibility, fixed live-state admission and final
build-workload approval remain necessary before enabling real compilation.

The owner selected Strata itself in Docker. The prepared compile route now uses
an ordinary capped Docker container, specified in
`.runtime/strata-build/1c9c3253/build-manifest.json`, selected in `build-candidate.json`;
the original package `1537f5ec` is retained unchanged. `build_preflight.py` verifies
the refreshed package and approved controls without starting Docker. The Dockerfile below is the
earlier reference recipe, not the selected execution path. `prepare.py`
downloaded the two pinned source archives (62,426,870 bytes total), validated
their paths, staged the source without executing it, and cross-checked four key
Strata files against the previously reviewed snapshot. The llama.cpp source is
already staged where setup expects it, avoiding that source download at compile
time. SHA-256 records establish the downloaded archive identities; source origin
is the pinned GitHub URL over TLS, not an independent signature verification.

The manifest proposes one CPU, 4 GiB RAM, zero swap, 128 processes, runtime
`runc`, no GPU requests, no restart, and a 30-minute inner timeout. Only its own
source/helper input is mounted read-only; no original installation, weights,
host credentials, or Docker socket. The writable container layer is needed for
apt/pip and build output. Bridge networking is proposed solely for build
dependencies; its download volume is not yet bounded or approved. The base CUDA
image still has not been pulled. The separate monitor/guard must be adapted and
the actual Docker settings inspected before this compiler is admitted. The
manifest does not execute anything and remains `buildEnabled: false`.

The [compiler guard connection](BUILD_GUARD.md) supplies a manifest-bound target
matcher, bounded ASUS reader, and independent stop-path rehearsals. Nine mocked
checks and four real non-compiling Docker cases passed. The real three-sample
CPU reader completed; source validation and workload approval still prevent
admission. The approved throttle exception does not authorize compilation.
No live build policy has been activated.

The future `bounded_build.py` now checks required staged source before importing
upstream setup code and never calls its source-download fallback. Two isolated
tests use synthetic source/output and mocked compiler commands; no source code
from Strata is executed in those checks. The refreshed source-only candidate
now contains this helper with a matching hash; its workload still needs final
review and approval before a build. apt/pip download bounds and
dependency reproducibility remain unresolved; this source check does not solve
or waive them.

After a successful approved compilation, image creation is a separate reviewed
step, with a disabled default entrypoint and a recorded resulting image identity.
Do not automatically run the engine as a build check. The source/archive path
test rejects traversal, wrong archive roots, case aliases, reserved Windows
names and symlinks before writing output files.

Source: Strata v0.1.44.1 at commit
`296b59d2f73c8f04a805df29c2fa97655adace78`; its llama.cpp dependency is pinned to
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. The official CUDA 13.0 Ubuntu 24.04
Linux amd64 base is pinned by manifest digest. Only registry metadata was read;
no CUDA image layers were pulled. Do not use the live `main` branch or copy the
existing `D:\AI` installation into the source context.

The suggested build targets only CUDA architecture 86, omits the vision build,
and compiles with exactly one job without an automatic retry. Inspection found
that upstream `setup.cmake_build` explicitly passes `-j max(2, cpu_count/2)`;
setting `CMAKE_BUILD_PARALLEL_LEVEL=1` alone would not override that. The proposed
helper uses explicit CMake commands instead. It is syntax-checked only, not a
validated Linux build recipe. It imports upstream setup only inside a future
approved builder; host tests never import or execute upstream code.

The proposed one-CPU / 4 GiB / no-swap builder envelope must be enforced and
inspected outside this Dockerfile, with a harmless quota check before compilation.
It is not assumed that ordinary Docker BuildKit build flags provide these caps.
Compiling CUDA code uses CPU/RAM and can heat the laptop even without GPU devices;
the CPU sensor/watchdog and explicit build-workload approval gates still apply.
There is no automatic builder start or approval bypass in this milestone.

The source and base identities are pinned; the build is not yet fully hermetic.
Upstream Python requirements pin versions but not all distribution hashes;
Ubuntu package repository state, compiler dependencies, and downloaded artifacts
need a captured lock/checksum record or an explicit reproducibility exception.
Full source staging, disk/download budgets, build output identity, and compiler
compatibility remain unverified. The current NVIDIA driver is 617.14, above the
CUDA 13 documented driver-generation floor of 580; no CUDA runtime test has run.
See [NVIDIA's CUDA 13.0 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html).

Runtime candidates deliberately differ from the preserved Windows setup:
8,192 engine context instead of 65,536; mmap expert reads instead of resident
experts; speculative decoding disabled initially; an explicit VRAM reserve;
separate capped RAM/CPU budgets; no automatic setup, downloads, or restart.
These are proposals requiring review, not established safe limits. mmap can
still cause substantial I/O and page-cache use or an OOM; a file fitting on disk
does not establish an acceptable runtime working set. The actual Linux engine
arguments, CPU-prefill behavior, profile update paths, and MTP-disabled path must
be checked before generating an owner-approvable launch manifest.

Model data would remain read-only, with a copied expert profile and generated
Linux configuration in an isolated session area. No existing launcher or JSON
configuration was modified. No automatic setup against the original data
volume is permitted by this proposal.
