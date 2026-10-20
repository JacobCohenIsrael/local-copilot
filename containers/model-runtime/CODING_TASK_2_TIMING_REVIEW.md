# Useful task 2: 150-second request deadline, other limits unchanged

19 October 2026. **Historical preparation review; approval consumed.**

The owner subsequently approved this exact packet. It ran once and returned a
complete API response, but the unrelated truncated code was rejected before
editing. No patch or retry. Independent shutdown and sealed evidence are in the
[execution result](CODING_TASK_2_TIMING_RESULT.md). The preparation-time statements
below describe the review before approval; they do not authorize another run.

The owner requested an offline timeout review and a fresh attempt with a longer
request deadline, while preserving failures and keeping every other limit.
This proposes **150 seconds instead of 90 seconds** for the one HTTP request
and its independent guest request-deadline check. No live workload has run during
preparation. No Docker, GPU, model, sensor or native compatibility test was run.

## Offline finding and rationale

The [preceding real result](CODING_TASK_2_RECOVERY_RESULT.md) records one API
request, `TimeoutError: timed out`, and independently confirmed shutdown of both
containers and all four host helpers. Native progress logs show 24 prompt tokens,
the first generated token at approximately 47 seconds, and token 21 at 89 seconds.
The request was still generating when its 90-second limit expired. No completed
API response/usage receipt, validated code, edit or patch was obtained.

This supports a request-time budget issue. It is not a coding-quality result or
an OOM finding: the container OOM flags were false, and the native -9 diagnostic
was recorded during the timeout shutdown path. No thermal emergency stop fired.

Using the rounded progress counters, tokens 1–21 took about 42 seconds, or
2.1 seconds per additional token. Extrapolating the same rate through the fixed
32-token allowance gives about **112 seconds** for the request. This is an
estimate, not a throughput guarantee. A 150-second deadline gives roughly
38 seconds beyond that estimate without raising output or context limits.

Historical startup from model-container start to API readiness was about
69 seconds; worker startup/preflight before the model added about 49 seconds.
Using those observations, a full 150-second request would consume about
219 model seconds and 268 worker seconds before teardown. The existing model
300-second and worker 400/410-second limits therefore have room under that
observed timing, but slow startup or proof checks can still exhaust them.

**The request does not receive an unconditional 150 seconds.** It ends at the
first request, model, worker, outer, silence, lease, cancellation or emergency
deadline. In particular, the unchanged 180-second startup ceiling plus a full
150-second request cannot both fit within the unchanged 300-second model
lifetime. That model lifetime wins; no later deadline extends it.

## The sole limit change

| Control | Proposed value |
| --- | --- |
| One request: HTTP timeout and independent request guard | **90 → 150 seconds** |
| Engine silence limit | 75 seconds, unchanged |
| Model startup ceiling / model lifetime | 180 / 300 seconds, unchanged |
| Worker subprocess / worker and outer lifetime | 400 / 410 seconds, unchanged |
| Stop allowance / freshness and host/guest leases | 5 / 2.5 seconds, unchanged |
| New attempt / model requests / OpenCode calls | 1 / 1 / at most 2, unchanged |
| Context / output reserve / runtime margin | 512 / 32 / 8 tokens, unchanged |
| Maximum actual tokenized prompt | 472 tokens, no truncation, unchanged |
| WSL | 1 CPU, 6 GiB, no swap, unchanged |
| Model | 1 CPU, 4 GiB, no extra swap, same pinned model/images/config |
| Worker | 0.5 CPU, 512 MiB, no extra swap, 64-MiB tmpfs, unchanged |
| CPU / GPU emergency stop | 97 C / 75 C, unchanged |
| GPU power / VRAM / host RAM used stop | 100 W / 14,336 MiB / 28,672 MiB, unchanged |

Ten seconds of valid startup telemetry, warning targets, source limitations,
AC/throttle/clock checks, independent watchdogs, owned stopping and latched faults
all remain. CPU-build 92/97 C policy and inactive 95/98 C history stay untouched.
There is no tuning, CPU-share change, resource change, installation, download,
build, firmware/power change, private-engine/disk action or global stop.

All file/request/output limits and isolation remain exactly as in the
[preceding review](CODING_TASK_2_RECOVERY_REVIEW.md): generated guard 128 bytes;
selected/output file 65,536 bytes; total 131,072; patch 65,536; provider request
65,536; model response 16,384; worker result 32,768; stdout/stderr 8,192/4,096.
The worker has no network/GPU/credentials/shell access, a read-only root/input/bridge,
UID 65532, 64 processes, dropped capabilities and no privilege escalation.

