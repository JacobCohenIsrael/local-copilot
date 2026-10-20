# Task 2: 30 GiB host RAM stop, readiness deferred

**Executed once; approval consumed.** See the [result](CODING_TASK_2_RAM30_RESULT.md):
the API returned truncated code, rejected before editing. Both containers and
all four host helpers were independently confirmed stopped/exited. The frozen
review below and its runtime snapshot remain preserved; do not rerun this scope.

19 October 2026. **Policy change approved; one live attempt awaits fresh approval.**

The owner directed: "Raise the crossing to 30" and "no need to add readiness
for now". This scope raises the used-host-RAM emergency stop from **28 GiB
(28,672 MiB) to 30 GiB (30,720 MiB)** and uses the existing compact task-2
request. No additional readiness gate, memory optimization or tuning is added.
The earlier readiness proposal is preserved as unrun, deferred preparation.

The [last real attempt](CODING_TASK_2_COMPACT_RESULT.md) stopped at 29,090.77 MiB
used. That reading is below the new stop. At the new crossing, the recorded
32,388.68-MiB physical host would have about 1,668.68 MiB available. This is a
monitored stop threshold, not a reservation or guarantee of future memory fit.

The offline RAM diagnosis remains in the [previous review](CODING_TASK_2_RAM_REVIEW.md).
It establishes aggregate pressure; it cannot attribute the increase to a
specific process, WSL allocation or cache. Its suggested readiness condition
does not apply to this scope.

## Fixed task and unchanged limits

Stage only `containers/worker/task_bundle.py`. Ask Strata for a single Python
guard that raises `ValueError` when integer `maximum` is negative. Validate the
complete response, insert only that guard at the start of staged `bounded_read`,
then let OpenCode return a patch. The repository original stays untouched.

Exact request: `Python guard only: reject negative integer maximum with ValueError.`
The previously audited template gives 23 prompt tokens. The strict validator
rejects truncated, unrelated or multiline output before editing.

| Limit | Prepared value |
| --- | --- |
| API requests / OpenCode calls | One / two (request and edit); no retry |
| Request deadline / native-engine silence base | 150 s / 75 s |
| Context / output / margin | 512 / 32 / 8 tokens |
| Guard / changed files | At most 128 bytes / selected file only |
| CPU emergency stop | 97 C |
| GPU emergency stops | 75 C / 100 W / 14,336 MiB VRAM |
| Host RAM emergency stop | **30,720 MiB used**, trip at or above |
| Startup targets | Advisory CPU 94 C, GPU 60 C / 40 W / 4,096 MiB, free RAM 8,192 MiB |
| Admission / freshness / controller lease | 10 s valid telemetry / 2.5 s / 2.5 s |
| WSL | One CPU / 6 GiB / no swap |
| Model container | One CPU / 4 GiB / no extra swap |
| Worker container | Half CPU / 512 MiB / no extra swap; no GPU or network |
| Model startup / lifetime / outer operation | 180 s / 300 s / 410 s |
| Owned stop deadline | 5 s |

Every other policy field, model/configuration, guest script, task contract and
request is compared against the last executed compact review. The controller
and independent watchdog both activate the new RAM threshold; default and
historical scopes retain their original policies. CPU-build admission stays
92 C with a 97 C stop. Source limitations and inactive 95/98 C history persist.
All original read-only mounts, isolation, faults, telemetry and cancellation
controls stay enforced. No server heartbeat is treated as native-engine progress.

## Reviewed attempt and preservation

Scope: `one-fresh-useful-task-2-30gib-host-ram-stop-no-readiness`.

Review SHA256: `4b1d0a4a15eec7f180a13d52ce23c68b4d2860fbe903960c645cfabc27937875`.

Frozen packet and helpers: `.runtime/strata-coding-2-ram30-review/4b1d0a4a15eec7f180a13d52ce23c68b4d2860fbe903960c645cfabc27937875/`.

Preparation creates selected-file staging and an immutable review snapshot.
New execution namespaces are `.runtime/strata-coding-2-ram30-model`,
`strata-coding-2-ram30-worker` and `strata-coding-2-ram30-launch`.
New decision file: `containers/model-runtime/coding-task-2-ram30-approval.json`.
All execution namespaces and that decision remain absent; launch flags are false.
The new decision must bind the exact review and policy hashes. Spent decisions
cannot authorize this scope. There is no readiness acceptance field or helper.

The snapshot includes the exact helpers/tests, validation receipts, an unexecuted
administrator wrapper and an independent post-exit capture script. The wrapper
syntax is checked offline. After fresh approval, dispatch once, preserve any
returned patch and evidence, check patch applicability without applying it,
and independently confirm both owned containers and all four host helpers
stopped/exited. Retain failures and stopped containers. No retry, fault reset,
patch application, global Docker/WSL action or private-disk action is authorized.

The latest executed preservation manifest remains
`e03c7f983f591e1c53bc1124798d6ce27778d27f74465360b6f2b828278827c0`.
The deferred, never-run readiness preparation remains
`1a8727abf13ed83d8476789ef7641ebadd7ec709fc9dcb4d4a2b4eaceb14f526`.
Both complete inventories and all older failure proofs are bound in this review.
Fourteen model attempts remain consumed; this preparation consumes none.

**128 offline runtime/integration checks passed**, including new RAM-boundary,
latching, unchanged emergency-stop, controller/watchdog consistency and missing/
spent-approval checks. All hardware and launch calls in those tests are mocked.
No live model, container, sensor or host RAM reading ran during preparation.

Read-only review: `python -B local_worker.py review-useful-coding-task-ram30`.
Execution after fresh approval: `python -B local_worker.py run-useful-coding-task-ram30`.
Context expansion, Hermes and further optimization remain deferred.
