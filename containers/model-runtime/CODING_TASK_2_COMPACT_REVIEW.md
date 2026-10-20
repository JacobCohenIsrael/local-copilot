# Task 2: shorter guard request, unchanged silence and safety limits

19 October 2026. **Historical preparation review; approval consumed.**

The owner subsequently approved this exact packet. It ran once and hit the
unchanged host RAM emergency stop before a completed API result. No patch or
retry. Both containers and all four host helpers were independently confirmed
stopped/exited; see the [execution result](CODING_TASK_2_COMPACT_RESULT.md).
Preparation-time statements below describe the review before approval and do
not authorize another attempt.

The [preceding attempt](CODING_TASK_2_STATEMENT_RESULT.md) returned HTTP 503 after
the unchanged engine-silence guard fired. This review explains the observed
messages and prepares a smaller request. It changes only the model prompt;
the strict single-statement adapter, task, engine/configuration and all safety,
resource, timing, context, output, file and attempt limits remain unchanged.

## Why the progress messages did not count

Two different sources of messages were involved:

| Message or signal | Meaning | Refreshes engine-silence clock? |
| --- | --- | --- |
| `reading the prompt: 34 tokens, 72 s so far` | API server is still waiting; 34 is the total input count, not a position reached | No |
| Native `PP position total elapsed rate` | Engine reports completion of a prompt segment/chunk | Yes |
| Native `T token-id`, `RESUME`, or another engine stdout line | Real engine control/output received by the server | Yes |
| HTTP/SSE keepalive or host/guest lease pulse | Connection/controller remains alive | No; separate checks apply |

In pinned `serve/server.py`, `StrataEngine.generate` waits on the engine's
stdout queue. A queue timeout can yield a `None` heartbeat every ten seconds
(lines 1893–1907). The service responds by calling `_progress`, printing elapsed
time and yielding a ping (4228–4233). Before any native prompt-progress position
arrives, `_progress` prints the request's total token count (4044–4055).
It can keep printing the same total while no native work is reported complete.

The independent activity timestamp `heard` is refreshed only when the queue
returns an engine line (1912), not when the server emits a heartbeat or prints
status. A `PP` line also updates the actual position/rate (1921–1930). Therefore
the repeated 34-token messages were evidence of a live waiting server, rather
than evidence that native inference had advanced. Counting those messages as
native progress would allow a waiting server to hide a silent engine indefinitely.

The configured silence base is **75 seconds**. The pinned upstream adds its
existing first-prompt allowance, `min(prompt_tokens, 32768) / 50`. For 34 tokens
this is **75.68 seconds**, consistent with the log's rounded 76-second failure.
Existing adaptive allowances after genuine `PP` output also remain unchanged.
The separate **150-second completed-response deadline** did not cause this fault
and is never renewed by progress, pings or leases.

## Why native progress can arrive late

Pinned `src/program/generate.cpp` defaults `short_read` to 64 tokens (663).
The request's first `n - 1` tokens can be read using the small verify windows
(11225–11232, 11763–11783). Inside `read_windows`, internal `pp_reached` advances
after each window, but the stdout `PP` line is printed and flushed only after
the whole selected segment and its pending commit complete (11349–11406).

With caches disabled and no image, both the 34-token request and the proposed
23-token request fit this short-read path. Their first segments are 33 and 22
tokens respectively. There is no evidence that crossing the configured
32-token prefill size selected a different path in this failure.

The failed request showed no reported prompt-position advance or generated
token before the guard fired. This does **not** establish whether the native
engine was stuck, computing slowly, blocked on CPU/disk or delayed elsewhere.
The logs do not expose completion of every internal window. No model response
was returned, so this failure also says nothing about the revised prompt's
coding fidelity. OOMKilled was false and no recorded emergency stop fired.

## Correction within the existing limits

The exact proposed user message is:

```text
Python guard only: reject negative integer maximum with ValueError.
```

Offline rendering/tokenization gives **23 prompt tokens**, down from 34 and
slightly below the 24-token request that previously completed its API response.
It retains the explicit integer variable, negative-value rejection and exception
type while removing extra prose. It does not supply a prewritten answer or ask
for a surrounding function. The unchanged adapter still rejects functions,
fences, multiple lines, wrong ASTs, and `finish_reason: length`; it accepts only
a completed one-line `if maximum < 0` raising `ValueError` or `ValueError()`.
No missing code, fence or statement is repaired or manufactured.

This reduces the prompt segment that must finish before the first `PP` message
from 33 to 22 tokens. It does not weaken or bypass the silence guard. Using the
preceding completed 24-token request's timing gives about **44.12 seconds to
first native progress**, and **104.23 seconds for the full 32-token output
allowance**. These extrapolations are not guarantees. The preceding silent run
had slower startup and less free host RAM than the completed run. Reducing input
cannot prove that the engine will make progress or produce correct code.

Context accounting is 23 input + 32 output + 8 runtime margin = **63 of 512**,
leaving 449 tokens. A representative valid guard requires eight output tokens;
it is only an offline acceptance example and is not sent as an answer to echo.
No output/context expansion or extra request is proposed.

