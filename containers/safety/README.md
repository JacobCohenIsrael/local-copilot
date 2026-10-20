> Current direction (20 October): follow [VIABILITY_POC.md](../../VIABILITY_POC.md). One real
> coding task within 30 minutes; new coding scopes use resource warnings/trends.
> The notes below describe historical or deferred work, not next-step instructions.
> Their strict thresholds, pending approvals and context ladders do not override
> the current contract. Preserve historical evidence and CPU-build policies.

# Hardware availability and independent watchdog milestone

This milestone contains a read-only sensor availability audit, a dedicated
monitor design, and an independent host watchdog **for CPU-only dummy tests**.
It does not start Strata/OpenCode, build CUDA code, load models, query model
weights, install drivers, or change firmware/power settings. The prior simulator
and dummy lifecycle policies are unchanged.

- [Dedicated monitor design](MONITOR_DESIGN.md): Windows APIs, NVIDIA NVML, and
  a verified CPU source; no extra monitoring UI or always-on GPU polling.
- [Pinned build proposal](../strata-proposal/README.md): unbuilt and disabled.
- `telemetry.py`: one Windows availability snapshot using native RAM/AC APIs,
  query-only `nvidia-smi`, and already-registered CPU WMI providers. It writes
  local evidence and always reports live execution disabled. Provider discovery
  is an audit step, not a recommended recurring polling loop.
- `watchdog.py`: separate host process that can stop/remove only an owned,
  specially labelled, isolated dummy with an exact known script hash. It refuses
  GPU-enabled targets, changed scripts, foreign labels, and existing session
  state. There is no automatic reset or live-target option.
- `uncooperative.py`: sleeping stand-in that ignores SIGTERM, reads no host
  heartbeat, and starts a sleeping descendant. Its 25-second fallback exit is
  solely for harmless tests; the external watchdog must stop it much sooner.

## Checks performed on 16 October 2026

The single read-only snapshot found RAM use, AC, NVIDIA GPU temperature/power,
VRAM, and GPU thermal-throttle flags available. It did not provide CPU temperature
or CPU thermal-throttle status. The laptop is an ASUS ROG Strix G733CX with an
Intel Core i9-12950HX, RTX 3080 Ti Laptop GPU (16 GiB), and NVIDIA driver 617.14.
This is a compatibility inventory, not a proof of safe operating limits.

The owner identified Armoury Crate. Its existing services were running and ASUS
WMI metadata exposed a DSTS device-status method. The initial CPU status read
was denied without administrator access; the owner-authorized administrator
probe subsequently succeeded, returning a 90 °C candidate. The owner's later
screenshot showed CPU 81 °C / GPU 57 °C. The observations were not simultaneous,
so a precise cross-check is still pending. No vendor control/set method was
invoked. See `CPU_ACCESS_VALIDATION.md` and the monitor design for evidence,
source attribution, and the unresolved CPU throttle channel.

Ten mocked tests passed: five sensor parsing/availability checks and five
independent watchdog checks. Three real Docker cases passed: explicit stop,
stalled heartbeat, and termination of the exact heartbeat-producing host process.
The separate watchdog persisted its first fault, stopped the uncooperative dummy
and descendant (container exit 137), and verified removal. Measured complete
guardian lifetimes were 3.17, 4.257, and 4.541 seconds respectively, well before
the dummy's 25-second fallback. These timings include arming, trigger detection,
Docker stop and cleanup, not just latency from the trigger itself.

The targets used the existing pinned Python image, 0.5 CPU, 256 MiB RAM, zero
swap, no GPU/network, no restart, non-root execution, and read-only mounts of
only their dummy script/control directory. No model/project/credential mounts.
All watchdog test containers were removed.

The subsequent CPU access step adds three mocked tests for the Windows CPU-limit
diagnostic, bringing this directory's total to 13. They ensure unavailable or
equal OS limits never certify the absence of hardware thermal throttling.

```powershell
# Mocked checks; no Docker/hardware access:
python -B -m unittest discover -s containers/safety -p 'test_*.py' -v
# One bounded real read-only availability snapshot:
python -B containers/safety/telemetry.py
# Explicit real Docker watchdog tests; no GPU or model:
python -B containers/safety/verify_watchdog.py --execute
```

Evidence resides under `.runtime/safety-readiness/` and
`.runtime/independent-watchdog/`. Real test verification is
`verification-e4b3eab7710d45b0907b67aee57a4b23.json`. Per-session states remain
faulted after the expected incidents; they are retained, never automatically
reset or restarted. The verifier uses new dummy-only test domains, not a live
admission domain.

## Limitations before live use

This is a tested watchdog mechanism, not a fully integrated production guard.
It is not connected to real thermal readings or the earlier dummy supervisor.
It polls a host heartbeat independently, with a 1.5-second dummy lease and a
12-second absolute guard deadline. Its separate process survives loss of the
tested producer; the tests do not cover simultaneous guard/host failure, driver
or Docker daemon failure, Windows suspend/resume, or a machine shutdown.

Initial isolation/identity failures prevent arming. Before stopping, it rechecks
the exact name, labels, image, arguments, mounts, and resource isolation; a
mismatch refuses the target. During admitted cleanup, log-collection failures
do not prevent removal. If Docker becomes unavailable, a stop cannot be
guaranteed; preserve the durable fault/active evidence and block further work.
Protected machine-wide state and independent live sensor freshness checks are
still required. The monitor design and build proposal remain unapproved.
CPU temperature access is available to the administrator probe; CPU throttle
status and complete sensor validation still block model launch and compilation.
`cpu_limits.py` queries Windows-reported frequency limits only and explicitly
leaves the hardware thermal-throttle field unknown.
