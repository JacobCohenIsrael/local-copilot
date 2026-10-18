# Local Copilot

## Current milestone: ordinary Docker import and first Strata build

The owner approved normal Docker Desktop storage for the first test. Private
engine/VHDX rehearsals are deferred. See containers/strata-proposal/DESKTOP_BUILD_REVIEW.md.

- Done: connected verified CUDA import directly to the guarded offline CPU build;
  338 offline tests pass. Exact combined review and disabled template are frozen.
- Left: obtain one combined workload approval, import and compile Linux Strata;
  then a real API answer, one Codex-submitted OpenCode edit, returned patch and stop.

Storage approval alone does not authorize import/compilation. Model execution
remains disabled. Keep existing 92/97 C controls and WSL 1 CPU/6 GiB/no swap.
Preserve old attempts, attached disk and unstarted container; do not pursue that
deferred route. The older execution checklists below are historical.


## Project purpose and scope - 18 October 2026

This project uses Strata for local coding in two equally important roles:

- A substitute for paid coding agents for tasks the local model can handle.
- A local coding subagent for paid agents such as Codex and Claude, reducing
  their paid-token use by delegating bounded implementation work.

Read README.md for the project purpose and MVP.md for the immediate milestone.
Strata supplies inference; OpenCode is the current coding worker. A person or
parent agent submits selected context and a bounded task; the supervisor returns
its patch and structured result for review, then stops the local components.
Measure usefulness, code quality and paid-token savings with real tasks rather
than assuming the local workflow already matches a paid agent.

The Rider/JetBrains autocomplete plugin and Ollama assistant are retired and
have been removed from the active source tree, along with their setup scripts,
demo, tests and validation guide. Do not restore them, develop them, recommend
their setup, or treat them as deferred work unless the owner explicitly changes
this direction. Git history retains the previous implementation.

Keep code that supports Strata, including the Python worker/supervisor,
container lifecycle and safety tools, and the independent TypeScript Strata
supervisor simulator under src/supervisor/ and src/supervisor-cli.ts. The Node
package exists only to build and test that simulator; it is not an Ollama client.
The main entry point is local_worker.py. npm start runs the simulator only.

Repository cleanup must preserve .runtime model files, cached build inputs,
reviewed helper snapshots, consumed attempts, faults and execution evidence.
Do not infer permission to uninstall software, stop unrelated services, delete
model weights, detach retained disks or change machine settings from source
cleanup requests.

The Strata execution notes below retain historical evidence and scoped policy
decisions. Earlier milestones or instructions do not supersede this purpose or
newer owner decisions. Preserve their evidence without reviving retired work.

## Current direction: first working Strata helper, 18 October 2026

The owner explicitly redirected this project to completing Strata in Docker as a local coding helper for cloud Codex, improving infrastructure afterward. See MVP.md. CPU monitoring is an existing background guard, not the next project milestone. Done means one real Strata model answer, then one bounded OpenCode edit submitted by Codex, patch returned, and both local components stopped. Linux Strata is not built; OpenCode works in Docker with scripted replies, and CUDA base blobs/source/build tools are staged. Prioritize base import/build, real API startup, worker connection and end-to-end task. Do not add more sensor research/manual comparisons, empty-engine rehearsals, optional MCP, dashboards or benchmarking before that proof unless a concrete failure makes them necessary. The owner approved normal Docker Desktop storage for the first test; see containers/strata-proposal/desktop-storage-approval.json. That storage decision does not approve build or model workloads. No runtime/resource/power changes are authorized implicitly. Preserve the consumed native fault, unstarted container, bare attached disk and all prior evidence. The earlier next-step/checkpoint paragraphs below are historical.


## 18 October 2026 native execution result - supersedes canceled-launch status

The owner-authorized Windows-consent retry succeeded and the exact reviewed native rehearsal ran once. See containers/strata-proposal/NATIVE_REHEARSAL_RESULT.md. The attempt .runtime/native-isolation-1 is now consumed and FAULT-latched (exit 3); do not retry/reset. Real CPU baseline passed; 71 raw frames at .runtime/compiler-guard/7ab8b9599c8e4236aaada55edc8fcb30 span 79-95 C, raw validation false/throttle null preserved. Fixed 128-MiB VHDX creation and owned Windows-to-WSL marker bridge succeeded; physical size observed 132 MiB. Device /dev/sdc, major/minor 8:32, disk sequence 27. Restricted container bbcaa8925a5dd9f9b944c2df91191b9fe8d7eb2258b4ea1919eb2390bfa72ff0 was created but NEVER STARTED (created, PID 0, zero StartedAt); no guest/runtime/formatter/private engine/model ran. Exact captured configuration fails only because Docker returns CAP_-prefixed capability names. Offline normalization alone passes all existing admission checks. No helper or live configuration was modified. Current stop predicate rejects created-never-started state, and final cleanup masked the admission error as NATIVE_ENGINE_STOP_UNCONFIRMED. Preserve original state unchanged. Helper and reader stopped. Retain the unstarted container and UNFORMATTED BARE ATTACHED VHDX; no reviewed guest unmount/exclusive proof exists, so no detach/reuse/delete/global stop. Native execution result/preservation and both UAC launch pairs are beside review 2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743. All four image attempts, blobs, approved 61-helper archive, WSL/Desktop settings still match. Next offline milestone: captured-response regression, strict capability-name normalization, safe never-started cleanup and original-error preservation, explicit retained-device recovery plus NEW attempt for review. No automatic new native work; imports/build/model remain disabled. Earlier approval-ready/canceled-launch paragraphs below are historical.


