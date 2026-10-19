# First working Strata helper for Codex

Success means cloud Codex submits one small coding task, the existing Coder
model runs through Strata inside Docker, OpenCode edits one disposable file,
Codex receives its patch, and the local processes stop. A build, health check,
simulation or empty-engine rehearsal alone does not complete this milestone.

## First milestone completed

The [real Docker answer](containers/model-runtime/STARTUP_WARNINGS_API_RESULT.md)
returned READY. The [coding pilot](containers/model-runtime/CODING_TASK_1_RESULT.md)
then returned a real 113-byte patch changing `VALUE = 1` to `VALUE = 2`.

Codex staged one disposable file. OpenCode made its real request, the host broker
asked Strata for replacement code, and OpenCode's edit tool applied the generated
text. The patch and structured result returned to Codex. Both containers stopped,
exit 0, with originals unchanged. The model's code was neither scripted nor
constructed by the adapter; the adapter only removed the surrounding code fence
and translated the result to an edit-tool call. Its final acknowledgement is local.

This proves a narrow one-file code-to-edit integration. It does not prove native
Strata tool calling or general interactive OpenCode behavior. Review this pilot
before choosing a useful small task and broadening the adapter. Do not expand
monitoring, storage infrastructure, optional MCP or UI work instead.

Startup targets are warnings; ten seconds of valid telemetry is still required.
CPU stop remains 97 C and all other emergency stops, resource caps, watchdogs,
leases, deadlines and isolation stay enforced. CPU-build policy remains 92/97 C.
The READY scope used eight output tokens; the coding task allowed 32 and used ten.
Both kept 512 context, one CPU/4 GiB, a 90-second call and 300-second model lifetime.

All ten model attempts are preserved and consumed. Further live workloads need
fresh scoped authorization; there is no automatic retry or fault reset.

## Approved storage route for the first test

The owner approved Docker Desktop's ordinary image storage for the first test.
The private engine, VHDX management and empty-engine rehearsals are deferred.
Free-space monitoring is not a hard cap. Preserve the consumed native attempt
and retained disk without further work on that route.

The connected `local_worker.py` commands `prepare-desktop-test`,
`review-desktop-test` and `run-desktop-test` prepare, inspect and execute one
verified CUDA import followed by the existing CPU build. That approved attempt
is now consumed: import succeeded and build startup failed. Do not rerun it.
That operation is historical; the subsequent CPU-only build is now complete.
See `containers/strata-proposal/DESKTOP_BUILD_RESULT.md` for the execution outcome.
`prepare-build-recovery`, `review-build-recovery`, `run-build-recovery` and
`cancel-build-recovery` now expose that separate, approval-gated CPU-only scope.
That first CPU-only recovery is now consumed and FAULT-latched; its stopped
container and logs are retained. These commands do not authorize a retry/reset.
The later `run-build-timing` attempt completed successfully and is also consumed.
Use its exported artifacts for runtime preparation; another build is unnecessary.

## Keep in the background

Reuse existing temperature checks, watchdogs, bounded context/files/output,
owned stopping and evidence preservation. Do not add monitoring features,
repeated manual temperature comparisons, benchmark suites, optional MCP, UI or
additional agent frameworks before the first real task.

Live execution still needs the exact workload/resource approval. The current
one-CPU / 6-GiB WSL limit was temporary build preparation; it is not a verified
model runtime budget. Resolve the runtime budget in the concrete launch package
without silently changing WSL, GPU, model or power settings. Do not reset the
consumed native attempt or detach its retained disk without the required proof.

## Upstream check, 18 October 2026

The checked release is now 0.1.45. Its published asset list contains Windows
engines, with no Linux engine asset listed. The setup source names a Linux asset,
but that does not establish that a downloadable one exists. Keep the staged,
pinned source build rather than assume a prebuilt Linux shortcut or update the
working Windows installation. The upstream Docker route also compiles the engine.

Sources: [release assets](https://github.com/Niko1221/Strata/releases/expanded_assets/v0.1.45),
[Docker build instructions](https://github.com/Niko1221/Strata/blob/main/docs/INSTALL.md#docker-linux).
