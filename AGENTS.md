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

## Current checkpoint (19 October 2026)

- Done: Linux CPU build 153/153, exported/hash-verified artifacts. Real Strata
  Docker answer **READY** (19 prompt/2 output tokens), followed by one real
  Codex-submitted OpenCode edit: `VALUE = 1` -> `VALUE = 2`, returned 113-byte patch.
- Done: [coding result](containers/model-runtime/CODING_TASK_1_RESULT.md). Real
  model response supplied the replacement; OpenCode's edit tool applied it.
  Both containers exit 0/stopped; originals unchanged. This narrow host-brokered
  one-file adapter does not establish general/native model tool calling.
- Startup targets now warn; CPU emergency stop remains 97 C and all other
  emergency stops remain enforced. Startup coordination exercised live. 81 offline
  runtime/integration checks passed, separately from the two successful live runs.
- Next: review the pilot patch and choose a small useful task before generalizing
  the adapter. Plan separately approved, incremental context-capacity tests toward
  64K; consider Hermes only after real capacity is proven. See the
  [Hermes context plan](containers/model-runtime/HERMES_CONTEXT_PLAN.md).
  Ten model attempts (nine API, one coding) are consumed/preserved;
  both current approvals are spent. No retry/reset or new workload approved.
  Preserve the inactive 95/98 C proposal and all historical settings/evidence.

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
  Keep CPU 97 C and all eighth-scope emergency stops enforced. WSL has
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
