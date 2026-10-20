# Local Copilot: agent guidance

## Purpose and current direction (20 October 2026)

Prove Strata can do useful coding work alongside Codex with less paid supervision.
OpenCode edits selected disposable files; the supervisor returns a patch and
structured result and confirms owned shutdown. Claude support is later.

**Active milestone: [one 30-minute coding viability test](VIABILITY_POC.md).**
Fix the real negative-read-limit bug in `containers/worker/task_bundle.py` and
have Strata add regression tests in `containers/worker/test_task_bundle.py`.
Strata receives source and behavior requirements, supplies implementation and
tests; Codex stages, validates and reviews without supplying/repairing the fix.
The previous fixed-guard adapter does not satisfy this contract.

- Maximum 10 minutes handoff preparation, 15 minutes execution including startup
  and confirmed shutdown, 5 minutes validation/report. One request, no retry,
  restart, continuation, fault reset or deadline extension. Not ready by the
  preparation cutoff is failure, not permission for more infrastructure work.
- All acceptance conditions in VIABILITY_POC.md must pass. On failure recommend
  stopping investment in this Docker approach. On success consider one further
  representative task, with no automatic batch. Token savings require comparison;
  record actual per-task paid input/output when available, never invent savings.
- Use 16K context/up to 4K output with relevant source, no padding. The old 512-input
  target and Fibonacci/doubling ladder are superseded. Do not repeat READY/toy
  tests. Hermes/64K, tuning, sensor research, private engines, MCP and UI are deferred.
- Documentation/policy alignment is offline work, not an executed coding attempt.
  Start the 30-minute clock when implementing the task handoff; include all its
  preparation. Do not restart that clock across chats.

## Owner-approved resource warnings

Latest owner direction explicitly accepts crash risk and replaces software
resource stops with warnings for the NEW coding viability scope. Do not ask
again for that policy change. Use `runtime_safety.viability_policy(base)` and
bind the complete policy to the fresh scope in both controller and watchdog.

CPU >=94 C, GPU >=87 C, used RAM >=30,720 MiB, GPU power >=100 W and VRAM
>=14,336 MiB warn and continue. CPU 97 C/GPU 90 C are no longer stop points in
this profile; reported active thermal throttling also warns. Observe rolling
30-second trends (current/min/max/mean/delta/direction/actual span), report every
five seconds and retain raw telemetry. Neither spikes nor sustained resource
crossings stop this scope. This is advisory monitoring, not crash prevention.

Keep fixed deadlines, cancellation, fresh/valid telemetry, leases, AC requirement,
isolation/ownership, file/context/output limits, process-health checks and owned
shutdown. OOM/process failure still ends the attempt. Keep physical protections
and existing WSL (one CPU/6 GiB/no swap) and container limits (model one CPU/4 GiB,
worker 0.5 CPU/512 MiB). No firmware/power/fan changes, extra readiness gate,
download, rebuild or automatic tuning. CPU-build policy remains 92/97 C.

Do not retrofit this profile into consumed historical scopes, frozen sources,
manual chat (separate owner session), simulator or CPU-build approvals. Shared
runtime defaults stay strict for old scopes; the new coding scope must explicitly
select the advisory profile. Do not present it as already exercised live.

## Current evidence and authorization

- Linux CPU build 153/153; real READY answer; tiny OpenCode pilot returned a
  113-byte patch with confirmed shutdown. Useful coding delegation remains unproven.
- Nineteen model attempts consumed. Fibonacci eventually passed once; subsequent
  doubled-input scopes stopped at historical GPU75 and then RAM30 limits. Latest
  GPU90 run: HOST_RAM_HIGH at 30,757.53 MiB, GPU peak 64 C, no response/evaluation;
  model 137/PID 0, four helpers exited. See the historical
  [GPU90 review/result](containers/model-runtime/FIBONACCI_GPU90_REVIEW.md).
- Every executed approval is spent. The latest owner message authorizes the new
  warning policy. Use a fresh workload decision/namespace for the new task and
  honor direct owner workload authorization without requesting it again. Never
  reuse old approvals, reset faults or claim an offline test is real inference.
- Preserve `.runtime/`, cached blobs, raw readings, failed scopes, exact executed
  sources and retained containers. No deletion/reuse/detach of the old bare disk
  or global Docker/WSL stop. Original installations/models/configurations stay intact.
- Historical firmware/calibration/CPU-throttle limitations remain documented;
  aggregate RAM attribution and general native tool calling remain unproven.

## Working conventions and handover

Read this file, [VIABILITY_POC.md](VIABILITY_POC.md), then
[NEXT_STEPS.md](NEXT_STEPS.md). They are current. Dated operation reviews/results,
old handoffs and [pre-pivot snapshots](docs/history/pre-viability-2026-10-20/)
are evidence, not active instructions. Never inherit their pending approvals or
Fibonacci/context ladders. Update one current checkpoint instead of appending logs.

Main CLI: `python -B local_worker.py`; `status` reads recorded state only.
`npm start` is the independent TypeScript simulator. Use focused offline checks
for changed guards/worker behavior; do not rerun unrelated suites or live probes
as preparation. Distinguish offline checks from real execution. Report short
Done/Left bullets and actual limitations; do not track account usage limits.
The Ollama assistant and JetBrains plugin remain retired.
