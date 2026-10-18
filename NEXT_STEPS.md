# Project checkpoint ג€” 17 October 2026

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


Project purpose: Strata as a substitute for paid coding agents and a local
coding subagent that reduces paid-token use. The current milestone serves both.

Repository cleanup done: Rider/JetBrains plugin, Ollama assistant, setup/demo
scripts, assistant tests and old validation guide removed. The Node package
retains only the Strata supervisor simulator. AGENT.md records the active scope.

Current focus, 18 October 2026: complete the first working Strata-in-Docker helper task for Codex. See MVP.md for the short path and definition of done.

Done: Docker, model files, verified CUDA base blobs/build inputs, OpenCode Docker compatibility and disposable patch workflow, background monitoring/watchdog.

Left: Linux Strata build -> real container API answer -> one OpenCode edit submitted by Codex -> returned patch and shutdown. Stop adding monitoring/storage features before this proof. Normal Docker Desktop storage is approved for the first test; the exact combined import/build operation is ready for workload approval. Model runtime resources remain to be reviewed.

Historical checkpoint details below are preserved for reference.


Latest result, 18 October 2026: the native rehearsal ran once and reached FAULT before guest startup. Done: real CPU admission, fixed disk creation, owned Windows-to-WSL device bridge. Blocker: our checker rejects Docker CAP_-prefixed permission names; offline replay confirms the naming issue. Helper/reader stopped; the container never started. Preserve the consumed fault, unstarted container and unformatted bare attached disk; do not detach without proof or retry. See containers/strata-proposal/NATIVE_REHEARSAL_RESULT.md. Left: correct admission/never-started cleanup/error reporting offline and prepare retained-device recovery plus a new native attempt for review, then image import/build/task scopes.


Execution update, 18 October 2026: the owner approved the exact native rehearsal. All preflight bindings passed, but Windows canceled administrator launch before startup. No native attempt was consumed; no disk, sensor or engine started. Approval and launch outcome are preserved beside the exact review. Next resolve Windows administrator consent and launch the same unused attempt; no automatic relaunch.


Goal: an on-demand Strata coding worker inside Docker, orchestrated by cloud
Codex first and Claude later. Keep tasks/context/files bounded and return patches
for review. Optional MCP, UI and tuning wait. The Ollama assistant and
Rider/JetBrains plugin are retired and removed, not deferred work.

Owner revoked account-usage tracking/reporting and usage-based pauses. Do not
check allowances. No task-owned workloads are running.

Current milestone: retained image verification is COMPLETE. The owner selected
a separate store with an enforced disk cap. Store/engine control primitives and
connected synthetic lifecycle are implemented. The Windows-to-WSL bridge,
offline runtime qualification and admitted guest startup are now connected.
One exact native empty-engine rehearsal is ready for approval; live import is
NOT approval-ready. No new disk, private daemon or import started.
See containers/strata-proposal/NATIVE_REHEARSAL_REVIEW.md.
See containers/strata-proposal/IMPORT_STORAGE_REVIEW.md and
containers/strata-proposal/IMAGE_VERIFICATION_SUCCESS.md.

Owner requested larger chunks: deliver integrated milestones, not isolated
helpers. Entry point is `python -B local_worker.py status`; the full safe
rehearsal is `python -B local_worker.py rehearse`. Both emit structured JSON.

## Done

- [x] Connected owned Windows marker/WSL device mapping, runtime closure staging,
  guest startup, fresh owner lease, real CPU-monitor renewal and engine-wide
  fault shutdown/unmount proof. 320 proposal tests pass, including 25 new mocked
  native-path checks; fifteen synthetic lifecycle cases also pass. Staged 33
  installed runtime files (~174 MiB), executing none. Preserved all four image
  attempts and cache. Native rehearsal packet is frozen and its approval absent.

## Immediate remaining milestones

- [ ] Owner approval, then one native 128-MiB / 180-second empty-engine rehearsal:
  real CPU baseline <=92 C for ten seconds, stop >=97 C; explicit source/throttle
  and capsule-privilege acceptance. Test lease expiry and confirm full stopping.
- [ ] Review native evidence and connect a tiny OCI-load compatibility/identity
  check without running an image. Prepare exact retained-image import approval.
- [ ] Import into the separate capped store, then adapt the disabled build to
  that same isolated engine and obtain the build workload approval.
