# Local Copilot

**Current checkpoint (20 October):** one [30-minute coding viability test](VIABILITY_POC.md)
is next: Strata fixes the real negative-read-limit bug and adds regression tests;
OpenCode returns a patch without Codex repairs. Resource readings warn with rolling
trends rather than stopping this new scope. The READY/toy pilot is completed;
useful delegation and paid-token savings are still unproven.

This project is focused on using **Strata for local coding work** in two ways:

- **As a substitute for paid coding agents:** run coding tasks locally through
  Strata, reducing reliance on paid services for work the local model can handle.
- **As a coding subagent for paid agents:** let an agent such as Codex or Claude
  delegate bounded implementation tasks to a local Strata worker, reducing paid
  token consumption while the parent agent plans, coordinates and reviews.

The goal is useful code changes with less paid-agent usage. Local execution
still has hardware, electricity and maintenance costs; coding quality and actual
paid-token savings need to be evaluated on real tasks.

## How it should work

Strata provides local model inference. A coding worker, currently based on
OpenCode, uses that inference to carry out a task. The project supplies the
supervision, selected-file staging and patch collection around that worker.

The intended workflow is:

1. A person or parent coding agent defines a small task and selects the files
   needed to complete it.
2. The supervisor stages those files in a disposable workspace and starts the
   local Strata and coding-worker components on demand.
3. The worker performs the implementation using the local model.
4. The supervisor returns a patch and structured result for review, then stops
   the local components.
5. The person or parent agent reviews and validates the change before applying it.

For delegated work, the parent agent receives the result and patch instead of
performing every implementation step through its paid model. Keeping delegated
context and returned output focused is part of the intended token savings.

## Current implementation focus

Follow [the viability contract](VIABILITY_POC.md): at most ten minutes handoff
preparation, fifteen minutes execution including confirmed stopping, five minutes
validation/report. One request, no retry, no repair by Codex. On failure recommend
stopping investment in this Docker approach. No more Fibonacci/context tests.

The owner approved warnings for resource pressure, including sustained crossings.
An explicit new-scope profile implements this; old strict defaults and historical
approvals remain preserved. This offline policy update is not live execution.

The existing build, real READY answer and tiny returned patch are groundwork.
Nineteen model attempts are consumed. General coding quality, native tool calling
and token savings remain unproven; record costs honestly. Hermes/64K, tuning,
MCP, UI and rebuilds are deferred. See [AGENTS.md](AGENTS.md) and
[NEXT_STEPS.md](NEXT_STEPS.md) for current handover instructions.

## Operating principles

- Start local components for bounded tasks and stop them when finished.
- Give the worker only the selected context and a disposable workspace; return
  changes as a reviewable patch.
- Keep task scope, context, output and runtime bounded.
- Reuse the existing monitoring and shutdown controls while prioritizing the
  first useful coding result.
- Keep live build/model execution and resource changes within their reviewed,
  approved scope. This README does not change existing execution approvals.

## Project map

| Location | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Compact agent guidance and current checkpoint |
| [MVP.md](MVP.md) | Current useful coding viability milestone |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Current checkpoint and bounded next action |
| [local_worker.py](local_worker.py) | Supervisor CLI for status, preparation, rehearsals and guarded operations |
| [containers/worker/](containers/worker/README.md) | Selected-file task boundary, OpenCode integration and patch collection |
| [containers/strata-proposal/](containers/strata-proposal/README.md) | Pinned Linux Strata build and runtime preparation |
| [containers/model-runtime/](containers/model-runtime/README.md) | Runtime guards, advisory viability profile and historical evidence |
| [containers/lifecycle/](containers/lifecycle/README.md) | Container lifecycle harness and shutdown validation |
| [containers/safety/](containers/safety/README.md) | Existing monitoring, watchdog and execution-control evidence |
| [STRATA_CONTAINER_PLAN.md](STRATA_CONTAINER_PLAN.md) | Container architecture findings and earlier planning context |
| [docs/history/](docs/history/AGENT-2026-10-18.md) | Archived agent notes; consult only when needed |

For a read-only view of the supervisor's recorded state, run from this directory:

```powershell
python -B local_worker.py status
```

This reports readiness and blockers; it does not start a model.

## Retired direction

The earlier **Rider/JetBrains autocomplete plugin and Ollama-based local
assistant** are retired project directions. Their chat, suggestion and review
workflows are no longer the focus and are not planned future work.

Their source, setup/demo scripts, tests and validation guide have been removed.
Git history retains the earlier implementation. The remaining Node/TypeScript
package builds and tests only the Strata supervisor simulator; see
[SUPERVISOR.md](SUPERVISOR.md).