## Same fixed task and acceptance

Only `containers/worker/task_bundle.py` is selected (9,293 bytes), SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
Insert the model-generated negative-maximum guard before any file access in
`bounded_read`; preserve every original byte. Strata prompt is unchanged:

```
Return only Python: if maximum < 0 raise ValueError.
```

The adapter still accepts only `if maximum < 0` with `raise ValueError` or
`raise ValueError()`. It may remove a Python fence and indent/insert the generated
guard at the fixed site; it cannot manufacture a missing replacement. OpenCode
edits only the disposable staged file. No general/native model tool calling is
established. A longer deadline does not guarantee admissible code or a full reply
within the unchanged 32-token output cap.

Require actual completed response/usage, response-to-edit hash lineage,
deterministic negative-limit rejection before access, unchanged valid/oversize
read behavior, an applicable one-file returned patch and unchanged repository
original/snapshot/sentinel. Run `git apply --check` against the snapshot, **do not
apply the patch**. Preserve errors rather than substituting or repairing output.

After stopping, independently inspect both exact owned container IDs for
stopped/PID 0 and exit/OOM state, plus saved parent/watchdog/reader/wrapper PIDs
for exit. Preserve raw inputs, response/logs, readings, faults, structured result
and a SHA256 inventory. One failed operation consumes its approval; no automatic
retry, restart, fault reset, context increase or deadline expansion is allowed.

## Scoped implementation and preserved history

The shared guest runner still defaults to 90 seconds. A small scope-specific
entry point sets **150** and invokes that same runner. The model package binds
the wrapper as `container_test.py`, the shared runner as `container_test_base.py`,
and the unchanged `api_wrapper.py`. All three source hashes and the complete
input-file set are checked. There is no optional deadline file, environment
override or unreviewed value accepted by this scope.

The review metadata changes only `requestTimingChange.hardRequestDeadlineSeconds`
from 90 to 150. Its earlier engine-silence `setting/from/to` fields are inherited
unchanged; configuration still fixes silence at 75 seconds. Every inherited
policy, task, resource, timing and input invariant is checked after normalizing
only that explicitly permitted comparison field. The original packet is not
mutated. Code/package identity changes needed to enforce the deadline are frozen
in this new review.

Both failed task-2 scopes, approvals, retained containers, selected inputs and
exact executed source snapshots remain unchanged. The new proof chain binds
the complete timeout inventory in addition to the earlier failed worker dispatch
and all earlier model/build evidence. Timeout preservation SHA256 remains
`ed524dcb61a59b10da3120c35d3d119fd46a5cb3ee8ff45a8e1629e9aa1d4c29`;
earlier worker-failure preservation remains
`7a8838a0f40b4af513b2dfb03a4e6caee03797ccdf2978dfbe221eb5a8f35354`.
Eleven model attempts and all earlier approvals remain consumed.

## Concrete new review and approval boundary

- Scope: `one-fresh-useful-task-2-request-150s-all-other-limits-unchanged`.
- Review SHA256: `de616a03b071844ed67685744ebf461e865358ecc4b05709197b8225b15d01da`.
- Packet: `.runtime/strata-coding-2-timing-review/de616a03b071844ed67685744ebf461e865358ecc4b05709197b8225b15d01da/review.json`.
- New model/worker/launcher: `.runtime/strata-coding-2-timing-model`,
  `strata-coding-2-timing-worker`, `strata-coding-2-timing-launch`.
- New staging: `.runtime/strata-coding-2-timing-files`.
- Required new approval: `containers/model-runtime/coding-task-2-timing-approval.json`,
  **absent**. No model/worker/launcher namespace has been created.

**100 offline runtime/integration checks passed**, including seven new checks for
deadline wiring, timeout/no-second-request behavior, unchanged container/lease
stops, pinned guest inputs, preservation and refusal of missing/spent approvals.
Fake HTTP/process fixtures establish no real execution. Earlier worker/proposal
checks were not rerun here; no new hardware observation or inference is claimed.

Read-only:

```
python -B local_worker.py review-useful-coding-task-timing
```

Only after fresh explicit approval:

```
python -B local_worker.py run-useful-coding-task-timing
```

The prepared administrator wrapper is not executed. A future approved operation
must recheck Docker readiness, reuse the unchanged admission/shutdown guards and
retain the stopped containers. It must not reprepare this packet after approval.
Context capacity and Hermes remain separate, unapproved work.
