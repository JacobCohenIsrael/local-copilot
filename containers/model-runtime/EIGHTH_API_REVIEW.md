# Eighth Strata API test: coordinated Docker startup status check

19 October 2026. **Prepared offline; not approved or launched.**

## Evidence and correction

The [seventh attempt](SEVENTH_API_RESULT.md) passed CPU admission at 94°C and
started its container. The watchdog's Docker inspect exceeded one second during
startup, causing MODEL_WATCH_ERROR and controlled stopping. Empty logs/no saved API
result leave actual guest/model initialization and request count unknown. All four
host processes exited. All seven attempts and original configurations are preserved.

Source review exposes an overlap: once ARMED is published, the parent can enter
its existing 1.5-second Docker start call while the watcher enters its one-second
Docker status check. A fake daemon with a 1.3-second start reproduces that timeout
class. It does not establish the real daemon's internal delay cause.

The correction coordinates that transition without extending existing limits:

1. After fresh admission and the final created-container contract check, the
   guard grants one start handoff and publishes ARMED. It remembers that instant
   on its own monotonic clock; grants cannot be reset or repeated.
2. The parent rechecks approval, latest ARMED state and guard lease, then calls
   Docker start **once**, still with the existing **1.5-second** command deadline.
   On success it publishes one complete bounded start receipt with exact owned
   container/review identity, one call and measured duration <=1.5 seconds.
3. While waiting for that receipt, only the competing periodic status check is
   deferred. CPU/GPU telemetry, every CPU-frame check, controller/guard pulses,
   freshness, cancellation, thermal/resource stops and outer deadline still run.
   The handoff is bounded by **2.5 seconds**, reusing the existing lease bound.
4. On a valid timely receipt, the guard resumes the full contract/running/OOM
   check under the unchanged **one-second** inspect deadline. Missing/late/invalid
   receipts, a successful start with no running container, contract drift or any
   later inspect timeout are fatal. No timeout suppression or retry.

The host's 300-second model lifetime now counts from the guard grant **before**
container startup, rather than a later first status observation. This prevents
the handoff from extending that lifetime. Guest/API/request limits remain intact.
The new coordination cap is not a longer start/status/lease deadline. No extra
monitor process, thermal-source work, CPU-placement or resource change is included.

## Exact single operation after approval

Reuse the existing imported pinned CUDA image, exported/hash-verified Linux Strata
0.1.44.1 executable/library, staged Python 3.13.15/API dependencies and read-only
IQ1_M data. Recheck all seven attempts/build/input identities and original settings.
Run the included tiny no-GPU capacity/swap probe, create one GPU-enabled container,
require fresh admission, qualify guest limits, load Strata once, wait for API
health, issue exactly one request, save its result and confirm owned stopping.
Retain the stopped container/logs on success and failure.

Loopback API inside network-none container; no host/LAN ports or project files.
Context 512 tokens, at most eight output tokens, response at most 16 KiB:

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

Passing requires real nonempty assistant text, consistent token accounting and
confirmed shutdown. No OpenCode worker/coding task, compilation, installer/setup,
downloads/import, benchmark/calibration, automatic engine reload/retry or fault
reset. GPU model/API startup was proved in the fourth run; a successful real text
answer and useful coding workflow remain unproven.

## Existing limits: unchanged from the seventh scope

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no edit/restart |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes; no added affinity |
| CPU admission / stop | **<=94°C for ten seconds / stop >=97°C** |
| CPU sampling/query | 1-second slots; query <=1.5 seconds |
| GPU admission | <=60°C, <=40 W, used device VRAM <=4096 MiB |
| GPU stop | >=75°C, >=100 W or used device VRAM >=14336 MiB |
| GPU sampling/query | About 1 second; query <=1 second |
| Host RAM | >=8192 MiB free at admission; stop >=28672 MiB used |
| Power/throttle | AC required; GPU thermal flag known false |
| Freshness/leases | 2.5 seconds; failed/missing/stale/invalid feeds fault |
| Admission/readiness | Admission <=90 seconds; initial CPU wait <=5 seconds; API readiness <=180 seconds |
| Start/status | Docker start <=1.5 seconds; periodic inspect <=1 second; coordinated handoff uses existing 2.5-second lease bound |
| Request | Inner engine silence 75 seconds; independent hard deadline **90 seconds**, exactly one request |
| Lifetime/stop | Model/container <=300 seconds; outer <=410 seconds; owned stop confirmation <=5 seconds |

