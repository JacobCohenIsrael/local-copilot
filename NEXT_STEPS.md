# Usage-conscious checkpoint — 16 October 2026

Owner stop rule: check the five-hour Codex allowance before substantial work
and between bounded steps. At 5% remaining (95% consumed), save this checkpoint,
stop any task-owned workers/containers, and pause. Leave unrelated processes
and Docker Desktop alone. Resume on owner direction or after the allowance
resets. The five-hour window reset; latest check: 97% remaining.
No task-owned workloads are running.

Owner priority: reach a first bounded Strata coding task quickly and reduce
cloud Codex usage. Freeze optional diagnostics, dashboards, new monitor suites,
MCP, performance tuning, and the historical TypeScript/JetBrains application.

## Decisions and safety scope

- Route selected by owner: keep Strata itself in Docker and prepare the Linux
  engine build. Do not reopen the temporary Windows-engine option.
- This choice is not model-start or policy-change approval. No Strata model,
  CUDA build, stress test, driver install, power/firmware change, or live policy
  activation has been performed or newly authorized.
- Preserve original `D:\AI` launch/config files. A first-use configuration must
  be a separate reviewed copy; do not run the original launcher as a shortcut.
- CPU temperature read works with administrator access through fixed ASUS DSTS
  endpoint `0x00120094`. Executed snapshot: 90 °C. Later Armoury screenshot:
  CPU 81 °C / GPU 57 °C. Not simultaneous, not a calibration or safe envelope.
- CPU hardware thermal-throttle source remains unknown. Windows frequency
  limits/counter metadata are advisory; do not fill the missing flag with false
  or silently waive it. Any provisional policy change needs owner approval.

## What already works

- Pure simulator: `SUPERVISOR.md`; its fixed policy is simulation only.
- Real CPU-only Docker lifecycle harness: `containers/lifecycle/README.md`;
  16 unit tests, seven Docker cases, JSON CLI smoke test passed.
- Independent host watchdog prototype: `containers/safety/README.md`;
  ten initial unit tests and three real Docker cases passed. It stops an
  uncooperative dummy/descendant after lost producer heartbeat. It is scoped to
  dummy targets and is not a live Strata guard yet.
- CPU access: `containers/safety/CPU_ACCESS_VALIDATION.md`; one hash-checked
  elevated probe completed and exited. Three additional CPU-limit unit tests
  were added. No persistent elevated helper was installed.
- Read-only GPU/RAM/AC availability worked. A low-overhead direct-NVML collector
  is designed, not implemented. ASUS is the preferred existing CPU source.
- Disabled pinned Linux build proposal: `containers/strata-proposal/`.

## Smallest next implementation

Pinned Strata and llama.cpp source archives are staged in
`.runtime/strata-build/1537f5ec/input/source`, with a disabled
`build-manifest.json` beside `input/`. Downloaded source totals 62,426,870 bytes;
no source code was executed. Four key source files match the reviewed snapshot.
`containers/strata-proposal/prepare.py` prepares this package without Docker calls.
The selected compile route is an ordinary Docker container capped at one CPU,
4 GiB RAM, zero swap, 128 processes, no GPU requests, one compiler job, and a
30-minute inner timeout. No Docker socket/model/credential mounts. Its writable
container layer holds build dependencies and output; source input is read-only.

The sensor/guard contract is connected to this compiler identity; see
`containers/strata-proposal/BUILD_GUARD.md`. Nine mocked checks and four Docker
rehearsals passed (synthetic heat, stale sensor, lost controller, cancellation).
The bounded elevated reader emitted three samples (94, 94, 83 °C) and exited.
CPU throttle remains null and sensor safety validation is incomplete, so actual
compilation remains blocked. Next settle the live CPU-only build admission
policy and outstanding channels; do not silently waive them.
Docker Strata requires the capped Linux engine build; it is not already a ready
cached image. Do not start the compiler until remaining admission gates and the
explicit build approval are satisfied.

Offline task intake and patch collection now work in `containers/worker/`:
eight tests passed, including real hard-link rejection and Git patch validity.
Only explicitly named UTF-8 files are copied; output growth, unexpected paths,
baseline changes, links and oversized patches are rejected. No originals are
edited, no process/model runs, and no patch is applied. Fixed offline caps:
eight files, 64 KiB/file, 128 KiB total, 4,000 task characters, 64 KiB patch.
These are test caps, not token accounting or an approved live policy.
OpenCode's Docker execution, token/time/tool budgets and guard integration
remain unfinished.
`containers/worker/opencode_plan.py` now emits a disabled container/config
proposal from a pristine bundle. Three new checks pass (11 worker tests total).
It denies tools by default, permits named-file read/edit only, and rejects
project OpenCode/agent/credential controls. Installed Windows package metadata
is version 2.0.26; Linux binary/checksum/runtime dependencies are not verified.
`Dockerfile.proposed` is unbuilt and refuses execution by default. Model ID is
unresolved. Request-gate proxy/network, actual token/call/deadline enforcement
and live sensor admission remain to implement; OpenCode steps are not a hard
request cap. No OpenCode command, Docker image build/pull, or model call ran.
Offline request-budget logic is now in `containers/worker/request_gate.py`:
15 additional tests pass, covering call/context/task reservations, monotonic
deadlines, bounded request/response bytes and latched faults. See
`containers/worker/REQUEST_GATE.md`. The CLI uses a synthetic token counter;
there is no HTTP server, exact tokenizer, engine cancellation or live enable.
Next connect this core to a bounded HTTP proxy with a fake backend, still
without loading Strata. Keep the change focused and reviewable on this branch.
Do not describe either route as ready for immediate model use.

Use a tiny disposable coding task and limited context for the first approved
local delegation. Cloud Codex reviews its output. Keep existing source/data
read-only and avoid feeding this full conversation to the local worker.

Important evidence: `.runtime/safety-readiness/elevation-fb0da8d4326c4053a7299605c8a280d5/admin-result.json`.
No task/model execution should be inferred from a successful read-only probe.
