# Second Strata API attempt: exact operation

18 October 2026. **Prepared offline; not approved or started.**

## Difference from the consumed first attempt

**No limit, model, request or configuration changes.** The first attempt ended
with `BASELINE_NOT_MET` before its container started. Its original approval,
frozen helpers, unstarted container, empty logs, raw readings and preservation
inventories remain untouched. This proposal creates a separate attempt, not a
reset of that fault. See [the first result](FIRST_API_RESULT.md).

New evidence folder: `.runtime/model-api-2`. New launcher: `.runtime/model-api-launch-2`.
New actual decision: `containers/model-runtime/model-api-2-approval.json` (**absent**).
The first approval cannot authorize this different scope/hash. Before any model
container creation, execution verifies the full failed-attempt inventories,
including their preserved supplement, frozen helpers, inputs and original decision.
Preparation likewise verified previous builds and unchanged Windows settings.

## One operation to approve

Use the existing imported CUDA image and exported Linux Strata 0.1.44.1 artifacts.
Create one new GPU-enabled container; wait at most 90 seconds for the ten-second
admission window; start it only after admission; qualify actual kernel limits;
start the pinned Python/upstream API and engine without reload/startup retries;
wait for API health; submit exactly one inference request; save its response;
stop and retain the container and bounded logs on success or failure. No automatic
retry, fault reset, compilation, image/model download/import, worker or MCP.
The existing tiny no-GPU capacity/swap probe is included, as in the first scope.

The API listens only on container loopback, 127.0.0.1:8080, with network none.
No Windows/LAN port is published. Exact request:

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

Context 512 tokens; at most eight completion tokens; response at most 16 KiB.
Require nonempty real assistant text and consistent usage within those budgets.
One request has a 90-second hard deadline; API readiness has 180 seconds.
The model/container may run at most 300 seconds, outer session 410 seconds.

## Unchanged limits

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no restart or settings edit |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes |
| CPU admission | At most 92°C for ten continuous seconds |
| CPU stop/query | Stop at 97°C; query at most 1.5 seconds |
| GPU admission | At most 60°C, 40 W and 4096 MiB device VRAM used |
| GPU stop | At least 75°C, 100 W or 14336 MiB device VRAM used |
| Host RAM | At least 8192 MiB free to start; stop at 28672 MiB used |
| Power/throttle | AC required; GPU thermal-throttle flag known false |
| Freshness/leases | 2.5 seconds; CPU 1-second slots, GPU about 1-second samples |
| Stop | Graceful owned shutdown, then forced stopping if needed; confirm within 5 seconds |

Admission requires all start conditions together. The historical readings do not
certify present eligibility. Execution obtains fresh readings; no live sensor,
Docker access, GPU workload or staged Linux code runs during this preparation.
The next attempt may fail the same admission window. No other application is
closed, no resource budget enlarged and no threshold adjusted automatically.

## Same model and containment

The separate Linux configuration still uses memory-mapped experts, 64 expert-cache
slots, prefill 32, one CPU pool worker, int8 KV and context 512. VRAM reserve 4096 MiB
is an engine hint, not a hard quota. Speculation, suffix drafting, MTP, vision,
prompt/conversation caches and response retries stay disabled. PCIe fraction 0.20
and PLE mmap skip the automatic bandwidth/disk probes. Ordinary initialization
still uses the GPU. No benchmark/calibration, installer or upstream entrypoint.

Non-root 65532, read-only root and engine/source/Python/config/model binds, dropped
capabilities, no-new-privileges, private IPC, no network/ports/socket/credentials/
project workspace. Work/tmp are 64 MiB each; shared memory 16 MiB, charged to the
same 4-GiB limit. Fixed GPU UUID `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`; exactly one GPU required.
The approved operation uses --gpus all only after that one-device identity check.
The same fixed CPU reader and host/guest/controller leases supervise execution.

Power and VRAM values are software stop thresholds, not hardware caps. Unknown
Linux/GPU compatibility and 4-GiB memory fit remain unproven. Host/driver/daemon/
suspend failure can prevent stopping; shared-Docker cancellation limitations
remain. No global Docker/WSL stop or historical container/disk cleanup is authorized.
CPU scope exception: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation remains false; CPU throttle is unknown. Small model files are
hashed; large files use identity/size/mtime/prefix checks, not a full-content hash.
A new approval must accept these unchanged source/cancellation/fit limitations
and retained stopped container. No old scope exception is silently extended.

## Evidence, exact launch and approval

392 offline tests pass: 27 runtime tests and all 365 existing supervisor tests.
They use saved evidence/fake hardware/processes, not real model execution.
New cases verify failed-attempt preservation, rejection of altered history,
old-decision refusal, unchanged policy/resource/request checks and pre-live refusal.
The runtime bundle/source/artifact/model/settings identities match the first review.

Review SHA256: `fc1d1d9c970ba58922483dd57aac625cef87fd4879d83fe0cf413a166ae04599`.
Policy SHA256: `4cf33c6e0f3cfeda2bbf8cd10af17a7a337c276600129667b21b11ec1bba3a98`.
Frozen packet: `.runtime/model-api-recovery-review/fc1d1d9c970ba58922483dd57aac625cef87fd4879d83fe0cf413a166ae04599/review.json`.
Separate read-only package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\a11f470f39084e228eb90aa46cf545d9`.
Exact Docker create arguments, complete mount/environment/isolation contract and
74 helper hashes are in that packet and frozen beside it. Preparation audit binds
this document, wrapper, test logs and unchanged configuration identities.

After owner approval, execute **`python -B local_worker.py run-model-api`** through
this review folder's hidden `run-model-api-reviewed.ps1` administrator wrapper.
Windows administrator consent enables the existing read-only CPU source. The
wrapper checks the new review decision and refuses an existing second namespace
or launcher. It changes no firmware, fan, clock, power or WSL setting.
`python -B local_worker.py cancel-model-api` targets only the new attempt;
it cannot clear a fault. The actual new decision and live namespace remain absent.

The [original first review](FIRST_API_REVIEW.md) is retained historical evidence;
its old namespace/approval/launch instructions must not be used for this attempt.

## If admission fails again

No limits change in this proposal. After another `BASELINE_NOT_MET`, inspect the
saved CPU/free-RAM failures and prepare one small admission adjustment at a time,
reporting the exact old/new value and reason before the next workload approval.
For example, a proposal could allow 1°C more at CPU admission, or 256 MiB less
required free RAM (allowing that much more host memory use), depending on the
recorded blocker. Those examples are not active policies or execution authority.
Keep the 97°C CPU stop, GPU stops and VM/container caps unchanged unless separately
reviewed. No automatic ladder, repeated model launch or weakening of freshness,
leases, fault latching or stop confirmation. First useful outcome remains the real
API answer, then one bounded OpenCode edit/patch submitted by Codex.