- [ ] Qualify model runtime separately, then run one bounded OpenCode task under
  Codex supervision. Optional MCP follows that end-to-end proof.

## Earlier completed work

- [x] Implemented fixed-VHDX API/property/nonce controls, overlapped cancellation,
  guest device checks, restricted engine-capsule configuration and owned stopping,
  independent lifecycle watchdog and latched faults. Fifteen connected synthetic
  cases passed; real VHDX/capsule/engine execution remains blocked. CLI has a
  separate isolation review/rehearsal; its native entry refuses before actions.
  Full proposal suite: 295 tests passed. See ISOLATED_CONTROLS_REVIEW.md for the
  exact frozen control packet and the remaining native integration gates.
- [x] Separate capped-store architecture selected; metadata-only review binds all
  four attempts and retained cache. Bounded OCI archive transport implemented;
  seven tiny synthetic transport cases and 262 proposal tests pass. Real import
  refuses before live access. No storage/engine/workload permission was created.
- [x] Docker installed; existing model/configuration data preserved.
- [x] Pinned Strata sources and Linux CMake/Ninja staged without execution.
- [x] Bounded OpenCode coding flow tested against a fake local API.
- [x] Supervisor/export connection tested with a separate watchdog, synthetic
  heat/heartbeat loss, persistent faults and confirmed worker removal.
- [x] CPU-only controls approved: <=92 C for ten seconds to start, >=97 C to stop;
  unknown hardware-throttle status may remain null for this build only.
- [x] Pinned CUDA image manifest/config verified, exact layer sizes locked, and
  host/Docker guest capacity measured. Download/import remain disabled.
- [x] Image-blob stager and restricted registry transport implemented and tested
  with synthetic bytes/mocked HTTP; verified cache reuse, retained partials and
  persistent fault/restart rejection. The real-download entry remains blocked.
- [x] Bounded gzip/diff-ID verification tested without extraction; separate host
  supervisor stopped stalled synthetic staging workers and preserved faults.
- [x] Windows process ownership covers abrupt supervisor death, including atomic
  job assignment at creation; native worker exit confirmed without PID reuse.
- [x] One CLI integrates staging, the CPU-feed/controller/export connection and
  real OpenCode against scripted replies. Full rehearsal returned a patch,
  preserved originals and confirmed all worker exits/removals in about 74 s.
- [x] CPU-source review complete for explicit acceptance with recorded limitations;
  all 6,001 source files matched to pinned archives, all 4,161 tools rechecked.
- [x] Production first-build admission/controller/export implemented behind an
  exact one-attempt approval; raw sensor data and existing controls preserved.
- [x] Temporary global WSL2 limits approved, applied and restart-verified: one CPU,
  6 GiB cap (about 5.79 GiB usable), zero guest swap. Prior absence and rollback
  evidence retained; no previous configuration was overwritten.
- [x] Guarded image acquisition/stream verification connected behind exact
  source/image-policy/workload approval. One durable attempt, live reader,
  monitor liveness thread, job ownership, metrics, confirmed stopping and faults.
- [x] Windows staging worker limited to one logical processor / 128 MiB / one
  process before creation, with queried limits and native effective-mask proof.
- [x] Exact image operation frozen for approval; 14 native connected synthetic
  cases and the full three-phase supervisor rehearsal pass.
- [x] 245 proposal tests and 24 native guarded cases pass; all test workers stopped.
- [x] Owner approved image-scope source/unknown-throttle policy and the exact
  image operation. It ran once: real CPU baseline passed, then authentication
  response framing was rejected before accepting payload. Worker/reader stopped;
  the single attempt is consumed and FAULT remains latched. No retry.
- [x] Authentication correction complete: the current endpoint returns chunked
  HTTP without Content-Length, reproducing the old parser's rejection. Bounded
  chunk decoding passes offline cases and one small live authentication-only
  check (5,481 bytes, zero blob requests, no retained token).
- [x] All 12 failed-attempt files remain unchanged; the exact 42 previously
  approved helpers, review and approval were archived before editing. One fixed
  successor is prepared behind a new, absent approval; no reset or retry ran.
- [x] Final refusal check passed before any new live namespace was created.
  Read-only Docker inspection confirms the resource envelope, no remaining
  containers and no CUDA image. Import/build/model remain disabled.
- [x] Owner approved the corrected image attempt; it ran once. All 12 compressed
  blobs (3,951,095,908 bytes) downloaded and passed size/hash verification.
  Expanded-stream verification stopped on SENSOR_FEED_ERROR. Worker and reader
  stopped; the second claim/fault and cache are retained. No retry/import/build/model.
