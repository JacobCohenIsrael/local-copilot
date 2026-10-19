# Fourth Strata API attempt: native-IQ startup correction

18 October 2026. **Prepared offline and awaiting execution approval.**

## Exact change and source diagnosis

| Setting | Third attempt | Fourth proposal |
| --- | --- | --- |
| Native verification window | `--spec 0`, rejected | **`--spec 2`**, minimum supported width |
| CPU admission / stop | 93°C / 97°C | **93°C / 97°C, unchanged** |
| All other limits, model args, API request and inputs | Third reviewed operation | Unchanged |

The [third attempt](THIRD_API_RESULT.md) passed admission and guest qualification,
then the native engine exited with code 2 before readiness because this IQ pack
requires spec >=2. The pinned `src/program/generate.cpp` has this requirement both
at the native-pack validation (3024) and the server gate (7232).

The corrected configuration changes only the value after `--spec`, from 0 to 2.
No MTP model/drafter is enabled or mounted; `--suffix-draft 0` remains explicit;
lookup-chain remains at its pinned default zero. The same source's serve loop
(12565) chooses one-token rounds without MTP, and checks suffix drafting before
proposing lookup tokens. Width 2 is the required verification capacity, not an
increase to the eight-token completion budget. Its allocation behavior has not
been verified natively; memory fit and successful GPU initialization remain unproven.

Source SHA256: `generate.cpp` `fd85d08db152867dfe9a36afaee584b643bd26ddd70d791f9ef95ca47ab940c7`;
`serve/server.py` `6c45c639e28a873b854606719d9ce2bb2e0df666f105164e78e2735878b9aa8f`.
Offline checking hashes those exact files, rejects the retained bad arguments,
validates the corrected native/serve requirements and executes only five selected
pure upstream argument-builder functions in host Python (no module imports or
initialization). They forward the exact corrected args without adding MTP,
parallelism, elastic VRAM or other unreviewed flags. No native engine, staged Linux
interpreter, GPU query/workload, live CPU reader or Docker call ran in preparation.
This source/argument check is not a native startup or inference test.

## One operation to approve

Reuse the imported pinned CUDA image, exported Linux Strata 0.1.44.1 artifacts,
staged CPython 3.13.15/API dependencies and existing IQ1_M pack/GGUF/tokenizer/profile.
Run the existing tiny no-GPU capacity/swap probe; create one new GPU-enabled model
container; wait for fresh admission; qualify actual guest limits; start the pinned
API/native engine once; wait for health; submit exactly one inference request;
save the response; stop and retain the container and bounded logs on all outcomes.
No automatic startup/reload/inference retry or fault reset. No compilation,
setup/installer, image/model download/import, calibration/benchmark, worker or MCP.

API: container loopback 127.0.0.1:8080 with network none; no Windows/LAN port.
Exact inference request:

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

Context 512 tokens, at most eight completion tokens, response at most 16 KiB.
Require nonempty real assistant text and consistent token usage within those bounds.

## Unchanged limits and containment

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no restart/edit |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes |
| CPU admission | At most 93°C for ten continuous seconds |
| CPU stop/query | Stop at 97°C; query at most 1.5 seconds |
| GPU admission | At most 60°C, 40 W, 4096 MiB device VRAM used |
| GPU stop | At least 75°C, 100 W or 14336 MiB device VRAM used |
| Host RAM | At least 8192 MiB free to start; stop at 28672 MiB used |
| Power/throttle | AC required; GPU thermal-throttle flag known false |
| Sampling | CPU 1-second slots; GPU about 1 second, query at most 1 second |
| Freshness/leases | 2.5 seconds; stale/failed/missing/invalid channels fault |
| Admission wait | At most 90 seconds; initial no-model reader wait at most 5 seconds |
| API startup/request | 180 seconds startup; one request hard deadline 90 seconds |
| Lifetime | Model/container at most 300 seconds; outer session at most 410 seconds |
| Stop | Graceful owned shutdown, forced stopping if needed; confirm within 5 seconds |

