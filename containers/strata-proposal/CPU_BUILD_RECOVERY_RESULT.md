# CPU build recovery: execution result

18 October 2026. **Startup succeeded and compilation reached step 131/153, then
the supervisor stopped the build on a sensor-feed fault.** No final Linux Strata
artifact was exported. The stopped container and its logs are retained.

## Done

- Ran the owner's one approved CPU-only attempt against the imported CUDA image.
  Review: `b01b440e575209bb8c2fb629b18a0c4703301d5272acd950db2714b0f310ffc6`.
- The real Ninja version check passed with the pinned Kitware suffix. CMake
  configured successfully, and real C/C++/CUDA compilation progressed to 131/153.
  The previous startup defect is resolved for this native run.
- Kept one CPU, 4 GiB, one compiler job, 1,800-second deadline, network none and
  no GPU devices. Existing WSL, Docker Desktop, temperature and timing settings
  stayed unchanged. No download, import, model or GPU workload ran.

## Stop and diagnostic evidence

The watchdog latched `SENSOR_FEED_ERROR`. The final recorded ASUS query took
**1.0943863 seconds**, exceeding the existing **one-second** query budget.
The reader script exits after publishing a query over that budget. All 840 raw
frames remain preserved; values ranged from 85 to 96 C, below the 97 C stop
threshold. Raw sensor validation remains false and hardware throttle unknown.

The parent also recorded `TimeoutExpired`. Detailed monitor exception context
and the timed-out parent command were not saved by this version, so the generic
fault's exact exception and the cause of the query slowdown remain unconfirmed.
Do not infer overheating, a hardware defect or OOM from this failure.

Stopping was confirmed in **0.903 seconds**. Docker reports exit 143, no OOM,
PID zero, not running/restarting, and restart policy `no`. The launcher returned
3. All matching owned host processes, reader, watchdog and wrapper have exited.
`cleanupComplete: false` is intentional retained evidence, not an unconfirmed stop.

Retained container:
`dc93f3edba64a13a13a3213a2231c064ff15da3f62cf2a1dc38cc3eaf437fa66`.
Do not start, remove or reuse it without a separately reviewed recovery decision.

Automatic diagnostics saved 34,228 bytes of combined stdout/stderr with exit,
runtime and OOM details. The retained container also allowed a subsequent read-only
copy of its complete bounded log: 266,340 bytes. It includes the successful version
checks, configuration, compilation and interruption. No compiler failure is
established by the watchdog's interruption. Partial tmpfs build outputs are not
an exported or resumable Strata artifact.

Evidence lives beside the exact review under `.runtime/cpu-build-recovery-review/`:
`execution-result.json`, `execution-preservation.json`, `retained-container.log`,
Docker inspections/events and owned-process observations. The manifest binds the
attempt, 840-frame reader, launcher and capacity probe. All older attempts, code
snapshots, approvals, blobs and retained native-device evidence remain unchanged.

## Left

- Replay the final slow-query/reader-exit path offline and preserve precise
  monitor and parent-timeout context. Review timing policy separately if a change
  is needed; do not silently increase the one-second limit or weaken freshness.
- Prepare a new CPU-only build after that review. This attempt and approval are
  consumed: no automatic retry, reset, resource increase or model execution.
- After a successful build: prepare model runtime, obtain a real API answer and
  complete the first bounded OpenCode coding task submitted by Codex.
