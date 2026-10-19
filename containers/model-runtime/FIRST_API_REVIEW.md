# First real Strata API answer in Docker: exact operation

18 October 2026. **Prepared, offline-tested and awaiting approval.** No model,
GPU workload, Linux Python process or new container ran during preparation.
The proposed operation now performs the useful next step: start the built Linux
Strata in Docker, obtain one real OpenAI-compatible API answer, and stop it.

## What will run

One container uses the existing pinned CUDA image and the verified Linux Strata
0.1.44.1 artifacts. A separate read-only Linux configuration points at the existing
IQ1_M model/pack/tokenizer and expert profile. The Windows configuration and launch
script stay unchanged. No setup.py, upstream Docker entrypoint, package installer,
image download/import/build, model download, OpenCode worker or MCP integration runs.

The server listens only on **127.0.0.1:8080 inside a container with network none**.
No port is published to Windows or the LAN. A fixed internal client polls health,
then submits exactly one inference request, with no HTTP inference retry:

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

Context is **512 tokens**, completion at most **8 tokens**, response at most
16 KiB. A passing result requires nonempty assistant text and consistent usage
accounting within these limits; scripted replies cannot count as a real result.
The client saves the exact response for Codex. The next milestone after this test
is the existing bounded OpenCode editing workflow using a real Strata answer.

## Minimal model configuration

- Memory-mapped experts instead of the Windows resident-expert arena.
- Fixed **64 expert-cache slots**, one CPU pool worker, prefill chunks **32**,
  int8 KV, context **512**. Requested VRAM reserve is **4096 MiB**; this is an
  engine hint, not a hard GPU memory quota, especially with an explicit slot count.
- Speculative decoding and suffix drafting off; no MTP or vision mounts.
  Prompt/conversation caching off for this disposable one-request test.
- Explicit PCIe share **0.20** skips the automatic PCIe bandwidth probe and
  adaptive share selection. No calibration or benchmark flags. PLE uses mmap;
  the startup disk probe is skipped. Ordinary model initialization still uses GPU.
- Automatic startup retries, engine reload/restart and response retries disabled.
  Failure ends this attempt; it cannot silently load a second engine.

Full Linux configuration and exact Docker arguments are frozen beside the review.
Existing large model contents are not rehashed: small files are hash-bound; large
files use file identity, size, modification time and a 16-byte prefix hash. This
does not exclude external mutation that preserves that metadata. Mounts are read-only.

## Proposed controls for this one model/API scope

These numbers are review proposals for model execution. The earlier CPU-build
approvals do not approve GPU/model work or extend their source exception.

| Control | Exact proposal |
| --- | --- |
| WSL | Keep **1 CPU, 6 GiB RAM, no swap**; no restart or setting edit |
| Container | **1 CPU, 4 GiB, no additional swap, 128 processes** |
| CPU | Start <= **92 C for 10 seconds**, stop >= **97 C**, query <= **1.5 s** |
| GPU admission | <= **60 C**, <= **40 W**, device VRAM used <= **4096 MiB** |
| GPU stop | >= **75 C**, >= **100 W**, or device VRAM used >= **14336 MiB** |
| Host RAM | At least **8192 MiB free** at admission; stop at **28672 MiB used** |
| Power/throttle | AC required; GPU thermal-throttle channel must be known false |
| Sampling | CPU reader 1 s slots; GPU about 1 s, query <= **1 s** |
| Freshness/leases | **2.5 s**; missing, stale, invalid or failed feeds fault |
| Startup/request | API ready within **180 s**, one request within **90 s** |
| Lifetime | Model/container <= **300 s**; outer session <= **410 s** including admission |
| Stop | Request graceful exit, then forced owned-group/container stopping if needed; confirm within **5 s** of a host stop trigger |

The power/VRAM values are **monitored stop thresholds**. No GPU power cap, fan,
firmware, clock, Windows power mode or hardware thermal limit is changed. A normal
inference burst can cross 100 W and end this test. These controls cannot guarantee
prevention of another instant shutdown or confirm stopping through a host/driver
failure. Shared-Docker cancellation limitations remain; no global Docker/WSL stop
or deferred-device cleanup is authorized.

