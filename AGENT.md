# Local Copilot

## Current priority

Owner usage rule: monitor the five-hour Codex allowance during active work. At 5% remaining (95% consumed), stop work gracefully: save a compact checkpoint, stop only this task's owned workers/containers if any are running, and report the pause. Check before starting substantial work and between bounded steps. Do not stop unrelated processes or Docker Desktop. Resume only on owner direction or after the allowance resets.

The main goal is an on-demand, Docker-contained Strata coding worker orchestrated by cloud Codex, with Claude support later. The existing TypeScript assistant and JetBrains plugin are secondary historical work.

The target is the owner's Windows laptop with an RTX 3080 Ti 16 GB GPU and 32 GB RAM. A previous sustained Strata workload caused an unexplained instant shutdown. Keep Strata off during architecture, simulator, and read-only compatibility work. Do not start a model, run GPU load tests, change firmware or power settings, or activate a changed safety policy without explicit owner approval. Preserve the existing installation and configurations.

See `SUPERVISOR.md` for the simulation-only supervisor, `STRATA_CONTAINER_PLAN.md` for Docker compatibility findings, and `containers/lifecycle/README.md` for the CPU-only Docker dummy lifecycle harness. The dummy harness uses synthetic telemetry and cannot launch Strata/OpenCode; its limits and reset acknowledgment do not approve live work. Use simulated sensors and harmless workers to validate lifecycle behavior before proposing a live task. Docker MCP is optional; any future interface must go through the bounded supervisor.

`containers/safety/README.md` records read-only sensor availability and the independently tested dummy watchdog. The owner prefers a small dedicated monitor; see `containers/safety/MONITOR_DESIGN.md`. The owner-authorized administrator ASUS CPU status probe now works (90 °C candidate; later Armoury screenshot CPU 81 °C / GPU 57 °C). See `containers/safety/CPU_ACCESS_VALIDATION.md`; sensor meaning/freshness and CPU hardware thermal-throttle status remain unvalidated. OS frequency-limit readings must not be treated as proof of no thermal throttling. Do not replace missing readings with guessed values or activate model/build work. `containers/strata-proposal/` is an unbuilt, disabled proposal requiring separate review and approval.

The owner chose to keep Strata itself in Docker. Prioritize the prepared pinned Linux compile package over Windows-engine reuse and optional diagnostics. See `NEXT_STEPS.md` for the compact checkpoint. The source-only staging is complete; compilation and model launch remain disabled.

On 16 October 2026 the owner approved the CPU-only build throttle exception and reviewed controls: unknown hardware throttle status may remain null for one capped CPU-only compilation, with a 75 C/10-second start baseline and 80 C stop. See `containers/strata-proposal/build-policy-approval.json` and `BUILD_POLICY_REVIEW.md`. Do not ask again for this policy decision. It does not approve compilation/image pull, model loading, or waiving CPU-source validation, reader coverage, watchdog/stop testing, disk/download limits, or final build-workload approval. The approved draft is preserved as a historical snapshot; reader implementation hashes may differ and must be revalidated/bound into the final build package.

## Historical application goal

Create a local copilot that can suggest code and provide code reviews.

## Initial success criteria

- Run on the user's machine and work with a local code repository.
- Suggest relevant code using the current file and surrounding project context.
- Review code changes and return actionable findings with file and line references, explanations, and suggested fixes.
- Let the user inspect suggestions before applying them.
- Provide clear setup instructions and a repeatable demonstration of both code suggestions and code review.

## Implementation decisions

- Interface: command-line tool, with human-readable and JSON output.
- Model runtime: local Ollama; portable Windows setup disables cloud features.
- Verified model: Qwen2.5-Coder 7B. The smaller 1.5B model failed the review demonstration.
- Initial validation language: JavaScript. Other text-based languages depend on model capability and need project-specific evaluation.
- Hardware used: Windows, Node.js 24, NVIDIA RTX 3080 Ti Laptop GPU with 16 GB VRAM. Loaded-model demonstration requests took approximately two seconds each.

## Initial milestones

1. Choose the interface and model runtime, and define a small end-to-end example.
2. Implement code suggestions with relevant repository context.
3. Implement review of local diffs with actionable findings.
4. Validate both workflows on representative examples and document setup and limitations.

## Current status

Implemented a TypeScript CLI backed by a loopback Ollama service. Source, demo, and tests use strict TypeScript and compile to `dist/`; the compiled Node.js CLI has no runtime package dependencies.

- `suggest`: insertion suggestions using target-file and related repository context.
- `review`: staged or unstaged Git diff reviews with validated file/line references.
- `doctor`: local service and installed-model discovery.
- Setup instructions and a repeatable model demonstration are in README.md.
- Five automated tests passed on Windows, covering the CLI and Git workflows against a local API stub.
- TypeScript migration verified with `npm run typecheck`, `npm test`, and `npm run demo` against the installed local model.

Real inference is verified with the 7B model on the local service at http://127.0.0.1:11435. The generated insertion passed functional checks, and both the demonstration and user-facing review command identified the introduced bug at the correct line with an actionable fix. See VALIDATION.md for evidence and limits.
