# Local Copilot: agent guidance

## Purpose and focus

Use Strata in Docker for local coding, both directly and as a bounded helper for
Codex (Claude later). OpenCode is the coding worker; the supervisor stages selected
files, returns a patch and structured result, and stops the local components.

Build on the proven Docker answer and one-file coding pilot. Prioritize useful
Codex-submitted tasks with returned patches and confirmed shutdown; do not repeat
the completed READY/toy tests without a concrete reason. Reuse existing guards. Defer sensor
research, private-engine rehearsals, tuning, MCP and UI unless a concrete blocker
requires them. The Ollama assistant and JetBrains plugin are retired; retain the
independent TypeScript Strata simulator. Do not restore retired components unless
the owner changes direction.

## Current checkpoint (20 October 2026)

- Proven: Linux CPU build 153/153, hash-verified artifacts; real Docker READY
  and [OpenCode pilot](containers/model-runtime/CODING_TASK_1_RESULT.md) returned a
  113-byte patch with both containers exit 0/stopped. Originals intact; general
  native tool calling remains unproven.
- Useful task 2 remains unfinished. Preserved failures: [Docker unavailable](containers/model-runtime/CODING_TASK_2_RESULT.md),
  [90-second timeout](containers/model-runtime/CODING_TASK_2_RECOVERY_RESULT.md),
  [unrelated 32-token answer](containers/model-runtime/CODING_TASK_2_TIMING_RESULT.md),
  and [34-token prompt/engine silence](containers/model-runtime/CODING_TASK_2_STATEMENT_RESULT.md).
  No task-2 patch/edit; originals unchanged. All owned containers/helpers stopped
  or exited independently; evidence and spent decisions retained. Docker remains running.
- Approved [compact attempt](containers/model-runtime/CODING_TASK_2_COMPACT_RESULT.md)
  ran once with the same limits: 23-token prompt started; `HOST_RAM_HIGH` stopped
  it at 29,090.77 MiB used (limit 28,672). No API result, edit or patch. Model exit
  137/worker 70, independently stopped/PID 0; all four host helpers exited.
  Evidence sealed. Server waiting messages do not renew native activity.
- Owner approved raising the host RAM crossing to 30 GiB (30,720 MiB used)
  and deferred added readiness/optimization. The [30-GiB attempt](containers/model-runtime/CODING_TASK_2_RAM30_RESULT.md)
  ran once with fresh approval and unchanged 150-second deadline/other limits:
  API returned 23 prompt/32 output tokens in about 95 s, truncated `solve(n)`
  function rejected as `MODEL_OUTPUT_INCOMPLETE` before editing. No patch.
  Model exit 0/worker 70; both independently stopped/PID 0, all four helpers
  exited. Peak host RAM 23,338.27 MiB; no emergency fault. Evidence sealed.
- Offline output review: native/API/BPE agree on the 32-token output-cap stop;
  deadline/RAM/context did not truncate it. Compacting removed explicit one-line/
  no-function/no-Markdown instructions while admission stayed strict. Only the
  short guard request reaches Strata, not file context/full OpenCode task.
  An eight-token guard fits; why the model chose a function remains unproven.