## 18 October 2026 execution update

Owner approved exact native review 2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743. The actual native-isolation approval and archived decision are recorded. Frozen helpers/runtime/preservation/configuration and read-only Docker VM/image checks passed. Windows reported the administrator launch as canceled before the reviewed wrapper started. execution-outcome.json beside the exact review records NOT_STARTED_WINDOWS_ADMINISTRATOR_REQUEST_CANCELED. No native attempt, launch folder, sensor session, VHDX, capsule or engine was created. The native attempt remains unused. Preserve administrator-launch request/response, approval and outcome; do not automatically relaunch. User must resolve/relaunch Windows consent; no new workload-scope approval is needed. Import/build/model remain disabled. Earlier preparation statements below predate this approval.


## Current priority

17 October 2026 native wiring milestone supersedes the earlier implementation
gaps below. See containers/strata-proposal/NATIVE_REHEARSAL_REVIEW.md. Owned
Windows marker/WSL mapping and exact-path detach, installed ISO ELF dependency
staging, admitted PID-1 startup, fresh guest lease handshake, real CPU controller
renewal, bounded private-engine startup and fail-closed stop/unmount proof are
connected. 320 proposal tests (25 new native-path offline checks) and all fifteen
synthetic lifecycle cases pass. Signals/devices/engines are mocked in new tests.
No native VHDX/mount/capsule/engine, sensor read, image import or model ran.
Runtime staging copied 33 files / 182104353 bytes from the installed Docker ISO
without executing them or downloading anything. Native compatibility remains
unproven. Latest exact review SHA256:
2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743.
run-isolation now has a live implementation behind NEW exact native approval;
it refuses ISOLATION_NOT_APPROVED before live access while approval is absent.
native-isolation-approval.template.json is disabled; the actual approval and
.runtime/native-isolation-1 attempt remain absent. Next obtain approval for one
128-MiB / 180-second empty-engine rehearsal with 92/97 C controls, explicit
source/unknown-throttle acceptance and reviewed SYS_ADMIN/AppArmor exceptions.
The native rehearsal deliberately withholds the guest lease after READY while
the real CPU monitor continues. Never confuse that expected test fault with
permission to retry or run images. Retain all partial/uncertain state; never
detach without guest/outer exit, unmount and exclusive-device proof. Keep the
four old image attempts, archived helpers, blobs, .wslconfig and Desktop settings
unchanged. run-import stays unconditionally blocked; build/model stay disabled.
After native proof, prepare tiny OCI-load compatibility (no image execution),
then exact retained-image import; adapt the build to the same isolated engine.
The following earlier checkpoint paragraphs are preserved historical context.

17 October 2026 isolation-control implementation: see
containers/strata-proposal/ISOLATED_CONTROLS_REVIEW.md. isolated_store.py implements
fixed-VHDX native creation/property/identity/reserve checks and overlapped provider
cancellation/progress. isolated_agent.py has owned-marker/block-device and namespace
fuse primitives; its entry unconditionally refuses. isolated_engine.py renders and
inspects a restricted outer capsule and private Docker/containerd config; stopping
uses full immutable identity and remains possible on safety-config drift.
isolated_session.py connects a one-attempt controller, independent watchdog and
stop-before-journal/detach ordering in fifteen synthetic cases. No native disk,
capsule, engine, import, hardware reader or GPU workload ran. Native DLL exports
were resolved read-only, with creation blocked by the guard. Current native gaps:
owned Windows/WSL attach/nonce/mapping bridge, qualified installed dynamic runtime,
and real CPU/lease/guest bootstrap wiring. prepare/review/rehearse-isolation expose
only preparation/synthetic checks; run-isolation refuses before native access.
The proposed resource route is one restricted outer Docker container with one CPU,
4 GiB/no swap/128 processes and image writes on the new device; no shared cgroup
controller edits. SYS_ADMIN and AppArmor exception are proposals, not activated
policy. Next finish integration, then obtain exact small-canary approval. Do not
claim native isolation/import is ready solely from this implemented/tested code.
All four retained image attempts/code/decisions and blobs must stay preserved.
295 proposal tests pass. Isolation-control packet:
6b498442c4e5876b927a56ce8deca9048e9c5cd7fd97c95009a1b1cc24afd585.
Import design successor (inactive):
179776b5fad8baf5dbfd3d302ce27e5a2ffa4e0cfa47b389bc5d123921d1c97b.