- [x] Offline sensor-feed milestone complete: all 262 saved frames replay cleanly;
  the historical root cause is unproved because its exception was discarded.
  Corrected premature sequence commitment and added redacted diagnostics after
  stopping. Reader exit/sharing-error reproductions and guarded native cases pass.
- [x] Both attempts and the second reader's 263 files are hash-bound; its exact
  43 reviewed helpers were archived before edits. One read-only cache verification
  path is frozen, unused and blocked by a separate absent approval. No new sensor
  read, downloaded blob-body read, download/import/build/model execution occurred.
- [x] Owner approved the retained-cache verification; it ran once. Baseline
  passed and worker started, then stopped on permission denied reading sample 71
  (OS error 13). Worker/reader shutdown confirmed. No completed stream receipt;
  all three attempts are consumed and latched. Both old attempts/cache unchanged.
- [x] Reproduced the sample-file conflict natively: a completed frame under a
  held publisher rename/delete handle gives the old read errno 13. Corrected
  read-only sharing passes 64 publication cycles, while writers/exclusive locks,
  malformed/stale/replaced/linked/oversized frames remain rejected. No retry.
- [x] First heartbeat now publishes a complete byte atomically; no lease rule
  changed. The new guarded publication-window case passes. Three old fault states,
  reviewed code/approvals, raw readings and cache remain intact. A new fixed
  verification-only packet is ready, unused and blocked by a separate approval.
- [x] Owner approved the corrected verification; it ran once and completed.
  Configuration + 11 layers / 3,951,095,908 compressed bytes and 7,454,964,736
  expanded bytes verified. Worker/reader stopped; 194 clean frames, 73-96 C.
  No access error, download, extraction/import, compiler or model execution.
  Three old faults/cache unchanged; successful fourth claim is consumed too.

## Left

- [ ] Complete isolated import readiness: stable runtime, new capped device
  ownership/mount/write containment, cgroup enforcement and independent daemon
  shutdown. Prepare a small native fixture operation for approval before real
  import. prepare-import/review-import are DESIGN REVIEW ONLY; run-import always
  refuses. The later build adapter must reuse this engine/store.
- [ ] Finish native isolation integration: host-to-guest owned-device bridge,
  qualified dynamic runtime and real CPU/lease/bootstrap connection. Then freeze
  one small empty-engine canary for approval. Keep native controls and import
  disabled until that scope is concrete; do not repeat synthetic proof as native.
- [ ] Milestone 2: one approved capped CPU-only build. The global Docker/WSL
  envelope is active and retained image verification is complete. Prepare/approve bounded
  daemon import and storage limits.
  Accept the build-source limitation and exact compiler workload after
  prerequisites are ready. The implemented admission rechecks live baseline,
  coverage and inputs; compile once and collect output. Image transfer and full
  stream verification completed; import and compilation have not run.
- [ ] Milestone 3: first real Strata coding task. Review/approve model/runtime
  policy; connect exact tokenization, authentication, restricted networking and
  GPU monitoring; complete one bounded task with shutdown evidence. MCP follows.

CPU-access update: the owner requested another administrator launch and approved
the prompt. Ten passive readings completed successfully, 95 C initially then
74-78 C near the end; query times 8-31 ms, reader stopped. The owner reported
Armoury values 78,73,67,82,93,95 C: overlapping ranges without paired timestamps.
Passive comparison is complete; no repeat is needed absent a new discrepancy.
Source acceptance remains; this observation approves no workload.

The previous CPU-source/build review is preserved in
`containers/strata-proposal/FIRST_BUILD_REVIEW.md`. CPU-source qualification is
ready for explicit acceptance; no more manual comparison is needed. Production
admission is wired, not active. Last disabled snapshot SHA256:
`a587cd09a408fd2053a18a6dc263aced51d789b57d2254999f605ee97b9650c3`.
Its helper binding is now stale after the publication corrections; refresh the
disabled packet when verification/import prerequisites are ready. Source/workload
approval and CUDA readiness remain gates. The owner approved
and we applied one CPU / 6 GiB / swap=0 to C:\Users\yaki_\.wslconfig, after
recording prior absence and confirming no unrelated Docker/WSL workload.
Docker stopped, WSL shut down and Docker restarted. Actual values: one CPU,
6,215,266,304 usable bytes and zero guest swap. The compiler stays at 4 GiB.
These global settings affect all WSL2 distributions and remain temporarily active;
do not ask for this policy approval again. Preserve any later owner edits.
Evidence: `.runtime/wsl-policy/8c26adaaf9a447df9af27320745e14d4/verification.json`
and `.runtime/image-storage/348333bf6a0947dcad05b7725dfbfae1/result.json`.
The read-only probe exited and was removed. Status reports saved verification,
detects config drift and never treats an observation as live workload permission.