CPU source acceptance for this scope: ASUS endpoint and changing-value evidence are reused, but firmware refresh/calibration and CPU throttle are unverified. Accept these limitations for one bounded model/API test only; this is a new scope, not inherited CPU-build approval.
Raw CPU validation remains false and CPU throttle remains unknown. NVIDIA Windows
queries supplied GPU temperature, power, VRAM and throttle channels in a read-only
snapshot. This is availability evidence, not future admission; execution re-samples
everything and requires a new cool baseline. GPU UUID is fixed to the existing
RTX 3080 Ti Laptop GPU, and exactly one attached GPU is required.

Linux/GPU compatibility and memory fit remain unproven until this approved test.
The low-RAM configuration may still OOM or be too slow inside 4 GiB/one CPU. Any
such failure stops and retains evidence; no RAM increase, retry or model change.
NVIDIA documents WSL pinned-memory and NVML limitations in its
[WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html#known-limitations-for-linux-cuda-applications).
The host driver observed was 617.14 (reports CUDA 13.4); the pinned image uses CUDA
13.0. Actual Linux GPU access is qualified by the first model startup, not claimed
from that Windows query alone.

## Containment, supervision and retained output

Non-root UID 65532, read-only root/source/engine/Python/models/config, capabilities
dropped, no-new-privileges, private process/IPC space, no Docker socket, credential
or project-workspace mounts. Work and temp tmpfs are 64 MiB each, plus 16 MiB shared
memory, all charged to the same 4-GiB cap. The guest checks kernel CPU/RAM/swap/PID
limits, UID, capabilities and loopback-only networking before starting the API.

The host controller and independent guard renew separate leases. The guest also
checks both leases and ends its own API/engine group if they stop progressing.
The guard checks every CPU frame (hot readings cannot be skipped), GPU/host metrics,
container identity/isolation, OOM status, deadlines and cancellation. Isolation drift
faults, but stopping retains authority over the original immutable owned ID.
There is no automatic fault reset or second attempt.

Save the response before acknowledging shutdown. First request the upstream API's
SIGTERM -> QUIT/close path, then reap any remaining owned process group within the
bound. Host emergency stopping keeps the existing TERM/KILL sequence. The container
is **retained stopped on success or failure**, preserving bounded Docker logs (two
1-MiB files), a 64-KiB combined log tail and exit/OOM diagnostics. Native engine logs
are mirrored to Docker logs and capped at 1 MiB. Retention is intentional, not an
unconfirmed stop. No older container, disk, approval or evidence is removed/reset.

## Frozen preparation and approval

The API bundle contains pinned portable **CPython 3.13.15**, Jinja2 **3.1.6**,
MarkupSafe **3.0.3** and regex **2026.9.10**. Official release/PyPI hashes verified;
35,773,134 compressed bytes downloaded, 1706 staged files totaling 194,358,061 bytes.
Unused terminal-description data with Windows case aliases was omitted. No global
Python installation changed, and no staged Linux code executed. Portable Python
provenance: [Astral's distributions](https://github.com/astral-sh/python-build-standalone).

**386 offline tests pass**: 21 new runtime checks and all 365 existing supervisor
tests. They cover fixtures for real-limit qualification, all stop channels,
inference/response budgets, startup/reload prevention, approval refusal, immutable
owned stopping after isolation drift, guest leases, and fake connected success,
failure and lost-guard cases. Native model/API compatibility is not simulated proof.

Review SHA256: `62e923cdc2e135540231d4594bf82ea6011828f3b64bdb966e6ab63ba9fb9ae6`.
Policy SHA256: `4cf33c6e0f3cfeda2bbf8cd10af17a7a337c276600129667b21b11ec1bba3a98`.
New namespace: `.runtime/first-model-api-1`.
Package: `C:\Users\yaki_\Desktop\Projects\local-copilot\.runtime\model-api-packages\af433b1c41f246caa37f409f6f8e8101`.
Frozen review: `.runtime/model-api-review/62e923cdc2e135540231d4594bf82ea6011828f3b64bdb966e6ab63ba9fb9ae6/`.

After exact owner approval, run **`python -B local_worker.py run-model-api`** using
the prepared hidden administrator wrapper `run-model-api-reviewed.ps1` for the
existing ASUS CPU reader. The operation includes the existing tiny no-GPU capacity/
swap probe and fresh image/driver/configuration checks. `cancel-model-api` requests
stopping the fixed new session without start approval; it cannot reset a fault.

The actual `first-model-api-approval.json` is absent. Its template is disabled and
binds this exact review, policy, source acceptance, limitations and retained stopped
container. Prior approvals are spent. The CLI refuses without this new approval
before Docker/reader access. No model/runtime configuration has been activated.