17 October 2026 separate-import update: the owner selected a separate store with
an enforced disk cap; the choice approved no provisioning or import. See
containers/strata-proposal/IMPORT_STORAGE_REVIEW.md. import_plan.py binds all four
preserved attempts, including COMPLETE verification, through archived code and
decisions without reading cache bodies. oci_archive.py and import_rehearsal.py
implement a bounded stream and tiny synthetic checks only. 262 proposal tests
pass. The proposed new 32-GiB VHDX/private engine has NO live runner, native disk
bound proof or engine-wide stop proof yet; do not describe it as approval-ready.
prepare-import/review-import are design-only; run-import unconditionally refuses
before live access and has no approval/bypass option. Next prepare one concrete
small native fixture operation for approval to qualify runtime, device ownership,
containment, cgroup limits and whole-engine stopping. Real import/build/model stay
disabled. Preserve existing Desktop configuration and .wslconfig. Later adapt
first-build to this isolated endpoint/store; don't silently use default Desktop.
Existing successful 48-helper code was archived before edits; do not refresh or
rerun its consumed verification candidate. No new approvals were created.

Owner preference updated 17 October 2026: advance in larger integrated milestones,
not one small helper/test per turn. Complete connected workflows and their
verification before handing back. Keep Done/Left at milestone level; existing
workload approval and hardware safety requirements still apply.

Owner preference updated 17 October 2026: maintain short Done and Left bullet lists in progress/final updates and in NEXT_STEPS.md so the owner can follow the route to the first real Strata task. Clearly distinguish simulated validation from actual build/model execution.

Owner preference updated 17 October 2026: stop tracking or reporting account usage limits. The earlier five-hour allowance monitoring and 5%-remaining pause rule are revoked. Hardware safety limits and workload approval requirements still apply.

The main goal is an on-demand, Docker-contained Strata coding worker orchestrated by cloud Codex, with Claude support later. The old Ollama assistant and Rider/JetBrains plugin are retired and removed; the Strata supervisor simulator remains.

The target is the owner's Windows laptop with an RTX 3080 Ti 16 GB GPU and 32 GB RAM. A previous sustained Strata workload caused an unexplained instant shutdown. Keep Strata off during architecture, simulator, and read-only compatibility work. Do not start a model, run GPU load tests, change firmware or power settings, or activate a changed safety policy without explicit owner approval. Preserve the existing installation and configurations.

See `SUPERVISOR.md` for the simulation-only supervisor, `STRATA_CONTAINER_PLAN.md` for Docker compatibility findings, and `containers/lifecycle/README.md` for the CPU-only Docker dummy lifecycle harness. The dummy harness uses synthetic telemetry and cannot launch Strata/OpenCode; its limits and reset acknowledgment do not approve live work. Use simulated sensors and harmless workers to validate lifecycle behavior before proposing a live task. Docker MCP is optional; any future interface must go through the bounded supervisor.

`containers/safety/README.md` records read-only sensor availability and the independently tested dummy watchdog. The owner prefers a small dedicated monitor; see `containers/safety/MONITOR_DESIGN.md`. The owner-authorized administrator ASUS CPU status probe now works (90 ֲ°C candidate; later Armoury screenshot CPU 81 ֲ°C / GPU 57 ֲ°C). See `containers/safety/CPU_ACCESS_VALIDATION.md`; sensor meaning/freshness and CPU hardware thermal-throttle status remain unvalidated. OS frequency-limit readings must not be treated as proof of no thermal throttling. Do not replace missing readings with guessed values or activate model/build work. `containers/strata-proposal/` is an unbuilt, disabled proposal requiring separate review and approval.

The owner chose to keep Strata itself in Docker. Prioritize the prepared pinned Linux compile package over Windows-engine reuse and optional diagnostics. See `NEXT_STEPS.md` for the compact checkpoint. The source-only staging is complete; compilation and model launch remain disabled.

On 16 October 2026 the owner approved the CPU-only build throttle exception: unknown hardware throttle status may remain null for one capped CPU-only compilation. On 17 October the owner explicitly approved revised controls: start at or below 92 C for ten seconds, trigger stopping at or above 97 C. See `containers/strata-proposal/thermal-revision-approval.json`, `build-policy-approval.json` and `BUILD_POLICY_REVIEW.md`. Do not ask again for either policy decision. These approvals do not approve compilation/image pull, model loading, or waiving CPU-source validation, reader coverage, watchdog/stop testing, disk/download limits, or final build-workload approval. Historical drafts are preserved; effective controls are resolved from both hash-bound receipts. The refreshed source-only candidate is recorded in `build-candidate.json`; `build_preflight.py` checks it without starting Docker or reading sensors.

