# Task 2: host RAM diagnosis and a readiness condition before launch

**Deferred by subsequent owner direction.** This proposal was never approved or
run. Its frozen snapshot remains unchanged. The owner approved a 30 GiB host RAM
stop and deferred added readiness; use the [new review](CODING_TASK_2_RAM30_REVIEW.md).
The diagnosis below remains evidence; its readiness proposal is historical.

19 October 2026. **Offline preparation only; fresh owner approval required.**

The [compact attempt](CODING_TASK_2_COMPACT_RESULT.md) was stopped by the existing
host RAM emergency guard. This successor retains the exact 23-token request,
strict code admission, model/configuration and all existing safety/resource/time
limits. It adds one explicitly approved task-readiness check before starting
the worker or model. No live query, Docker workload, GPU or sensor was started
to prepare this review.

## What caused the stop, and what cannot be attributed

The preserved Windows reading is **total physical RAM minus available physical
RAM**, obtained by `GlobalMemoryStatusEx`. The fact that these records are named
`gpu-*.json` does not make their RAM fields GPU readings; the same sampling
operation merges NVIDIA GPU telemetry with native Windows RAM/power status.

The last two samples were 28,611.38 and **29,090.77 MiB used**, 1.32 seconds apart.
The second crossed the unchanged **28,672-MiB (28-GiB) emergency stop** by
418.77 MiB, and the existing gate correctly latched `HOST_RAM_HIGH`.
Replaying that saved reading through the gate reproduces the fault. The model
exited 137 during owned stopping; OOMKilled was false in both containers.

The first saved sample was already 24,921.60 MiB used, after the worker had
started but before the model container started. However, RAM then **fell to
20,528.82 MiB just before model start**. It subsequently rose 8,561.95 MiB to
the stopping point. It would be misleading to call the first reading the
actual launch baseline, or attribute the full increase to the model alone.

| Recorded task-2 run | First used MiB | Used just before model start MiB | Peak used MiB |
| --- | ---: | ---: | ---: |
| 90-second timeout | 18,501.56 | 18,489.86 | 23,974.90 |
| Completed API, unrelated answer | 20,734.96 | 21,040.46 | 25,949.55 |
| Engine silence | 21,478.63 | 21,420.37 | 28,418.73 |
| Host RAM stop | 24,921.60 | 20,528.82 | 29,090.77 |

The concrete cause was **aggregate host memory pressure with insufficient,
volatile headroom** while the model was processing the prompt. Windows,
applications, WSL/Docker and driver allocations all share that physical RAM.
The model's 4-GiB container ceiling limits that container's accounting; it is
not a limit on the whole Windows host. WSL's 6-GiB ceiling and the worker's
512-MiB ceiling are also separate bounds. The 4,096-MiB GPU VRAM reserve
concerns a different memory pool.

The saved evidence has **no process working-set/commit breakdown, contemporaneous
WSL memory breakdown or cache attribution**. It cannot establish which process
caused the increase, whether memory was retained from earlier work, or whether
there is a leak. The model logs show mapped expert files and ordinary model
startup allocations; mapping a large file does not establish that its full
size was resident. No claim that a specific application, cache or model
allocation consumed the missing RAM is supported. No current live measurement
can reconstruct that historical attribution, so none was taken for this review.

## Correction: one task-readiness check before any workload

The new, additional condition is **host used RAM at or below 18,432 MiB
(18 GiB)** before creating/starting the worker. That leaves **10,240 MiB
(10 GiB) below the unchanged emergency stop**. On the recorded 32,388.68-MiB
host, it corresponds to at least 13,956.68 MiB of available physical RAM.
This is headroom to the stop threshold, not a reservation of OS memory.

The largest observed within-run minimum-to-peak span was 8,561.95 MiB. Ten GiB
leaves 1,678.05 MiB beyond that span, including room for the worker, which was
already present in those historical samples and is capped at 512 MiB. This is
a conservative planning allowance based on observations, **not a measured
model-only requirement or a guarantee against later pressure**. Other host work
can still grow; the existing emergency guard remains necessary.

The owner should close unneeded applications before authorizing the attempt.
The agent will not choose applications to terminate or purge caches. There is
no Docker/WSL restart/stop, retained-disk action, memory-limit increase or
operating-system/power change in this proposal.

This is a **new blocking task-eligibility condition**, separately bound in the
review and requiring `acceptHostRamReadiness` in the fresh owner decision.
The existing 8-GiB startup free-RAM target remains advisory in the unchanged
model/API guard, as do the other owner-approved startup targets. No shared
safety policy or startup-warning behavior is changed. The additional job check
must not be described as merely another warning or silently inherited approval.

After explicit approval, the single run will:

1. Claim a fresh readiness namespace, binding the review and decision hashes.
2. Run one read-only Windows RAM/power-status helper, recording its PID and exit.
   Its runtime is bounded at 1.5 seconds, with a one-second owned stop/reap
   allowance; output is bounded to 4,096 bytes. The native query must report
   duration at most one second and a frame no older than 2.5 seconds.
3. Evaluate the condition once. Insufficient RAM, missing/stale/malformed data
   or a query failure consumes the operation approval and ends the attempt
   before worker/model/probe startup. No polling, waiting for improvement or retry.
4. If eligible, enter the existing one-shot coding runner. Subsequent approval
   checks validate the immutable readiness observation, decision and helper-exit
   receipts. The observation is historical job admission, not replacement
   runtime telemetry. The normal fresh monitoring/watchdogs remain active.
