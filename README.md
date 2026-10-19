# Local Copilot

**Current checkpoint (19 October):** Strata returned a real **READY** answer in Docker, then completed a [real Codex/OpenCode coding test](containers/model-runtime/CODING_TASK_1_RESULT.md): `VALUE = 1` -> `VALUE = 2`, with a 113-byte returned patch. Both containers exited successfully and stopped; originals stayed unchanged. Startup targets are warnings, emergency stops remain enforced. This is a narrow one-file adapter; general interactive coding remains future work. Both approvals are spent.


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

- Linux Strata built in Docker; executable/library exported and hash-verified.
- Real model answer returned through the Docker API with confirmed shutdown.
- Codex submitted one disposable file task. OpenCode made a real provider request,
  Strata generated replacement code, and the adapter supplied that exact text to
  OpenCode's edit tool. A 113-byte patch returned to Codex; originals were unchanged.
- Both containers exited 0 and stopped. Existing emergency limits, monitoring,
  leases and preservation remained enforced; startup targets became warnings.
- 81 offline runtime/integration checks passed, separately from real execution.

Left:

- Generalize the narrow one-file code-to-edit adapter to a useful selected task.
- Verify native model tool-calling/full interactive provider compatibility before
  claiming a general OpenCode coding agent.
- Evaluate code quality and usefulness on real tasks before tuning performance.

See [the completed pilot](containers/model-runtime/CODING_TASK_1_RESULT.md),
[the milestone](MVP.md) and [the checkpoint](NEXT_STEPS.md). No further live run
is authorized by these results; consumed attempts and evidence remain preserved.

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
| [containers/model-runtime/](containers/model-runtime/README.md) | First real model/API test and its exact approval scope |
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