The historical apt/pip compiler recipe is superseded, not an execution candidate. Prepare the offline successor in `containers/strata-proposal/offline-build-candidate.json` for final review: staged verified CMake/Ninja, network=none, read-only root/input and bounded tmpfs. Its filesystem limits are proposed, not activated/approved. Tools have not been executed and the CUDA image remains unpulled. See the offline section in `containers/strata-proposal/README.md`. The bounded artifact collector now connects to `controller_session.py` and a separate synthetic watchdog; three native fake-worker cases pass, including stopping during blocked export and persistent fault/restart rejection. `offline_target.py` freezes the current proposal matcher for future admission. The production target, live CPU admission and model launch remain disabled; real reader validation, fixed live FAULT storage, image readiness and final workload approval are still required. A saved-export receipt does not replace confirmed stopping. These changes do not activate new policy or permit a real build.

Image preparation update: `image_plan.py` verifies the public pinned CUDA
manifest/config and records exact layer payload and proposed disk budgets.
A tiny cached-Python read-only probe observed host/guest headroom; the active
VHD mapping and hard import limits remain unconfirmed. No image layer was
fetched/decompressed/imported and no staging approval exists. Download/import,
compilation and model launch remain disabled. Maintain the Done/Left checklist
in NEXT_STEPS.md. The bounded acquisition kernel and registry transport now pass
22 new synthetic/mocked tests and three on-disk fake-byte cases. stage_pinned
remains blocked before any transport/path creation. Bounded expanded-stream/
diff-ID verification passes synthetic tests without tar extraction. Windows
job assignment is now atomic at process creation, with kill-on-close ownership
and a native abrupt-owner-death proof. local_worker.py is the single CLI:
status, rehearse, probe-cpu, prepare-task, collect, cancel and a blocked run-task.
Its full rehearsal passed image staging, connected CPU-feed/controller fake-build
export and an actual OpenCode edit against scripted replies; originals stayed
unchanged and all workers stopped. 162 proposal tests pass. No real image layer,
compiler or model ran. The passive reader adapter preserves unvalidated/unknown
channels and is integrated into the rehearsal controller. Its ordinary real
probe recorded administrator-access-required; the first Windows consent launch
was canceled. The owner then requested a retry and approved the prompt. The
hash-checked retry collected ten passive real readings (95,87,81,77,74,75,75,78,
75,78 C) in 9 s with 8-31 ms queries and confirmed reader stop. Evidence is
.runtime/compiler-guard/99766c3642bd4773af3121e5595e3631/probe-result.json.
The owner reported Armoury values 78,73,67,82,93,95 C after this probe. The ranges
overlap, but the observations have no paired timestamps and establish no offset
or firmware freshness bound. The passive comparison step is complete; do not
request another manual comparison without a new discrepancy. G-Helper's public
AsusACPI.cs independently labels endpoint 0x00120094 as CPU temperature and
uses DSTS minus 65536, corroborating meaning/decoding. Source admission review
is now complete for an explicit owner acceptance decision; no source flag or
workload approval was activated. See the admission milestone below.
Work next in two substantive milestones: approved image/build readiness and
one capped build, then approved real runtime/task integration. Stream byte caps
do not prove bounded Docker import disk allocation. No policy was activated.

CPU-source/build admission milestone: see FIRST_BUILD_REVIEW.md in the proposal
directory. The source is qualified for one CPU-build acceptance decision, with
firmware freshness/calibration explicitly not guaranteed. build_admission.py
compares all 6,001 source files to the pinned ZIPs and rechecks all 4,161 staged
tool files. first_build.py wires the real reader, independent controller, fixed
one-attempt namespace, emergency stopping and export behind exact approval.
Raw frames remain unvalidated/unknown; a permitted copy is qualified only after
explicit source/workload acceptance. No approval exists. 180 proposal tests and
three re-run native dummy-controller cases pass. No real build/model ran.

Selected offline proposal is c47d018e42244443a72bf166081da9c4, SHA256
c6e632e6d21f02c70f0e27b37190afa0e221a9c083501a8dac7b85e33f0dc9a0;
the previous proposal remains intact. Ready-file publication is atomic.
First-build review SHA256:
a587cd09a408fd2053a18a6dc263aced51d789b57d2254999f605ee97b9650c3.
Use local_worker.py review-build --check-environment for exact current gates.

WSL policy update: the owner explicitly approved applying temporary WSL2 limits
of one CPU, 6 GiB and swap=0, restarting Docker/WSL and verifying. The exact
wsl-build-limits.proposed bytes were exclusively created at
C:\Users\yaki_\.wslconfig after recording prior absence and idle Docker/WSL.
Docker stopped, WSL shut down and Docker restarted. Effective values are one
CPU, 6,215,266,304 usable bytes and zero guest swap. Probe exit/removal confirmed.
Evidence is .runtime/wsl-policy/8c26adaaf9a447df9af27320745e14d4/verification.json;
approval is containers/strata-proposal/wsl-policy-approval.json. Do not ask for
that policy/restart approval again. Limits remain temporarily active; preserve
owner edits and restore prior absence only after checking the exact file hash
when restoration is requested or agreed in workload cleanup. This global VM
envelope is separate from the one-CPU/4-GiB compiler and covers all WSL2 distros.
Fresh actual values still need checking before work. No image/build/model
permission was granted. The build runner never pulls/loads images.

