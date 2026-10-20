# Fresh useful task-2 attempt: request timeout, shutdown confirmed

19 October 2026. **One approved real attempt; no returned patch, no retry.**

The owner approved the existing fresh review
`55ef192ab57dde085aab4dd8840b7a765e019507f1ba96782eedd09bfcae8059`.
It ran once under the unchanged [reviewed limits](CODING_TASK_2_RECOVERY_REVIEW.md).
Docker was ready, OpenCode made its provider request, and Strata started in
Docker. The API submitted exactly **one** model request.

The request reached its **90-second deadline** and returned the recorded fault
`TimeoutError: timed out`. The supervisor latched `API_TEST_FAILED` and stopped
its owned components. No complete API response, model-supplied edit, or returned
patch was obtained. Nothing was applied to the repository, and no retry,
restart, fault reset or deadline/resource/policy change occurred.

Native logs report **24 prompt tokens**, approximately 47 seconds before the
first generated token, and **21 generated tokens of the 32-token allowance**
before the 90-second error. These are native progress-log counts, not a completed
API `usage` receipt. The API has no response/usage object or complete code to
validate. Do not fabricate a patch from progress or claim a useful coding result.
Configured context remained 512; usable near-limit context remains unproven.

## Independent shutdown confirmation

| Owned component | Independent finding |
| --- | --- |
| Model `1db119824bd3958b1006d379d2c7482614320ece19287381784f3b2ee5a5867e` | Exited, Running false, PID 0, exit 70, OOMKilled false |
| Worker `ab9c9dddb71c859e922788dbac34e9ddf77ecec0e21a4ca7cc45e225a7c3ec88` | Exited, Running false, PID 0, exit 70, OOMKilled false |
| Parent PID 31176 | Independently confirmed exited |
| Watchdog PID 37404 | Independently confirmed exited |
| CPU reader PID 41024 | Independently confirmed exited |
| Administrator wrapper PID 33348 | Independently confirmed exited; wrapper recorded exit 3 |

The model ran 13:30:36–13:33:16 Israel time (10:30:36–10:33:16 UTC).
The worker ran 13:29:46–13:33:16 Israel time. Both containers are retained stopped.
The approved capacity/swap probe also confirmed cleanup and zero guest swap.
No global Docker/WSL stop, retained private-engine action or attached-disk action
was performed. Docker Desktop was left running.

The stock upstream log emits a generic message about an engine killed with -9
and suggests OOM as a usual cause. That text is **not an OOM finding** here:
the recorded API timeout triggered the shutdown path, and both container
inspections report OOMKilled false. No automatic engine restart occurred.

Recorded telemetry: 172 CPU samples, 138 GPU samples; CPU 91–96 C, GPU 59–72 C,
peak GPU power 86.67 W, peak VRAM 6,864 MiB, minimum host free RAM 8,413.78 MiB.
CPU 95 C was recorded as a startup-target warning under the existing policy.
CPU emergency stop stayed 97 C; all other emergency stops stayed unchanged.
The recorded terminal fault is the API timeout, not a thermal or memory stop.
Existing sensor-source calibration/refresh/throttle limitations still apply.

## Preserved evidence and remaining state

Directory:
`.runtime/strata-coding-2-recovery-review/55ef192ab57dde085aab4dd8840b7a765e019507f1ba96782eedd09bfcae8059/`.

- Exact review/frozen helpers, task inputs, original and approved decision.
- Single dispatch/wrapper records and raw launch output.
- API fault, actual OpenCode request, native/container logs, raw readings,
  state transitions, worker fault and controller/reader receipts.
- Independent container and host-process inspections, metrics summary.
- Structured `execution-result.json` and `execution-preservation.json` covering
  the model/worker/reader/launcher/probe, selected-file staging, task bundle and
  review evidence. No empty or invented `returned.patch` was written.

Execution-result SHA256:
`68c5d2a532617f1722d2dd0933aa06798e496f1eb6a4b144ea43e6d0348ecaa7`.
Preservation SHA256:
`ed524dcb61a59b10da3120c35d3d119fd46a5cb3ee8ff45a8e1629e9aa1d4c29`.

Repository target, disposable original and unselected sentinel are unchanged.
All ten preceding model attempts, the earlier failed worker-only attempt and
its spent approval, build evidence, model/source identities and existing settings
were verified unchanged. Frozen sources preserve exactly what executed.

There are now **eleven consumed model attempts**. This operation's approval and
worker/model scopes are spent. The 93 offline runtime/integration checks were
pre-execution validation; this real timeout does not establish coding success.
Review the timing/result before any separately reviewed successor. No retry,
new workload, context expansion or Hermes integration is authorized.

Read the consumed scope without launching hardware:

```
python -B local_worker.py review-useful-coding-task-recovery
```