Next image scope is pinned-blob acquisition plus bounded stream verification,
without import. See containers/strata-proposal/IMAGE_PREPARATION_REVIEW.md and
disabled executable packet 861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323.
Source/policy acceptance, live process/reader guard and host CPU bounds are now
connected and tested. The owner explicitly approved this image-scope policy and
the one attempt, which has now run and failed closed. Approved <=92 C for ten
seconds / stop >=97 C, unknown throttle
remaining null, one attempt, 1,800 seconds across download/stream verification,
5-GiB accepted-body budget, 16-GiB stream ceiling, 20-GiB host reserve and fixed
7,918,969,032-byte retained namespace. The image-stage-approval.json receipt is
present; the template remains disabled. These decisions do not approve import,
compilation or model execution, or another attempt. See IMAGE_STAGE_RESULT.md.
Attempt 3487a42f960b47f887ddcada151a269a is consumed, FAULT IMAGE_WORKER_FAILED /
HTTP_FRAMING_INVALID. Accepted auth/blob bodies zero, cache empty, no streams
expanded; worker exit and reader shutdown confirmed. Twelve real readings
(78-92 C over 11 s) passed admission; hardware throttle stayed null. The exact
rejected HTTP header condition is unknown because headers were not retained.
Preserve .runtime/guarded-image-stage/ and the archived reviewed helpers. The
correction is now reviewed in IMAGE_AUTH_RECOVERY_REVIEW.md. Current packet:
2f703f5a6b0b17eb9b2005a8d90275237532e9931cdb63ecbed116944c762c30.
Its fixed .runtime/guarded-image-stage-recovery-1/ is now consumed under the new
image-stage-recovery-approval.json. Session 82dc1b816889471f98fd25ee8d31ea95 ended
FAULT SENSOR_FEED_ERROR during stream verification, with all compressed blobs
already verified. Worker/reader stopped; no completed stream receipt. Existing
numeric/source decisions remain accepted; neither spent receipt authorizes more
work. Raw reader .runtime/compiler-guard/746421aeb6f34c85b7dcd3a837cda5f7/ has
262 frames, consumed through 261, 72-96 C, no raw frame errors. Underlying feed
exception/reader exit status was not retained; exact cause remains unproven.

The sensor-feed correction/cache-only recovery is now reviewed in
SENSOR_FEED_RECOVERY_REVIEW.md, current packet
fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232.
CLI: prepare-verification, review-verification, run-verification,
cancel-verification. Fixed .runtime/guarded-image-verification-1/ is unused;
image-verification-approval.json is absent. One future worker will rehash the
retained config/compressed layers and expanded diff IDs without extraction,
copying, download fallback or import. Same 92/97 C, CPU/RAM/deadline limits.
Native evidence: .runtime/cache-verification-rehearsals/cbe674027e7a4c7b882dc4360e16ee23/result.json
and .runtime/guarded-image-rehearsals/8ba5bac91ae1463491e35e460e3b1cb7/result.json.
Archive/diagnosis: .runtime/verification-recovery/7ce23bea0a5848529330874891b08013/.
The owner then approved this exact cache verification; session
429518fb72464042bbaa0e960de2000d ended FAULT SENSOR_FEED_ERROR, with specific
permission denied on sample-file read (OS error 13), consumed sequence 70 and
pending sample 71. Worker/reader stopped; all 71 raw frames have no sensor error,
73-96 C. Sample 71 reads normally after stopping; sharing/publication is a
candidate, not a proved Windows sharing error or the old historical cause.
Actual approval image-verification-approval.json now exists and is spent.
The new verification namespace/launcher are consumed; do not reuse them.
Current outcome: VERIFICATION_RESULT.md. No further real verification is approved.