## Exact unchanged task and safety envelope

Only `containers/worker/task_bundle.py` is selected: 9,293 bytes, SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
Insert the model-supplied guard at the start of `bounded_read`, before file
access; preserve every original byte, the disposable original and the sentinel.
The same deterministic acceptance checks reject negative -1/-2/-65536 before
access and preserve valid reads and oversize rejection. OpenCode edits only the
disposable staged file; response/edit hash lineage is mandatory.

| Control | Proposed value, unchanged |
| --- | --- |
| Attempts / model requests / OpenCode calls | 1 / 1 / at most 2 |
| Request / model startup / model lifetime | 150 / 180 / 300 seconds |
| Worker subprocess / worker and outer lifetime | 400 / 410 seconds |
| Engine silence base / stop allowance / freshness and leases | 75 / 5 / 2.5 seconds |
| Context / output / runtime margin | 512 / 32 / 8 tokens |
| WSL | 1 CPU, 6 GiB, no swap |
| Model container | 1 CPU, 4 GiB, no extra swap, same pinned image/model/config |
| Worker | 0.5 CPU, 512 MiB, no extra swap, 64-MiB tmpfs, no network/GPU |
| CPU / GPU emergency stops | 97 C / 75 C |
| GPU power / VRAM / host used RAM stops | 100 W / 14,336 MiB / 28,672 MiB |

The existing file/request/result/stdout/stderr budgets remain, including guard
128 bytes, selected/output file and patch 65,536 bytes, and API response 16,384
bytes. Read-only mounts, UID/capability restrictions, ten seconds of valid
startup telemetry, advisory targets, accepted sensor-source limitations,
AC/throttle checks, independent watchdogs, owned stopping and latched faults
remain enforced. Earliest request/outer/emergency deadline wins.

All model arguments stay fixed, including prefill 32, spec 2, one pool worker,
disabled prompt/conversation caching and 4,096-MiB VRAM reserve. No engine/source
patch, build, image change, CPU-share adjustment, tuning, installation, download,
sensor query, firmware/power change, private-engine/disk action or global
Docker/WSL stop is part of this offline preparation. CPU-build 92/97 C and the
inactive 95/98 C proposal are preserved.

After fresh approval, execute once; preserve any returned patch and evidence,
check applicability without applying it, and independently inspect both exact
container IDs plus the parent/watchdog/reader/wrapper PIDs. Retain stopped
containers and faults. There is no automatic retry, restart or fault reset.

## Offline validation and preservation

Scope: `one-fresh-useful-task-2-compact-guard-same-safety-limits`.
Review SHA256:
`9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a`.
The packet, frozen helpers/tests, source excerpts, audit and validation records,
unexecuted administrator wrapper and post-exit capture helper are under
`.runtime/strata-coding-2-compact-review/9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a/`.
Wrapper syntax was checked without executing it. Do not reprepare this packet
after approval; recheck Docker readiness and dispatch once.

Fresh model/worker/launcher namespaces are `.runtime/strata-coding-2-compact-model`,
`strata-coding-2-compact-worker` and `strata-coding-2-compact-launch`; all are absent.
Selected-file staging is `.runtime/strata-coding-2-compact-files`.
Required new approval `containers/model-runtime/coding-task-2-compact-approval.json`
is absent. Read-only review reports `MODEL_API_READY_FOR_APPROVAL` with both
launch flags false; old approvals cannot authorize this scope.

**112 offline runtime/integration checks passed**, including five new checks.
Two execute only the pinned Python silence/progress methods with fake time,
queues and pipes: waiting messages reproduce the rounded 76-second fault, while
an actual `PP` line refreshes activity and changes the displayed position.
Other new checks bind the complete latest failed inventory, reject safety/input
drift and refuse missing or every spent approval before Docker access.

The first suite run exposed an older test's assumption that the now-consumed
statement scope was unused. Its fixture now supplies explicit absent approval
and worker paths to exercise that gate independently. The original test remains
in the sealed historical review; the failed validation log and final passing
suite are both preserved. This changed no production gate or historical attempt.

The template/BPE audit uses small pinned metadata and pure text code with the
same explicit ASCII-only character-class reduction as the previous review.
It reproduces earlier 24/32 token counts, the failed request's 34 input tokens,
the new 23 input tokens and exact round trips. It is not a full Unicode or live
engine-compatibility test. Native source excerpts, audit and test receipts are
preserved with the review. No real model, Docker workload, GPU or sensor was
started during preparation.

The latest failed inventory remains SHA256
`2d5084feb8d468cca11d011631b50b9b363c748ec4b96e1be97d60bf38e8cf74`.
All four failed task-2 scopes, their approvals, previous model/build evidence,
settings, model/source identities and exact executed helpers remain unchanged.
Thirteen model attempts and all previous approvals remain consumed.

Read-only review:

```text
python -B local_worker.py review-useful-coding-task-compact
```

Execution, **only after fresh explicit approval for the frozen packet**:

```text
python -B local_worker.py run-useful-coding-task-compact
```

No new approval, model/worker/launcher namespace or workload is created during
preparation. Context capacity and Hermes remain separate and deferred.
