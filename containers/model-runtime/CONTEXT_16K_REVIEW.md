# Direct 16K start: one coding probe with 64 response tokens

**Superseded before approval or execution, 20 October 2026.** The owner selected
16K context with up to **4K output**, an initial **roughly 512-token input budget**,
and a simple function task with requirements added progressively. Fibonacci was
an example, not a fixed task specification. Do not pad short requests to 512.
The 64-output packet below remains preserved and unrun; it is not the current
proposal. A new runnable scope, task acceptance and timing review are still needed.

20 October 2026. **Prepared offline; fresh run approval required.**

The owner's direction is to move directly near the 64K goal and use doubling/
halving, rather than visit every smaller size. This proposal interprets **16K
as a 16,384-token context window**, and doubles the previous **32-token response
cap to 64**. These are separate settings. It does not request 16K output tokens.

## What the first attempt will test

Start the same Strata model with `--max-context 16384`, then send the same useful
task-2 guard request with `max_tokens: 64`. The prompt remains exactly:
`Python guard only: reject negative integer maximum with ValueError.`
Keeping it unchanged makes the response-cap experiment comparable to the last
run. Its formatting weakness remains known; more output may still be rejected.

Use the existing OpenCode adapter, selected-file staging, strict response/AST
admission and returned-patch boundary. Only staged `task_bundle.py` may change,
and only by the accepted guard for negative `maximum`. The guard remains limited
to 128 bytes. A length-ended answer, function or Markdown is still rejected.
No patch is applied to the repository.

The exact pinned template/BPE audit reproduces **23 input tokens**; input plus
64 output plus eight-token margin is **95 tokens**. The full file and OpenCode
tool prompt are not sent to Strata. Thus this first run tests **16K allocation
and a small coding request**, and can also finish useful task 2 if a correct
answer arrives. Even a returned patch does **not** establish usable 16K input
capacity, full-window recall, native tool calling or Hermes compatibility.
That limitation is bound in the review packet, not left to interpretation.

## Offline support and bounds

The selected model's GGUF header declares `qwen4exp.context_length: 262144`.
16K is within that declared range. The bounded reader read 11,024,416 header
bytes and no tensor payload; no engine or GPU ran. This metadata is not proof
that the laptop can execute a 16K workload.

The pinned session code allocates context-dependent state from the requested
maximum. Ordinary INT8 KV codes/scales for the 12 attention layers are about
198 MiB at 16K versus 6.19 MiB at 512. This arithmetic excludes recurrent state,
indexer, scratch, graphs, weights, driver and other allocations; it is not a
total-memory estimate or a fit guarantee. No cache, quantization, prefill,
parallelism, installation or model change is proposed.

| Setting | Proposed value |
| --- | --- |
| Configured context | **16,384**, from 512 |
| Response cap | **64**, from 32 |
| Actual request / maximum calls | 23 prompt tokens / one inference request |
| Request deadline / engine silence | 150 s / 75 s, unchanged |
| Model startup / lifetime / outer operation | 180 s / 300 s / 410 s, unchanged |
| CPU / GPU emergency stops | 97 C / 75 C, unchanged |
| GPU power / VRAM stops | 100 W / 14,336 MiB, unchanged |
| Host RAM stop | 30,720 MiB used; no added readiness gate |
| WSL | One CPU / 6 GiB / no swap |
| Model container | One CPU / 4 GiB / no extra swap |
| Worker | Half CPU / 512 MiB / no extra swap; no GPU/network |
| Valid startup telemetry / freshness / lease | 10 s / 2.5 s / 2.5 s |
| Owned stop | 5 s; retain stopped containers and latched faults |

Startup targets remain advisory and warnings are saved. Both independent host
and guest validation paths admit up to 64 output tokens, reserve the context
margin and reject overflow. Historical profiles keep their earlier bounds.
All other policy/configuration/input invariants are compared against the last
executed RAM30 review. The independent watchdog activates this exact profile.

At the last measured prompt/decode rates, consuming all 64 output tokens would
take roughly **150.94 seconds**, close to the unchanged 150-second request
deadline. That is an estimate from a short request, not a throughput forecast
for long prompts. A correct guard could stop much earlier. A timeout will be
recorded as a timing failure, not evidence that 16K cannot fit. Deadlines,
lifetimes, sample budgets and resources are not silently extended.

## How to move around 16K

After this separately approved result and confirmed shutdown:

- If 16K allocation works, consider 32K, then 64K; skip smaller checkpoints.
- If allocation fails from capacity, consider 8K; if 8K passes, refine between
  8K and 16K, such as 12K. Keep task-quality or timeout failures out of that bracket.
- If output ends as length at 64, review 128 output tokens at the same context,
  together with its timing budget. Do not mistake more output for more context.
- To establish actual 16K capacity, prepare a near-window input (up to **16,312
  prompt tokens** with 64 output and eight margin), with verifiable content
  throughout the input and a separately reviewed finite time budget. A 23-token
  request cannot establish that. The same applies to the eventual 65,536 gate.

This is result-driven selection, not an authorized batch, automatic retry or
fault reset. Completion quality need not vary monotonically with context size.

## Frozen review and execution boundary

Scope: `one-16k-context-allocation-task-2-64-output-no-readiness`.

Review SHA256: `534020a6c8d4c56480a71a610da3579828a8cfce12a2e5884dff2b9f2a98ec93`.

Frozen packet: `.runtime/strata-context-16k-review/534020a6c8d4c56480a71a610da3579828a8cfce12a2e5884dff2b9f2a98ec93/`.

Fresh execution namespaces: `.runtime/strata-context-16k-model`,
`strata-context-16k-worker`, `strata-context-16k-launch`. Required decision:
`containers/model-runtime/context-16k-approval.json`. They remain absent; both
launch flags are false. No previous approval is reused. Fifteen model attempts
remain consumed; this preparation adds none.

The frozen review contains exact helpers/tests, metadata/token audit, validation
records, an unexecuted administrator launch wrapper and post-exit capture helper.
Run once only after fresh approval; preserve any patch, response and readings,
and independently inspect both exact owned containers and all four host helper
PIDs after exit. Check patch applicability without applying it. Preserve every
failure, the previous output audit and the deferred readiness preparation.

**133 offline runtime/integration checks passed.** The first full run exposed
an old RAM30 test assuming its approval was absent; the fixture now explicitly
uses missing paths while preserving the consumed live decision. The failed log
and final pass are retained. No real model/container/sensor/hardware query ran.

Review: `python -B local_worker.py review-context-16k-coding-probe`.
Run, after fresh approval: `python -B local_worker.py run-context-16k-coding-probe`.