The model still uses memory-mapped experts, 64 expert-cache slots, prefill 32,
one CPU pool worker, int8 KV and context 512. VRAM reserve 4096 MiB remains an
engine hint, not a hard quota. No MTP/vision, prompt/conversation caches or retries.
PCIe fraction 0.20 and PLE mmap skip bandwidth/disk probes; ordinary initialization
uses GPU. No new tuning flags or larger resources are introduced.

Non-root UID 65532, read-only root/source/engine/Python/config/model binds, all
capabilities dropped, no-new-privileges, private IPC, no Docker socket, credentials,
project workspace, network or ports. Work/tmp each 64 MiB and shared memory 16 MiB,
charged to the same 4-GiB memory cap. Exactly one fixed GPU UUID
`GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; --gpus all is used only after that single-device check.
Host controller, independent guard and guest dual leases remain active. Every CPU
frame is checked; hot frames cannot be skipped. No automatic retry/reset or removal.

## Preserved evidence and accepted limitations

All three failed attempts remain consumed and FAULT-latched. Their containers,
original approvals, frozen helpers/inputs, raw readings, logs and inventories
remain untouched. Preparation and future execution verify all three inventories,
the first supplement and their chained review identities. The third's nonempty
engine log and unknown `modelStarted`/GPU-start fields are preserved as recorded.
Prior build/source/artifact/runtime/model identities and Windows/WSL/Desktop
configurations are likewise checked. No old candidate, disk or container is reset.

Software GPU power/VRAM stops are not hardware caps. Linux GPU model compatibility,
4-GiB memory fit and a real API answer remain unproven. Host/driver/daemon/suspend
failure can prevent stopping; shared-Docker cancellation limitations remain.
No global Docker/WSL stop or deferred device cleanup is authorized.
CPU exception: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation stays false; CPU throttle is unknown. Small model files are
hashed, large files use identity/size/mtime/prefix checks rather than full hashes.
These unchanged source/cancellation/fit/integrity limitations and retained stopped
container/logs must be accepted for this one new operation.

## Frozen packet, validation and exact launch

401 offline tests pass: 36 runtime and 365 existing supervisor tests. New checks
replay the recorded bad argument list, verify the corrected upstream forwarding,
reject missing/duplicate/invalid native arguments, unreviewed MTP/other expansion
and changed pinned source, preserve all three attempts, reject old decisions,
and retain the 93°C admission/97°C stop and other fault channels. Fake-process
success and static/source qualification cannot establish native model readiness.

Review SHA256: `29c70fec244b6f0f747dc60e39aab091387af43b55d5bc7708e2320ebc533bb2`.
Policy SHA256: `58c2cb4fc16faeb62279cfee73c1b66b0b0c06d7a631091efd4730771015a4df` (unchanged from the third attempt).
Frozen packet: `.runtime/model-api-native-review/29c70fec244b6f0f747dc60e39aab091387af43b55d5bc7708e2320ebc533bb2/review.json`.
Read-only input package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\1b1a205f278245c88448a39fe45638ec`.
The packet and 75 frozen helpers bind the complete Docker command, mounts,
environment/isolation contract, unchanged policy, single argument correction,
source audit and all three preservation proofs. The preparation audit binds this
document, wrapper, test logs and unchanged settings identities.

New namespace: `.runtime/model-api-4`. Launcher: `.runtime/model-api-launch-4`.
Actual decision: `containers/model-runtime/model-api-4-approval.json` (**absent**).
Its disabled template requires this exact scope/review/policy, explicit
`--spec 0 -> 2` acceptance with MTP off, limitations and retained stopped container.
All previous decisions are spent. CLI refusal was verified before live access.

After owner approval, execute **`python -B local_worker.py run-model-api`** through
this review folder's hidden `run-model-api-reviewed.ps1` administrator wrapper.
It checks the new review decision, Python identity and unused fourth namespace/
launcher. Windows administrator consent is for the existing read-only CPU reader;
no fan, firmware, power, clock, WSL or existing Windows Strata configuration changes.
`python -B local_worker.py cancel-model-api` requests stopping only the new session,
without start authority; no fault reset. Historical first/second/third reviews and
launchers must not be used for this operation.

The next functional outcome remains one real API answer, then the existing
bounded OpenCode edit submitted by Codex, returned patch and confirmed shutdown.