Same fixed GPU `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; --gpus all only after single-device identity
confirmation. Same UID 65532, read-only root/source/engine/Python/config/model
binds, capabilities dropped, no-new-privileges, private IPC, no sockets, credentials,
network/host ports. Work/tmp 64 MiB each and shared memory 16 MiB charged to the
same 4-GiB cap. Same --spec 2 minimum verification width, no MTP/suffix drafting,
prefill 32, one pool worker, context 512/int8 KV, requested cache 64 (engine
previously rounded to 82), no optional probes. No CPU affinity change: WSL still
exposes one virtual CPU and Docker's one-CPU quota has no primary-core pin.

Keep immutable state snapshots (at most 16 x 16 KiB) and bounded parent errors;
the start receipt also uses the bounded single-open file reader. Watcher errors
now retain the same precise bounded command/timeout/traceback details. Same
independent host/guest leases, graceful close then owned forced stop if needed,
Docker logs bounded 2 x 1 MiB plus retained diagnostics. Stop only the immutable
owned ID; no old-container/bare-disk cleanup or global Docker/WSL stop. No firmware,
fan, power, clock, driver or original Strata configuration edit. CPU-build controls
remain 92°C admission / 97°C stop.

## Limitations and new approval

CPU source: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation remains false and CPU throttle unknown. GPU power/VRAM are
monitored software stops, not hard hardware quotas. Host/driver/daemon/suspend
failure can defeat stopping; shared-Docker cancellation limits remain. Small
inputs are hashed; large model files use metadata/identity/prefix checks, not full
hashes. Memory fit and response completion/quality remain unproven. The fifth
exact file-error call site and seventh underlying daemon-delay cause are unknown.
Offline simulation is not proof that the next live request will succeed.

All seven earlier approvals are spent. Their original decisions, frozen helpers/
inputs, raw metrics, logs/events and inventories are verified unchanged, including
the first supplement and fifth consent history. Old faults are not reset/reused.
The new decision must accept this startup coordination, unchanged source/
cancellation/integrity limitations and retained stopped container/logs.

## Frozen validation and launch

**436 offline tests pass: 71 runtime + 365 existing supervisor tests.** They
reproduce the old overlap and exercise a slow start through the real watcher with
fake time/daemon/telemetry. During the handoff, CPU/GPU hot events, cancellation
and lease loss still stop. Missing/invalid receipts, start timeout, post-start
inspect timeout, no running container and contract drift remain fatal without a
retry. Lifetime anchoring is checked; the exact unchanged policy/limits and all
seven histories are checked, old approvals rejected, and absent approval refuses
before live access. No live CPU sensor/GPU query, Docker access or Linux native
model process ran in preparation. Generated-file Windows fixtures are file-only.

Review SHA256: `5e7f1a40d21c24bd64fa495d8b821994def2e8e3c189318c3175b432de42b8d1`.
Policy SHA256: `578ca27e5ba15466544c3f520a1ba9c00efe0d3969b3ef0842fe495d37fde5e2`, identical to the seventh scope.
Packet: `.runtime/model-api-startup-review/5e7f1a40d21c24bd64fa495d8b821994def2e8e3c189318c3175b432de42b8d1/review.json`.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\0acb217836d94275996d07271e555c2d`.
Frozen helper count: 77. The packet binds source/helpers,
exact Docker contract/arguments/configuration, unchanged policy/request/timing,
startup coordination and seven-attempt preservation proofs.

Fresh namespace `.runtime/model-api-8`; launcher `.runtime/model-api-launch-8`.
Actual `containers/model-runtime/model-api-8-approval.json` is **absent**; its
template is disabled. After exact approval, `python -B local_worker.py run-model-api`
runs through this folder's frozen hidden `run-model-api-reviewed.ps1` administrator
wrapper. Syntax and eighth log destination checked offline. Windows consent is
for the existing passive CPU reader. `cancel-model-api` only addresses this new
session and cannot reset a terminal fault. Earlier launchers/decisions are spent.

The next functional milestone remains one real answer, then one bounded OpenCode
edit and returned patch alongside Codex with confirmed shutdown. This review
authorizes no execution by itself.
