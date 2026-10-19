# Second Docker Strata API attempt — 18 October 2026

## Outcome

The owner-approved second attempt ended at **FAULT / BASELINE_NOT_MET**, after
the 90-second admission window, under the unchanged reviewed limits. CPU did not
remain at or below 92°C together with the other start conditions for ten seconds.
Free RAM and every recorded GPU admission channel met their requirements.

The container was created but **never started**: status `created`, PID zero,
no start/finish timestamp, no OOM. No Strata engine, API server, GPU workload,
inference request or worker ran. Docker's default exit-code field of zero is not
a successful model test. Linux/GPU compatibility and model memory fit remain unproven.
No policy/resource change, retry, fault reset or removal occurred.

## Recorded observations and next adjustment

| Channel | Observed | Admission requirement |
| --- | --- | --- |
| CPU, 89 samples | 87–95°C; 33 samples above 92°C | At most 92°C |
| Free host RAM, 70 samples | 13324.25–14995.04 MiB; no samples below requirement | At least 8192 MiB |
| GPU temperature | 59–60°C | At most 60°C |
| GPU power | Maximum 24.43 W | At most 40 W |
| Device VRAM used | Maximum 1713 MiB | At most 4096 MiB |

The CPU query maximum was 0.033365 seconds; GPU query maximum 0.536205 seconds.
Raw CPU validation remains false and CPU throttle unknown, as explicitly accepted.

Offline timestamp replay found an approximate longest combined admission window
of 9.918 seconds at the unchanged limits. A hypothetical **CPU admission change
from 92°C to 93°C only** produced a 21.417-second window in those saved readings.
Raising GPU admission alone did not extend the window; free RAM did not block it.
Host-loop receipt times were not logged, so replay is explanatory and cannot prove
native admission or future eligibility. It does not change or authorize policy.

The recommended next small proposal is therefore CPU start **92°C → 93°C**,
retaining CPU stop **97°C**, the ten-second window and every other limit. That
proposal is not implemented or approved here; another execution requires a new
review/namespace/decision. No autonomous threshold ladder or repeated launch.

## Shutdown and evidence

- Non-running container confirmed and retained in its original unstarted state;
  guard confirmation took 0.175 seconds. No removal occurred.
- Wrapper, controller, independent guard and CPU reader all exited, checked by PID.
- Empty Docker logs, automatic bounded diagnostic tail, inspections, raw readings,
  offline replay, controller/guard results and launcher output are retained.
- The included tiny no-GPU capacity/swap probe completed and confirmed no swap.
- Full post-run input verification confirmed original Windows configurations,
  WSL/Desktop settings, runtime/source/artifact/model identities and all previous
  build/API evidence unchanged. First API container and older retained containers
  were also checked non-running. No historical disk or attempt was modified.
- Existing 392 passing offline tests bind the reviewed code. No runtime code
  changed in this execution turn; no additional live workload was launched.

## Evidence identities

- Review: `fc1d1d9c970ba58922483dd57aac625cef87fd4879d83fe0cf413a166ae04599`.
- Session: `bc55b716b2b346eaac01a5da44157052`.
- Container: `bb32c325d280fb3c8ea2d4ffcfbf9d48f6c3df20b6af74c9b6ddf8082e75b8ca`.
- Attempt: `.runtime/model-api-2/`.
- Reader: `.runtime/compiler-guard/137f9177d82741c0983331e3de8ac62b/`.
- Launcher: `.runtime/model-api-launch-2/`.
- Capacity probe: `.runtime/image-storage/bd76ebd49df243e1ba91ef1072571230/`.
- Frozen review folder: `.runtime/model-api-recovery-review/` followed by the
  review SHA above; contains `owner-approval.json`, `execution-result.json` and
  `execution-preservation.json`.
- Preservation manifest SHA256:
  `1958b8f961e60ab2abe8884a416a12fa9f08a300c0580585bc1e31b1fdc71cdd`.

The [second review](SECOND_API_REVIEW.md), disabled template, frozen helpers and
the [first result](FIRST_API_RESULT.md) remain unchanged historical evidence.
Both approvals/attempts are consumed. The next functional outcome is still one
real API answer, then one Codex-submitted OpenCode edit, returned patch and shutdown.
