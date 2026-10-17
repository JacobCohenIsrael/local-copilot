# Project checkpoint ג€” 17 October 2026

Goal: an on-demand Strata coding worker inside Docker, orchestrated by cloud
Codex first and Claude later. Keep tasks/context/files bounded and return patches
for review. Optional MCP, UI, tuning and historical TypeScript/JetBrains work wait.

Owner revoked account-usage tracking/reporting and usage-based pauses. Do not
check allowances. No task-owned workloads are running.

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
`.runtime/offline-build/836b14c728b047e695b24a48e6bf35fb/offline-plan.json`, SHA256
`bf8a31786ec53163124244d1e82813108fa0e2b240d77d79d5979036c5e7d2dc`.
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
Current helpers match; four blockers remain:

1. CPU-source validation: ASUS fixed status read works, but meaning/update
   coverage is not yet accepted as a safety feed; the reader emits
   validatedCpuSensor=false. Armoury 90ג€“95 C and read-only ASUS 95/95/94 C
   broadly agreed. These observations do not prove calibration/future freshness.
2. Live admission remains disabled. The offline-target matcher and controller
   are now implemented, with independent-process guarding, durable FAULT within
   each rehearsal namespace and output collection. Three native fake-worker cases
   pass, including safety stops while export is blocked. The real CPU reader is
   not connected/validated; the production target is rejected by Session and
   GuardedExport. Before enabling an approved build, use one fixed live state
   namespace, recheck all input/tool hashes and bind the final workload approval.
3. Dependency/image/storage readiness: tool staging is bounded and the offline
   compiler profile avoids downloads/root writes. Still bound/approve CUDA image
   staging and measure VM capacity; verify base GCC/CUDA/loader compatibility.
   The bounded artifact collector is implemented and synthetically rehearsed;
   connect it to the live controller before tmpfs unmount. The draft waits for
   acknowledgement within the same 30-minute deadline. Proposed filesystem and
   artifact limits need final review; no live exporter is connected yet.
4. Final executable workload approval, bound to current manifest/guard/reader
   hashes and tested stop behavior. No build/start command is enabled.

Next: validate CPU-source update behavior/reader coverage and prepare bounded CUDA
image staging plus host/VM disk-capacity checks. The image remains unpulled;
review/approve its concrete staging operation before downloading layers. Then
verify compiler/tool compatibility and connect the validated real feed to the
reviewed controller. Final build-workload approval is still separate; do not
launch the draft or rerun previously approved policy questions.

## Verified work and evidence

- Branch: feature/strata-container. Earlier checkpoint 1af84a5 contains the fake
  worker bundle flow and initial CPU-only controls. The next checkpoint includes
  the offline build preparation, bounded artifact collector and rehearsed safety
  controller described here. Use git log for its commit identity; no push or
  actual build/model execution is part of this checkpoint.
- Worker: 59 tests plus real pinned OpenCode in a capped, network-free Docker
  fixture using scripted API replies. Selected copy -> scratch edit -> confirmed
  removal -> bounded patch collection. Original files unchanged; no actual model.
  See containers/worker/BUNDLE_REHEARSAL.md and OPENCODE_ACTIONS.md.
- Proposal: 89 tests pass, including approval tampering/scope, real-shaped mock
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
