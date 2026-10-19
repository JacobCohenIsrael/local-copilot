# Ninth Strata API test: CPU admission 95°C / stop 98°C

19 October 2026. **Prepared offline; live execution is not approved or launched.**

## Exact policy change

At the owner's request, change only the model/API scope's CPU admission
**94 -> 95°C** and CPU stop **97 -> 98°C**. Admission still requires ten continuous
seconds of qualifying, fresh readings within 90 seconds; stop at **>=98°C** latches
FAULT. A pre-start CPU reading above 95°C resets admission. Once running, a fresh
97°C reading alone does not stop this proposed scope; 98°C does. Cooling cannot
reset a fault. Both changes must be explicitly accepted in the new live decision.
This is a software policy change, not a firmware/power/thermal setting change.

All other limits, startup coordination, arguments, configurations, GPU/RAM/AC
channels, deadlines and CPU placement remain identical to the eighth review.
CPU-only build policy stays **92°C admission / 97°C stop**; its helpers are
byte/hash-unchanged. The new runtime gate uses the reviewed stop policy value
instead of a fixed 97°C comparison. No other runtime execution logic changes.

The [eighth result](EIGHTH_API_RESULT.md) expired admission before Strata started:
89 CPU readings at 91–95°C, 45 above 94°C; five GPU readings above 40 W admission.
The container never started, no model/request ran, and all four host processes
exited. All eight attempts, original decisions and configurations are preserved.
The startup correction remains untested live. The fourth run proved model/API
readiness; a successful generated answer remains unproven.

Offline comparison of the saved eighth CPU stream finds a longest qualifying
sample-endpoint span of about **6.022 seconds at 94°C**, versus **87.995 seconds
at 95°C**, with zero readings above 95°C. This is not continuous physical
temperature evidence or exact guard-clock replay. GPU power above 40 W still
independently resets admission. The next attempt is not guaranteed to admit or
complete, and the new thresholds are not proof of hardware safety.

## One operation after exact approval

Reuse the existing imported pinned CUDA image, exported/hash-verified Strata
0.1.44.1 Linux executable/library, staged Python 3.13.15/API dependencies and
read-only IQ1_M models. Verify all eight attempts, build/source/runtime/model
identities and original settings. Run the included tiny no-GPU capacity/swap
probe; create one GPU container; require fresh admission; qualify guest kernel
limits; start Strata once; wait for API health; submit exactly one request; save
its response and confirm owned stopping. Retain container/logs on either outcome.

Private loopback API within network-none container, no host/LAN port or project
files. Context 512 tokens, maximum eight output tokens, response <=16 KiB:

```json
{
  "model": "qwen3.8-flash-next-coder-iq1_m",
  "messages": [
    {
      "role": "user",
      "content": "Reply with READY. No explanation."
    }
  ],
  "max_tokens": 8,
  "temperature": 0,
  "stream": false,
  "reasoning_effort": "none"
}
```

Success requires real nonempty assistant text, strict token accounting and
confirmed shutdown. No OpenCode/coding worker, compilation, downloads/import,
setup, benchmark/calibration, engine reload/retry or fault reset is included.

## Exact limits

| Control | Value |
| --- | --- |
| CPU admission | **<=95°C for ten seconds**; previously 94°C |
| CPU stop | **>=98°C**, latched; previously 97°C |
| WSL | 1 CPU, 6 GiB RAM, no swap; no edit/restart |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes; no added affinity |
| CPU sampling/query | 1-second slots; query <=1.5 seconds |
| GPU admission | <=60°C, <=40 W, device VRAM <=4096 MiB |
| GPU stop | >=75°C, >=100 W or device VRAM >=14336 MiB |
| GPU sampling/query | About 1 second; query <=1 second |
| Host RAM | >=8192 MiB free at admission; stop >=28672 MiB used |
| Power/throttle | AC required; GPU thermal flag known false |
| Freshness/leases | 2.5 seconds; missing/stale/invalid feeds fault |
| Admission/readiness | Admission <=90 seconds; initial CPU wait <=5 seconds; API health <=180 seconds |
| Startup/status | Start <=1.5 seconds; periodic inspect <=1 second; bounded handoff <=2.5 seconds |
| Request | Inner engine silence 75 seconds; independent hard request deadline 90 seconds; one POST |
| Lifetime/stop | Model/container <=300 seconds; outer <=410 seconds; stop confirmation <=5 seconds |

