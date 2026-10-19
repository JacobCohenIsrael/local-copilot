# Sixth API test: CPU admission not met; file-access correction held

18 October 2026, approximately 21:21 Israel time. **Approved attempt consumed;
FAULT-latched, stopped and retained. No model workload started.**

The owner explicitly approved the exact [sixth test](SIXTH_API_REVIEW.md),
including the file-access correction and unchanged limits/source/cancellation
limitations. Administrator consent succeeded. The supervisor verified the frozen
packet/inputs and all five previous attempts, ran the included tiny no-GPU
capacity/swap probe, created one model container and monitored admission.

## Actual outcome

- Terminal fault: **BASELINE_NOT_MET** at the reviewed 90-second admission limit.
  CPU did not provide the required ten-second window at or below 93°C. Every
  recorded GPU/RAM/AC/thermal-throttle start condition passed.
- No parent file-access error was recorded. The new immutable state journal
  published three snapshots through terminal stopping. This is live admission-stage
  evidence for the correction; API/request-stage behavior was not exercised.
- Container remained `created`, never started, PID 0 and zero start/finish
  timestamps. No model load, inference request, OpenCode worker or GPU workload.
- Owned stopping confirmed in **0.182 seconds**. Container retained:
  `564ce1f313db7d9aa6494072015c57caf58529651c8112ec403fc6bf436e46d1`.
- Parent, watchdog, CPU reader and administrator wrapper all exited. Docker log
  is empty, as expected for an unstarted container; raw readings, states, launch
  output, post-inspection and structured results are preserved.
- No OOM, daemon error or hardware stop event was recorded. No automatic retry,
  fault reset, threshold/resource adjustment or global Docker/WSL stop occurred.
- Post-verification confirms all five previous API attempts, older build evidence,
  source/runtime/model identities and original configurations unchanged.

## Recorded observations

| Observation | Value |
| --- | --- |
| CPU readings | 89; 87–95°C |
| CPU readings above 93°C admission | 38 |
| Longest span between consecutive qualifying CPU points | Approximately 8.986 seconds |
| Maximum CPU query time | 0.0343 seconds, below 1.5-second cutoff |
| GPU readings | 68; 58–59°C |
| Maximum GPU power / device VRAM | 39.5 W / 2,265 MiB |
| Host free RAM | 8,870.82–9,498.36 MiB |
| Maximum GPU query time | 0.2407 seconds, below 1-second cutoff |

The recorded-point span omits delivery/poll timing; it is explanatory, not a new
admission proof. The native guard's terminal result is authoritative. CPU remained
below the 97°C stop threshold; the blocker was the **start** rule. This run does
not establish model memory fit, request performance or generated text quality.

## Preservation and next work

Review SHA: `1f8494f279fb07c3c3ae2f62b39ba854e04fd1c915816696544416681d3c5b6a`.
Session: `0bb6678c456845bbadeb065729c71caf`.
Evidence: `.runtime/model-api-file-access-review/<review SHA>/`,
`.runtime/model-api-6/`, `.runtime/model-api-launch-6/`, and reader
`.runtime/compiler-guard/ec6b4b8bf9be48e0bbc072cec7b35275/`.

Execution preservation SHA:
`7df84f76a54baa38441ca1718434674b910c0170cfbb802b499eeecec9a6039d`.

All six approvals are spent. No seventh packet or approval exists. Keep this
fault latched and all existing limits unchanged. The remaining immediate decision
is how to obtain CPU admission: another fresh scoped attempt at unchanged limits,
or an explicitly reviewed admission-policy adjustment. Neither is authorized by
the sixth one-test approval. Do not increase the 97°C stop or retry automatically.
Then obtain a real Strata answer and complete the bounded OpenCode edit/patch
alongside Codex. Fourth-run GPU/API readiness remains the latest model-start proof.
