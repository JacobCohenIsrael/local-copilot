# Third Strata API attempt: exact operation

18 October 2026. **Prepared offline and awaiting execution approval.** No native
reader, container, GPU query/workload or staged Linux process ran in preparation.

## Exactly one policy change

| Setting | Previous two attempts | This proposal |
| --- | --- | --- |
| CPU admission | At most 92°C for ten seconds | **At most 93°C for ten seconds** |
| CPU stop | 97°C | **97°C, unchanged** |
| All other limits and inputs | Second reviewed operation | Unchanged |

This is an API-only proposal. The CPU-build policy and original Windows/Strata/
WSL/Desktop/power settings are unchanged. No additional change or retry ladder
is authorized. A concrete packet comparison rejects any other limit, model,
request, environment or resource change. The exact adjustment is also required
in the new owner decision; neither previous approval can authorize this scope.

Reason: the [second attempt](SECOND_API_RESULT.md) failed admission because CPU
alone blocked the ten-second window. Free RAM and GPU start conditions passed.
Saved-timestamp replay found approximately 21.417 seconds eligible at 93°C versus
9.918 seconds at 92°C. Receipt times were not logged; replay cannot prove native
or future eligibility. Execution must obtain a fresh ten-second admission window.

Both failed attempts remain FAULT-latched, with their original unstarted
containers, empty logs, raw readings, approvals and frozen helpers retained.
Preparation and future execution verify both preservation inventories, the first
supplement, all frozen helpers/inputs/decisions and their evidence chain. The
older successful/failed builds and original configuration identities are verified
as well. No old namespace, approval, candidate, evidence, disk or container is reset.

## One GPU-enabled API operation to approve

Use the existing imported pinned CUDA image and exported Linux Strata 0.1.44.1
artifacts. Run the existing tiny no-GPU capacity/swap probe; create one new
GPU-enabled model container; admit fresh telemetry; check actual guest kernel
limits; start the pinned Python/upstream API and engine; wait for health; submit
exactly one inference request; save its response; stop and retain the container
and bounded logs on success or failure. No inference/startup/reload retry.
No compilation, setup/installer, image/model download/import, benchmark,
calibration, OpenCode worker, MCP or additional GPU test.

The API listens only on container loopback 127.0.0.1:8080, with network none.
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

## Complete limits

| Control | Exact value |
| --- | --- |
| WSL | 1 CPU, 6 GiB RAM, no swap; no restart/edit |
| Container | 1 CPU, 4 GiB, no additional swap, 128 processes |
| CPU admission | **At most 93°C for ten continuous seconds** |
| CPU stop/query | **97°C stop**, query at most 1.5 seconds |
| GPU admission | At most 60°C, 40 W, 4096 MiB device VRAM used |
| GPU stop | At least 75°C, 100 W or 14336 MiB device VRAM used |
| Host RAM | At least 8192 MiB free to start; stop at 28672 MiB used |
| Power/throttle | AC required; GPU thermal-throttle flag known false |
| Sampling | CPU 1-second slots; GPU about 1 second, query at most 1 second |
| Freshness/leases | 2.5 seconds; invalid/stale/missing feeds or leases fault |
| Admission deadline | 90 seconds; initial no-model reader wait at most 5 seconds |
| API startup/request | 180 seconds startup; one request hard deadline 90 seconds |
| Lifetime | Model/container at most 300 seconds; outer session at most 410 seconds |
| Stop | Graceful owned shutdown, then forced stopping if needed; confirm within 5 seconds |

The same independent host guard, controller lease and guest dual-lease checks
apply. Every CPU frame is checked, no hot frame skipping, no fault reset or retry.
Software power/VRAM stop thresholds are not hardware caps. Host/driver/daemon/
suspend failure can prevent stopping; shared-Docker cancellation limitations
remain. No global Docker/WSL stop or historical device/container cleanup.

## Same model and isolation

Memory-mapped experts, 64 expert-cache slots, prefill 32, one CPU pool worker,
int8 KV, context 512. VRAM reserve 4096 MiB remains an engine hint, not a hard quota.
Speculation/suffix drafting, MTP/vision, prompt/conversation caches and response
retries stay off. PCIe fraction 0.20 and PLE mmap skip the bandwidth/disk probes.
Ordinary model initialization still uses the GPU. Model fit within 4 GiB and
native Linux/GPU compatibility remain unproven because neither prior container ran.

Pinned portable CPython 3.13.15 plus Jinja2 3.1.6, MarkupSafe 3.0.3 and regex
2026.9.10 are already staged and hash-verified. No downloads or global installs.
Non-root UID 65532, read-only root and engine/source/Python/config/model binds,
capabilities dropped, no-new-privileges, private IPC, no socket/credentials/project
workspace/network/ports. Work/tmp 64 MiB each, shared memory 16 MiB, charged to
the same 4-GiB cap. Exactly one GPU, UUID `GPU-3a13992a-a407-6100-dec6-7abab3f0ad2d`;
--gpus all is used only after that single-device identity check.

CPU source exception for this scope: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation remains false; CPU throttle is unknown. Small model files are
hashed; large model files use identity/size/mtime/prefix checks, not full-content
hashing. Source/cancellation/fit/large-file limitations must be accepted anew for
this one operation, along with retained stopped container and logs.

## Frozen packet and exact launch

395 offline tests pass: 30 runtime and 365 existing supervisor tests. They verify
93°C admission, the unchanged 97°C stop and fault latch, all other stop/lease/data
channels, two-attempt preservation, old-decision rejection and the new decision's
exact adjustment. Saved data/fake processes are not proof of real model execution.

Review SHA256: `fa9eeb3023db47bc8fd00a338979dabb13a0a8f16026e31c127d22d04a6c96b8`.
Policy SHA256: `58c2cb4fc16faeb62279cfee73c1b66b0b0c06d7a631091efd4730771015a4df`.
Frozen review: `.runtime/model-api-admission-review/fa9eeb3023db47bc8fd00a338979dabb13a0a8f16026e31c127d22d04a6c96b8/review.json`.
Read-only input package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\be47cdc10e6b4b39a5da3ea074cab445`.
The packet and frozen helpers contain the complete Docker command, mounts,
environment, isolation contract, policy change and preservation proofs.

New namespace: `.runtime/model-api-3`. Launcher: `.runtime/model-api-launch-3`.
Actual new decision: `containers/model-runtime/model-api-3-approval.json` (**absent**).
The disabled template binds this exact scope/review/policy/source, the explicit
92°C -> 93°C admission adjustment, limitations and retained stopped container.
Neither earlier decision is reused. CLI refusal was verified before live access.

After owner approval, run **`python -B local_worker.py run-model-api`** through
this review folder's hidden `run-model-api-reviewed.ps1` administrator wrapper.
It checks the review decision, Python identity and unused third namespace/launcher.
Windows administrator consent is for the existing read-only CPU source; no fan,
firmware, power, clock or WSL setting changes. Cancellation via
`python -B local_worker.py cancel-model-api` targets only the new session; no reset.
The [first](FIRST_API_REVIEW.md) and [second](SECOND_API_REVIEW.md) reviews remain
historical; do not use their launch/approval instructions for this third attempt.

The next functional result is one real API answer, followed by the existing
bounded OpenCode edit submitted by Codex, returned patch and confirmed shutdown.
