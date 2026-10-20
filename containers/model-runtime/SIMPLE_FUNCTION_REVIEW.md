# First simple-function test: Fibonacci, 16K context and up to 4K output

**Executed once; approval consumed.** See the [timeout result](SIMPLE_FUNCTION_TIMEOUT_RESULT.md).
The 150-second deadline ended the request during prompt reading, with no generated
function. Independent shutdown is confirmed. Do not rerun this scope; its frozen
review and execution evidence remain unchanged. The owner requested a separate
[longer-duration proposal](FIBONACCI_EXTENDED_REVIEW.md).

20 October 2026. **Prepared offline; fresh approval required before one live run.**

The owner chose a simple function first, then increasing input and requirements
based on observed results. This uses Fibonacci as the first concrete task, with
no dynamic-programming or performance requirement. Useful task 2 remains preserved
and unfinished; this experiment does not pretend to complete it.

## Exact first request

> Write a Python function fibonacci(n) that returns a list of the first n Fibonacci numbers, starting with 0, 1. Assume n is a non-negative integer. For n=0 return []; for n=1 return [0]; for n=7 return [0, 1, 1, 2, 3, 5, 8]. Return only the function code, optionally in one Python code fence. Use standard Python without imports, I/O, examples, or top-level calls. Do not add other requirements or explanations.

The exact pinned template/BPE audit counts **123 input tokens**, including the
template. The initial input budget is 512; the prompt is not padded. The model
may generate up to **4,096 tokens** and may stop much earlier. With eight-token
slack, the current reservation uses 4,227 of the **16,384-token context**.

This is one direct Strata API request. No OpenCode edit worker, repository edit,
patch application, tool-calling test or automatic follow-up is included. Preserve
the raw response and any admitted function as artifacts. The model-facing task
and the acceptance checks agree on the function name, signature and sequence.

## Acceptance and code handling

Require natural `finish_reason: stop`. Accept either plain Python or one complete
Python code fence, with exactly one top-level `fibonacci(n)` function. Multiple
algorithms are supported; no dynamic-programming style is imposed. Static
admission allows a documented subset of ordinary Python syntax, arithmetic,
lists, branches, loops and local helper functions. It rejects imports, top-level
execution, decorators, access to double-underscore names, arbitrary calls and
attributes other than list append/extend. Syntax or admission refusal is recorded
separately from an incorrect function result; the answer remains preserved.

Only after the supervised model has stopped, run the admitted function in the
existing Windows kill-on-close job: **one CPU, one process, 128 MiB, two seconds**.
The child runs a fixed isolated Python evaluator with restricted builtins. Check
inputs 0, 1, 2, 7, 10 and 20 against exact lists, including integer element types.
It receives no repository or model file handles. No arbitrary model-generated
code runs in the supervisor process. A timeout kills the owned job and records
exit evidence; it does not retry. Unsupported syntax may refuse an otherwise
correct implementation and will be reported as admission failure, not a capacity
or model-quality conclusion.

This is a function-correctness probe, not proof of full 512-token input use,
16K recall, sustained 4K generation, general coding/tool calling or Hermes.

## Explicit bounds

| Setting | Value |
| --- | --- |
| Configured context / actual input / input ceiling | 16,384 / 123 / 512 tokens |
| Output ceiling / context slack | 4,096 / 8 tokens |
| API response/result transport | 262,144 bytes, up from the historical 16,384-byte transport bound |
| Admitted function code | 32,768 bytes |
| Inference requests / worker containers | One / zero |
| Request / native silence base | 150 s / 75 s, unchanged |
| Model startup / lifetime / outer operation | 180 s / 300 s / 410 s, unchanged |
| CPU / GPU emergency stops | 97 C / 75 C, unchanged |
| GPU power / VRAM emergency stops | 100 W / 14,336 MiB, unchanged |
| Host used-RAM stop | 30,720 MiB; no added readiness gate |
| WSL | One CPU / 6 GiB / no swap |
| Model container | One CPU / 4 GiB / no extra swap |
| Startup monitoring / telemetry freshness / lease | 10 s valid telemetry / 2.5 s / 2.5 s |
| Owned model stop | 5 s |
| Post-model evaluator | One CPU / 128 MiB / one process / 2 s |

The larger response-byte allowance supports the requested token ceiling. It does
not enlarge the 16-KiB immutable state journal or allow arbitrary files. Both
guest and host paths use the new bounded response allowance; historical defaults
remain unchanged. Startup targets stay advisory, with warnings saved. Existing
model/configuration, isolation, fault latches and settings remain bound to the
last executed review except the explicit task, context/output and response-size
changes. No installation, optimization, model substitution, global Docker/WSL
action, private-disk action or fault reset is part of the test.

The output ceiling is not a promised amount of generation. At the previous
short-request decode rate, generating all 4K tokens alone would take about two
hours. This first trial retains the finite 150-second request and 300-second
model limits. It may time out before returning a complete function; that would
be a timing result. Long-prompt throughput is unmeasured. No live time budget
has been extended, and a timeout or wrong answer is not a capacity boundary.

## Frozen operation and evidence

Scope: `one-simple-fibonacci-function-16k-context-4k-output-512-input-budget`.

Review SHA256: `7d4942f8f036a09979bc014f956edc8528c1f1c43cf44e9f299b826c5953546d`.

Frozen packet: `.runtime/strata-simple-function-review/7d4942f8f036a09979bc014f956edc8528c1f1c43cf44e9f299b826c5953546d/`.

Fresh namespaces: `.runtime/strata-simple-function-model`,
`strata-simple-function-operation`, `strata-simple-function-launch`.
Decision file: `containers/model-runtime/simple-function-approval.json`.
All remain absent, with model and worker launch flags false. The approval must
bind this exact review and policy, with worker launch disabled. No prior decision
is reused. The durable operation claim prevents reuse even if preflight fails
before a model attempt is claimed.

After approval, run once and retain raw response, admitted code, correctness
result, readings and errors. Independently inspect the exact owned model
container and the parent/watchdog/reader/administrator-wrapper processes after
exit. If an evaluator ran, also retain its owned-handle exit receipt and inspect
its saved PID. Keep stopped containers and faults; do not apply code or retry.

The last executed preservation manifest remains
`ee0da137ccc41fa58afa3a7734c79741d4d9e1631bd92d97739939d037136da2`.
The superseded 64-output proposal remains unrun, with preservation SHA256
`257531f96c6e818254e5abf35f7f3e81119944bd408dd5f2eb4940cfefc89688`.
The full earlier failure chain and unrun readiness proposal remain preserved.
Fifteen model attempts are consumed; this preparation consumes none.

**140 offline runtime/integration checks passed**, including the new token/byte
bounds, unsafe/incomplete code rejection, algorithm-independent correctness,
evaluation-timeout cleanup, missing/spent approvals and policy-drift checks. A
known Fibonacci fixture passed in the real restricted Windows job; no model,
container, GPU, sensor or hardware telemetry was started by these checks.

The frozen packet contains helpers/tests, the token audit, passing validation
records, an unexecuted administrator wrapper and post-exit capture script. The
manual Docker-chat feature is being built separately and is not executed here.

Review: `python -B local_worker.py review-simple-function-test`.
Run after fresh approval: `python -B local_worker.py run-simple-function-test`.
