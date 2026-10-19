# First Docker Strata API attempt — 18 October 2026

## Outcome

The owner-approved attempt ended with latched **FAULT / BASELINE_NOT_MET** after
the 90-second admission window. CPU temperature and free host RAM did not stay
within the reviewed start limits together for the required ten seconds.

The model container was created but **never started**: Docker status `created`,
PID zero, no start/finish timestamp and no OOM. No Strata engine, API server,
GPU workload, inference request or OpenCode worker ran. Its default exit-code
field of zero is not a successful model test. Linux/GPU compatibility and memory
fit remain unproven. No retry, fault reset or policy/resource change occurred.

## Recorded observations

| Channel | Observed | Admission requirement |
| --- | --- | --- |
| CPU temperature, 89 samples | 83–95°C; 38 above 92°C | At most 92°C |
| Free host RAM, 69 samples | 7904.86–8429.43 MiB; 50 below 8192 MiB | At least 8192 MiB |
| GPU temperature | 58–60°C | At most 60°C |
| GPU power | Maximum 39.78 W | At most 40 W |
| Device VRAM used | Maximum 2428 MiB | At most 4096 MiB |

All start requirements must hold together for ten seconds. An offline replay
using recorded sensor timestamps found an approximate longest combined window
of 4.433 seconds; host-loop receipt times were not recorded, so this is explanatory
analysis, not a replacement for the native guard decision. Maximum CPU query was
0.043861 seconds; maximum GPU query was 0.247381 seconds. Raw CPU validation remains
false and CPU throttle unknown, as explicitly accepted for this scope.

## Shutdown and preservation

- Non-running status confirmed; guard confirmation took 0.183 seconds. The owned
  container is retained in its original, unstarted state. No removal occurred.
- Wrapper, controller, independent guard and CPU reader all exited, verified by PID.
- Docker logs and the automatic 64-KiB-tail capture are retained and empty because
  the container never started. Container inspections, guard state, raw CPU/GPU
  samples, launcher output and diagnostics are preserved with SHA256 inventories.
- The tiny no-GPU capacity/swap probe completed and confirmed no guest swap.
  Existing WSL 1 CPU/6 GiB/no swap and container 1 CPU/4 GiB limits were unchanged.
- Post-run verification confirmed prior build evidence, model identities,
  original Windows configurations, WSL/Desktop settings and pinned runtime/source
  inputs unchanged. The older retained failed-build container and private capsule
  remain non-running. No existing disk or historical attempt was modified.

## Evidence identities

- Review: `62e923cdc2e135540231d4594bf82ea6011828f3b64bdb966e6ab63ba9fb9ae6`.
- Session: `b778a58043f84cf99f48c5c6d56c3fa4`.
- Container: `f8b485a463ccc4bd65e5093140c2b26f2e64a68f5309e8b43a0cffc579bd9d48`.
- Attempt: `.runtime/first-model-api-1/`.
- CPU readings: `.runtime/compiler-guard/dba68df3f930473ab899cc43143b19e8/`.
- Launcher: `.runtime/model-api-launch-1/`.
- Capacity probe: `.runtime/image-storage/97009579a3b340648f2323b45aabb632/`.
- Review folder: `.runtime/model-api-review/` followed by the review SHA above;
  contains `owner-approval.json`, `execution-result.json` and `execution-preservation.json`.
- Preservation manifest SHA256:
  `e3481c7b5efbacdc418b761a9f84413fdc54422026f8281e36e9500f0877eed8`.
- `execution-preservation-supplement.json` verifies all 198 original inventory
  entries unchanged and binds the one offline admission-replay file added after
  that inventory. The original manifest was retained unchanged. Supplement SHA256:
  `1e32f294234ee4ab22b0efc35973de426d238973408edb578b0d2a9b934d1f5d`.

The [original review](FIRST_API_REVIEW.md), disabled template and frozen helpers
remain unchanged; its preparation-time approval-absent statements are historical.
386 offline tests were recorded before execution. This turn changed no runtime
code and used the approved frozen helpers, not simulated model success.

## Next outcome

A real API answer is still the next functional milestone, followed by one
Codex-submitted OpenCode edit and returned patch. Prepare a separately reviewed
attempt when ordinary host activity permits the existing CPU/free-RAM admission
window; do not lower thresholds, change WSL resources, close other applications,
reuse this decision or restart its container automatically.
