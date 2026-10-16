# Docker lifecycle milestone — 16 October 2026

The CPU-only Docker lifecycle harness is implemented and tested. It can start one
fixed harmless worker, cancel it, react to simulated safety events, preserve a
fault latch, and clean up only its own container. It exposes a JSON CLI for
developing cloud orchestration. It cannot run Strata, OpenCode, or a coding task.

## Results

| Verification | Outcome |
| --- | --- |
| 16 mocked host tests | Passed: locking, admission, persistent faults/reset, cancellation identity, unsafe configuration rejection, ownership, cleanup, bounded heartbeat, and state/log/journal/stop failure handling |
| 5 existing container-preflight unit tests | Passed |
| 7 real Docker lifecycle scenarios | Passed, listed below |
| Actual default CLI success run | Passed; structured result, graceful worker exit, container removed, saved state `OFF`, no fault |
| Final Docker inventory | No dummy-worker or foreign-fixture test containers remain |
| Changes to existing simulator/model setup | TypeScript implementation and policies unchanged; no Strata/OpenCode configuration, firmware, power, or driver changes |

| Real Docker case | Observed result |
| --- | --- |
| Normal completion | Worker exited 0; receipt saved; container removed; `OFF` |
| Cancellation | Exact-run cancellation; wrong-run rejected; concurrent admission rejected; graceful exit 0; cleanup confirmed |
| Simulated GPU heat | `SYNTHETIC_GPU_HOT` persisted before stopping; new run rejected until an audited dummy reset |
| Missing simulated sensor | `SYNTHETIC_SENSOR_LOST`; cleanup and latch verified |
| Task timeout | Sleeping worker reached the dummy deadline; `TASK_DEADLINE`; cleanup verified |
| Ignored SIGTERM | Docker forced termination, exit 137; `STOP_TIMEOUT`; container removed |
| Host supervisor terminated | Worker exited 78 on heartbeat expiry; recovery acquired the released OS lock, latched `UNCLEAN_EXIT`, removed the stopped container, and refused another run |

Every running test worker had a sleeping descendant. A stopped test fixture with
a different ownership label survived every case and was removed afterward by
its creating test. No unrelated workload was deliberately stopped.

Final real-suite evidence:
`.runtime/docker-dummy-tests/9be06828ebb1483182e088841e72bdae/verification.json`.
Default CLI smoke run: `0f110c148e7a47f28f10ce88f12e5e61`, under
`.runtime/docker-dummy-supervisor/`. Dummy policy fingerprint:
`c914d937e5fd1017388a3e95c383c182f9b6fbfe4ff37bd98f078029566975a1`.

## What runs and what remains

The container uses 0.5 CPU, 256 MiB RAM, no swap, no GPU or network access, and
only read-only mounts of its own dummy script and control directory. It performs
ordinary low CPU process/file operations; no GPU load, temperatures, model data,
or real AI endpoint is involved. The cached Python image is pinned by digest.

The lease uses bounded append-only heartbeat metadata to avoid Windows bind-mount
file replacement conflicts. Docker's logging driver is explicitly selected so
daemon-specific rotation defaults cannot reject startup. Tests also inject
evidence-storage failures to confirm they do not skip stop/removal attempts.

This establishes lifecycle behavior for cooperative dummy workers on this
Docker/WSL installation. It does not establish an operating envelope for the
laptop or explain the earlier shutdown. In particular, cooperative lease expiry
cannot control a hung native engine or CUDA workload. Real hardware telemetry,
an independent watchdog, two-container stop ordering, request/context limits,
and OpenCode filesystem restrictions remain required before live operation.

The next step is a reviewable pinned Linux Strata build/configuration proposal,
plus read-only host telemetry and watchdog validation. Building Strata or loading
a model is separate work that needs its own explicit approval; no live policy is
activated by these dummy results. See `README.md` beside this report for the CLI
and exact implementation limits.
