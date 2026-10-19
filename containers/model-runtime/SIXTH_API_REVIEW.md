# Sixth Strata API test: Windows state-file correction

18 October 2026. **Prepared offline. Not approved; nothing launched.**

## What changed and what is still unknown

The [fifth attempt](FIFTH_API_RESULT.md) ended during admission on a parent
PermissionError. Its container never started. The saved error omitted the failing
filename/operation/traceback, so its exact cause cannot be proved afterward.
Its cleanup FAULT/CANCELLED followed that exception; it was not a second user
cancellation. All five attempts, both fifth consent launches and original settings
are preserved and verified by pinned inventories.

Generated-file tests reproduced a relevant defect in the old parent state reader:
a complete renamed file can be visible while Windows still holds DELETE access;
the ordinary read fails. Tests also exposed replacement conflicts while an old
state file is held open. This is consistent with [Microsoft's explanation of
rename sharing](https://devblogs.microsoft.com/oldnewthing/20211022-00/?p=105822/),
but does not prove the fifth failure's missing call site.

The correction publishes **immutable sequenced state snapshots**, each through a
new filename, rather than replacing the shared state file. It reads a complete
snapshot once with read/delete sharing and no write sharing. At most 16 state
records of 16 KiB each; the existing single-writer guard lock is retained. Pending
files cannot become state, missing/gapped/oversize/malformed/linked/actively written
records fail closed, and genuine access denial/exclusive handles still stop the
attempt. No permission/ACL changes, error suppression, retries or longer leases.
The existing guard/guest leases remain independent safety controls; state files
are not substituted for fresh telemetry or lease progression.

Parent failures now retain bounded operation, message, errno/Windows error,
filenames and traceback locations, in addition to existing process timeout data.
This makes a different remaining file-access failure diagnosable. Historical
error records remain unchanged. The fix is offline-tested; live success is unproven.

## Exact single operation

After a new exact owner decision and Windows administrator consent, reuse the
already imported pinned CUDA image, exported Linux Strata 0.1.44.1 executable and
library, staged Python 3.13.15/API dependencies and read-only IQ1_M model data.
Recheck all five previous attempts/build/settings/input identities. The included
tiny no-GPU capacity/swap probe precedes one GPU-enabled model container. Require
fresh admission, qualify the guest, load Strata once, wait for API health, submit
exactly **one** request, save the result, stop and retain the container/logs.

Private container loopback API only, no network/host port or project files.
Context 512 tokens, output at most eight tokens, response at most 16 KiB:

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

Success requires actual nonempty assistant text, valid token accounting and
confirmed stopping. No OpenCode/coding task in this test, compilation, downloads,
image import, benchmark/calibration, setup, engine reload/restart, automatic retry
or fault reset. The next milestone remains a real answer, then one bounded
OpenCode edit and returned patch alongside Codex.

## Limits: unchanged from the fifth reviewed test

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no edit/restart |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes |
| CPU | Admit <=93°C for ten seconds; stop >=97°C; query <=1.5 seconds |
| GPU admission | <=60°C, <=40 W, used device VRAM <=4096 MiB |
| GPU stop | >=75°C, >=100 W or used device VRAM >=14336 MiB |
| Host RAM | >=8192 MiB free at admission; stop >=28672 MiB used |
| Power/throttle | AC required; GPU thermal flag known false |
| Freshness/leases | 2.5 seconds; failed/missing/stale/invalid feeds fault |
| Sampling | CPU 1-second slots; GPU about 1 second, query <=1 second |
| Admission/readiness | Admission <=90 seconds; initial CPU wait <=5 seconds; API readiness <=180 seconds |
| Request timing | Inner engine silence 75 seconds; independent hard deadline **90 seconds** |
| Lifetime/stop | Model/container <=300 seconds; outer <=410 seconds; owned stop confirmation <=5 seconds |

No further timing adjustment. Inner silence remains 75 as approved for the fifth
test; that attempt never reached it. The independent 90-second deadline still
wins even if upstream prompt allowance or progress extends its silence window.

Same native --spec 2 minimum verification width, no MTP/suffix drafting, prefill
32, one pool worker, requested expert cache 64 (native previously rounded to 82),
int8 KV, context 512 and no optional probe/benchmark. VRAM reserve is a hint;
monitored power/VRAM stops are not hardware quotas. Same UID 65532, read-only root
and source/engine/Python/config/model binds, capabilities dropped, no-new-privileges,
private IPC, no sockets/credentials/network/host ports. Work/tmp 64 MiB each and
shared memory 16 MiB charged to the same 4-GiB memory cap. Exactly the fixed GPU
`GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; --gpus all only after its single-device identity check.

Same controller/guard/guest leases, every CPU frame checked, graceful shutdown
then owned forced stop if needed. Retain stopped container on success/failure,
Docker logs bounded 2 x 1 MiB plus recorded diagnostics. Stop only the immutable
owned container ID; no old-container removal, bare-disk cleanup or global Docker/
WSL stop. No firmware, fan, power, clock, driver or original Strata setting edit.

## Unchanged accepted limitations; new approval required

CPU source: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation remains false and CPU throttle unknown. The fourth run proved
GPU model startup/API readiness but no successful generated text yet. Worst-case
memory fit and useful request completion remain unproven. GPU power/VRAM are
software stops; host/driver/daemon/suspend failure can prevent stopping. Shared-
Docker cancellation limits remain. Small inputs are hashed; large model files
use metadata/identity/prefix checks, not full hashes. Accept these limitations
for this one scope, retain logs/container and accept the reviewed file-access
correction. All five previous approvals are spent.

## Validation and frozen launch

**416 offline tests passed:** 51 runtime + 365 existing supervisor tests. The
generated Windows rehearsal reproduced four old-reader denials, accepted all four
corrected reads and published eight immutable snapshots, including a new snapshot
while a previous reader was held open. Old snapshots unchanged; native handle
counts unchanged; active writers/exclusive holders still rejected. Simulated
unreadable-state failure stopped without a model start or retry and retained
precise cause. Original policy/inputs and all five inventories are verified.
No live sensor/GPU query, Docker access, model or Linux native process was used
for this preparation. File-only Windows fixture calls are real; model runs are not.

Review SHA256: `1f8494f279fb07c3c3ae2f62b39ba854e04fd1c915816696544416681d3c5b6a`.
Policy SHA256: `58c2cb4fc16faeb62279cfee73c1b66b0b0c06d7a631091efd4730771015a4df`, unchanged.
Packet: `.runtime/model-api-file-access-review/1f8494f279fb07c3c3ae2f62b39ba854e04fd1c915816696544416681d3c5b6a/review.json`.
Frozen helper count: 76.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\fdb1803c2c5c4643b6d5529848b6689d`.
The packet binds helpers, exact Docker contract/arguments/config, file correction,
unchanged policy/timing/request, source audit and five-attempt preservation proof.

Fresh namespace `.runtime/model-api-6`; launch logs `.runtime/model-api-launch-6`.
Actual `containers/model-runtime/model-api-6-approval.json` is absent; its template
is disabled. Previous decisions and frozen launchers must not be reused.
After approval, `python -B local_worker.py run-model-api` runs through this folder's
frozen hidden `run-model-api-reviewed.ps1` administrator wrapper. Windows consent
is needed for the existing passive CPU reader. Wrapper syntax and sixth log
destination are checked offline. `cancel-model-api` addresses only this new
session and cannot reset a terminal fault. Current state is read from the latest
`states/state-NNNN.json`, not a mutable state.json. Session result/diagnostic files
are retained on completion. Preparation does not authorize execution.
