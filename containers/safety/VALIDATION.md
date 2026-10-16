# Strata safety readiness — 16 October 2026

The next milestone is complete as a preparatory step: the Linux build proposal
is pinned and disabled, available sensors have been audited without a workload,
and a separate host watchdog has stopped non-cooperating dummy containers.
**CPU sensor access and throttle status remain unresolved; live admission stays
disabled.** No Strata build, model load, GPU benchmark, installation, or
firmware/power/performance-mode change occurred.

Update: the subsequent owner-authorized administrator probe resolved CPU
temperature access (90 °C candidate; later owner screenshot CPU 81 °C / GPU
57 °C). See `CPU_ACCESS_VALIDATION.md`. CPU hardware throttle status and sensor
meaning/freshness validation remain unresolved. The table below records the
earlier availability audit; its denied-access finding is now superseded.

## Findings that determine the next step

| Area | Result |
| --- | --- |
| Linux build | Strata v0.1.44.1 / source commit `296b59d2f73c8f04a805df29c2fa97655adace78`; CUDA 13.0 Ubuntu 24.04 Linux amd64 base pinned by digest; no layers pulled or compilation run |
| Proposed compilation | Architecture 86 only, no vision, one compiler job, no retry; external builder quotas and owner approval still required |
| Existing NVIDIA driver | 617.14; driver reports CUDA 13.4 support. This exceeds CUDA 13's generation floor but does not prove the Linux image runs |
| Readable channels | GPU temperature/power/VRAM/thermal-throttle flags, RAM use, AC status |
| Missing safety channels | CPU temperature and CPU thermal-throttle status |
| Existing ASUS source | Armoury Crate services running; `AsusAtkWmi_WMNB` exists. Its fixed DSTS CPU-temperature read was denied in the current process context; no control method was called |
| Independent watchdog | Three real Docker cases passed with an uncooperative sleeping worker and descendant; no worker-side lease; separate host process performed stop/removal |
| Mocked checks | Ten passed, covering sensor parsing/missing data and watchdog identity/isolation/latching |

The one-shot snapshot reported GPU 56 °C, 16.67 W, 1,501 MiB of 16,384 MiB VRAM
in use, AC connected, and about 15.2 GiB host RAM in use. These are observations
at one moment, not a safe-load envelope, idle baseline, or evidence about the
earlier shutdown. CPU readings were not invented from GPU data or ACPI zones.

The tested watchdog can act when the heartbeat producer stalls or is killed,
even though the target ignores SIGTERM and has no cooperative host lease. The
container exited 137 and was removed in each case. Complete guardian lifetimes
were about 3.2–4.5 seconds, including arming/trigger detection/Docker cleanup;
the dummy had a 25-second fallback. These results do not establish a real-time
stop bound under driver/daemon failure or a hardware power cutoff.

## Dedicated monitor direction

The owner prefers a dedicated monitor with low overhead. Use a small headless
Windows collector with native RAM/AC reads, direct NVIDIA NVML reads, and a
verified CPU source through an existing suitable driver. Enumerate once, query
only necessary channels, and measure actual overhead. No repeated process scans,
dashboard, overlay, full monitoring-suite installation, or always-on GPU polling
is part of the proposed design.

Applications running on Windows do not all use one common CPU temperature API.
A custom program still needs permission to use the relevant hardware interface.
The existing ASUS read-status source is the preferred lead; the access denial
does not prove the hardware lacks a sensor or that elevation would resolve it.
A fixed read-only probe is ready for review, but it does not elevate itself or
install anything. If a candidate reading becomes available, validate its sensor
meaning, refresh behavior, and agreement with Armoury Crate before using it for
safety. CPU throttling needs its own verified channel.

Keep the watchdog independent of both the collector and task supervisor; losing
fresh sensor evidence must stop admission or end the owned session. Neither the
monitor nor cloud orchestrator may approve or adjust thermal/power policies.
No dedicated production collector, new driver, or live guard is activated here.

Next: resolve CPU access and the throttle source, then implement the narrow
read-only collector and its freshness/liveness contract. Validate the integrated
watchdog before reviewing any compilation or model workload. All original
Strata/OpenCode settings and the prior simulator policy remain unchanged.

Details are in `MONITOR_DESIGN.md`, `README.md`, and the sibling
`../strata-proposal/` directory. The evidence copied alongside this report is
query/test output, not an authorization to build or start a model.
