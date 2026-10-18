# Local Copilot

**Current next operation (18 October):** normal Docker Desktop storage is approved. The verified-image import and first CPU Strata build are connected and ready for one combined workload approval; see [the exact review](containers/strata-proposal/DESKTOP_BUILD_REVIEW.md). 338 offline tests pass. No model has run. Separate-engine rehearsals are deferred. Earlier milestone notes below are historical.


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

The immediate milestone is **one real Strata coding task completed end to end**.
The active implementation targets Strata inside Docker on Windows, with cloud
Codex as the first parent-agent integration and Claude support planned later.
Direct local use is also a project goal; it is not yet a completed standalone
coding-agent workflow.

Done:

- Docker-based OpenCode editing has been demonstrated against scripted API
  replies, with selected-file staging and a returned patch.
- CUDA base-image blobs and pinned Linux build inputs have been staged and
  verified.
- Task boundaries, lifecycle controls and background monitoring/watchdog work
  provide the foundation for supervised local execution.

Left:

- Make the verified base image available to the selected Docker engine and build
  the Linux Strata executable.
- Start the supervised Strata container and obtain a real model answer.
- Connect OpenCode to Strata, complete one disposable coding task submitted by
  Codex, return its patch and confirm shutdown of both components.
- Evaluate code quality, practical usefulness and paid-token savings before
  expanding the workflow.

**The Docker workflow has not yet completed a real Strata model request or coding
task.** Scripted-response tests and infrastructure rehearsals do not establish
that the full local coding workflow works. See [the first working helper
milestone](MVP.md) and [the current checkpoint](NEXT_STEPS.md) for implementation
details, remaining decisions and execution requirements.

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
| [MVP.md](MVP.md) | Immediate path to the first real Strata answer and coding patch |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Current checkpoint, blockers and preserved execution history |
| [local_worker.py](local_worker.py) | Supervisor CLI for status, preparation, rehearsals and guarded operations |
| [containers/worker/](containers/worker/README.md) | Selected-file task boundary, OpenCode integration and patch collection |
| [containers/strata-proposal/](containers/strata-proposal/README.md) | Pinned Linux Strata build and runtime preparation |
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
