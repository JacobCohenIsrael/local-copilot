> Current direction (20 October): follow [VIABILITY_POC.md](VIABILITY_POC.md). One real
> coding task within 30 minutes; new coding scopes use resource warnings/trends.
> The notes below describe historical or deferred work, not next-step instructions.
> Their strict thresholds, pending approvals and context ladders do not override
> the current contract. Preserve historical evidence and CPU-build policies.

# Strata container readiness — read-only findings

Checked 16 October 2026. This is a plan, not an activated live policy. The initial file audit ran no container. A subsequent bounded CPU-only diagnostic passed as recorded below; no Strata process, model load, CUDA build, GPU command, or hardware sensor query was run. Existing Strata files were only read. The inspected model files were located through Strata's own configuration; Ollama was not used.

## Upstream update and completed container check

The latest published release checked was [v0.1.44.1](https://github.com/Niko1221/Strata/releases/tag/v0.1.44.1), published 14 October 2026. Source and release tag resolved to commit `296b59d2f73c8f04a805df29c2fa97655adace78`. The installed engine remains 0.1.41; it was not updated. The release improves CPU crash reporting/startup handling and preserves the installed model when setup is rerun. These changes do not explain or resolve the laptop's previous shutdown.

Text snapshots of the pinned Dockerfile, entrypoint, setup, server, and relevant docs are under `.runtime/strata-preflight/references`, with SHA-256 fingerprints in `upstream-lock.json`. Upstream code was not imported or executed. Compared with the installed Dockerfile and entrypoint, the changes add copying an optional K-quant library into the image and an AVX2 warning. The automatic setup/start path, default model/context, host-RAM detection, and normal shutdown considerations still apply. Future supervised startup should explicitly disable Strata's internal startup retries (`STRATA_START_RETRIES=0`) and Docker restarts, leaving the supervisor in control.

The fixed [CPU-only diagnostic](containers/preflight/README.md) ran using the official Python Linux amd64 image pinned by digest. It is not a Strata image. Docker inspection and in-container checks confirmed:

| Check | Actual result |
| --- | --- |
| CPU / RAM / swap / process cap | 0.5 CPU, 256 MiB RAM, zero swap, 32 processes |
| Isolation | Non-root, zero capabilities, no new privileges, read-only root/mounts, no network or ports, no GPU devices or requests |
| Existing data visibility | Both configured GGUF paths, pack, tokenizer, MTP directory, expert profile, dense and expert BIN files present via read-only mounts; metadata only |
| RAM detection | `/proc/meminfo`: 16,569,262,080 bytes (15.43 GiB); cgroup `memory.max`: 268,435,456 bytes (256 MiB) |
| Completion | Exit 0, no OOM, roughly 0.4 seconds runtime, owned container removed |
| Preservation | Four original file fingerprints below unchanged; no installation or live policy update |

Evidence: `.runtime/strata-preflight/3bf3cedcafa0/`. Five standard-library host tests cover path translation/escape rejection, duplicate flags, synthetic isolation failures, and rejecting unsafe Docker settings before startup. This confirms basic container isolation and path mapping, not model compatibility, peak memory needs, GPU access, telemetry coverage, or laptop thermal safety. The diagnostic image remains cached; no diagnostic container remains.

## What is confirmed

| Item | Evidence from the installed files |
| --- | --- |
| Linux/container support | `D:\AI\Dockerfile`, `docker-entrypoint.sh`, and `docs/INSTALL.md` supply an NVIDIA/Linux container build and launch path. Runtime compatibility on this laptop is still untested. |
| Windows engine | `BUILD.json` reports release engine 0.1.41, CUDA 12.9, with `experimental: true`. This does not establish a source commit for every local file. |
| Container build | The local Dockerfile compiles a Linux engine using CUDA 13.0 and Ubuntu 24.04. It is a different executable from the Windows `strata.exe`; driver compatibility remains to be checked before GPU use. |
| Current launcher | `run-coder-iq1_m.bat` starts the Python server with the existing JSON configuration, port 8080, and browser opening enabled. |
| Selected model | `qwen3.8-flash-next-coder-iq1_m`, GPU index 0. The configuration currently sets `--max-context 65536`, `--expert-cache auto`, and the boolean `--resident-experts` flag. |
| Model locations | Both configured GGUF shards exist under `D:\Strata-data\models\coder-IQ1_M`. The configured pack, tokenizer, MTP folder, and expert profile also exist. Presence is verified; file contents and Linux format compatibility are not runtime-verified. |
| Prepared expert data | The existing pack contains `experts.bin` (25,146,163,200 bytes, about 23.4 GiB) and `dense.bin` (about 1.37 GiB). Their on-disk size is not a measurement of peak RAM usage. |
| Existing MCP support | `docs/MCP_SERVER.md` describes Strata's own standard-library Python MCP server, including start, stop, status, install, logs, and benchmark tools. It was inspected as text and was not launched or connected. |

The public [Strata repository](https://github.com/Niko1221/Strata) also documents Windows/Linux support. The installed files and pinned upstream snapshots were inspected separately; the installed engine version does not establish the version of every source file beside it.

## Why the default container start needs review

The supplied entry point defaults to the original Qwen family, IQ2_XS, a 32,768-token context, and automatic setup followed by serving. Missing data can trigger a large model download and preparation. These defaults do not select the owner's Coder IQ1_M configuration. Even the configuration-override branch ultimately calls `setup.py`, whose start path can update configuration timestamps, GPU choices, and MTP vocabulary state.

The current Windows JSON contains Windows paths and a Windows engine executable, so it cannot be used unchanged inside Linux. The prepared files are candidates for reuse, with separate Linux paths and configuration. Do not mount the existing model installation writable and run automatic setup against it.

The Dockerfile also uses unlimited memory locking in its example run command. Do not copy that example into the supervisor as an operating policy. CPU, RAM, swap, locked memory, GPU access, and thermal shutdown need separate review.

## Proposed architecture

`Cloud Codex → Windows supervisor → two owned containers: OpenCode worker + Strata inference server`

The supervisor stays on Windows, where it can observe the host and stop the workloads it owns. It admits exactly one bounded task, stages only selected files, starts the components on demand, collects results, stops the worker before Strata, and preserves a fault latch. Both containers belong to a single session with no automatic restart. A failed or disconnected orchestrator must not leave the model running indefinitely.

The OpenCode worker should have no GPU device, Docker socket, host credentials, or access to the original repository. Only Strata receives the selected GPU. The worker receives a disposable workspace and access to the approved inference endpoint. The model files are mounted read-only, with a separate writable session area for logs, generated configuration, and any copied expert profile that the engine updates. Missing files fail admission rather than triggering downloads.

Use an internal container network. Any API published to Windows should bind only to loopback and require an API key; Strata's container listener must also be authenticated. Restrict runtime network access to the intended worker/server relationship. Image construction and dependency download are separate, explicitly planned work, never a surprise at model startup.

A later MCP wrapper should expose only bounded task submission, status, and cancellation. Strata's existing MCP implementation may provide useful lifecycle code, but its documented direct-start behavior can leave the model running after the client closes. Its install and benchmark tools must not become unrestricted cloud-agent tools. The safety supervisor remains responsible for admission, monitoring, deadlines, and cleanup.

## Decisions to settle before live execution

| Decision | Finding and consequence |
| --- | --- |
| RAM budget | The last Docker inventory exposed about 15.4 GiB to its Linux engine. The current Windows configuration uses resident experts. Existing settings cannot be assumed to fit a container cap. No WSL memory ceiling or model setting was changed. |
| Memory mode | The local source accepts explicit `--low-ram mmap` and `resident` modes. Automatic low-RAM selection also considers the detected RAM and can select residency. A generic `LOW_RAM=on` is not proof that a specific container budget is respected. A separate Linux configuration must make the intended mode explicit, with failure if it cannot fit. |
| Context | Preserve the current 65,536-token Windows configuration. Propose a smaller independent Linux engine context and a stricter full-request budget for coding tasks. The documented setup menu starts at 8,192 tokens; the simulator's 4,096-token task budget is an admission budget, not proof of a supported engine setting. |
| CPU, RAM, swap, and VRAM reserve | Agree on concrete values before creating a live launch manifest. CPU/RAM limits do not provide a laptop temperature or GPU-power guarantee. No claim that “75% of the PC” is an enforceable single limit. |
| Startup deadline | The simulator allows 30 seconds; local Strata documentation describes model loading taking 1–3 minutes. A live deadline requires a separately reviewed policy, not an automatic extension. Loading itself must remain monitored and cancellable. |
| Normal and emergency shutdown | The simulator permits 5 seconds per component. Strata's local installation guide recommends a 60-second normal Docker stop grace period because releasing locked RAM can take time. Thermal emergencies need a separately bounded stop policy; a long normal grace period must not imply permission to keep a dangerous workload running. |
| Telemetry and watchdog | Verify a read-only host provider for all required channels before any model start. Missing CPU temperature, stale data, monitor failure, suspend/resume, and supervisor failure must block or end the session. No hardware provider has been selected or tested in this audit. |
| Dependencies and versions | Pin the Linux source/build identity, image digests, CUDA/driver compatibility, and OpenCode version. No installed CLI was executed to discover versions during this audit. No driver or dependency updates were performed. |

The prior unexplained shutdown remains unresolved. None of these file-level findings establishes a safe live operating envelope.

## Next implementation step

The [Docker dummy lifecycle harness](containers/lifecycle/README.md) now implements real container control for a fixed sleeping worker and descendant, with synthetic telemetry, no GPU, and no model or project mounts. It validates one active session, ownership, deadlines, cancellation, forced stop, host-process death/lease expiry, persistent faults, and cleanup. It is a separate development CLI, not a live adapter for Strata/OpenCode or an extension of the TypeScript simulator's approved scope. Live model launch paths remain absent.

A [pinned Linux build/configuration proposal](containers/strata-proposal/README.md) is now prepared with build/launch disabled: Strata commit `296b59d2f73c8f04a805df29c2fa97655adace78`, CUDA 13.0 Linux amd64 base manifest digest, architecture 86 only, no vision, one compiler job, and no compile retry. Only registry metadata was read; no CUDA image was pulled or Strata source compiled. Proposed Linux context/mmap/speculation/resource changes are unapproved and do not alter the Windows configuration.

The [safety milestone](containers/safety/README.md) records ten mocked tests and three real non-GPU watchdog cases. The separate host watchdog stopped a dummy that ignored SIGTERM and read no lease of its own, including when the heartbeat-producing parent was killed. Required production liveness/daemon/suspend/thermal integration is still outstanding. A one-shot sensor audit read GPU temperature/power/VRAM/throttle flags and RAM/AC status. CPU temperature and CPU thermal-throttle status are not validated. Existing Armoury Crate/ASUS status access was investigated; the fixed CPU status read was denied. The owner prefers a dedicated headless monitor; its [design](containers/safety/MONITOR_DESIGN.md) reuses verified driver interfaces without another full monitoring UI.

The owner-authorized administrator ASUS CPU probe subsequently resolved the read-access denial: DSTS returned a 90 °C candidate. The owner's later Armoury screenshot showed CPU 81 °C / GPU 57 °C; the readings were not simultaneous. See [CPU access validation](containers/safety/CPU_ACCESS_VALIDATION.md). A query-only Windows CPU-limit diagnostic was added, but it does not establish hardware thermal-throttle status and is not used to fill that channel.

The immediate gate is CPU sensor meaning/freshness validation and a CPU throttle source, then an integrated dedicated monitor/watchdog and a reviewed capped-builder manifest. Model/driver compatibility, two-container shutdown ordering, API request budgets, and OpenCode's filesystem restrictions still require implementation and testing. Before any Strata startup, obtain explicit owner approval for the model workload and policy. Future Strata image builds and downloads must also be separately identified because they can use significant CPU, network, and disk resources. No Strata source build was run during these milestones.

## Preserved-file fingerprints

These SHA-256 fingerprints identify the inspected inputs and allow checking that this audit left them unchanged:

| File | SHA-256 |
| --- | --- |
| `D:\AI\Dockerfile` | `020a6207a93233beb31a00217276ccb94882f8967cb47caeefaa68e8655d0c6f` |
| `D:\AI\docker-entrypoint.sh` | `ef162824f69c28adbb12595a86f722fc35708cfaf5d48650b5f50f4fb90a6bfe` |
| `D:\AI\run-coder-iq1_m.bat` | `3bfb70e4fa093674d13f1d9470f5cd3f6bce82bb1d86ca538f23d0e3bbbf528b` |
| `D:\AI\strata-coder-iq1_m.json` | `e622edbaf8f415a5555d91511efd99525b53c866e53b70d844246f3afa56d031` |