- Latest owner direction: **16K context, up to 4K output**, roughly **512 input
  tokens initially**, simple function task, then double input/add requirements.
  Do not pad short requests. Fibonacci was an example. The unrun
  [64-output proposal](containers/model-runtime/CONTEXT_16K_REVIEW.md) is superseded
  and preserved. The [first function review](containers/model-runtime/SIMPLE_FUNCTION_REVIEW.md)
  selects Fibonacci: 123 actual input tokens within 512 budget, 4K output ceiling,
  direct API/no edit worker; admitted code checked after model stop in a one-CPU,
  128-MiB/2-second Windows job. It [ran once](containers/model-runtime/SIMPLE_FUNCTION_TIMEOUT_RESULT.md):
  150-second timeout during prompt reading, last reported 96/123 input, zero
  generated tokens. Model exit 70, independently stopped/PID 0, all four helpers
  exited. Evidence sealed; no code returned/evaluated, repository edit or retry.
  The [longer-duration scope](containers/model-runtime/FIBONACCI_EXTENDED_REVIEW.md)
  then passed once: 123 input/74 complete output tokens, all six cases passed,
  model exit 0/PID 0, four helpers and evaluator independently exited. Evidence
  sealed under `.runtime/strata-fibonacci-extended-relaunch/`; the earlier canceled
  Windows administrator launch remains separately sealed. Request 900 s/model
  1,200 s and all safety limits stayed enforced. No source edit or model retry.
  The [246-input scope](containers/model-runtime/FIBONACCI_DOUBLE_INPUT_REVIEW.md)
  ran once: GPU_HOT at 75 C after 62 generated tokens, no complete answer/evaluation.
  Model 137/PID 0 and all four helpers independently exited; evidence sealed.
  Owner explicitly approved [GPU warning above 87 C / stop at 90 C](containers/model-runtime/FIBONACCI_GPU90_REVIEW.md)
  and a fresh run of the exact same 246-token task. Startup GPU advisory is 87 C;
  other limits unchanged. 159 offline checks passed. That run stopped once on
  HOST_RAM_HIGH at 30,757.53 MiB (limit 30,720), GPU peak 64 C, no response or
  evaluation. Model 137/PID 0 and all four helpers independently exited. Evidence
  sealed; no further run/reset/code application approved. Preserve all attempts.
  Owner reports native ~12 tok/s; native config uses auto cache/prefill and MTP,
  versus Docker's 0.16-GiB cache/13% hit rate, prefill 32 and one CPU. Tuning is
  a separate future scope; do not activate it in the unchanged input experiment.
  Keep 30-GiB RAM stop/no readiness; no silent deadline changes. Manual Docker
  chat is being built in a separate owner-created session. No search batch or
  automatic next step. Nineteen model attempts/all
  executed operation approvals consumed. No further workload, code application,
  automatic retry or fault reset approved. The unrun readiness proposal and
  every failed attempt remain preserved. Offline checks are separate from
  real execution. Aggregate RAM-pressure attribution remains unavailable.
  Keep exact executed sources and every failed scope. Startup targets warn;
  CPU emergency stop stays 97 C. LF rules preserve pinned checkout bytes.
  Context work stays separate under the [Hermes plan](containers/model-runtime/HERMES_CONTEXT_PLAN.md)
  and [offline preparation](containers/model-runtime/CONTEXT_CAPACITY_PREPARATION.md).
  64K/Hermes remain unproven/deferred; preserve inactive 95/98 C history.

## Execution boundaries

- Target: Windows laptop, RTX 3080 Ti 16 GB VRAM, 32 GB RAM; an earlier sustained
  Strata workload caused an unexplained shutdown. Preserve existing installations,
  model files and configurations. Obtain explicit approval for live workloads,
  model/GPU tests, safety-policy changes, firmware or power-setting changes.
  Reuse existing scoped approvals; do not ask again for already-approved policy.
- CPU-build admission stays at or below 92 C for ten seconds; stop at 97 C.
  Model/API startup targets are advisory by owner instruction: CPU 94 C, GPU
  60 C/40 W/4096 MiB and host free RAM 8192 MiB. Require ten seconds of valid
  telemetry without resetting for target exceedances; save startup warnings.
  Keep CPU 97 C and the owner-approved GPU90 scope's warning above 87 C/stop at
  90 C. Historical scopes retain 75 C. All other eighth-scope emergency stops
  stay enforced. The new
  task-2 RAM30 scope uses the owner-approved 30-GiB host used-RAM stop; no added
  readiness gate. Historical scopes retain their original policies. WSL has
  1 CPU, 6 GiB and no swap; compiler/API containers use 1 CPU and 4 GiB,
  compiler one job. A consumed approval never authorizes another attempt.
  The older 95/98 C proposal is inactive; CPU-build policy is unchanged.
  CPU firmware freshness/calibration and throttle status have documented
  limitations; never invent readings or extend scope-specific acceptance.
- Keep task/context/file/output limits, fresh telemetry, independent watchdogs,
  owned stopping and latched faults. No automatic retries or fault resets.
  Simulated success is not proof of real execution or confirmed shutdown.
- Preserve `.runtime/`, cached blobs, approvals, raw readings, consumed attempts
  and reviewed snapshots. Never overwrite historical evidence or reuse spent
  decisions. The failed native rehearsal left an unstarted container and bare
  attached disk: no detach, reuse, deletion or global Docker/WSL stop is authorized.

## Working conventions

- Complete integrated milestones; report short Done/Left bullets and distinguish
  simulated validation from real execution. Do not track account usage limits.
- Main CLI: `python -B local_worker.py`; `status` reads recorded readiness.
  `npm start` runs the simulator only. Relevant offline checks are Python proposal
  tests under `containers/strata-proposal/` and `npm test` for the simulator;
  real readers, imports, compilation and models are separate approved operations.
- Keep this file compact: durable rules and one current checkpoint only. Replace
  stale checkpoint text rather than appending session logs. Put detailed results
  in operation reviews or history. The [archived agent notes](docs/history/AGENT-2026-10-18.md)
  are reference material, not required startup reading or current authorization.
