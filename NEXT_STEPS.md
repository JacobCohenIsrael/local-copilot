# Current checkpoint - 20 October 2026

**Next milestone: [one 30-minute useful coding experiment](VIABILITY_POC.md).**
This supersedes the Fibonacci/context ladder and threshold-stop approach for new
coding scopes. Read [AGENTS.md](AGENTS.md) first.

Done:

- Reused the proven build, Docker answer, tiny OpenCode patch and shutdown path.
  These are groundwork; useful delegation and paid-token savings remain unproven.
- Owner approved resource warnings, accepts crash risk and wants viability first.
  Added an explicit advisory runtime profile with rolling 30-second resource
  observations. Fixed deadlines, ownership, monitoring integrity and shutdown stay.
  Historical/CPU-build/manual-chat policies are not silently changed.
- Validation: 35 focused offline checks passed, including resource spikes,
  recovery, sustained pressure, fake-watchdog trend publication, deadline stops
  and historical guard behavior. No Docker/sensor/model workload ran. An old
  approval-refusal test now also accepts the legitimate consumed-operation
  refusal; no historical decision or evidence was reset.
- Replaced current handover instructions; previous documentation bytes are
  preserved under `docs/history/pre-viability-2026-10-20/` with an inventory.

Left:

- Implement the handoff for Strata-written implementation AND tests for the real
  negative-read-limit bug. Current adapter still encodes a fixed insertion and
  cannot count as success. Start the experiment clock when this work begins.
- Stop if preparation is not ready in 10 minutes. Allow at most 15 minutes for
  startup, ONE request, edits, patch return and independently confirmed shutdown;
  finish validation/report within another five minutes. No retry or Codex repair.
- Bind `runtime_safety.viability_policy(base)` and all remaining deadlines into
  the fresh review in both processes; preserve nineteen consumed model attempts.
  This policy/documentation update executed no model workload. Do not reuse an
  old approval or ask again for the already authorized warning policy.
- Report every acceptance condition as PASS/FAIL, elapsed time and per-task paid
  tokens when available. Missing direct-Codex comparison means savings unproven.
  On failure recommend stopping this Docker approach; no automatic next attempt.

The last historical workload was GPU90 Fibonacci: RAM stop at 30,757.53 MiB,
no complete answer, model stopped/PID 0 and all four helpers exited.
See its [sealed result](containers/model-runtime/FIBONACCI_GPU90_REVIEW.md).
No more Fibonacci, READY, synthetic coding or context-capacity tests are next.
Manual Docker chat belongs to a separate owner-created session.