Fixed GPU `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; --gpus all only after confirming exactly one
matching device. Same UID 65532, read-only root/source/engine/Python/config/model
binds, all capabilities dropped, no-new-privileges, private IPC, no sockets,
credentials, project files, network/host ports. Same work/tmp 64 MiB each and
shared memory 16 MiB within the 4-GiB cap. Same native --spec 2 minimum, no
MTP/suffix drafting, prefill 32, one pool worker, context 512/int8 KV, requested
cache 64 (engine previously rounded to 82), no optional probes.

Retain eighth startup coordination unchanged: guard grants one handoff before
start, parent publishes one same-target successful-start receipt; only competing
periodic inspect is deferred. CPU/GPU telemetry, cancellation and leases remain
active. Missing/late/invalid receipt, contract drift or later status timeout
faults. Host lifetime counts from the guard grant before startup. Same bounded
immutable state files, detailed errors, independent host/guest leases and every
CPU-frame check. Graceful stop then owned force-stop if needed; only the fixed
owned container ID, with Docker logs bounded 2 x 1 MiB plus retained diagnostics.
No old-container/disk cleanup, global Docker/WSL stop, firmware/fan/power/clock/
driver change or original Strata configuration edit.

## Limitations and approval boundary

CPU source: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation stays false and CPU throttle unknown. Raising software
thresholds does not establish firmware calibration or explain the earlier laptop
shutdown. GPU power/VRAM are monitored software stops, not hardware caps;
host/driver/daemon/suspend failure can defeat stopping. Shared-Docker cancellation
limitations remain. Small inputs are hashed; large model files use metadata,
identity and prefix checks, not full hashes. Memory fit and successful response
completion/quality remain unproven. Previous failure causes retain their recorded
limitations. Offline success is not proof of real inference safety or completion.

All eight earlier approvals are spent, with histories, frozen helpers/inputs,
metrics, logs/events and inventories verified unchanged, including the first
supplement and fifth consent history. No old fault/namespace is reset or reused.
Preparing this policy is authorized; **one live attempt still needs the exact new
decision**, accepting both CPU changes, unchanged startup coordination and
source/cancellation/integrity limitations, and retained stopped container/logs.

## Frozen validation and launch

**442 offline tests pass: 77 runtime + 365 supervisor.** Checks include 95°C
admission after ten seconds, reset at 96°C, 97°C allowed while running, 98°C
latched stop, GPU-power admission reset above 40 W, all other fault/deadline
channels, bounded startup/status coordination, eighth manifest/helper tampering,
all eight preservation chains, rejection of all old decisions and refusal before
live access without new approval. Both changed CPU values must be accepted
exactly; all other policy fields, model/configuration/resources/placement remain
unchanged. Windows generated-file fixtures use no hardware. No live CPU/GPU
reading, Docker access, Linux native process or model workload ran in preparation.

Review SHA256: `973f9f16d51c40d8cd2204330a3d87692c4d96b20ad1c818f9664aae7dc649ef`.
New policy SHA256: `03bfb7a9342b266d8e326c66ce6a1aedd8aebc39b7e0b8cf5bfa4832e1d3f109`.
Previous policy SHA256: `578ca27e5ba15466544c3f520a1ba9c00efe0d3969b3ef0842fe495d37fde5e2`.
Only policy changes: `cpuStartC: 94 -> 95`, `cpuStopC: 97 -> 98`.
Packet: `.runtime/model-api-95-98-review/973f9f16d51c40d8cd2204330a3d87692c4d96b20ad1c818f9664aae7dc649ef/review.json`.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\b9126f82673748678fe96b249d36eb34`.
Frozen helper count: 77; frozen inputs: 3.

Fresh namespace `.runtime/model-api-9`; launcher `.runtime/model-api-launch-9`.
Actual `containers/model-runtime/model-api-9-approval.json` is **absent**, template
disabled. After exact approval, `python -B local_worker.py run-model-api` uses
this folder's frozen hidden `run-model-api-reviewed.ps1` administrator wrapper.
Syntax and ninth log destination checked offline; wrapper unexecuted. Windows
consent is for the existing passive CPU reader. `cancel-model-api` only addresses
the new session and cannot reset a terminal fault. Previous decisions cannot
activate it. The next functional milestones remain real text, then one bounded
OpenCode edit/returned patch alongside Codex with confirmed shutdown.
