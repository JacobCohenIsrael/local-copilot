> Current direction (20 October): follow [VIABILITY_POC.md](../../VIABILITY_POC.md). One real
> coding task within 30 minutes; new coding scopes use resource warnings/trends.
> The notes below describe historical or deferred work, not next-step instructions.
> Their strict thresholds, pending approvals and context ladders do not override
> the current contract. Preserve historical evidence and CPU-build policies.

# Pinned Linux Strata build proposal

**Current checkpoint (18 October):** [the CPU-only build completed](CPU_BUILD_TIMING_RESULT.md): all 153 steps passed, artifacts are hash-verified, and owned shutdown is confirmed. The [first real model/API test](../model-runtime/FIRST_API_REVIEW.md) is prepared for approval with unchanged CPU/RAM caps and explicit runtime controls; 386 offline tests pass. Previous evidence/configurations are preserved. Model/GPU execution remains disabled. Earlier checkpoints below are historical.


**Isolation implementation update:** see [the native rehearsal review](NATIVE_REHEARSAL_REVIEW.md).
The Windows-to-WSL device bridge, staged runtime and guest startup are connected
to exact admission and independent leases. All 320 proposal tests pass. One
128-MiB empty-engine native rehearsal is ready for approval; none has run.
`run-isolation` refuses without its new exact approval. `run-import` remains
unconditionally blocked. No new live policy or workload was activated.

**Import architecture update:** the owner chose a separate store with an
enforced disk cap. See [the design review](IMPORT_STORAGE_REVIEW.md).
The bounded archive producer and synthetic transport checks are implemented;
the native empty-engine runner is wired but not yet qualified. `prepare-import` and `review-import`
report DESIGN REVIEW ONLY. `run-import` always refuses. A native fixture and
exact workload review are required before import approval. No existing Docker
configuration changed; compilation/model execution remain disabled.

This directory contains disabled build preparation. No compiler or model has
been started. The owner approved CPU-only controls and an unknown-throttle
exception, but not a build workload; see `BUILD_POLICY_REVIEW.md`. The 92 C
start / 97 C stop revision is approved; do not ask for that decision again.
`build-proposal.json` has both build and model launch disabled. The
Dockerfile is named `.proposed`; its default entrypoint refuses execution even
if a future owner-approved build succeeds. The production build command now
exists behind exact admission; no first-build approval or live policy is active.

**Current image milestone: verification COMPLETE.** One approved corrected run
verified config + 11 layers, 3.95 GB compressed / 7.45 GB expanded streams, without
extraction/import. Worker and reader stopped; the three old faults and cache are
unchanged. See [IMAGE_VERIFICATION_SUCCESS.md](IMAGE_VERIFICATION_SUCCESS.md).
The successful claim/approval is consumed too. Import/build/model remain disabled;
next is a concrete bounded import review, not another verification attempt.

## Current CPU-source and build admission milestone

See [FIRST_BUILD_REVIEW.md](FIRST_BUILD_REVIEW.md) for the exact disabled package,
CPU-source limitations and remaining decisions. All 6,001 staged source files
were compared with the pinned archives and all 4,161 tool files rechecked.
The real reader, independent guard, one-attempt state and bounded export are
connected behind source/workload approval. All 245 proposal tests pass; native
dummy-controller cases also passed. No real build or model ran.

The selected offline successor is now
`.runtime/offline-build/c47d018e42244443a72bf166081da9c4/offline-plan.json`;
the earlier plan below remains preserved as historical evidence. The temporary
one-CPU/6-GiB/no-swap WSL2 envelope in `wsl-build-limits.proposed` is now approved,
applied and verified after Docker/WSL restart. Saved evidence reports one CPU,
6,215,266,304 usable bytes and zero guest swap. It affects all WSL2 distributions.
This does not authorize image transfer/import, compilation or model work.
See [the image-preparation approval review](IMAGE_PREPARATION_REVIEW.md) for the
exact connected operation: one pinned-blob acquisition and bounded stream check,
no import. Real CPU-source/image-policy acceptance, one-attempt state, job-owned
Windows worker, liveness thread, metrics and exit confirmation are implemented.
Fourteen connected native synthetic cases pass, including monitor/owner loss and
blocked I/O, with an effective one-logical-processor job. The full CLI rehearsal
also passed; no real image transfer or hardware workload ran. Only execution
approval and fresh runtime admission were needed for this acquisition scope.
The owner then approved it and the one attempt ran: authentication response
HTTP_FRAMING_INVALID, no accepted body bytes/cache, confirmed worker/reader stop.
The fault and consumed claim remain; no automatic retry. See
[IMAGE_STAGE_RESULT.md](IMAGE_STAGE_RESULT.md) before any recovery work.