5. Preserve any patch and evidence; check applicability without applying it.
   Independently confirm the two exact containers and all four existing host
   helpers stopped/exited, plus the one-shot readiness helper. If readiness
   fails, preserve its fault and independently confirm the launched host helpers
   exited and that the two named workload containers were never created.

A refusal before workload startup consumes this operation, but does **not**
consume another model attempt. Its evidence is preserved in a separate namespace;
no old fault or approval is reset. No automatic process termination outside the
owned helper/containers is permitted.

## Same fixed task, request and safety limits

Exact model message remains:

```text
Python guard only: reject negative integer maximum with ValueError.
```

Only `containers/worker/task_bundle.py` is selected: 9,293 bytes, SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
The adapter still requires a completed `finish_reason: stop`, a single line
without fences, and the narrow AST for `if maximum < 0` raising `ValueError` or
`ValueError()`. Maximum guard size is 128 bytes. The model must supply the guard;
the adapter cannot repair or invent it. All existing source bytes are preserved.
Acceptance still proves negative rejection before access and unchanged normal
and oversize reads; response/edit hashes must agree. OpenCode edits only the
disposable staged file. Native/general model tool calling remains unproven.

| Existing control | Unchanged value |
| --- | --- |
| Attempts / model requests / OpenCode calls | 1 / 1 / at most 2 |
| Request / engine silence base | 150 / 75 seconds |
| Model startup / model lifetime | 180 / 300 seconds |
| Worker subprocess / worker and outer lifetime | 400 / 410 seconds |
| Stop allowance / freshness and leases | 5 / 2.5 seconds |
| Actual prompt / context / output / runtime margin | 23 / 512 / 32 / 8 tokens |
| WSL | 1 CPU, 6 GiB, no swap |
| Model container | 1 CPU, 4 GiB, no extra swap, same image/model/configuration |
| Worker | 0.5 CPU, 512 MiB, no extra swap, 64-MiB tmpfs, no network/GPU |
| CPU / GPU stop | 97 C / 75 C |
| GPU power / VRAM / host used RAM stop | 100 W / 14,336 MiB / 28,672 MiB |

All file, patch, request, response, stdout/stderr and process caps, read-only
mounts, UID/capability restrictions, ten seconds of valid model-start telemetry,
advisory startup targets, accepted source limitations, AC/throttle checks,
independent watchdogs, owned stopping and latched faults remain unchanged.
The new readiness helper completes before workload startup, with its own small
bound; it grants no extra model/request/worker time. Earliest existing guard wins.

No engine/source patch, build, model/configuration tuning, CPU-share change,
installation, download, context/output expansion or extra model request is
proposed. CPU-build 92/97 C and inactive 95/98 C history are preserved.

## Offline validation, evidence and approval boundary

Scope: `one-fresh-useful-task-2-host-ram-readiness-same-safety-limits`.
Review SHA256:
`ef7fe198b880eedb015cf92949ba15ae04fb8109f32610a00570ab78a094ef01`.
The packet, frozen helpers/tests, saved-series audit, validation receipts,
unexecuted administrator wrapper and post-exit capture helpers are under
`.runtime/strata-coding-2-ram-review/ef7fe198b880eedb015cf92949ba15ae04fb8109f32610a00570ab78a094ef01/`.
Wrapper/capture syntax was checked without execution. The capture includes a
readiness-refusal path and independent inspection of the new one-shot helper.
Unexpected earlier worker failures still require preserving their raw records
and inspecting any exact created target before sealing; never rerun the workload.

Fresh namespaces are `.runtime/strata-coding-2-ram-readiness`,
`strata-coding-2-ram-model`, `strata-coding-2-ram-worker` and
`strata-coding-2-ram-launch`. All are absent. Selected-file staging is
`.runtime/strata-coding-2-ram-files`. The required new decision,
`containers/model-runtime/coding-task-2-ram-approval.json`, is absent.
Read-only review reports `MODEL_API_READY_FOR_APPROVAL`, with launch flags false.
Do not reprepare the packet after approval or reuse any spent decision.

**123 offline runtime/integration checks passed**, including eleven new checks
covering saved-fault replay, the readiness boundary, invalid/stale data, bounded
helper stop/reap, query failure, refusal before workload, success handoff,
consumed attempts, the extra owner acceptance, readiness receipt integrity,
unchanged limits, and every spent approval refusing before Docker/status access.
All status-query and workload calls were mocked. A test for the now-consumed
compact scope uses explicit absent approval/worker fixtures; its original test
remains in the sealed historical evidence. No real RAM query ran during testing.

The saved-series audit preserves all four model-run timelines, exact crossing
readings, native log references, source accounting and planning arithmetic. The
latest model-run preservation remains SHA256
`e03c7f983f591e1c53bc1124798d6ce27778d27f74465360b6f2b828278827c0`.
All five earlier task-2 failures, their approvals, exact executed helpers and
previous model/build evidence remain unchanged. Fourteen model attempts and
all earlier approvals are consumed.

Read-only review:

```text
python -B local_worker.py review-useful-coding-task-ram
```

Execution, **only after fresh explicit approval including the new readiness condition**:

```text
python -B local_worker.py run-useful-coding-task-ram
```

The new approval, readiness, model, worker and launcher namespaces are absent
during preparation. No live workload, reset, patch application or retry is
authorized by this review. Context capacity and Hermes remain separate/deferred.
