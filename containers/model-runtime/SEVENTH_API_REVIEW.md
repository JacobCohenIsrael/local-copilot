# Seventh Strata API test: CPU admission 94°C

18 October 2026. **Prepared offline; not approved or launched.**

## Exact change and evidence

The [sixth attempt](SIXTH_API_RESULT.md) reached its admission deadline without
another file-access error, but CPU alone prevented startup. Its 89 CPU readings
were 87–95°C; 38 exceeded 93°C. All recorded GPU/RAM/AC/thermal-throttle start
conditions passed. The container never started and all owned processes exited.

At the owner's request, this proposal changes **only CPU admission 93 -> 94°C**.
The **97°C stop**, required ten-second baseline, all hardware/resource/request/
freshness/lease/lifetime/stop limits, model arguments and configuration remain
unchanged. This is a separately gated seventh scope; it does not reset any old
fault or turn on live execution. CPU-build policy remains at 92°C admission / 97°C
stop. No model test runs without the exact new decision below.

Recorded-point comparison of the sixth CPU stream: at 93°C, 38 samples fail and
the longest qualifying point span is about 8.986 seconds; at 94°C, 19 fail and the
longest span is about 36.006 seconds. This omits real delivery/poll timing and is
explanatory, not a native admission proof or a guarantee of the next run's result.
All original records remain unchanged. Source/cancellation limitations remain.

## CPU placement considered; unchanged

One read-only Windows topology observation reports **Intel i9-12950HX, 16 cores /
24 logical processors**. The reviewed
WSL configuration exposes **one virtual CPU**; the retained Docker contract uses
`NanoCpus=1000000000`, with `CpusetCpus` empty. No least-used-core or primary-core
pin is configured in Docker; `--cpus 1` is a budget, not selection of core 0.