Offline sample-access correction is now complete: native held-rename publication
reproduces errno 13, while the read-only READ|DELETE-share consumer passes all 64
cycles without handle leaks. WRITE sharing is denied; genuine errors still fault.
The first heartbeat byte is also published complete, retaining all lease checks.
Current review: cd28c631f1e82edc58a4273ea9798009d566a5a46c36a942db260b860562254b,
SAMPLE_ACCESS_RECOVERY_REVIEW.md. Fixed .runtime/guarded-image-verification-2/
is unused; image-verification-recovery-approval.json is absent and its template
disabled. No sensor/new downloaded-blob body read or live verification occurred.
The new fixed launcher is under .runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d/;
it has not run. All three prior receipts remain spent; no reset or retry.
Evidence: .runtime/frame-access-rehearsals/27497b1748de4c3bbb6b9a926d19ae99/result.json,
.runtime/cache-verification-rehearsals/bc04472646db428a93cc9243e003d9ec/result.json
and .runtime/guarded-image-rehearsals/617b52930cdf494d930e839b3c4b631f/result.json.

Execution update: the owner approved cd28... and it ran once successfully,
session e21da7b06fdc4fab903af2efec885f54. Fixed verification-2 namespace is now
COMPLETE and consumed, not unused. image-verification-recovery-approval.json now
exists and is spent. No new run is authorized. Result:
IMAGE_VERIFICATION_SUCCESS.md. Raw reader:
.runtime/compiler-guard/2a5cc9fcdcb940ac94d5a8d452d3e67e/ (194 frames, no errors).
Snapshots: .runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d/verification-approved-helpers/
contains all 48 exact approved helpers; verification-code-preservation.json
binds helper/review/decision/current attempt/reader files. Preserve all four
attempts and the unchanged cache. Next operation is separately reviewed import.

The latest 17 connected native cases are in
.runtime/guarded-image-rehearsals/1f48e7371fb0465e829cc5bf70f59104/result.json.
The earlier 14-case results and their timing observations remain preserved.
These are tiny generated-byte/fake-frame observations, not physical guarantees.
The complete CLI rehearsal passed in about 74 s at
.runtime/local-worker/daa4aa0769b84700be2e9bd45c2a1ec5/result.json.
An earlier dummy-suite result publication failure is preserved; immutable
per-case receipts fixed its repeated Windows replacement issue. No workload
retry/reset or safety policy was enabled to make the rehearsal pass.

## Approval boundaries

- CPU-only build exception: unknown hardware throttle status may remain null.
- Approved temperature revision: <=92 C for ten seconds before admission;
  latch FAULT and trigger stopping on a reading >=97 C. One CPU, 4 GiB RAM,
  no extra swap/GPU, 128 processes, one compiler job, 30 minutes, no retry.
- Receipts: `containers/strata-proposal/build-policy-approval.json` and
  `thermal-revision-approval.json`. Historical proposals remain unchanged;
  `load_effective_controls()` verifies both hash bindings. Do not ask again
  for these decisions.
- These approvals do NOT authorize compilation, image pulls, model loading,
  GPU load tests, new drivers or firmware/power/fan/performance-mode changes.
  Prepare the concrete final build workload for owner approval after gates pass.
- Preserve D:\AI and model/configuration data. The earlier instant shutdown
  (Kernel-Power 41, bugcheck 0) remains unexplained; do not diagnose its cause.

## Source holder and offline compiler proposal

`containers/strata-proposal/build-candidate.json` identifies the source-only holder
`.runtime/strata-build/1c9c3253` with disabled build/model flags.
Manifest SHA256:
`ea5b063e3ebbacb3fea1f82d9b83f78b7502abc9d2b5bc1656514c4cbbf48804`.

Sources are Strata 296b59d2f73c8f04a805df29c2fa97655adace78 (v0.1.44.1)
and llama.cpp 3cf03257f219afbe7334045ff7c6a06ac68c627d. The refreshed package
uses existing verified archives, includes the current compiler helper and has
a disabled guard contract. No new downloads, image pull, upstream code execution
or compilation occurred. Original package 1537f5ec and its manifest are intact.
The CUDA 13 Ubuntu base remains unpulled. The historical networked apt/pip recipe
is superseded and not an execution candidate; missing staged source fails rather
than invoking a download.

