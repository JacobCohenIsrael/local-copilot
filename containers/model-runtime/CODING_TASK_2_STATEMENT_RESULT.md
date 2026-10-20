# Corrected task-2 attempt: engine silence, shutdown confirmed

19 October 2026. **One approved real attempt; no patch, no retry.**

The owner approved the frozen [single-statement review](CODING_TASK_2_STATEMENT_REVIEW.md),
SHA256 `268602b8691a2d036f2c239f955eb1aa2a056b2fe24b5ab64936d27c8be0caad`.
Its preparation inventory and all previous failed scopes passed integrity checks.
Docker readiness passed with zero running containers, and the prepared
administrator wrapper was dispatched once. The request deadline stayed 150
seconds and all other reviewed limits stayed unchanged.

The API submitted **one model request**, which returned
`HTTPError: HTTP Error 503: Service Unavailable`. The supervisor latched
`API_TEST_FAILED`, stopped its owned components and did not retry. No completed
API answer or usage receipt, validated guard, OpenCode edit or patch was returned.
The selected repository file, disposable original and sentinel remain unchanged.

## Recorded cause and progress semantics

Native/server logs show the expected **34 prompt tokens**, matching the offline
template/tokenizer audit. Periodic status lines report reading the prompt at
10, 20, 31, 41, 51, 61 and 72 seconds. At approximately 76 seconds the server
reports that the engine had said nothing, ends the engine and records
`done: 0 tokens in 76 s ... (error, cancel=False)`.

The unchanged **75-second engine-silence base** ended the request before its
150-second completion deadline. This was not another 150-second request timeout
or a 32-token output cutoff. The status text is server narration while waiting;
it does not demonstrate advancing native prompt processing or refresh the engine
activity clock. There is no completed code response on which to judge the revised
prompt's task fidelity. The reason native progress failed to arrive is unproven.
No inference, safety, resource, silence or deadline setting was changed afterward.

The retained host-stop traceback occurred during shutdown after the HTTP error.
The model container exited 1; this is preserved as observed rather than described
as a clean exit. Both container inspections report OOMKilled false. No recorded
thermal or memory emergency stop fired. Do not infer an OOM or a proven native
hang from the generic HTTP error or the lack of control output alone.

The raw integration record says `modelStarted: false` because its assignment
occurs only after `first_api.run()` returns successfully, and that call raised.
This field does **not** mean no model ran: the API receipt records
`modelStarted: true`, the attempt/session and native logs exist, and independent
inspection confirms the exact model container ran. This is the thirteenth
consumed model attempt. The original records are preserved without alteration.

## Independent shutdown confirmation

| Owned component | Independent finding |
| --- | --- |
| Model `aa3f9c677dd842cf3574eb5c8fbb7c06cf350fa46d071edece8254c813dd0bd6` | Exited, Running false, PID 0, exit 1, OOMKilled false |
| Worker `4cd826beffa0439cdea19b5bb866745bd92d75b41ef0854cadc896324cc67d6c` | Exited, Running false, PID 0, exit 70, OOMKilled false |
| Parent PID 61068 / watchdog PID 59276 | Both independently confirmed exited |
| CPU reader PID 40080 / administrator wrapper PID 59580 | Both independently confirmed exited; wrapper recorded exit 3 |

The model ran 14:14:26–14:17:20 Israel time (11:14:26–11:17:20 UTC).
The worker ran 14:13:40–14:17:19 Israel time. Both containers are retained
stopped; the capacity probe confirmed cleanup and zero guest swap. Docker
Desktop remains running. No global Docker/WSL stop, private-engine operation or
attached-disk action was performed.

Recorded telemetry: 186 CPU samples, 141 GPU samples; CPU 92–96 C, GPU 61–74 C,
peak GPU power 86.83 W, peak VRAM 6,755 MiB, minimum host free RAM 3,969.95 MiB.
Startup warnings recorded CPU 95 C and GPU 61 C. CPU stop stayed 97 C and all
other emergency thresholds stayed unchanged. Sensor-source limitations remain.

## Preserved evidence and remaining state

Directory:
`.runtime/strata-coding-2-statement-review/268602b8691a2d036f2c239f955eb1aa2a056b2fe24b5ab64936d27c8be0caad/`.

It retains the review, frozen helpers and tests, offline audit/validation,
owner-approved decision, exact inputs, single dispatch/wrapper records,
API fault, native/container logs, raw readings, state history, integration fault,
independent container/process inspections and hashed inventories covering all
owned attempt components and staged task inputs. No empty or fabricated
`returned.patch` was created; nothing was applied to the repository.

Execution-result SHA256:
`f03b512bb2e6a7715a8bea29ad3fed65e0f2fcd50bfa14a22353ac8b452da2da`.
Preservation SHA256:
`2d5084feb8d468cca11d011631b50b9b363c748ec4b96e1be97d60bf38e8cf74`.

All earlier model/build evidence, three failed task-2 scopes, spent approvals,
source/model identities and machine settings were verified unchanged. The
107 pre-execution offline checks are separate from this real failure; they do
not establish a useful corrected answer. There are now **thirteen consumed model
attempts**, plus the earlier worker-only failure. This approval and operation
namespaces are spent. No retry, restart, fault reset, patch application, safety
change or further workload is approved.

Left: review the native-progress/silence failure offline before proposing any
successor. Context expansion and Hermes remain separate and deferred.

Recorded-status entry point, without launching hardware:

```text
python -B local_worker.py review-useful-coding-task-statement
```
