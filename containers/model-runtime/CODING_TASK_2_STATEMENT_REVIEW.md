# Useful task 2: corrected single-statement request

19 October 2026. **Historical preparation review; approval consumed.**

The owner subsequently approved this exact packet. It ran once, returned HTTP
503 after the engine-silence guard fired, and produced no patch. Both containers
and all four host helpers were independently confirmed stopped/exited. See the
[execution result](CODING_TASK_2_STATEMENT_RESULT.md). Preparation-time statements
below describe the review before approval and do not authorize another run.

The preceding [150-second attempt](CODING_TASK_2_TIMING_RESULT.md) completed its
API response but failed the useful task. This successor keeps the same selected
file, task, acceptance criteria, model and all safety/resource/time/output limits.
It changes the short model prompt and tightens response admission. It does not
repair or apply the previous answer.

## Offline diagnosis: established facts and remaining uncertainty

The saved request contains exactly one user message:

```text
Return only Python: if maximum < 0 raise ValueError.
```

The broker intentionally supplied this short request instead of OpenCode's full
task/file context. It did not send the selected function or its signature to the
model. The preserved request, package, API receipt and native counters agree:
24 prompt tokens, 32 output tokens, `finish_reason: length`. Generation took
about 106 seconds, inside the approved 150-second deadline. Neither the request
deadline nor an emergency stop truncated this answer.

The model generated an unrelated `def max_value(values)` function, then reached
the **32-token output cap**, ending after `maximum = values[0]` and indentation.
Its opening Markdown fence had no closing fence. The adapter therefore raised
`CODE_FENCE_INVALID` before publishing an edit. Missing syntax was a symptom;
adding a closing fence would still leave the wrong code. No bytes were lost
through retained-log truncation: saved log metadata reports `truncated: false`.

Offline template/BPE replay, using the pinned tokenizer metadata and frontend,
reproduced the previous 24 prompt tokens and 32 answer tokens with exact text
round trips. The rendered request is one user turn, followed by the normal
assistant prefix and disabled-thinking markers. The unrelated function text is
absent from the inspected API server, frontend and model chat-template sources.
The fresh engine had prompt/conversation caching disabled. These checks show no
evidence of broker substitution or a stale conversation; they cannot prove the
cause of the model's choice or validate model internals/weights.

**Why it selected that function remains unproven.** A terse, underspecified
prompt and imperfect model instruction following are plausible contributors.
This one response cannot distinguish prompt sensitivity, quantization/model
quality or another inference issue. No model tuning, template change, engine
change or compatibility claim is justified by this offline review.

## Corrected request and stricter response admission

The new exact user message is:

```text
Python only, one line, no function or markdown. Validate integer maximum: raise ValueError when it is negative.
```

It identifies `maximum` as an integer and requests one validation statement,
explicitly excluding a surrounding function and Markdown. It supplies no
prewritten guard to echo. All other request fields are unchanged:
`max_tokens: 32`, `temperature: 0`, `stream: false`, `reasoning_effort: none`,
same model identifier. No system/tool messages, examples, stop strings or
additional model calls are added.

The corrected scoped host and guest both require `finish_reason: stop` before
using any code. Even a valid-looking guard with `finish_reason: length` is
rejected as `MODEL_OUTPUT_INCOMPLETE`. The answer must be one line without
backticks. Existing AST validation still admits only `if maximum < 0` raising
`ValueError` or `ValueError()`, with no extra body statements or else branch,
within the existing 128-byte guard limit. No incomplete fence, prose, function
or missing statement is repaired or fabricated.

The shared adapter still inserts the model-supplied guard at the fixed site,
preserving all existing bytes. OpenCode edits only the disposable staged file;
response/edit hashes must agree. Native/general tool calling remains unproven.
The small shared preparation change uses an explicit helper map: previous
scopes retain their original helpers, and this scope stages the strict probe
plus its unchanged shared AST/acceptance helper. All helper hashes are frozen.

## Offline capacity and timing check

The corrected request renders to **34 prompt tokens**. With 32 output tokens
and the unchanged 8-token runtime margin, it uses 74 of the configured 512
tokens, leaving 438. A representative valid guard requires **8 output tokens**;
this is an offline acceptance example, not model output and not a supplied answer
in the live request. A larger output cap is unnecessary for the intended result.

The audit imports only pure text/template code and small tokenizer metadata.
It uses an explicitly ASCII-only equivalent character-class reduction because
the Windows interpreter lacks the staged Linux regex extension. It checks ASCII
inputs and exact round trips, and reproduces both previous recorded counts.
It is not a full Unicode tokenizer-compatibility test or model execution.