[Docker documents](https://docs.docker.com/engine/containers/resource_constraints/)
`--cpuset-cpus` as core selection, separate from the CPU budget.
[Microsoft documents](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
the WSL `processors` setting as the number assigned to its VM. Inference for this
setup: with one guest virtual CPU there is no alternative guest CPU to select,
and a guest CPU number does not identify the least-used Windows physical core.
Do not set affinity on Docker's client and claim it pins the model in WSL.

No per-core utilization sampling, Windows/VM affinity change, WSL processor-count
increase/restart or new placement policy is included. Keep the one-CPU envelope
and let the existing scheduler operate. This preserves all other reviewed limits
while considering the owner's suggestion. Per-core placement can be reviewed
separately if it becomes a measured runtime blocker.

## One operation after approval

Reuse the imported pinned CUDA image, hash-verified Linux Strata 0.1.44.1 artifacts,
staged Python 3.13.15/API dependencies and read-only IQ1_M model files. Recheck all
six attempts/build/input identities and original settings. Run the included tiny
no-GPU capacity/swap probe, create one GPU-enabled container, require fresh
admission at 94°C, qualify guest limits, load Strata once, wait for API readiness,
submit exactly one request, save the result and confirm owned stopping. Retain
the stopped container/logs on success and failure. No automatic retry/reload.

Loopback API inside network-none container, no host/LAN port. Context 512 tokens,
at most eight output tokens and a response at most 16 KiB. Exact request:

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

Passing needs real nonempty assistant text, valid token accounting and confirmed
shutdown. No OpenCode worker/coding task, compilation, downloads/import, setup,
benchmark/calibration, tuning or fault reset. GPU/API startup was proven in the
fourth run; successful generated text remains unproven.

## Limits

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; unchanged, no edit/restart |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes; no added affinity |
| CPU admission | **<=94°C for ten continuous seconds**, previously 93°C |
| CPU stop/query | **Stop >=97°C**, query <=1.5 seconds; unchanged |
| GPU admission | <=60°C, <=40 W, used device VRAM <=4096 MiB |
| GPU stop | >=75°C, >=100 W or used device VRAM >=14336 MiB |
| Host RAM | >=8192 MiB free at admission; stop >=28672 MiB used |
| Power/throttle | AC required; GPU thermal flag known false |
| Sampling/freshness | CPU 1-second slots; GPU about 1 second, query <=1 second; freshness/leases 2.5 seconds |
| Admission/readiness | Admission <=90 seconds; initial CPU wait <=5 seconds; API readiness <=180 seconds |
| Request | Inner engine silence **75 seconds**, independent hard deadline **90 seconds**, exactly one request |
| Lifetime/stop | Model/container <=300 seconds; outer <=410 seconds; owned stop confirmation <=5 seconds |

Same fixed GPU `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; --gpus all only after single-device identity
confirmation. Same non-root UID 65532, read-only root/source/engine/Python/config/
model binds, capabilities dropped, no-new-privileges, private IPC, no sockets,
credentials/project files/network/host ports. Work/tmp 64 MiB each and shared
memory 16 MiB charged to the same 4-GiB cap. Same native --spec 2 verification
minimum, no MTP/suffix drafting, prefill 32, one pool worker, context 512/int8 KV,
requested cache 64 (engine previously rounded to 82), no optional probes.

Keep the sixth file-access correction: at most 16 immutable state snapshots of
16 KiB each, single-open read/delete sharing without write sharing, strict genuine
denial handling and bounded detailed parent errors. Controller/guard/guest leases
remain independent. Every CPU frame checked; graceful close then owned forced
stop if necessary. Docker logs bounded 2 x 1 MiB plus retained diagnostics.
Stop only the immutable owned ID; no old-container or bare-disk removal, global
Docker/WSL stopping, firmware/fan/power/clock/driver or original Strata edits.

## Limitations and approval boundary

CPU source: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation stays false and CPU throttle unknown. GPU power/VRAM are
monitored software stops, not hardware caps; driver/host/daemon/suspend failure
can defeat software stopping. Shared-Docker cancellation limitations remain.
Small inputs are hashed; large model files use metadata/identity/prefix checks,
not full hashes. Useful response completion and worst-case memory fit remain
unproven. The fifth exact file-error call site remains unknown; the correction
held through the sixth admission stage but has not run a successful full request.

All six earlier approvals are spent. Their evidence, containers, decisions,
frozen helpers/inputs, first supplement and fifth consent records are verified
unchanged. Their faults are never reset/reused. This new decision must accept
the one-degree admission change, the unchanged source/cancellation/integrity
limitations and retained stopped container/logs.

## Frozen validation and launch

**420 offline tests pass (55 runtime + 365 supervisor).** Tests verify ten-second
94°C admission, reset at 95°C before admission, 97°C latched stop, all other fault
channels/deadlines, exact one-field policy change, unchanged CPU budget/no new
affinity, strict six-attempt preservation, rejection of old decisions and refusal
before live access without a new approval. Native Windows generated-file fixtures
remain offline and use no sensors/model. Static CPU topology was read for
the placement review; no live temperature/GPU query, Docker access or Linux native
process/model workload occurred in preparation. Recorded-stream comparison is
offline explanatory evidence only.

Review SHA256: `8d6239ba96a8ec346554470479c861315520ee63808781f5a3322cf5c75af3ed`.
New policy SHA256: `578ca27e5ba15466544c3f520a1ba9c00efe0d3969b3ef0842fe495d37fde5e2`.
Previous policy SHA256: `58c2cb4fc16faeb62279cfee73c1b66b0b0c06d7a631091efd4730771015a4df`.
Only difference: `cpuStartC: 93 -> 94`.
Packet: `.runtime/model-api-94-admission-review/8d6239ba96a8ec346554470479c861315520ee63808781f5a3322cf5c75af3ed/review.json`.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\0b121b41735347b3a6ac9d4eb33be727`.
Frozen helper count: 76. The packet binds all helpers,
Docker contract/arguments/configuration, admission change, unchanged request/
timing/file handling, native source audit and six-attempt preservation proofs.

Fresh namespace `.runtime/model-api-7`; launcher `.runtime/model-api-launch-7`.
Actual `containers/model-runtime/model-api-7-approval.json` is **absent** and its
template disabled. After exact approval, `python -B local_worker.py run-model-api`
runs through this folder's frozen hidden `run-model-api-reviewed.ps1` administrator
wrapper. Syntax and seventh log destination checked offline. Windows consent is
for the existing passive CPU reader. `cancel-model-api` only addresses this new
session and cannot reset a terminal fault. State lives in `states/state-NNNN.json`;
session result/diagnostics are retained. Earlier launchers/decisions are spent.

The next functional result remains a real answer, then one bounded OpenCode edit
and returned patch alongside Codex with confirmed shutdown. This review authorizes
no execution by itself.
