# Fifth Strata API attempt: bounded request-silence correction

18 October 2026. **Prepared offline, not approved or started.**

## Breakthrough and remaining blocker

The [fourth result](FOURTH_API_RESULT.md) confirms real GPU model startup, captured
CUDA verification graphs and API health on container loopback. Exactly one request
was sent. It returned HTTP 503 after the upstream server ended its engine for
30 seconds of silence during the 19-token prompt. Zero text tokens were reported.
No temperature, power, RAM, VRAM or OOM stop occurred. The logs establish that
watchdog action; they cannot distinguish ordinary CPU/I/O slowness from a stall.

## One application-setting correction

| Setting | Fourth attempt | Fifth proposal |
| --- | --- | --- |
| `engine_silence_s` | 30 | **75** |
| Independent request hard deadline | 90 seconds | **90 seconds, unchanged** |
| CPU admission / stop | 93°C / 97°C | Unchanged |
| All hardware/resource/context/output/lifetime limits | Fourth reviewed scope | Unchanged |

This changes the upstream application's silence window, not the independent
safety or request deadlines. Upstream adds a prompt-size allowance to the first
silence window and valid progress can reset it; the independent 90-second request
watcher still ends a request even if that inner watchdog has time left. No zero/
unlimited timeout, no retry/reload, no extra request, no larger hardware budget.
This may allow a slow prompt to finish; it cannot guarantee a useful response.

The actual pinned `engine_silence_s` parser was executed offline, along with the
five pure upstream argument-builder functions, without importing the full server,
starting native code or reading live sensors. The arguments remain exactly the
same as the fourth attempt, including `--spec 2`, prefill 32, context 512, 64
requested cache slots and no MTP/suffix drafting. The fourth engine rounded cache
slots to 82 internally (0.16 GiB); the CLI flag is not a hard VRAM quota. Monitored
VRAM/power stops remain the actual guard boundaries.

## Single operation and exact request

Reuse the imported pinned CUDA image, hash-verified Linux Strata 0.1.44.1 artifacts,
staged Python 3.13.15/dependencies and existing read-only IQ1_M data. The included
tiny no-GPU capacity/swap probe precedes one GPU-enabled container. Require fresh
admission, qualify guest limits, start the model/API once, wait for health, submit
exactly one request, save its result and stop/retain container/logs on all outcomes.
No compilation, installer/setup, image/model download/import, benchmark, calibration,
OpenCode worker, MCP, automatic restart/retry or fault reset.

API only on container loopback 127.0.0.1:8080; network none, no host/LAN ports.
Request, context 512 tokens, completion at most eight tokens, response at most 16 KiB:

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

A passing answer needs nonempty real assistant text and consistent token usage.

## Unchanged hard limits

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no restart/edit |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes |
| CPU | Admit <=93°C for ten seconds; stop >=97°C; query <=1.5 seconds |
| GPU admission | <=60°C, <=40 W, device VRAM used <=4096 MiB |
| GPU stop | >=75°C, >=100 W or device VRAM used >=14336 MiB |
| Host RAM | >=8192 MiB free at admission; stop >=28672 MiB used |
| Power/throttle | AC required, GPU thermal-throttle flag known false |
| Freshness/leases | 2.5 seconds; invalid/missing/stale/failed feeds fault |
| Sampling | CPU 1-second slots; GPU about 1 second, query <=1 second |
| Admission/startup | Admission <=90 seconds; initial reader wait <=5 seconds; API readiness <=180 seconds |
| Request | **90-second hard deadline**, exactly one request |
| Lifetime/stop | Model/container <=300 seconds; outer <=410 seconds; owned stop confirmation <=5 seconds |

Same non-root UID 65532, read-only root and source/engine/Python/config/model binds,
capabilities dropped, no-new-privileges, private IPC, no socket/credentials/project
workspace/network/ports. Work/tmp 64 MiB each and shared memory 16 MiB charged to
the same 4-GiB memory cap. Exactly one fixed GPU `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`;
--gpus all only after that identity check. Same controller/guard/guest leases,
every CPU frame checked, graceful shutdown then owned forced stop if needed.
No Windows/WSL/Desktop/fan/firmware/power/clock or original Strata configuration edit.

All four attempts remain consumed and preserved with original decisions, frozen
helpers/inputs, raw samples, logs and inventories; the first supplement and fourth
launch-path correction are checked as recorded. Their containers/disks are not
reset/removed. Preparation/execution verify all four and older build evidence.

GPU power/VRAM thresholds are software stops, not hardware caps. Host/driver/daemon/
suspend failure can prevent stopping; shared-Docker cancellation limitations remain.
No global Docker/WSL stop or device cleanup. Model startup worked in the fourth run,
but request completion/quality and worst-case memory fit remain unproven.
CPU exception: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation stays false and CPU throttle unknown. Small files are hashed;
large model files use metadata/identity/prefix checks, not full-content hashes.
These unchanged source/cancellation/integrity limitations require this new scope's
acceptance along with retained container/logs and the explicit 30 -> 75 change.

## Frozen validation and launch

404 offline tests pass (39 runtime + 365 supervisor), including the actual upstream
75-second parser, rejection of zero/90/91 as proposal values and independent
90-second hard termination, all prior fault channels and four-attempt preservation.
No native Linux process, live CPU/GPU reader or Docker call ran in preparation.

Review SHA256: `cbbcdf85aa9a72b6122fc1c30ecdaf89fe2ba0347ef5e17b73868cbcfcfaf38b`.
Policy SHA256: `58c2cb4fc16faeb62279cfee73c1b66b0b0c06d7a631091efd4730771015a4df`, unchanged.
Packet: `.runtime/model-api-timing-review/cbbcdf85aa9a72b6122fc1c30ecdaf89fe2ba0347ef5e17b73868cbcfcfaf38b/review.json`.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\64524f90cfec430b958dddb887dbcdef`.
The packet/frozen 75 helpers bind all arguments, mounts/environment, contract,
unchanged policy, parser/source audit, timing change and preservation proofs.

New namespace `.runtime/model-api-5`; launcher `.runtime/model-api-launch-5`.
Actual `containers/model-runtime/model-api-5-approval.json` is **absent**. Its disabled
template binds this exact scope/review/policy, explicit request timing acceptance,
source/limitations and retained stopped container. Earlier approvals are spent.
The one-attempt fourth approval does not authorize a fifth launch.

After owner approval: **`python -B local_worker.py run-model-api`**, through the
frozen hidden `run-model-api-reviewed.ps1` administrator wrapper in this review
folder. Wrapper syntax and the fifth log destination are checked; the original
fourth wrapper/correction stay preserved. Windows administrator consent is for the
existing passive CPU reader. `cancel-model-api` targets only this fresh attempt;
it cannot reset a fault. Historical launchers/decisions must not be reused.

The desired next result is one real answer, followed by a bounded OpenCode edit
submitted by Codex, returned patch and confirmed shutdown.