Using the preceding measured prompt/generation rates, 34 prompt tokens plus
the full 32-token allowance estimates **125.37 seconds**. That is an estimate,
not a guarantee. Startup, CPU contention and inference behavior may differ.
The absolute 150-second request deadline and every earlier outer/emergency
guard still win when reached; progress does not extend them.

## Unchanged task and safety envelope

Only `containers/worker/task_bundle.py` is selected: 9,293 bytes, SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
Insert the negative-maximum guard at the start of `bounded_read`, before file
access. Negative -1/-2/-65536 must fail before any access; valid reads and
oversize rejection must remain unchanged. Preserve the original and sentinel.

| Control | Proposed value, unchanged from latest approved run |
| --- | --- |
| Attempt / API requests / OpenCode calls | 1 / 1 / at most 2 |
| Request / model startup / model lifetime | 150 / 180 / 300 seconds |
| Worker subprocess / worker and outer lifetime | 400 / 410 seconds |
| Engine silence base / stop allowance / freshness and leases | 75 / 5 / 2.5 seconds |
| Context / output / runtime margin | 512 / 32 / 8 tokens |
| WSL | 1 CPU, 6 GiB, no swap |
| Model container | 1 CPU, 4 GiB, no extra swap, same image/model/configuration |
| Worker | 0.5 CPU, 512 MiB, no extra swap, 64-MiB tmpfs, no network/GPU |
| CPU / GPU emergency stops | 97 C / 75 C |
| GPU power / VRAM / host used RAM stops | 100 W / 14,336 MiB / 28,672 MiB |

Every file/request/result/stdout/stderr bound remains as in the
[150-second review](CODING_TASK_2_TIMING_REVIEW.md), including guard 128 bytes,
file/patch 65,536 bytes and model response 16,384 bytes. Ten seconds of valid
startup telemetry and advisory startup targets, source limitations, AC/throttle
checks, independent watchdogs, owned stopping, latched faults, read-only mounts,
UID/capability restrictions and no automatic restart/retry remain enforced.
GPU memory reserve remains 4,096 MiB; it does not reserve GPU processing time.
CPU-build 92/97 C and inactive 95/98 C history remain unchanged.

After a separately approved run, preserve any returned patch and structured
result, check applicability without applying it, and independently inspect both
exact container IDs and all four saved host PIDs. Retain stopped containers and
all faults. No global Docker/WSL stop, private-engine/bare-disk action, install,
download, build, tuning, firmware or power change is part of this scope.

## Validation and approval boundary

The prepared scope is
`one-fresh-useful-task-2-single-statement-150s-same-safety-limits`.
Review SHA256:
`268602b8691a2d036f2c239f955eb1aa2a056b2fe24b5ab64936d27c8be0caad`.
The packet and frozen helpers are under
`.runtime/strata-coding-2-statement-review/268602b8691a2d036f2c239f955eb1aa2a056b2fe24b5ab64936d27c8be0caad/`.
That directory also preserves the offline audit, validation receipts, unexecuted
administrator wrapper and post-exit capture helper. The wrapper's syntax was
checked without executing it. After any future approval, recheck Docker readiness
and dispatch once; do not reprepare the packet or reuse a spent decision.

Fresh model/worker/launcher namespaces are `.runtime/strata-coding-2-statement-model`,
`strata-coding-2-statement-worker` and `strata-coding-2-statement-launch`.
Selected-file staging is `.runtime/strata-coding-2-statement-files`.
The required new decision, `containers/model-runtime/coding-task-2-statement-approval.json`,
is absent. An offline review call reports `MODEL_API_READY_FOR_APPROVAL` with
both launch flags false. A missing approval fails before Docker access.

All **107 offline runtime/integration checks passed**: 106 in the workspace-temp
suite, plus its one sandbox-blocked hardlink test passed separately with the
needed filesystem access. The original sandbox-default-temp run was denied
temporary-file access; the workspace run and isolated hardlink receipt preserve
those validation outcomes. Seven new checks cover the actual rejected response,
completed-generation requirement, narrow AST/byte preservation, complete prior
evidence inventory, unchanged limits and missing/spent approval rejection before
Docker. These are offline checks, not proof of a real corrected answer.

The previous twelve model attempts, worker-only failure, spent approvals and
sealed evidence remain unchanged. New execution needs a fresh decision for this
exact packet. No corrected model/worker/launcher namespace or approval file is
created during preparation. No live workload or hardware query is authorized
by this document. One approval permits one attempt; no retry or patch application.

Read-only review:

```text
python -B local_worker.py review-useful-coding-task-statement
```

Execution entry point, **only after explicit fresh approval**:

```text
python -B local_worker.py run-useful-coding-task-statement
```
