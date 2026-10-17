# Usage-conscious checkpoint — 16 October 2026

Owner stop rule: check the five-hour Codex allowance before substantial work
and between bounded steps. At 5% remaining (95% consumed), save this checkpoint,
stop any task-owned workers/containers, and pause. Leave unrelated processes
and Docker Desktop alone. Resume on owner direction or after the allowance
resets. The five-hour window reset; latest check: 57% remaining.
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
- CPU hardware thermal-throttle source remains unknown. Owner approved the
  CPU-only build exception and reviewed controls on 16 October 2026; the missing
  flag stays null. Windows frequency limits remain advisory. This exception
  does not cover model runtime or authorize compilation. Do not ask again for
  this policy decision; see the approval record below.

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
is version 2.0.26; the matching Linux musl binary and libraries are now verified
for the fake-only compatibility check described below.
`Dockerfile.proposed` is unbuilt and refuses execution by default. Model ID is
unresolved. Request-gate proxy/network, actual token/call/deadline enforcement
and live sensor admission remain to implement; OpenCode steps are not a hard
request cap. No Docker image build/pull or real model call has run.
Offline request-budget logic is now in `containers/worker/request_gate.py`:
15 additional tests pass, covering call/context/task reservations, monotonic
deadlines, bounded request/response bytes and latched faults. See
`containers/worker/REQUEST_GATE.md`. The CLI uses a synthetic token counter;
there is no HTTP server, exact tokenizer, engine cancellation or live enable.
That next step is complete in `containers/worker/http_rehearsal.py`: 16 real
loopback integration tests and two CLI checks passed. Auth, gate admission,
JSON/SSE relay, deadlines, cancellation/client loss and cleanup are exercised
against owned fake servers only. See `containers/worker/HTTP_REHEARSAL.md`;
evidence is `.runtime/worker-http/{stream,timeout}.json`. No arbitrary upstream
URL or live-enable exists; that HTTP-only milestone started no Strata/OpenCode/container. The timer
is same-process; actual engine cancellation, exact token counting, durable
FAULT state and isolated Docker networks remain unfinished.
Linux OpenCode compatibility is now complete for a text response: the pinned
`@opencode/cli-linux-x64-baseline-musl` 2.0.26 binary and two pinned Alpine
libraries ran in the cached Python/Alpine container, network=none, no GPU,
0.5 CPU, 512 MiB/no extra swap, 64 pids, read-only input/root and a 10-second
inner deadline. The real CLI returned `synthetic OK` via fake loopback servers
and the request gate; no workspace file was edited. All test containers were
removed. The CLI needed `--standalone` and cwd, not the draft's `--dir`.
The gate strictly accepts observed store=false, usage-only stream_options and
the output-cap alias, without increasing budgets. All 48 worker tests passed.
See `containers/worker/OPENCODE_COMPATIBILITY.md`. Artifact directory:
`.runtime/opencode-linux/2.0.26-musl-44f176ba`; successful receipt:
`.runtime/opencode-linux/checks/4c0271d5a7514d5f8c4b62f89519500e/result.json`.
Auxiliary requests and fake-directed file actions are now verified; see
`containers/worker/OPENCODE_ACTIONS.md`. Disabling agent.title reduces a plain
reply to one model request. An allowed example.py edit and shell/external-read/
unlisted-write denials each complete within the unchanged two-call limit.
Internal allow rules use location-relative paths; actual tool arguments use
path, and the command tool is shell. The proposal is corrected accordingly.
All 51 worker tests passed. Native receipts are recorded in that report;
all owned test containers were removed. No actual model or host project ran.
The complete bundle path now passes in `containers/worker/bundle_rehearsal.py`:
synthetic originals -> selected copy -> read-only worker input -> scratch edit
-> bounded returned bytes -> confirmed removal -> host import/patch collection.
Original selected/unselected files stayed unchanged. The native result is
PATCH_FOR_REVIEW with a 113-byte patch, two fake calls and no OOM. All 59 worker
tests pass (eight new bridge tests). See `containers/worker/BUNDLE_REHEARSAL.md`.
Evidence: `.runtime/bundle-rehearsals/00b01b6a858d448686e1f5cc7049645c/result.json`.
No original/baseline or writable host workspace is mounted; no real project,
arbitrary task, actual tokenizer/model or live policy is enabled by this CLI.
The concrete CPU-only policy review is now in
`containers/strata-proposal/BUILD_POLICY_REVIEW.md` and `build-policy.draft.json`.
The owner APPROVED the exception allowing unknown hardware throttle status for
one CPU-only compile, never model runtime. Reviewed start <=75 C for 10 seconds,
stop >=80 C, one CPU/4 GiB/no GPU, 30 minutes, no retry; these are restrictive
review values, not certified safe limits. The decision is hash-bound in
`build-policy-approval.json`, quoting the owner's reply. It is controls-only,
not workload approval. The original draft remains unchanged as a historical
snapshot. Existing `build_guard.py` rejects all actual builds; no live policy
was enabled. Its legacy sample validator still requires a throttle flag.
`build_policy_review.py` accepts synthetic observations only and now reports
POLICY_APPROVED_BUILD_BLOCKED, preserving unknown as null. Policy/manifest
changes invalidate the approval binding; reader changes are explicitly reported
for revalidation. Five additional tests pass (23 proposal tests total), including
three real PowerShell -Describe checks outside the sandbox, without sensor reads.
The reader's former timing gap is addressed in code: 1,920 samples/32 minutes,
fixed monotonic slots, remaining coverage and early exit on query failure/overrun.
The three-sample default stays unchanged. Short probes cannot admit a build;
simulation requires enough remaining reader time for the full build plus stop,
subtracting sample age. No long hardware run or real stop-latency proof occurred.
Next validate source meaning/update behavior and the revised reader, then wire
and test the live controller/stop deadlines. Source validation, actual coverage,
controller/stop deadlines, disk/download
budgets and final build workload approval remain outstanding. Do not read an
approval of the exception as approval to start compilation or load a model.
Keep build/model launch disabled
until those gates and explicit approvals are satisfied; avoid more optional
dummy infrastructure, MCP or UI work.
Strata engine build/admission, live tokenizer, durable FAULT/watchdog and
real coding-task integration remain gated. Keep each diff focused.
Do not describe either route as ready for immediate model use.

Use a tiny disposable coding task and limited context for the first approved
local delegation. Cloud Codex reviews its output. Keep existing source/data
read-only and avoid feeding this full conversation to the local worker.

Important evidence: `.runtime/safety-readiness/elevation-fb0da8d4326c4053a7299605c8a280d5/admin-result.json`.
No task/model execution should be inferred from a successful read-only probe.
