# Fresh Fibonacci attempt: 15-minute request, 20-minute model lifetime

20 October 2026. **Prepared offline; ask the owner before running once.**

The [failed attempt](SIMPLE_FUNCTION_TIMEOUT_RESULT.md) used all 150 seconds
while still reading the 123-token prompt. The saved 32-token progress steps took
about 41 seconds each, suggesting roughly 158 seconds for the input alone.
That extrapolation is not a guarantee, but it explains why the old cutoff could
prevent generation. The owner requested more time with the safety limits kept.

## Requested timing change

| Bound | Failed attempt | Fresh proposal |
| --- | ---: | ---: |
| Hard request deadline | 150 s | **900 s (15 minutes)** |
| Hard model lifetime, measured from host start grant | 300 s | **1,200 s (20 minutes)** |
| Host controller/watchdog session deadline | 410 s | 1,310 s |
| CPU reader samples | 480 | 1,500 at the existing one-second cadence |
| GPU/host sample cap | 512 | 1,536 at the existing cadence |
| Bounded heartbeat file size | 2,048 bytes | 4,096 bytes |

The outer deadline and counters are duration support, not longer telemetry
freshness allowances. Their limits remain finite and bound in this packet.
The unchanged reader already supports at most 1,920 samples/seconds; its source
and pinned hash are untouched. It supplies at least 1,205 seconds of declared
coverage before admission (model lifetime plus five-second stop budget), with
fresh actual readings required throughout. The 1,499-second last sample slot
covers the entire 1,310-second host session. GPU capacity exceeds that session;
two heartbeat bytes/second plus startup slack stay below 4,096 bytes.

The 180-second startup budget plus 900-second request plus five seconds to stop
is 1,085 seconds, below the model lifetime. Ninety seconds of admission plus
1,200 seconds of model lifetime and stopping fits in the host deadline. Model
time is anchored before container start, never reset at readiness or on progress.
The container independently enforces the same lifetime and request deadline.

Fifteen minutes leaves substantial room for input processing and an ordinary
short function. It does not promise that all 4,096 output tokens can be generated
at the earlier measured decode rate; that would take roughly two hours. The
4K figure remains a ceiling, not required generation. Any timeout remains a
recorded result, never an automatic extension or retry.

## Everything else stays fixed

The prompt, model/configuration, token allocation, response format and acceptance
checks are byte-for-byte the same task as the failed scope:

- **16,384 context**, **123 actual input / 512-token input budget**, up to
  **4,096 output**, eight-token context margin. No padding.
- `fibonacci(n)` returns the first `n` values starting with 0, 1. Plain function
  code or one complete Python fence; no extra algorithm/performance requirement.
- One inference request; no OpenCode worker or repository edit. Preserve raw
  answer and admitted function; accept only naturally completed output.
- After supervised model shutdown, unchanged static code admission and the
  existing one-CPU/one-process/128-MiB/two-second evaluator check the six inputs
  0, 1, 2, 7, 10 and 20. No model code executes in the supervisor process.
- API result bound 262,144 bytes, admitted code 32,768 bytes. State-journal and
  log bounds are unchanged. No native tool-calling or full-window claim.

| Unchanged safeguard | Limit |
| --- | --- |
| CPU / GPU emergency stop | **97 C / 75 C** |
| GPU power / VRAM stop | **100 W / 14,336 MiB** |
| Host used-RAM stop | **30,720 MiB** |
| Native engine-silence base | **75 s**; server waiting messages do not renew it |
| Telemetry freshness / controller lease | **2.5 s / 2.5 s** |
| CPU / GPU query bounds | 1.5 s / 1 s |
| Model startup / admission window | 180 s / 90 s |
| Required valid startup telemetry | 10 s; targets remain advisory |
| Owned stopping deadline | **5 s** |
| WSL | One CPU / 6 GiB / no swap |
| Model container | One CPU / 4 GiB / no extra swap |
| Retry / fault reset / added readiness gate | None |

No sensor, calibration, firmware, power, fan, model, cache, prefill, CPU-share or
installation change is proposed. CPU-build 92/97 C and inactive 95/98 C history
are preserved. Existing isolation, read-only mounts, cancellation and latched
faults remain enforced. A heartbeat or successful token cannot renew a wall-clock
deadline. Safety stops may still end the run earlier.

## Fresh scope and preserved evidence

Scope: `one-fresh-fibonacci-900s-request-1200s-model-safety-unchanged`.

Review SHA256: `f49604f6854d0ca84042f6442d9da034abb880a6f60eba2b1640be4892665733`.

Frozen packet: `.runtime/strata-fibonacci-extended-review/f49604f6854d0ca84042f6442d9da034abb880a6f60eba2b1640be4892665733/`.

New execution namespaces are `.runtime/strata-fibonacci-extended-model`,
`strata-fibonacci-extended-operation` and `strata-fibonacci-extended-launch`.
The new decision is `containers/model-runtime/simple-function-extended-approval.json`.
They remain absent; launch flags are false. A new approval must bind the exact
packet/policy and permit one model attempt with no worker container. The old
operation remains spent; no previous namespace, approval or fault is reset.

The complete failed operation, reader, model, launcher, capacity-probe evidence,
all 150 sealed review files and separate notes are verified against their
preservation hashes. The entire older failure chain, unused readiness proposal
and superseded 64-output review are retained. Sixteen model attempts remain
consumed; this offline preparation consumes none.

The shared guest runner's historical bytes are preserved. Longer duration support
uses a scope-specific copy with only finite lifetime/heartbeat accounting changes.
Host defaults retain the original shorter durations/counters; only this scope
activates the new values in both controller and independent watchdog processes.

**147 offline runtime/integration checks passed.** Fake-time checks exercise the
full extended lifetime, exact deadline boundaries, stale telemetry/heartbeat
stopping, scaled reader coverage, unchanged temperature/RAM/power stops, paired
host/guest settings, policy drift and every spent approval. The known-function
restricted-job test remains separate from model execution. No model, container,
sensor or GPU/host telemetry was started to prepare this review.

The first full suite exposed that changing the shared guest source invalidated
four historical pinned-input tests. Its failed log is retained. Moving duration
support into the scope-specific runner restored the exact shared guest bytes;
the complete suite then passed. Historical evidence and production checks were
not relaxed.

After fresh approval: dispatch once, preserve response, candidate function,
correctness result, raw readings and errors, then independently inspect the exact
model container and all four main host helpers. If an evaluator ran, preserve
its owned-handle exit receipt and inspect its saved PID too. Retain stopped
containers. Do not apply code or retry. No other chat's manual model session is
started or altered by this operation.

Read-only review: `python -B local_worker.py review-extended-fibonacci-test`.
Run after approval: `python -B local_worker.py run-extended-fibonacci-test`.
