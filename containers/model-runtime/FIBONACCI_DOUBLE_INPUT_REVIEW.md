# Fibonacci: double input, unchanged execution and safety limits

20 October 2026. **Prepared offline; fresh owner approval required before one run.**

The previous real attempt returned a complete function, passed all six cases,
exited 0 and independently stopped the model, four main helpers and evaluator.
Its response used 123 input / 74 output tokens: 136.731 seconds for input and
141.171 seconds for generation. Complete evidence is sealed under
`.runtime/strata-fibonacci-extended-relaunch/`, preservation SHA256
`a703fe3c4eafac45adf5ff61590d67f4c637e823b55e68caa6a807872f5b28c1`.
The earlier canceled administrator launch remains separately sealed and unchanged.
Seventeen model attempts are consumed; this preparation consumes none.

## Exact next task

The pinned ASCII template/BPE audit reproduces **246 actual input tokens**,
exactly twice 123, including chat-template overhead. The 512-token input budget
stays unchanged. No padding: added text explains recurrence, count versus index,
the repeated 1, independent calls and examples already covered by the evaluator.
The function, output format and six correctness cases remain the same. There is
no new algorithm, dynamic-programming, complexity or performance requirement.

The exact prompt is `PROMPT` in [simple_function_double.py](simple_function_double.py)
and the frozen packet's `request.messages[0].content` and token audit. It asks for
`fibonacci(n)`, returning the first n Fibonacci values as a list starting 0, 1,
with function code only, optionally one Python fence. No imports, I/O, examples
or top-level calls. Static admission and the existing restricted evaluator run
only after supervised model shutdown. Cases: 0, 1, 2, 7, 10 and 20.

| Bound | Same as successful attempt |
| --- | --- |
| Context / output ceiling | 16,384 / 4,096 tokens |
| Actual input / input budget / margin | **246** / 512 / 8 tokens |
| Hard request / model lifetime / outer session | 900 / 1,200 / 1,310 seconds |
| CPU / GPU emergency stop | 97 / 75 C |
| GPU power / VRAM stop | 100 W / 14,336 MiB |
| Host used-RAM stop | 30,720 MiB (30 GiB) |
| Native engine-silence base | 75 seconds; server waiting messages do not renew it |
| Telemetry freshness / controller lease / stopping | 2.5 / 2.5 / 5 seconds |
| Startup / admission / valid telemetry | 180 / 90 / 10 seconds; targets advisory |
| WSL | One CPU, 6 GiB, no swap |
| Model container | One CPU, 4 GiB, no extra swap |
| CPU / GPU sample caps; heartbeat byte bound | 1,500 / 1,536; 4,096 bytes |
| API response / admitted code | 262,144 / 32,768 bytes |
| Evaluator | One process, one CPU, 128 MiB, two seconds |

All model files/configuration, guest scripts, worker count, cache, prefill,
speculation, reasoning, resource envelopes, source limitations, isolation,
read-only mounts, journals, logs, watchdogs and latched faults stay unchanged.
The request's input text and expected input count are the only experiment changes.
There is one API request, no coding worker, no repository edit, no patch application,
no added readiness gate, no retry or fault reset. Progress cannot renew deadlines.
All 4K output tokens need not be consumed; completion within the fixed deadline
is not guaranteed. This is not a full-window capacity or native tool-calling test.

## Offline verification and new scope

**152 offline runtime/integration checks passed.** Drift checks reject changed
CPU/RAM/deadlines/output/configuration, monitor coverage and old token counts.
Approval/watch/CLI checks use mocks and refuse every spent decision before live
access. The known-function restricted-process fixture is separate from inference.
The initial suite's one test-fixture path error and corrected final log are both
retained. No container, model, GPU workload or sensor reader started in preparation.

Scope: `one-fibonacci-246-input-16k-context-4k-output-900s-request-1200s-model`.

Review SHA256: 86755db0f8e6477bfe036a7847be3eca2a49cec831fa9ab3079632e8101d0f06.

Fresh namespaces: `.runtime/strata-fibonacci-double-model`,
`strata-fibonacci-double-operation`, `strata-fibonacci-double-launch`.
Fresh decision: `containers/model-runtime/simple-function-double-approval.json`.
They remain absent; model/worker launch flags are false. Preserve all previous
operations, approvals, failed attempts, frozen helpers and unrun proposals.

After approval, run once; preserve the raw response, admitted code, correctness
result, raw telemetry, logs and failures. Independently inspect the exact owned
model container, four main host helper PIDs and any evaluator PID/exit receipt.
Keep the stopped container. Do not apply the returned code or retry.

Read-only review: `python -B local_worker.py review-double-input-fibonacci-test`.
Run only after approval: `python -B local_worker.py run-double-input-fibonacci-test`.

## Speed review: separate future experiments

The owner reports about **12 output tokens/s natively**, versus this Docker
attempt's 0.5 tokens/s. The exact native workload and its historical settings
are not yet established, so that is a useful target, not an apples-to-apples
measurement or a promised Docker speed.

Reading `D:/AI/strata-coder-iq1_m.json` confirms the same named Coder model and
pack/GGUF paths. Its current settings differ materially:

| Setting | Executed Docker attempt | Current native config |
| --- | --- | --- |
| Expert cache | Fixed budget 64; 82 slots / **0.16 GiB**, **13%** decode hit rate | `auto` |
| Prompt batching | `--prefill 32` | `--prefill auto` |
| CPU workers / CPU access | One worker plus host sharing a one-CPU VM/quota | No explicit worker count in config; actual native concurrency unverified |
| Speculation | Window 2, no MTP; zero draft tokens | Window 4, MTP configured, minimum probability 0.70 |
| Expert storage | Memory-mapped files, container 4 GiB / VM 6 GiB | `--resident-experts` |
| Context | 16K | 64K |

The saved Docker log reports 80,759.3 MB of logical expert reads and 1,888.8 MB
of actual storage reads for that request. Those are different quantities; neither
means all logical reads hit the SSD. The log also reports 10,065 MiB VRAM free at
engine readiness. The small cache is a deliberate test setting, not evidence
that this GPU lacks memory. Host/device free-memory accounting differs.

Recommended order after this unchanged input test:

1. Compare a larger **bounded expert cache**, retaining the 4-GiB VRAM reserve,
   14-GiB VRAM stop and every thermal/RAM stop. Higher residency may remove much
   CPU/file traffic; measure hit rate and both input/output throughput.
2. Compare prompt batching separately. Match native automatic prefill only after
   checking its memory and native-progress behavior against existing silence
   stops. Do not silently change timeouts to hide stalled progress.
3. Review a separate CPU-resource scope if needed. More CPU access could help
   remaining misses, but changes both WSL/container envelopes and requires new
   approval. The observed CPU peak was 96 C against the 97 C stop; keep that stop.
4. Evaluate native-style MTP/residency only after the simpler comparisons; they
   add memory/assets or alter runtime behavior. No tuning setting is activated here.

These are hypotheses supported by saved evidence and current native configuration,
not measured speedups. Docker overhead has not been isolated. Returning shorter
answers reduces total time but does not raise measured generation throughput.

The [Strata technical documentation](https://github.com/Niko1221/Strata/blob/main/docs/DETAILS.md)
describes cache sizing, prompt batching and CPU worker tuning. Its current version
is newer than the executed engine 0.1.44.1; the pinned local source was also read.
[Docker's CPU documentation](https://docs.docker.com/engine/containers/resource_constraints/#cpu)
confirms that the one-CPU quota caps CPU access. No native files were modified
or executed; no new profiling, tuning, model or hardware run occurred.