`offline-build-candidate.json` selects the disabled offline successor:
`.runtime/offline-build/c47d018e42244443a72bf166081da9c4/offline-plan.json`, SHA256
`c6e632e6d21f02c70f0e27b37190afa0e221a9c083501a8dac7b85e33f0dc9a0`.
The earlier 836b14c7 proposal is preserved; the new helper publishes readiness
atomically. This does not execute the script or authorize compilation.
Its final filesystem/workload profile is not approved. It proposes network=none,
read-only root/source/tools and non-root execution; /work 2 GiB, /tmp 128 MiB,
/dev/shm 16 MiB, all sharing the same approved 4 GiB/no-extra-swap memory cap.
It removes apt/pip/setup.py from compilation; only the engine target is built.
Full compile fit is unknown: OOM/ENOSPC must fault without retries/cap increases.

Verified tool bytes are staged at
`.runtime/build-tools/ec73930b8fe5475296d70e1eacb4b065`: CMake 4.4.3 and Ninja
1.13.2, exactly 30,415,348 archive bytes / 76,349,964 extracted bytes (4,161 files).
No downloaded tool was installed/executed. `stage_build_tools.py` enforces locked
HTTPS URLs, no redirects/retries, exact size/hash, safe archive paths, 64 MiB
archive/256 MiB expanded budgets and a 512 MiB combined namespace limit with a
cross-process lock. The 20 GiB host free-space check is not a reservation or
Docker-VM capacity proof. A failed first Ninja-layout attempt is retained and
counted; its directory has no successful receipt and must not be used.

Run `python -B containers/strata-proposal/build_preflight.py` for the read-only
candidate/policy/helper check. It cannot call Docker, read sensors or start work.
Current helpers match. The controller/reader/export path is implemented and the
source evidence is qualified for review. Remaining prerequisites are concrete:

1. Explicit source acceptance and final workload approval bound to the generated
   review. No automatic validation flag, model scope or retry is granted.
2. VM limits are approved, applied and restart-verified at one CPU/6-GiB/no-swap.
   Recheck actual values before live work; existing compiler limits do not cap
   daemon import or Windows workers. No additional WSL policy approval is needed.
3. The exact pinned CUDA image is absent. Finish reviewed image acquisition,
   stream/import/storage controls and approval. The first-build runner verifies
   image/config/platform/diff IDs and fresh capacity; it cannot pull/import.
   Base compiler compatibility and build fit are validated only by the approved
   bounded attempt, with failures stopping rather than increasing limits.

Next milestone: complete real CPU/image/build readiness and deliver one approved
CPU-only build. The single-command integrated rehearsal and production admission
implementation are complete; image preparation and explicit approvals remain.
No image layers were fetched. Image/import and final build approval remain
separate; do not launch the draft or rerun approved policy questions.

## Verified work and evidence

- Branch: feature/strata-container. Latest committed checkpoint: 69aa403, offline
  build preparation and rehearsed guarded export. Image metadata/storage planning,
  the synthetic stager/expansion/process checks and this Done/Left checklist are new uncommitted changes; do not commit/push
  unless requested. No actual build/model execution is part of these checkpoints.
- Worker: 59 tests plus real pinned OpenCode in a capped, network-free Docker
  fixture using scripted API replies. Selected copy -> scratch edit -> confirmed
  removal -> bounded patch collection. Original files unchanged; no actual model.
  See containers/worker/BUNDLE_REHEARSAL.md and OPENCODE_ACTIONS.md.
- Proposal: 198 tests pass, including approval tampering/scope, real-shaped mock
  frames, stale/lost feed/controller, source/builder checks and disabled preflight.
  None of these tests validate actual sensor hardware or run a compiler.
- Bounded artifact collector: fixed non-root tar/touch transfer, named files only,
  exact metadata hash and ELF-header checks, per-file/wire/aggregate storage caps,
  shared deadline, identity/lease rechecks and acknowledgement only after saving.
  Nineteen unit tests plus two native cached-Python cases passed: 176 fake bytes
  saved/acknowledged/exit 0; bad metadata rejected without acknowledgement.
  Both removals confirmed. No compiler/model ran. Evidence:
  `.runtime/artifact-export-rehearsals/2a1c94a7c3d44fa8b43febcaf68a03ce/result.json`.
  Docker cp could not access tmpfs, so the collector uses fixed tar/touch execs.
  Its controller connection is now exercised with synthetic data (below); real
  CPU admission/global live state and CUDA-image compatibility remain pending.