181 proposal tests pass, including status detecting configuration drift and
keeping saved resource observations separate from workload permission. The
disabled first-build packet was refreshed only for this status-code change;
the old packet remains preserved. No numeric build policy changed.
The older 8187e5fd snapshot remains history. The guarded image milestone is now
complete: image_admission.py and image_stage.py connect exact source/image-policy
acceptance, a real reader, durable one-attempt claim, Windows-owned worker and
bounded acquisition/stream-verification kernels. Windows job affinity restricts
the worker to one logical processor, 128 MiB committed memory and one process,
queried before creation; multi-group ambiguity fails. An independent liveness
thread stops the job if the monitor loop stalls, including blocked child I/O.
Owner death uses kill-on-close. Immutable start records avoid child reads of
mutable state during Windows replacement. Stop precedes fault-journal I/O;
unconfirmed stopping or reader exit never becomes success. No automatic retries.

198 proposal tests pass, plus 14 connected native synthetic cases at
.runtime/guarded-image-rehearsals/394e5fe82a094d7f8f66d2067f032f1d/result.json.
Fake baseline/deadlines are shortened; unit cases exercise full ten-second
real-format baseline and 97 C faults. Every started worker exited, every restart
was denied; deliberately failed reader close stayed FAULT. The full CLI rehearsal
passed image staging, dummy build/export and scripted-API OpenCode in about 74 s:
.runtime/local-worker/daa4aa0769b84700be2e9bd45c2a1ec5/result.json. Original files
were preserved and all workers stopped. An earlier dummy-suite publication fault
after cleanup is retained; immutable per-case progress receipts fixed repeated
Windows final-result replacement. No safety policy/workload retry was enabled.

Exact image operation ready for owner approval:
861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323,
under .runtime/guarded-image-review/<sha>/review.json. See the proposal directory's
IMAGE_PREPARATION_REVIEW.md. CLI: prepare-image, review-image, rehearse-image,
run-image and cancel-image. The no-approval real command was checked: exit 3,
IMAGE_STAGING_NOT_APPROVED, no reader/process/socket/live claim. The actual
image-stage-approval.json is absent; the template is disabled and not authority.
The packet binds helpers, interpreter and exact immutable image descriptors.

Only explicit approval plus fresh admission remain for the acquisition scope:
3,951,095,908 pinned bytes, 5-GiB accepted bodies, 16-GiB expanded stream ceiling
without extraction/import, 7,918,969,032-byte retained namespace, 20-GiB host
reserve, one attempt and 1,800 seconds across both phases. Propose the same
92/97 C values and ten-second baseline for this image-only scope; unknown throttle
remains null. Build-only source/unknown-throttle approval is not automatically
extended: the owner must explicitly accept the image policy/source limitation.
No additional manual sensor comparison is needed. Windows administrator access
is required for the live ASUS reader; the runner never self-elevates. Import
keeps separate backing-volume/disk/stop review and approval. No real image
download, stream expansion, import, compilation, model or GPU workload has run.

## First approved live image attempt outcome

The owner explicitly approved the one image download/verification attempt under
the reviewed limits and accepted the image-scope source limitation and unknown
throttle status, keeping import/build/model disabled. The actual receipt now
exists at containers/strata-proposal/image-stage-approval.json, bound to unchanged
review 861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323.
Do not ask for that same policy decision again or treat the receipt as permission
for retries. The one attempt was consumed on 17 October at 14:48:24-39 UTC.

Session 3487a42f960b47f887ddcada151a269a under .runtime/guarded-image-stage/ is
latched FAULT IMAGE_WORKER_FAILED, worker detail HTTP_FRAMING_INVALID. CPU
baseline passed: 12 real samples 92,91,80,91,83,83,79,81,78,85,82,82 C over 11 s,
maximum query 47.6 ms, hardware throttle null; raw source flags were preserved.
Registry authentication response framing failed before accepted auth/blob bodies:
both counters zero, no completed blobs, empty cache, no stream expansion/import.
Exact rejected header condition was not retained and must not be guessed.

The worker exit and reader stop are confirmed; CLI exit 3. The fixed UAC runner
completed, cached read-only swap preflight removed its container, Docker inventory
empty and pinned CUDA image still absent. No firmware/power/config changes,
compilation, model or GPU workload occurred. No alternate download, auth-request
retry, reset or helper modification followed failure. All live receipts and the
frozen packet remain intact; WSL limits remain active.