The correction is now complete; see
[IMAGE_AUTH_RECOVERY_REVIEW.md](IMAGE_AUTH_RECOVERY_REVIEW.md) for the exact new
attempt awaiting approval. Authentication accepts bounded HTTP/1.1 chunk decoding
without weakening blob framing. Offline tests, 17 native guarded cases and one
small live auth-only check pass; no blob was requested by this correction.
All old live files remain unchanged and the 42 approved helpers were archived
before editing. The owner approved the successor and it ran once: all pinned
compressed blobs passed size/hash verification, then stream verification stopped
on SENSOR_FEED_ERROR. Worker/reader stopping is confirmed. Both attempts are
consumed; no reset, retry, import, compilation or model run occurred. See
[IMAGE_RECOVERY_RESULT.md](IMAGE_RECOVERY_RESULT.md) for evidence and next work.

Offline diagnosis/correction and retained-cache recovery preparation are complete:
see [SENSOR_FEED_RECOVERY_REVIEW.md](SENSOR_FEED_RECOVERY_REVIEW.md). All saved
frames replay cleanly; the original generic exception's cause remains unproved.
Feed sequence/receipt commit now follows all checks, and redacted error/exit
details are saved after stopping. Six cache-only native cases and the existing
17 guard cases pass. The fixed unused verification namespace requires its own
absent approval; both faults and the cache remain preserved. There is no new
download path, cache copying, extraction/import or compilation/model execution.
That exact verification was subsequently approved and ran once. It stopped on
permission denied reading sensor sample 71 (OS error 13); worker/reader shutdown
is confirmed. All three attempts are now consumed and preserved, with the cache
unchanged and full verification still incomplete. See
[VERIFICATION_RESULT.md](VERIFICATION_RESULT.md). No retry/new execution is approved.

The next offline milestone is complete. See
[SAMPLE_ACCESS_RECOVERY_REVIEW.md](SAMPLE_ACCESS_RECOVERY_REVIEW.md): a held native
rename/delete handle reproduces the observed errno-13 file read. Read-only
READ|DELETE sharing fixes that publication window while denying content writes;
single-read/no-retry and frame freshness/provenance checks remain. Initial
heartbeat publication is now atomic too. Tests: 245 proposal cases, 64 direct
native publication cycles and 24 guarded native cases pass. Three attempts and
their approved code/receipts/readings/cache remain preserved. The fixed unused
verification successor needs a new approval; downloads/import/build/model stay off.

## Offline compiler successor ג€” 17 October

The historical apt/pip recipe is no longer an execution candidate. Its source
package remains a read-only input to the offline successor, recorded in
`offline-build-candidate.json`. The successor is prepared but unapproved; it
has an approval-gated build command and controller. Existing CPU controls remain
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

## CUDA image metadata and storage plan — no layer download

`image_plan.py` verifies public manifest/config bytes by their pinned SHA256
identities, Linux/amd64 architecture and the ordered compressed-layer/diff-ID
mapping. Files `cuda-base.manifest.json` and `cuda-base.config.json` are inert
metadata; their history/entrypoint text is never executed. LF bytes are restored
before hashing after Windows text checkout. Total metadata is 22,864 bytes;
the config's hash/size is bound by the already pinned image manifest.

