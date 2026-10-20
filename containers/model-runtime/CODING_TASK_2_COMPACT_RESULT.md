# Compact task-2 attempt: host RAM stop, shutdown confirmed

19 October 2026. **One approved real attempt; no patch, no retry.**

The owner approved the frozen [compact review](CODING_TASK_2_COMPACT_REVIEW.md),
SHA256 `9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a`.
The preparation inventory and all previous task-2 failures passed integrity
checks. Docker readiness passed with zero running containers; the prepared
administrator wrapper was dispatched once. The 150-second request deadline
and every other reviewed limit remained unchanged.

The real attempt reached model startup and prompt processing. Logs report the
expected **23 prompt tokens**, with server waiting messages at 10, 20 and 31
seconds. The supervisor then latched **`HOST_RAM_HIGH`** and stopped its owned
components. The highest saved host reading was **29,090.77 MiB used** of
32,388.68 MiB, above the unchanged **28,672-MiB emergency stop**. At that reading
3,297.91 MiB was free. This is host system RAM, separate from GPU VRAM and the
model container's 4-GiB system-memory limit.

No completed API result/usage receipt, validated guard, OpenCode edit or patch
was obtained. `api-result.json` was not saved before shutdown; no response or
usage is fabricated. The selected repository file, disposable original and
unselected sentinel remain unchanged. The attempt was not retried or reset.

## What this result establishes

The RAM emergency guard fired; the recorded cause is not a 150-second request
timeout or engine-silence fault. Server waiting messages alone still do not
prove native prompt-position advancement. The RAM stop ended this attempt
before the shorter request's useful result or silence behavior could be
established. It does not validate the prompt's coding fidelity or prove that
shortening it resolved the preceding silence failure.

The saved readings identify total host RAM pressure; they do not attribute
the increase to a particular host process, WSL cache or model allocation.
No memory, safety, workload, power or system configuration was changed afterward.

The integration record's `modelStarted: false` is a reporting limitation:
that assignment happens only after `first_api.run()` returns successfully,
whereas this call raised `MODEL_API_FAILED_OR_STOP_UNCONFIRMED`. The model
attempt/session, native startup and 23-token prompt logs, and independently
inspected running interval prove the model did execute. Preserve the original
record as written; this is the **fourteenth consumed model attempt**.

## Independent shutdown confirmation

| Owned component | Independent finding |
| --- | --- |
| Model `64f61dfa731eab53d48e4f63145f7186cdddde5061713eabf1079eabee20e0bd` | Exited, Running false, PID 0, exit 137, OOMKilled false |
| Worker `2299e1408c1a4d8aa7b454e263c7829389fc727fb284ae714a2e13a09f2bae9a` | Exited, Running false, PID 0, exit 70, OOMKilled false |
| Parent PID 44656 / watchdog PID 64448 | Both independently confirmed exited |
| CPU reader PID 64504 / administrator wrapper PID 54260 | Both independently confirmed exited; wrapper recorded exit 3 |

The model ran 14:32:50–14:35:00 Israel time (11:32:50–11:35:00 UTC).
The worker ran 14:31:58–14:34:59 Israel time. Containers are retained stopped;
the approved capacity probe confirmed cleanup and zero guest swap. Docker
Desktop remains running. No global Docker/WSL stop, private-engine operation
or attached-disk action occurred.

Model exit 137 is recorded as observed, without calling it a clean exit.
The latched host RAM fault caused owned stopping, and both inspections report
OOMKilled false. Exit 137 alone is not proof of a container OOM kill.

Recorded telemetry: 142 CPU samples, 108 GPU samples; CPU 94–96 C, GPU 62–72 C,
peak GPU power 81.76 W, peak VRAM 6,875 MiB. Startup warnings recorded CPU 96 C,
GPU 63 C, GPU power 45.33 W and host free RAM 6,427.51 MiB. The startup targets
remained advisory; host RAM's emergency threshold remained enforced. CPU stop
stayed 97 C, with all other limits unchanged. Sensor-source limitations remain.

## Preserved evidence and remaining state

Directory:
`.runtime/strata-coding-2-compact-review/9f22e8cddf631f9b541a6c6388ae277d1f32d1df67d2e8a92d4086a86ffa4f3a/`.

It retains the exact review, frozen helpers/tests, source excerpts, offline
audits and validation, owner decision, selected inputs, single dispatch/wrapper
records, raw logs/readings, state history, worker/integration fault, independent
container/process inspections, metrics and complete hashed inventories of the
owned components and staged task. No empty or fabricated `returned.patch`
was created; no patch was applied to the repository.

Execution-result SHA256:
`07ee38dab305b8f2e020c245310aa9526f30815d0140526f3bdd6facad90d9d9`.
Preservation SHA256:
`e03c7f983f591e1c53bc1124798d6ce27778d27f74465360b6f2b828278827c0`.

All four earlier failed task-2 scopes, spent approvals and previous model/build
evidence were verified unchanged, as were source/model identities and machine
settings. Fourteen model attempts are now consumed, plus the earlier worker-only
failure. This operation's approval and namespaces are spent. The 112 offline
checks were pre-execution validation and remain separate from this real fault.
No retry, restart, fault reset, patch application, safety change or further
workload is approved.

Left: review the host RAM failure offline before preparing any successor.
Context capacity and Hermes remain separate and deferred.

Recorded-status entry point, without hardware launch:

```text
python -B local_worker.py review-useful-coding-task-compact
```