Read containers/strata-proposal/IMAGE_STAGE_RESULT.md for evidence and next work.
Raw reader frames are .runtime/compiler-guard/9fa838d2ad494e60850f63a3948b26fd/;
swap proof .runtime/image-storage/f66b023abd464e22a39ab95f758ec43d/result.json;
admin launch evidence .runtime/guarded-image-launch/. Diagnose the precise auth
framing condition and rehearse compatible bounded transport handling before
presenting a new concrete recovery/attempt for authorization. Preserve the
consumed namespace; no second attempt is currently authorized. Existing build/
model/import approvals are still absent. No commit unless requested.

## Current authentication recovery checkpoint

The diagnosis/correction milestone is complete. See
containers/strata-proposal/IMAGE_AUTH_RECOVERY_REVIEW.md. Current endpoint headers
are HTTP/1.1 chunked without Content-Length, reproducing the old parser error;
the original failed response headers were not recorded. Auth now accepts bounded
chunk decoding or its prior Content-Length form; blob framing stays strict.
213 proposal tests and 17 native guarded cases pass. A bounded live auth-only
check passed with 5,481 bytes, zero blob requests and no retained token/body.
No image attempt, import, compiler or model ran during the correction.

The old FAULT and all 12 live files remain unchanged. Before editing, all 42
approved helpers plus the old review/approval were archived at
.runtime/image-recovery/8de46ce61487484694d473faf9f9bb29/ and hash-bound.
Current review: 2f703f5a6b0b17eb9b2005a8d90275237532e9931cdb63ecbed116944c762c30.
One fixed successor .runtime/guarded-image-stage-recovery-1/ remains unused.
The separate image-stage-recovery-approval.json is absent; its template is
disabled. The old approval cannot authorize a new attempt. No reset, automatic
retry or arbitrary namespace option exists. Preserve all earlier evidence.
The prepared run-recovery-approved.ps1 launcher has NOT run. Next: obtain the
owner's approval for this exact new acquisition/verification attempt under the
unchanged image limits. Existing image-source/unknown-throttle acceptance remains
recorded; do not ask for those policy decisions again. Import/build/model remain
disabled and need their own later approvals. No commit unless requested.

## Approved recovery execution outcome (latest)

The owner approved the exact new image attempt. It ran once, 15:43:31-15:47:59
UTC. See containers/strata-proposal/IMAGE_RECOVERY_RESULT.md. All 12 compressed
blobs / 3,951,095,908 bytes passed size/hash checks and remain cached. Auth chunk
handling worked (65,771 accepted auth bytes; categorical observations only).
Expanded-stream verification did not complete: SENSOR_FEED_ERROR, CLI exit 3.
Worker and reader stopping confirmed; worker reported GUARD_PERMISSION_LOST.
The successor is now consumed and latched FAULT, session
82dc1b816889471f98fd25ee8d31ea95. Its approval file exists and is spent; the
previous checkpoint's unused/absent statements describe pre-execution only.
Neither approval authorizes another attempt or reset. Preserve both faults,
cache, reader frames, launch receipts and reviewed helper snapshots.

Raw reader directory .runtime/compiler-guard/746421aeb6f34c85b7dcd3a837cda5f7/
contains 262 frames, 261 consumed; 72-96 C, zero frame errors, max query 30.3 ms.
The last raw frame is 95 C with substantial declared coverage remaining. The
generic exception hides its precise reason and reader exit status; do not infer
overheating or a physical sensor defect. Next work: offline feed/lifecycle
diagnosis/tests and a concrete separately approved retained-cache verification
recovery. Do not run more real verification or download in this consumed attempt.
Docker inventory empty; image absent; import/compilation/model remain disabled.
Existing WSL limits/settings and original fault evidence remain unchanged.
No production helper was changed this turn; no commit unless requested.

## Latest offline sensor-feed / cache verification checkpoint

User authorized offline diagnosis/fixes/testing and recovery preparation only.
No new live sensor reading, actual downloaded blob-body read, download, import,
compilation, model or GPU workload occurred this turn. The exact historical
failure remains unproved: all 262 saved raw frames replay cleanly and no matching
event appeared in the bounded historical Application log window. Do not claim
overheating, memory exhaustion or a physical sensor defect was diagnosed/fixed.

Corrected premature sequence/receipt commitment in cpu_feed.py; rejection now
leaves both unchanged. Monitor exceptions retain fixed reason, phase/operation,
reader exit code and numeric OS/Windows errors, journaled after stopping without
exception text/credentials. The original generic symptom is reproducible with an
injected reader exit at frame 262; this is a tested failure path, not its proven
historical cause. No error tolerance, reader restart, retry or policy change.

Before edits, 43 exact second-attempt approved helpers/review/approval and all
24 non-cache files plus 263 raw reader files were bound at
.runtime/verification-recovery/7ce23bea0a5848529330874891b08013/.
Preservation SHA e2a57b04d73a68991bdec3a3e2725e713577c2810a9e56a74918044c138ec6e9.
The first attempt/archive and second fault/cache remain unchanged. Both old
approval receipts are spent and must never be reused or reset.