The image has 11 gzip layers, **3,951,075,675 bytes** total (3.68 GiB). Including
the 20,233-byte config, the exact blob budget is **3,951,095,908 bytes**. Descriptor
types, sizes, hashes, platform, layer count and diff-ID coverage are checked;
foreign descriptors, changed bytes and a widened payload budget fail closed.
Registry metadata was read over HTTPS. The small config redirect used a Docker
[documented CDN host](https://docs.docker.com/desktop/enterprise/allow-list/)
without forwarding its registry bearer token. No layer payload was downloaded.
Origin/digest verification is not an independent code signature.

Proposed staging ceilings: 5 GiB accepted blob payload and 16 GiB expanded-stream
bytes. The expanded size is **not measured**; this ceiling is a proposed failure
limit requiring review, not a prediction that the image fits. The acquisition kernel/transport are now synthetically tested (below);
bounded expansion/diff-ID verification is synthetically tested (below), while
actual layer verification and the import procedure remain pending;
there is no download, decompression, import or pull command in image_plan.py.
No retries, automatic cleanup, limit increases or shared-layer savings are
assumed. Future decompression/import needs validated CPU monitoring and its own
reviewed workload/stop controls; importing can use daemon resources outside a
container's CPU/RAM caps.

This Docker daemon reports the containerd image store, which keeps compressed
content and expanded image data ([Docker documentation](https://docs.docker.com/engine/storage/containerd/#disk-space-usage)).
Planning includes two Windows blob copies (cache plus possible import archive),
compressed+expanded guest storage, 2 GiB import scratch, 16 MiB staging metadata,
20 GiB host reserve and 4 GiB guest reserve. For the observed shared host volume,
the proposed requirements are **52,672,254,252 bytes** Windows free (~49.1 GiB)
and **27,573,416,036 bytes** guest free (~25.7 GiB). Different staging/backing
volumes are checked separately. These are planning headroom, not an actual disk
reservation, decompression proof or enforced daemon import quota.

`probe_image_storage.py --read-only-probe` used only the cached Python image,
0.5 CPU / 64 MiB RAM / 16 processes, no extra swap/network/GPU and a three-second
alarm. It reads root-filesystem capacity/mount type; no filesystem scan, pressure
test, settings change or model read occurs. Source/root are read-only, the owned
container identity/profile is verified, and removal/exit were confirmed. It
observed 1,366,043,017,216 bytes host free (~1.24 TiB) and 1,024,433,799,168 bytes
guest available (~0.93 TiB). Evidence:
`.runtime/image-storage/2121628011b54300982aa6433d1cf1d8/result.json`.
The default-location docker_data.vhdx exists on C:, but its active mapping is
not independently confirmed. The guest probe covers its actual container root
filesystem; it is not a complete host mount audit. The WSL CLI returned an empty
running-distro inventory, so no distro was started or settings changed to obtain
these observations.

`image-storage-observation.json` binds the probe receipt hash without granting
start/download authority. Preflight reports this historical snapshot and requires
an immediate capacity recheck before any approved staging. Enough free space
cannot remove admission/approval gates. Twelve new tests cover hash/shape/type
checks, platform changes, budgets, combined-volume accounting, missing/invalid
capacity and receipt tampering; the proposal suite now has **101 passing tests**.
The existing 89 controller/build checks remain intact. Image download/import,
compilation and model launch remain disabled; original source/model/configuration
files, owner approvals and the frozen offline build plan are unchanged.

## Image-blob acquisition — synthetic validation only

`image_download.py` implements the streaming acquisition kernel and a restricted
anonymous Docker Hub transport. Accepted blobs are fixed digest/size descriptors.
A single writer lock protects the namespace; successful bytes are flushed and
renamed from a digest-named partial file to cache only after exact size/SHA256
verification. Existing cache is fully rehashed; changed, linked or missing cache
fails instead of silently downloading a replacement. Prior FAULT, unfinished or
corrupt state refuses automatic restart. There is no reset, retry, automatic
cleanup, decompression, image import or container/model launch operation.

The kernel checks guard permission and monotonic session/per-blob deadlines
before/after reads and around state transitions. Reads are at most 64 KiB (with
an extra-byte probe at the declared boundary). Received blob/auth body bytes
count against one payload budget even when a later guard check fails. Counters
cover application body reads, not HTTP/TLS/TCP overhead or bytes buffered inside
the network stack. Unexpected
length, hash, HTTP status/framing, duplicate Content-Length, Transfer-Encoding,
HTTP content encoding, clock regression, disk shortage or lost permission faults
the attempt. Partial files and verified earlier blobs are retained with bounded
structured receipts. Disk reserve checks run before reads/writes; they cannot
reserve space against other programs. Namespace accounting includes failed and
completed files, prior receipts and worst-case new payload/metadata; entry cap
is 4,096 and individual receipts are capped at 128 KiB. Proposed production
namespace size stays within the existing host-stage budget; it is not activated.

The transport uses fixed HTTPS auth/registry endpoints for `nvidia/cuda`, normal
TLS validation, no proxy/environment credential inheritance and no credential
file reads. Anonymous tokens are memory-only; auth bodies are capped at 256 KiB
and charged to the total payload budget (12 blobs permit at most 3 MiB auth body
allowance for this image). It allows only one 307 redirect to the documented
Docker CDN hosts and the exact digest path; bearer auth is stripped from that
request. Downgrades, foreign hosts/ports/paths, credentials/fragments in redirect
URLs and further redirects fail closed. Registry errors are sanitized so signed
URLs/tokens are not journaled; transport failures do not trigger retries.
Only mocked HTTP responses were exercised: real registry/TLS/large-transfer
compatibility has not been validated by this step.

`stage_pinned()` always raises IMAGE_STAGING_NOT_APPROVED before constructing
transport or creating staging paths. No CLI/flag/receipt can enable it. A future
reviewed approval and independently supervised process bridge is still required;
there is no claim that per-read checks stop a blocked OS read/fsync on time.
Socket timeouts are at most five seconds within the remaining deadline, but
independent cancellation/termination and CPU monitoring remain live prerequisites.
The existing CPU-only thermal approval is not silently extended to new workloads.
Read-only preflight reports implementation hashes and keeps all start flags false.

`verify_image_download.py --execute-synthetic-only` uses only two fixed tiny
in-memory byte strings and real filesystem/lock/hash operations. Three cases
passed: 78 bytes staged then cache reused without refetch; wrong hash rejected;
extra byte rejected. Both failures retained partials and rejected restart.
Evidence: `.runtime/image-blob-rehearsals/804006c5eaf9470b98410b22a6833ff4/result.json`.
The verifier uses isolated synthetic namespaces under a combined 32 MiB/4,096
entry budget with a 4 MiB worst-case suite reservation. It never calls HTTP or
Docker. Twenty-two new tests cover acquisition, auth/redirect framing, cache
integrity, two-writer exclusion, disk loss, cancellation/deadlines and error
redaction. That acquisition checkpoint had **123 passing proposal tests**. No real layer
payload, decompression, import, compiler, model or hardware stress was performed.

## Expanded-stream verification and process stopping — synthetic only

`image_expand._verify` rehashes each compressed cache file and validates its
gzip CRC/end marker and expected SHA256 of the entire uncompressed stream
(the pinned config's diff-ID). Each inflate call returns at most 64 KiB;
per-layer and aggregate output limits stop at the first excess byte. Input
reads, inflate calls and hashes share cooperative guard/deadline checks. The
caller owns admission, the writer lock and the authoritative fault journal.
There is no live CLI, host extraction, Docker import or automatic retry.

Only one gzip member is accepted. Concatenated members and trailing bytes are
rejected, including when the extra data begins in a later read. This stricter
format's compatibility with the actual pinned layers remains untested. The
verifier hashes bytes without interpreting tar metadata: a stream-byte cap does
not establish Docker disk allocation limits, sparse-file limits or import
safety. The proposed 16 GiB real-image ceiling remains unapproved/unmeasured.

`image_process_rehearsal.py --execute-synthetic-only` supervises a fixed Python
child through its retained process handle. The command/source, owned namespace
and seven scenarios are fixed; there is no URL, command or live-source override.
The child stages generated bytes through the actual acquisition kernel and
checks the gzip stream under the same cache writer lock. Blocked read/expansion
cases sleep instead of performing any real I/O or GPU work. **gpu-hot is solely
a synthetic event; it neither reads nor heats the GPU.**

The supervisor checks its local monotonic clock, deadline and a bounded synthetic
controller pulse. It latches FAULT before requesting cooperative cancellation,
then terminates the owned child if it remains blocked; confirmation is a wait
on that handle. It never kills a PID supplied by the caller. Stopping continues
even if recording a fault fails; persistence failure cannot be reported as
success. Unconfirmed termination remains FAULT. The parent state.json is
authoritative; a killed child's receipt may remain STAGING. Every used rehearsal
namespace rejects restart, including completed sessions; no reset/delete exists.

Seven native host-process cases passed: a 130-byte fake gzip verified as 10,240
stream bytes, plus blocked download read, blocked expansion read, lost lease,
cancellation and simulated GPU heat. All five fault cases confirmed worker exit
in 0.11-0.13 s from detection and refused restart. No HTTP, Docker, sensor,
compiler, real image layer or model operation occurred. Evidence:
`.runtime/image-process-rehearsals/bbed7f775b534d17be0e30a33ddd81a2/result.json`.
Twenty new unit checks cover stream corruption/overflow, output-chunk bounds,
aggregate accounting, cancellation/deadlines, lease clocks, unconfirmed stops,
namespace rejection and stopping after journal failure. **162 proposal tests pass**
after the connected CLI/feed/ownership milestone.

The seventh case abruptly kills the supervisor. Its worker exits through an
unnamed non-inheritable Windows kill-on-close job; exit is confirmed with a
read-only duplicated process handle, without PID reuse. An unfinished RUNNING
journal blocks restart even before the verifier records SUPERVISOR_EXIT. Job
membership uses the Windows job-list creation attribute, avoiding a separate
create/assign gap; the child starts suspended and is resumed only after success.
Assignment/setup failure cannot run the child. The synthetic worker's job caps
commit memory at 128 MiB and active processes at one; no global/device setting
changes. See [Microsoft job ownership](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
and [process creation attributes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

OS failure and the production approval/telemetry bridge remain pending. No claim
of a physical thermal cutoff or live process guard follows from a sleeping-child
test. Read-only preflight reports the two synthetic
implementations and helper hashes while all production enable flags remain
false. `stage_pinned` still rejects before opening any transport or staging path.

## Single CLI and connected feed milestone

From the repository root, `python -B local_worker.py status` gives one compact
read-only JSON readiness report. `rehearse` runs the staging/ownership cases,
then the independently guarded fake-build/export flow, then the actual pinned
OpenCode CLI against scripted replies. It produces a bounded patch on a disposable
example. The stages exercise their own synthetic fixtures; a fake ELF is never
executed as an engine and scripted API replies are not real inference.

Evidence: `.runtime/local-worker/802fc15c847d47f4929a4e2caeb12b6a/result.json`.
All three phases passed (4.34/52.65/7.20 seconds), original files stayed unchanged
and every worker stopped/was removed. Its controller phase uses cpu_feed.Monitor
through Session, not a separate unused adapter. Ten new feed tests and nine
CLI/job tests cover lost/replayed/malformed/unvalidated frames, query coverage,
assignment/resume failure, bounded intake, canceled/failed flows and denial of
real runtime execution. There is no synthetic-to-production approval path.

`cpu_feed.Feed` launches only the hash-pinned fixed ASUS reader, with a 256 MiB /
four-process Windows job and immutable bounded frames. Its real mode preserves
validatedCpuSensor=false and throttle=null; it does not replace missing data.
The reader's query invokes existing WMI services; those services are outside
the reader's job, and software cannot guarantee firmware/OS query completion.
The adapter ticks the CPU-build gate when no new frame arrives, so a stopped
reader cannot renew permission by leaving an old file. Hardware source validation
and production admission are still required. `probe-cpu` is a passive ten-sample,
18-second diagnostic, not an eligibility check. Ordinary access returned an
administrator-required error and no temperature, then stopped. A Windows consent
launch was initially canceled. The owner then explicitly requested a retry and
approved Windows consent: ten passive readings completed in 8.996 s, starting
at 95 C and finishing near 75-78 C, with 7.69-31.35 ms query times. Reader stop
was confirmed; the hash-bound latest observation appears in CLI status.
Evidence: `.runtime/compiler-guard/99766c3642bd4773af3121e5595e3631/probe-result.json`.
No source certification, ten-second cool baseline, sustained-coverage guarantee
or workload approval follows from the observation. The owner subsequently
reported Armoury values 78,73,67,82,93,95 C. The passive comparison is complete;
the ranges overlap without paired timestamps or an inferred offset. Carry the
evidence into source admission review; all real workload flags stay disabled.

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
