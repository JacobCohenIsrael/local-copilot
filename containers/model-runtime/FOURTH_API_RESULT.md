# Fourth Docker Strata API test — 18 October 2026

## Confirmed functional progress

**The model loaded on the RTX 3080 Ti in Docker, native CUDA graph capture
succeeded, and the OpenAI-compatible API became ready.** Admission, guest resource
and isolation checks passed at the approved 93°C start / 97°C stop settings.
The corrected `--spec 2` arguments passed the native-IQ and serve requirements.

Exactly one request was submitted. It failed with **HTTP 503** because the upstream
server ended the engine after 30 seconds without native progress during the
19-token prompt. It reported zero generated tokens. This preceded the independent
90-second request deadline. The host latched `FAULT / API_TEST_FAILED` and confirmed
the container stopped within **0.994 seconds**. No successful text answer or coding
task has been demonstrated. Logs do not establish whether the silence was normal
CPU/I/O slowness or an engine stall.

## Native observations

- Native embedding mapped: 322 MiB. Pack weights loaded: 1406 MiB; native
  projection weights: 2018.88 MiB; native Q5_K head: 521472000 bytes.
- The engine identified GPU compute capability 8.6, filled its cache, reported
  session up and captured the two-token window with upload/sync reporting no error.
- The requested expert-cache flag stayed 64. The engine rounded it to 82 slots
  internally (0.16 GiB); this flag is not a hard GPU quota. Device VRAM/power stops
  remained the guard boundaries.
- API ready at `2026-10-18T14:42:12.357584773Z`; request silence failure at
  `2026-10-18T14:42:43.046794155Z`. The guest saved `modelStarted: true`, one
  submitted request, and `HTTP Error 503: Service Unavailable`.

| Recorded metric | Observed |
| --- | --- |
| CPU, 109 samples | 85–96°C; maximum query 0.044453 s |
| GPU, 82 samples | 56–67°C; maximum 78.46 W |
| Device VRAM used | Maximum 7291 MiB |
| Free host RAM | 6351.82–11232.73 MiB |
| GPU query | Maximum 0.226347 s |

All stop conditions remained within limits; no OOM, daemon error or thermal/
power/RAM/VRAM fault was recorded. The 8-GiB free-RAM rule applies at admission;
running host RAM stayed below its separate stop threshold. Startup fit in the
reviewed envelope is observed; successful request completion and worst-case
memory fit are not established. Hardware settings, budgets and token caps did
not change. Raw CPU validation/throttle limitations remained as accepted.

## Retention and verification

The container is retained `exited`, PID zero, exit code 1, not OOM-killed. It ran
from `2026-10-18T14:41:09.349943058Z` to `2026-10-18T14:42:43.878440669Z`.
All four owned host processes exited. Full timestamped Docker logs (9959 bytes),
bounded diagnostic tail, qualification, request result, raw readings, inspections,
launcher output and failure diagnosis are hash-inventoried.

The prepared wrapper incorrectly named the third log destination. Before launch,
an exact one-string correction selected the reviewed fourth log folder. Original
wrapper, corrected copy and `launcher-path-correction.json` remain preserved;
no third-attempt log or workload argument was modified. Only one UAC launch and
one model attempt occurred. No automatic retry/reload/reset occurred.

All three previous API inventories, frozen helpers/inputs/approvals, old build
evidence, model/source/runtime/artifact identities and original Windows/WSL/Desktop
configurations were verified unchanged. Older retained containers were checked
non-running. No historical disk/container was removed or altered.

## Evidence identities

- Review: `29c70fec244b6f0f747dc60e39aab091387af43b55d5bc7708e2320ebc533bb2`.
- Session: `599ada6e0e4448d28211427153c6f545`.
- Container: `8257d6cfc5da92dcc687285f9c7e21a513031d60ba98a71f1df9210b22ae9dc4`.
- Attempt: `.runtime/model-api-4/`.
- Reader: `.runtime/compiler-guard/c44e62293d2c4525b1953c9dc846e938/`.
- Launcher: `.runtime/model-api-launch-4/`.
- Capacity probe: `.runtime/image-storage/a3fa2929a2ba4a4893c961e719fca7af/`.
- Review folder: `.runtime/model-api-native-review/` followed by the review SHA;
  contains owner approval, execution result, wrapper correction and preservation manifest.
- Manifest SHA256: `9515d7896260b0ac430e636bd2e617bc5d5270a40b848533c7b2f54b93e0573d`.

The fourth approval is spent. The [next exact proposal](FIFTH_API_REVIEW.md) changes
only the inner application's `engine_silence_s` from 30 to 75, retaining the
independent 90-second request deadline, 300-second runtime, 93/97°C and all other
limits. It is prepared offline with 404 passing tests and needs its own live-test
approval. All four historical attempts stay preserved. No fifth workload has run.