The new cache-only operation is frozen at review
fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232.
See containers/strata-proposal/SENSOR_FEED_RECOVERY_REVIEW.md. It verifies the
retained config/all compressed layers and expanded diff IDs read-only, without
downloader fallback, copy, extraction/import or engine execution. Same existing
source/thermal decision and worker limits; no extra policy approval is needed.
One new execution approval IS needed: image-verification-approval.json is absent,
its template disabled. .runtime/guarded-image-verification-1/ is unused. No reset
or arbitrary namespace option exists. CLI: prepare-/review-/run-/cancel-verification.
The fixed run-verification-approved.ps1 launcher is prepared but has NOT run.
Missing-approval CLI test returned exit 3 without new namespace/process/reader.

232 proposal tests and 23 native cases pass (six cache-only + 17 shared guard).
All fixture workers stopped; cache unchanged/restart denied. No real sensor,
actual image bytes or network used. Evidence: .runtime/cache-verification-rehearsals/cbe674027e7a4c7b882dc4360e16ee23/result.json
and .runtime/guarded-image-rehearsals/8ba5bac91ae1463491e35e460e3b1cb7/result.json.
First-build packet a587cd09a408fd2053a18a6dc263aced51d789b57d2254999f605ee97b9650c3
is refreshed/disabled; sources/tools rechecked. Prior packets remain history.
Next: owner approval for one cache verification attempt with the historical cause
still unproved; preserve both faults and collect improved diagnostics if it fails.
Import/build/model remain disabled and require later scoped approvals. No commit.

## Latest approved cache-verification outcome

The owner approved review fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232.
It ran once, 16:14:35-16:15:54 UTC. Baseline passed; worker started; verification
did not complete. Specific fault: SENSOR_FEED_ERROR, OS error 13, read operation,
last consumed sample 70, pending sample 71. No Windows-specific error or reader
exit code available. The corrected diagnostics and sequence commitment worked.
Worker/reader shutdown confirmed; CLI exit 3; worker GUARD_PERMISSION_LOST.

Session 429518fb72464042bbaa0e960de2000d is consumed and latched in
.runtime/guarded-image-verification-1/. image-verification-approval.json exists
and is spent; its fixed administrator launcher has completed and must not rerun.
Preserve all THREE attempts, their reviews/approvals, raw reader data and code.
Both old attempts and 12 retained blobs are unchanged. No download, import,
compilation, model/GPU workload or hardware/configuration change occurred.

Raw reader .runtime/compiler-guard/278afc85eaec4534a0e41f091aa5e751/ has 71 frames,
73-96 C, zero frame errors, max query 42.9 ms. Sample 71 is readable after stop.
This localizes the current failure to sample-file access; sharing/publication is
a candidate, not a proven Windows sharing error or permanent ACL condition.
Do not retroactively claim this proves the earlier generic failure's cause.
Read containers/strata-proposal/VERIFICATION_RESULT.md. Structured observation:
.runtime/verification-recovery/7ce23bea0a5848529330874891b08013/verification-outcome.json.
Swap proof .runtime/image-storage/0d28dfadc09b41c1a229d823a91f4a29/result.json.
Docker inventory empty; pinned CUDA image absent. No cache-body read after stop.
Next: offline sample publication/read reproduction and correction, then a new
concrete verification review for approval. No automatic retry/reset or new
attempt authorized; no helper changed during this execution and no commit made.
The exact 46 approved helpers/review/decision are already archived under the
same verification-recovery directory as verification-approved-helpers/ and
verification-approved-review.json / verification-approved-decision.json.
verification-code-preservation.json binds these snapshots plus the current
attempt and raw reader file trees. Preserve them; do not overwrite or recreate
these archives on the next turn.

## Latest sample-access correction and recovery checkpoint

User authorized offline reproduction/fix/testing and preparation of another
verification only. No live sensor, actual downloaded blob-body read/verification,
download/import/compiler/model/GPU workload or policy/configuration change ran.

Reproduced the exact errno-13/no-winerror signature natively: a complete visible
frame remains under a publisher DELETE-access handle, so Python's ordinary read
fails until that handle closes. The fix uses read-only CreateFileW with
SHARE_READ|SHARE_DELETE and NO SHARE_WRITE, open-existing/no-reparse; one bounded
read, handle/path identity/size/write-time/link checks. No retry, ACL change,
error tolerance or stale-data substitution. 64 held-publication cycles pass;
legacy fails all 64; handle count unchanged. True writers/exclusive holders
still fail with native Windows error 32. This establishes a matching mechanism,
not the historical handle owner or cause of the older generic failure.

