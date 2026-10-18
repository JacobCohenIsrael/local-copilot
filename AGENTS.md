# Local Copilot: agent guidance

## Purpose and focus

Use Strata in Docker for local coding, both directly and as a bounded helper for
Codex (Claude later). OpenCode is the coding worker; the supervisor stages selected
files, returns a patch and structured result, and stops the local components.

Prioritize the first real Strata answer, then one Codex-submitted OpenCode edit
with a returned patch and confirmed shutdown. Reuse existing guards. Defer sensor
research, private-engine rehearsals, tuning, MCP and UI unless a concrete blocker
requires them. The Ollama assistant and JetBrains plugin are retired; retain the
independent TypeScript Strata simulator. Do not restore retired components unless
the owner changes direction.

## Current checkpoint (18 October 2026)

- Done: verified CUDA blobs/build inputs, scripted-API OpenCode editing and a
  connected ordinary-Docker import-to-CPU-build workflow. Linux Strata is unbuilt;
  no real model request has run in Docker.
- Next: execute the prepared combined import/build after exact workload approval,
  then prepare runtime admission and the first real coding task. Normal Docker
  storage is approved for the first test; import/build execution is still pending.
  See [the exact operation](containers/strata-proposal/DESKTOP_BUILD_REVIEW.md)
  when working on that step. [MVP.md](MVP.md) describes the remaining route.

## Execution boundaries

- Target: Windows laptop, RTX 3080 Ti 16 GB VRAM, 32 GB RAM; an earlier sustained
  Strata workload caused an unexplained shutdown. Preserve existing installations,
  model files and configurations. Obtain explicit approval for live workloads,
  model/GPU tests, safety-policy changes, firmware or power-setting changes.
  Reuse existing scoped approvals; do not ask again for already-approved policy.
- Existing CPU controls: admission at or below 92 C for ten seconds; stop at
  97 C. WSL currently has 1 CPU, 6 GiB RAM and no swap; the compiler proposal has
  1 CPU, 4 GiB and one job. These are not approved model-runtime limits.
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
