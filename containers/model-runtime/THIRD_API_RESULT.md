# Third Docker Strata API attempt — 18 October 2026

## Outcome

**Admission passed at 93°C. The GPU-enabled container, Python API process and
native Linux Strata engine process started.** Guest qualification verified one
CPU, 4 GiB memory, zero additional swap, 128 processes, UID 65532, zero effective
capabilities, no-new-privileges and loopback-only networking under Python 3.13.15.

The engine then rejected the prepared configuration: this native IQ pack requires
`--spec T` with `T >= 2`, while the reviewed arguments used **`--spec 0`**.
The engine exited with code 2 before readiness. The host latched
**FAULT / API_TEST_FAILED** and stopped the container, which exited with code 1.
The controller returned code 3 to report the failed attempt. No inference request
or coding worker ran. No retry, resource change or further threshold change occurred.

This exposed an incompatible value in our prepared startup arguments. It is not
an admission failure, OOM or temperature-stop event. Another temperature increase
is not indicated by this result. Native GPU model execution/memory fit and a real
API response remain unproven.

## Source diagnosis and readiness limits

The retained engine log names the native-IQ requirement. The pinned source
`src/program/generate.cpp:3024` checks `o.spec < 2` and returns 2 before calling
`native_embed.load`. Its source SHA256 is
`fd85d08db152867dfe9a36afaee584b643bd26ddd70d791f9ef95ca47ab940c7`.
The prepared `--native` paths and prefill 32 are also present in the logged command.
Review the complete native-pack startup contract before choosing the next values;
changing this one argument alone is not yet evidence of successful startup.

The raw guest result correctly retains `modelStarted: null`, since health/READY
was never observed, with `apiProcessStarted: true`, `requestsSubmitted: 0` and
`API_EXIT_BEFORE_READY`. The native process launch is independently evidenced by
its log. The extent of early GPU initialization is not independently established;
the structured execution record retains `gpuWorkloadStarted: null`. Do not turn
these unknown fields into a claim of real model execution or successful inference.

The later guest `HOST_STOP` traceback follows the original engine argument
rejection during host cleanup; it is not the initial startup failure.

## Recorded metrics and stopping

| Channel | Observed |
| --- | --- |
| CPU, 19 samples | 88–95°C; maximum query 0.024933 s |
| GPU, 15 samples | 57–59°C; maximum power 39.24 W |
| Device VRAM used | Maximum 1822 MiB |
| Free host RAM | 12240.30–13260.79 MiB |
| GPU query | Maximum 0.204686 s |

CPU admission was 93°C for ten seconds; CPU stop remained 97°C. Readings above
admission after startup remain governed by the unchanged stop threshold. WSL
1 CPU/6 GiB/no swap, container 1 CPU/4 GiB, all GPU/host/data/lease/deadline limits,
512 context and eight output tokens stayed exactly as approved. Raw CPU validation
remains false and CPU throttle unknown, under the accepted source limitation.

Container start: `2026-10-18T14:23:45.463552661Z`.
Container finish: `2026-10-18T14:23:51.141099489Z`.
Owned non-running confirmation took **0.650 seconds**, within the five-second
bound. Retained inspection confirms `exited`, PID zero, no OOM and no daemon error.
Wrapper, controller, independent guard and CPU reader all exited, verified by PID.

## Preservation

- The stopped container is retained, with all 4534 bytes of timestamped Docker
  logs and the automatic bounded diagnostic tail. Raw CPU/GPU readings, guest
  qualification/result, guard/controller outcomes, launcher output, inspections
  and offline source diagnosis are hash-inventoried.
- The existing tiny no-GPU capacity/swap probe completed with no guest swap.
- Post-run verification confirmed both previous failed API inventories, first
  supplement, frozen helpers/inputs/approvals, prior build evidence, model/runtime/
  source/artifact identities and original Windows/WSL/Desktop configurations
  unchanged. Earlier retained containers were checked non-running; no disk or
  historical evidence was changed or removed.
- No runtime code changed in this execution turn. The reviewed 395 passing
  offline tests remain preparation evidence, not proof of model inference.

## Evidence identities

- Review: `fa9eeb3023db47bc8fd00a338979dabb13a0a8f16026e31c127d22d04a6c96b8`.
- Session: `548aa6faf73d43ada7d516555317d52b`.
- Container: `bde071578cca6701809c592f2fe7ca90416260677f0ef579734c3b1a964c99c5`.
- Attempt: `.runtime/model-api-3/`.
- Reader: `.runtime/compiler-guard/25307246f62941a480e394667b0bf076/`.
- Launcher: `.runtime/model-api-launch-3/`.
- Capacity probe: `.runtime/image-storage/9f4b0fc07051477fab2c844c6f789896/`.
- Frozen review folder: `.runtime/model-api-admission-review/` followed by the
  review SHA above; contains owner approval, execution result and preservation manifest.
- Preservation manifest SHA256:
  `6eeb23d789f2ee67549c5c39fea1ab11dc9ee168245a192ab5ac2a169ef3fdc4`.

The [third review](THIRD_API_REVIEW.md), template and frozen helper snapshot remain
unchanged. All three approvals/attempts are consumed; no restart/reset is authorized.

## Next functional step

Correct and test the native-IQ startup arguments offline against this pinned
source, then prepare a fresh exact API operation for approval. Keep 93°C admission,
97°C stop and all other limits. Preserve this failure and its stopped logs. The
next outcome remains one real API answer, then a Codex-submitted bounded OpenCode
edit, returned patch and confirmed shutdown. No new live operation ran after this fault.
