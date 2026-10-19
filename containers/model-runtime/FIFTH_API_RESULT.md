# Fifth API test: parent file-access failure before model startup

18 October 2026, approximately 20:59 Israel time. **Attempt consumed; stopped and retained.**

The owner approved the [fifth operation](FIFTH_API_REVIEW.md): inner engine silence
75 seconds, independent request deadline 90 seconds, CPU admission 93°C / stop
97°C, all other hardware/resource limits unchanged. The first administrator
prompt was canceled while the owner was away. That launch record is preserved.
The owner explicitly requested a consent retry; the second prompt succeeded.

## Actual result

Input/preservation checks and the tiny no-GPU capacity/swap probe passed. The
supervisor created the reviewed model container and began baseline admission.
Its parent then raised `PermissionError`. Cleanup requested cancellation, and the
watchdog recorded `FAULT / CANCELLED`. That label is cleanup following the parent
error; it does not mean the owner canceled this running attempt.

- Container never started: Docker state `created`, PID 0, zero start/finish
  timestamps, no OOM or daemon error. Zero inference requests; no model/GPU workload.
- Owned stopping confirmed in **0.171 seconds**. Retained container:
  `3eacfdda1f9f3a3965af96377a945fc410eed95b65797e510e8766ed4332624e`.
- Parent, watchdog, CPU reader and administrator wrapper all exited.
- Combined Docker log is empty, as expected for an unstarted container. Raw
  parent error, state, readings, launch output and post-inspection are retained.
- All four earlier API attempts, prior build evidence and original configurations
  were verified unchanged after this attempt. No automatic retry or reset.

The raw parent record contains only the exception type, empty stderr and
`automaticRetry: false`. It lacks the exception message, filename, Windows error
number and traceback. **The exact failing file operation is not established.**
Do not attribute it to the earlier sample-file conflict or to the model engine
without further evidence. The new 75-second setting was never exercised.

## Recorded readings

| Observation | Value |
| --- | --- |
| CPU readings | 38; 83–95°C |
| Maximum CPU query time | 0.0363 seconds |
| GPU readings | 30; 58–59°C |
| Maximum GPU power / device VRAM | 39.91 W / 1,985 MiB |
| Host free RAM | 10,601.91–11,155.70 MiB |

No hardware stop event was recorded. These are passive admission readings;
they do not demonstrate model execution or its memory/performance behavior.

## Evidence and next work

Review SHA: `cbbcdf85aa9a72b6122fc1c30ecdaf89fe2ba0347ef5e17b73868cbcfcfaf38b`.
Evidence lives in `.runtime/model-api-timing-review/<review SHA>/`,
`.runtime/model-api-5/`, `.runtime/model-api-launch-5/`, and reader directory
`.runtime/compiler-guard/96d4e6caabad450fa5dce69b58be34c2/`.

Execution preservation SHA:
`5ef88755dad5b0c78122ca631a67ff1b73cadfe9bc9bc201eaa466c10ec4a2c2`.

Next: diagnose the parent file-access paths offline, reproduce the conflict if
possible, retain precise bounded error details, and prepare a separately reviewed
attempt. Keep the current fault latched and all limits unchanged. The immediate
functional goal remains a real Strata answer, then one OpenCode edit/returned
patch alongside Codex. GPU/API startup was proven by the fourth run; successful
text generation remains unproven.