- Controller connection: 17 new unit tests; three separate-process Docker cases
  passed with fixed fake files/temperatures, 0.5 CPU / 64 MiB / 16 processes,
  no GPU/network, 64 KiB tmpfs and a ten-second worker alarm after start. Each
  waits through the actual ten-second synthetic <=92 C baseline before starting.
  Success: 176 bytes exported, acknowledged, exited and removed. Synthetic 97 C
  and controller heartbeat loss: independent guard stopped/removed the worker
  while export was blocked; first FAULT persisted and reopening was rejected.
  Stop confirmations were 1.55 and 1.56 s from fault detection. Evidence:
  `.runtime/offline-controller-rehearsals/89d484304f1d4241a6bbb33b1ffdb094/result.json`.
  Clock gaps, journal failures, changed identity and daemon outages are unit-tested.
  No sensor hardware validation, compiler/model run, pull or policy change occurred.
- Image preparation: public pinned manifest/config (2,631 / 20,233 bytes)
  are checked into containers/strata-proposal and verified by SHA256. Linux/amd64,
  11 layers, 3,951,075,675 compressed layer bytes (3.68 GiB); with config the exact
  blob budget is 3,951,095,908 bytes. No layer payload was fetched or decompressed.
  Proposed ceilings are 5 GiB payload / 16 GiB expanded (expanded size unmeasured).
  Shared-volume planning includes cache/archive + containerd compressed/expanded
  storage, scratch and a 20 GiB host reserve: ~49.1 GiB Windows free / ~25.7 GiB
  guest free. This is headroom planning, not reserved space or an enforced import
  quota. Read-only probe observed ~1.24 TiB host / ~0.93 TiB guest available.
  Active VHD mapping remains unconfirmed; default-location file existence alone
  is insufficient. Probe container removal/exit confirmed, evidence:
  `.runtime/image-storage/2121628011b54300982aa6433d1cf1d8/result.json`.
  `image-storage-observation.json` binds the receipt hash without granting approval.
  `image_plan.py` and build_preflight include the disabled plan/capacity snapshot.
- Image stager: image_download.py streams digest-locked blobs to owned partial
  files, verifies exact size/hash, flushes and promotes to cache under a writer
  lock. Warm-cache bytes are rehashed before reuse; changed/hard-linked cache,
  disk shortage, deadline, permission loss and bad HTTP framing fault without
  refetch/retry. Failed partials and receipts remain; no reset/import/decompression
  API exists. Registry transport is tested with mocked auth/HTTP/CDN replies;
  only fixed NVIDIA/CUDA scope and one approved CDN redirect are allowed, without
  forwarding bearer credentials. Auth payloads count against the shared budget.
  A live call to stage_pinned always fails before transport/path creation.
  Twenty-two new unit tests pass. Three on-disk synthetic cases passed: 78 bytes
  staged, warm cache verified without refetch, wrong hash/extra byte rejected,
  fault preserved and restart refused. Evidence:
  `.runtime/image-blob-rehearsals/804006c5eaf9470b98410b22a6833ff4/result.json`.
  No real network, image-layer transfer, decompression, import, compiler or model
  operation occurred. Blocking OS I/O still requires independent supervision.
- Expanded verification/process rehearsal: image_expand.py rehashes compressed
  bytes and hashes the uncompressed stream in <=64 KiB output chunks; per-layer
  and aggregate byte caps, CRC/truncation, diff-ID mismatch, cancellation and
  deadlines are tested. Trailing bytes/concatenated gzip members fail closed;
  actual layer compatibility is untested. No tar is extracted; stream limits
  do not bound Docker disk allocation or sparse-file expansion.
  Twenty new unit tests pass, including lease clocks, unconfirmed stops and
  stopping despite journal failure. Six separate-host-process cases passed:
  one 130-byte synthetic gzip -> 10,240 stream bytes; blocked read/expansion,
  lost controller lease, cancellation and synthetic GPU heat all latched FAULT,
  stopped the owned child and rejected restart. Stops took 0.11-0.13 seconds
  from detection. No real GPU/sensor/network/Docker call occurred. The supervisor
  remains alive in these cases; supervisor death/OS failure is not covered and
  production remains disconnected. Parent state.json is authoritative even if a
  killed child's staging receipt remains unfinished. Evidence:
  `.runtime/image-process-rehearsals/ccbc807277ad445997af88bcc5bc9c76/result.json`.