First heartbeat publication also now renames a complete initial byte into place,
closing an empty-first-file window. Empty/regressed pulses still fault and lease
budgets are unchanged. A failed earlier synthetic case is retained at
.runtime/cache-verification-rehearsals/9d2aae9636d54657a4a135b665e3f060/; no live
attempt was reset or retried to make tests pass. Final 245 tests and 24 guarded
native cases pass (seven cache-only, 17 shared), plus 64 direct native cycles.
Evidence: .runtime/frame-access-rehearsals/27497b1748de4c3bbb6b9a926d19ae99/result.json,
.runtime/cache-verification-rehearsals/bc04472646db428a93cc9243e003d9ec/result.json,
.runtime/guarded-image-rehearsals/617b52930cdf494d930e839b3c4b631f/result.json.
All fixture workers stopped; no actual sensor/network/blob bodies/Docker used.

All three consumed attempts, their readings and exact 42/43/46-helper archives
are preserved. The third archive was checked BEFORE edits; never recreate or
overwrite it. Its verification-code-preservation.json hash is
4fe1bc1ef8fe9eae8673d63a83001ffbf3f33f63230041188fa060f2cdff1ada.
verification_admission now binds all three states/archives, latest session
429518fb72464042bbaa0e960de2000d, prior approvals and unchanged cache metadata.

Current unused verification review:
cd28c631f1e82edc58a4273ea9798009d566a5a46c36a942db260b860562254b.
See containers/strata-proposal/SAMPLE_ACCESS_RECOVERY_REVIEW.md. New fixed live
namespace .runtime/guarded-image-verification-2/ remains absent/unused; actual
image-verification-recovery-approval.json is absent, template disabled. Old
image-verification-approval.json is preserved and cannot authorize this packet.
Same CLI prepare-/review-/run-/cancel-verification; no arbitrary namespace/reset.
The prepared launcher at .runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d/run-verification-approved.ps1
has NOT run. Original launcher/completion remains spent. Missing-approval launch
must remain blocked before reader/preflight/cache bodies. Existing 92/97 C,
job/reader/time/WSL/source/throttle decisions remain unchanged; no repeat policy
approval is needed. The exact new one-attempt execution does need owner approval.
First-build snapshot a587... is retained/disabled but stale after these helper
changes; refresh when build prerequisites are ready, not as an image prerequisite.
No commit unless requested. Next: one explicitly approved retained-cache check,
then separate bounded import/build work; downloads/import/compiler/model stay off.

## Latest successful live verification checkpoint

Owner approved the immediately preceding exact cache verification request. The
one attempt ran 17:54:36-17:57:59 UTC under unchanged controls, review
cd28c631f1e82edc58a4273ea9798009d566a5a46c36a942db260b860562254b.
Session e21da7b06fdc4fab903af2efec885f54 in
.runtime/guarded-image-verification-2/ is COMPLETE, fault null, CLI exit 0.
Configuration + all 11 layers / 3,951,095,908 compressed bytes and 7,454,964,736
expanded bytes passed pinned size/hash/diff-ID verification. No extraction or
import; networkRequests=0. Worker/reader stopped. All 194 frames consumed,
73-96 C, zero frame errors, max query 94.2 ms, sensorFeedError absent. Raw flags
remain false and throttle null; existing scoped qualification only. The sample
access fix worked in this bounded live attempt; do not infer universal stability.

Three older faults/code/receipts/readings and retained cache are unchanged.
All FOUR claims, including this success, are consumed; no rerun/reset authorized.
Actual image-verification-recovery-approval.json exists and is spent. Its fixed
launcher has completed. No download, import, compilation, model/GPU workload,
WSL/power/firmware/fan/configuration change occurred. Docker inventory empty;
CUDA image absent. The cached read-only swap preflight stopped/removed, swap 0.

Read containers/strata-proposal/IMAGE_VERIFICATION_SUCCESS.md. Raw reader:
.runtime/compiler-guard/2a5cc9fcdcb940ac94d5a8d452d3e67e/. Swap proof:
.runtime/image-storage/f7b1d5e946fc47c886509fc0e94ece62/result.json.
Launcher/outcome at .runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d/.
Its verification-approved-helpers/ ALREADY contains the exact 48 approved helper
snapshots; verification-approved-review.json and verification-approved-decision.json
are saved there too. Never recreate/overwrite those archives. The bound code/
attempt/reader preservation record is verification-code-preservation.json,
SHA 23a48f19ab38b5b198ef9cc663f5457f57e7979a9ad87a4721ec0dcae2c7467f.
No production helper changed this execution turn, no extra post-stop blob-body
verification ran, and no commit was made.

Next milestone: prepare a concrete bounded Docker image-import review, proving
actual backing-volume/storage allocation controls, monitored resources, finite
deadline/independent stopping and cleanup. Stream verification does NOT prove
bounded daemon import allocation. Import is not approved. After approved import,
refresh the stale disabled first-build packet and seek exact CPU-source/workload
approval for one capped build. Existing numeric/source/throttle decisions should
not be re-asked; import/build/model scopes stay separate and disabled.
