# One useful Strata coding task: viability decision

Current owner direction, 20 October 2026. This supersedes the Fibonacci/input
ladder, threshold-stop policy for new coding scopes, and open-ended preparation.
The owner explicitly accepts crash risk and authorizes resource warnings rather
than temperature/RAM stops. Do not request that policy approval again.

## Deliverable

Fix the real negative-limit defect in `containers/worker/task_bundle.py` and add
regression tests in `containers/worker/test_task_bundle.py`. A negative limit can
currently reach `read(-1)`, reading the whole file before rejecting it.

Send Strata the relevant source and test conventions plus this behavior request:

> Reject negative byte limits before any filesystem access. Preserve valid reads
> and existing oversized-file rejection. Add regression tests demonstrating these
> behaviors. Change only the two selected files.

Strata supplies both implementation and tests. No solution line in its prompt,
hardcoded correct replacement, AST validator that encodes the expected fix, or
Codex repair of its answer. A bounded response format and mechanical translation
into OpenCode edits are allowed. Return a patch from a disposable workspace;
do not apply it to repository originals. Native tool calling is not a prerequisite.

Use existing Docker artifacts/guards, 16,384 context and up to 4,096 output
tokens. Supply relevant context, measure actual input, do not pad or truncate
away source to hit the former 512-token input target. No installs, rebuilds,
tuning, Hermes, MCP, UI, new readiness gate or context benchmark.

## Absolute budget: 30 minutes, including preparation

The clock starts with implementation of this task's handoff, not at model launch.
This documentation/policy alignment is not an executed coding experiment.

| Elapsed | Work and cutoff |
| --- | --- |
| 0-10 minutes | Adapt existing handoff for model-written edits to both files; freeze acceptance checks and fresh scope. If not ready by minute 10, fail and stop. |
| 10-25 minutes | One model request; startup, generation, OpenCode edits, patch collection and independently confirmed shutdown all fit in this phase. Reserve the existing five-second owned-stop allowance before its end. |
| 25-30 minutes | Validate the patch and report PASS/FAIL. No implementation repair. |

These are maximum allocations, not renewable timers. Bind the remaining absolute
time into controller, worker, model, reader and watchdog deadlines. Existing
longer Fibonacci lifetimes must not override this budget. No restart, retry,
continuation request, fault reset, silent extension or automatic next task.

## Resource policy for the new coding scope

Use `runtime_safety.viability_policy(base)` in the new scope, with that complete
policy bound into the review and activated identically in controller/watchdog.
The shared gate honors it; old/default policies remain strict for historical
scopes and CPU builds. Merely importing the module does not enable it.

| Reading | New coding behavior |
| --- | --- |
| CPU temperature >=94 C; GPU >=87 C | Warn and record trend; continue |
| CPU >=97 C; GPU >=90 C (former stop points) | Continue with warnings; no software temperature stop |
| Host used RAM >=30,720 MiB | Warn and continue, including a sustained crossing |
| GPU power >=100 W; VRAM used >=14,336 MiB | Warn and continue |
| Reported active CPU/GPU thermal throttling | Warn and continue; missing/invalid required telemetry still faults |

Rolling **30-second** observations expose current/min/max/mean, first-to-last
delta, rising/falling/steady direction, sample count and actual observed span.
A short window is identified as incomplete. Duplicate reused frames do not
count as new samples. Save a bounded current report every five seconds and final
observations with the result; retain existing raw telemetry. Neither spikes nor
sustained resource pressure trigger a resource stop. Trends are observations,
not a claim that a crash is predictable or prevented.

Do not raise physical limits, disable hardware protection, alter firmware/power
settings or change WSL/container CPU/memory/swap caps. Those caps remain real:
an OOM/process exit or hardware shutdown can still end the attempt. Preserve
deadlines, cancellation, ownership/isolation, AC requirement, valid/fresh telemetry,
leases, process-health checks and confirmed stopping. A resource warning is not
a fault; an actual failed process is. CPU-build policy stays 92/97 C.

## Pass/fail and decision

All required for PASS:

1. One real response yields the implementation and meaningful regression tests.
2. New regressions fail on the original and pass on the returned implementation.
3. Independent checks reject -1/-2/-65,536 before validation/open/read, preserve
   valid reads and oversized-file rejection. Existing task-bundle tests pass.
4. Patch applies cleanly and changes only the two selected files, without Codex
   correction. Repository originals and unselected files remain unchanged.
5. Owned containers/helpers are independently confirmed stopped. Everything,
   including preparation, validation and reporting, finishes within 30 minutes.

Any missing condition is FAIL. Preserve whatever output/evidence exists; do not
convert infrastructure failure into another preparation cycle. Recommend stopping
investment in this Docker approach on failure. A pass justifies considering one
further representative task; it does not authorize an automatic run.

Report actual paid input/output tokens for preparation, supervision and review
when available, including setup cost. Record unavailable measurements honestly;
do not substitute account usage percentages. Token savings remain unproven until
measured against a comparable direct-Codex task. Correctness alone is not savings.

## Authorization and handover

The warning-policy change is explicitly authorized by the latest owner message.
All nineteen previous model attempts and their approvals are spent. Use a fresh
namespace and decision for the new workload; never rewrite a historical approval
or reset its fault. Do not infer live execution from this offline policy update.
Honor any direct owner authorization for the new workload without asking again.
No new model run or patch application occurred during this documentation update.

Policy validation: 35 focused offline checks passed. They cover spikes/recovery,
sustained warnings, bounded rolling observations, fake connected watchdog
publication, unchanged deadline/monitoring stops and historical strict guards.
Thirteen pre-update documentation snapshots were hash-verified. These checks
are synthetic/offline evidence, not coding-task success or live thermal proof.

Read `AGENTS.md`, this file and `NEXT_STEPS.md` for new sessions. Older operation
reviews/results are historical evidence, not active next-step instructions.