- New native quota proof passed with the cached Python image only, 0.5 CPU,
  64 MiB RAM/no extra swap, no network/GPU and a four-second alarm. It reached
  ENOSPC at 65,536 bytes, proved read-only root and parsed the offline shell
  script without executing it. Container removal was confirmed. Evidence:
  `.runtime/offline-quota/27b244a65d3f4ebcb58459c9f89be342/result.json`.
  This scaled proof does not establish real compiler fit or image compatibility.
- Five native sleeping-worker Docker shutdown cases passed; confirmed exits
  1.57ג€“1.62 s. Identity is pinned, Docker calls share a five-second stop budget,
  removal is separately bounded, and unconfirmed stops stay unresolved faults.
  No task-owned containers remain. See containers/strata-proposal/CPU_COMPARISON.md
  and .runtime/compiler-guard/verification-c1845cf5fb9143bfbe0b45b461203cd8.json.
- Real three-sample probe: .runtime/compiler-guard/7e30d8f6fad24e17afeff52dca1458e7.
  The reader precision fix came afterward and passed description-only checks.
  Reader coverage is 1,920 samples/32 minutes; default three-sample probes cannot
  admit a build. No long hardware sampling session has been validated.

Detailed policy/history: containers/strata-proposal/BUILD_POLICY_REVIEW.md.
Do not describe these preparations as a completed Strata runtime or live supervisor.

## Integrated milestone evidence

- Full CLI rehearsal: `.runtime/local-worker/802fc15c847d47f4929a4e2caeb12b6a/result.json`.
  Image phase 4.34 s, controller/export phase 52.65 s, OpenCode phase 7.20 s.
  All phases passed; patch changes VALUE 1 to 2 in a disposable example.
  No real CUDA image, compiler, Strata/model or GPU load ran. Rehearsal state is
  separate from production authority; a SHA-bound latest pointer cannot enable it.
- Connected CPU-feed adapter/controller native proof:
  `.runtime/offline-controller-rehearsals/71e3ffd55d5743fcb77cb88514454d96/result.json`.
  Three Docker cases passed; hot/lease-loss during blocked export stopped in
  1.59/1.55 s. No fake sensor frame can be accepted by the real adapter.
- Final atomic Windows job proof:
  `.runtime/image-process-rehearsals/bbed7f775b534d17be0e30a33ddd81a2/result.json`.
  Seven cases pass, including abrupt owner death with confirmed child exit in
  about 4 ms and restart rejection for the unfinished journal. Creation uses the
  Windows job-list attribute, avoiding a create/assign orphan gap. Job handles
  are unnamed and non-inheritable; exit witnesses have query/wait rights only.
  Memory/process limits apply only to the new owned tree, not device settings.
  This supersedes the earlier living-supervisor-only limitation above. OS/driver
  failures and real production admission remain outside that proof.
- Passive ordinary-access observation:
  `.runtime/compiler-guard/a1d41bd6858a48b887e128073b279be5/probe-result.json`.
  Source access was denied; temperature stayed null, validatedCpuSensor false,
  throttle null, reader stopped. Administrator launch 7343f061916741fc81f0797fb3a7f34e
  was canceled at Windows consent; it collected no sensor data. Do not retry
  automatically or treat the denial as evidence of a safe temperature.
- Owner-requested administrator retry succeeded:
  `.runtime/compiler-guard/99766c3642bd4773af3121e5595e3631/probe-result.json`.
  Launch folder `43b26afc371048e6b5c4fc8e9f63b1d4` binds helper/source hashes and
  records exit code 0. Ten real frames numbered 1-10 span 8.996 s, intervals
  0.974-1.020 s. Temperatures: 95,87,81,77,74,75,75,78,75,78 C. Query times:
  7.69-31.35 ms; no returned query error; readerStopped=true. The source produced
  changing values in this short observation, not a proven hardware update bound
  or sustained coverage guarantee. validatedCpuSensor remains false and hardware
  throttle null. The run cannot supply a ten-second cool admission baseline.
  No model/compiler/container, GPU load or device/policy setting change occurred.
  The owner subsequently supplied Armoury CPU values 78,73,67,82,93,95 C.
  Ranges overlap, but no exact offset/hardware update bound can be inferred.
  G-Helper's public AsusACPI.cs independently corroborates CPU endpoint
  0x00120094 and DSTS minus 65536 decoding; see CPU_COMPARISON.md. No software
  was installed/executed from that source. Carry this evidence into source/build
  admission review instead of repeating passive/manual comparison steps.
