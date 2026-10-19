# Seventh API test: admission passed; Docker status check timed out during startup

18 October 2026, approximately 22:37 Israel time. **One approved attempt consumed;
FAULT-latched, container stopped/retained, all owned host processes exited.**

## Actual progress and failure

The owner approved one test at **94°C admission / 97°C stop**, accepting the
documented limitations and retaining the container/logs. All other limits and CPU
placement were unchanged. Frozen review/input checks, six-attempt preservation,
administrator consent and the included tiny no-GPU capacity/swap probe passed.

The required ten-second baseline **passed**. The immutable state journal recorded
`WAITING_BASELINE -> ARMED`; Docker then started the model container. During that
startup transition, the watchdog's `docker container inspect <owned ID>` exceeded
its **one-second deadline**. The watcher latched `MODEL_WATCH_ERROR`, recording
`TimeoutExpired`. It did not record a temperature/resource or file-access fault.

The retained inspection reports:

- Started: `2026-10-18T19:37:44.719895553Z`.
- Finished: `2026-10-18T19:37:47.118085679Z` (about **2.398 seconds**).
- Exited, PID 0, **exit 137**, `OOMKilled: false`, empty daemon error.
- Owned stop confirmed in **1.729 seconds**, within the unchanged five-second bound.
- Container retained: `d279798aad898617df6b94a5012699cc4e136eb0bcc022682de46e2c2d28612b`.
- Parent, watchdog, CPU reader and administrator wrapper all confirmed exited.

Bounded Docker events retain the start, TERM/KILL and exit sequence. Combined logs
are empty, no `/work/result.json` was saved, and no API readiness or answer was
observed. **Whether guest/API/native model initialization began is unknown**;
container startup is not proof of successful model loading. Request count is
unobserved, not invented as zero. The underlying reason for the slow Docker status
operation is not established by this timeout alone.

The raw watchdog error, all four journal states, raw readings, bounded log/events,
post-inspection, process-exit check and structured result are retained. No retry,
fault reset, resource/affinity change, further threshold increase or global
Docker/WSL stop occurred. The native helper remains stopped.

## Recorded observations

| Observation | Value |
| --- | --- |
| CPU readings | 15; 89–95°C |
| CPU admission / stop | 94°C / 97°C |
| Maximum CPU query time | 0.0386 seconds |
| GPU readings | 10; 60°C |
| Maximum GPU power / device VRAM | 24.37 W / 2,042 MiB |
| Host free RAM | 10,716.95–10,831.02 MiB |
| Maximum GPU query time | 0.1978 seconds |

No hardware stop event was recorded. These short observations do not establish
sustained inference safety, model memory fit or generation speed. The approved
software stop/source/cancellation limitations still apply.

## Preservation and next milestone

Review SHA: `8d6239ba96a8ec346554470479c861315520ee63808781f5a3322cf5c75af3ed`.
Session: `47f0fe727ad14c0aa761663a4c565155`.
Evidence: `.runtime/model-api-94-admission-review/<review SHA>/`,
`.runtime/model-api-7/`, `.runtime/model-api-launch-7/`, and reader
`.runtime/compiler-guard/9aacac04c23e4d7db931aad4558cd1a3/`.

Execution preservation SHA:
`46997b4ff1e1533eb0a66f240bb5b8a6253b952537df5298f13d0d84816ff9b1`.

Post-verification confirms all six prior attempts and older build evidence,
source/runtime/model identities and original settings unchanged. All seven
approvals are spent; no eighth packet/approval exists.

Next: reproduce the Docker status-probe/startup transition offline, test a bounded
correction and prepare a new operation for review. Keep CPU 94/97°C, thermal/
resource limits, independent telemetry/watchdogs, stop bound and API/request
deadlines intact. This run supplies no basis for another temperature increase.
Then obtain a real answer and one bounded OpenCode edit/returned patch alongside
Codex. The fourth run remains the latest proof of GPU model/API readiness.
