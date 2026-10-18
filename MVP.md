# First working Strata helper for Codex

Success means cloud Codex submits one small coding task, the existing Coder
model runs through Strata inside Docker, OpenCode edits one disposable file,
Codex receives its patch, and the local processes stop. A build, health check,
simulation or empty-engine rehearsal alone does not complete this milestone.

## What is already usable

- Docker Desktop, existing model files and the Windows Strata installation.
- Downloaded and verified CUDA base-image blobs and pinned Linux build inputs.
- The Linux OpenCode executable and a restricted one-file editing workflow,
  verified in Docker against scripted API replies.
- File staging, patch collection, task limits and the existing host watchdog.
- CPU monitoring with the existing 92 C admission / 97 C stop controls.

The Linux Strata executable has NOT been built. No real Strata model request
has run in Docker. That is the current functional gap.

## Immediate path

1. Make the verified CUDA base available to the selected Docker engine and
   compile the pinned Strata source for this laptop's GPU architecture (86),
   without vision or benchmark work. Reuse the existing bounded compiler path.
2. Prepare a separate Linux configuration pointing at the existing model and
   pack through read-only mounts. Keep automatic setup/downloads/restarts off.
   Leave the working Windows configuration unchanged.
3. Start one supervised Strata container, wait for its API, and request a very
   short answer. This is the first actual runtime compatibility test.
4. Connect the existing OpenCode worker to that API and submit one disposable
   one-file edit from Codex. Return the patch and structured result to Codex.
5. Stop the worker and Strata, retain the result, and assess usefulness before
   doing any performance tuning or expanding access to real projects.

The first artifact to demonstrate is the real model's answer; the final artifact
is its code patch. Report progress against those outcomes.

## Approved storage route for the first test

The owner approved Docker Desktop's ordinary image storage for the first test.
The private engine, VHDX management and empty-engine rehearsals are deferred.
Free-space monitoring is not a hard cap. Preserve the consumed native attempt
and retained disk without further work on that route.

The connected `local_worker.py` commands `prepare-desktop-test`,
`review-desktop-test` and `run-desktop-test` prepare, inspect and execute one
verified CUDA import followed by the existing CPU build. Execution requires one
exact combined workload approval; the storage choice alone cannot launch it.
See `containers/strata-proposal/DESKTOP_BUILD_REVIEW.md` for the prepared operation.

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
