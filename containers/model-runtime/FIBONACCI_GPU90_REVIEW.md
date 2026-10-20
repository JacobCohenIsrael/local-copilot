# Fresh Fibonacci attempt: GPU warning above 87 C, stop at 90 C

20 October 2026. The owner explicitly authorized the policy change **and one
fresh run**: "Change GPU HOT threshold to 90 and only warn above 87. Then rerun
the test." No additional owner confirmation is required for this scope.

The previous 246-input attempt stopped at the historical 75 C threshold after
62 generated tokens. No complete response or correctness result returned.
Model exit 137/PID 0 and all four helpers independently exited. Preserve it
unchanged under `.runtime/strata-fibonacci-double-review/86755db0f8e6477bfe036a7847be3eca2a49cec831fa9ab3079632e8101d0f06/`;
execution-preservation SHA256
`f0bd8516a5ace3a5abc33caa5d46ae3ddf2ee10194a198adb145c72a5dad539d`.
Eighteen prior model attempts remain consumed. The previous approval is not reused.

## Exact approved change

| GPU temperature | New behavior |
| --- | --- |
| At or below 87 C | No GPU-temperature warning |
| Above 87 C and below 90 C | Warn; continue while other controls permit |
| At or above 90 C | Latch `GPU_HOT` and stop the owned model |

The advisory startup GPU-temperature target changes from 60 to 87 C as well;
it does not become a readiness gate. Startup still requires ten seconds of valid
telemetry. CPU, power, VRAM and free-RAM startup warnings retain their existing
targets. Other emergency causes, including a reported active GPU thermal-throttle
flag, remain fatal independently of this temperature threshold.

The shared base gate now reads its existing `gpuStopC` policy value rather than
hard-coding 75. Historical/default policy remains 75. Only the new scope sets
90 and installs the scoped warning observer, in both parent and independent
watchdog processes. A first warning produces one immutable
`gpu-temperature-warning.json` receipt and a watchdog log message. Every raw GPU
reading remains preserved, including later peaks and repeated crossings. Warnings
do not renew model, request, lease or freshness deadlines and do not reset faults.

## Everything else unchanged

- Exact same **246-token** Fibonacci request, same six correctness cases and code
  admission. **16,384 context**, **4,096 output ceiling**, 512 input budget, eight
  tokens of context margin. No prompt or model/configuration change.
- Request **900 seconds**, hard model lifetime **1,200 seconds**, host outer bound
  **1,310 seconds**. Startup/admission 180/90 seconds; native silence base 75 seconds.
- CPU stop **97 C**, GPU power **100 W**, VRAM **14,336 MiB**, host used RAM
  **30,720 MiB**. Telemetry/leases **2.5 seconds**, owned stop budget **5 seconds**.
- WSL one CPU/6 GiB/no swap; model container one CPU/4 GiB/no extra swap. CPU/GPU
  sample caps 1,500/1,536; heartbeat byte bound 4,096. No extra readiness gate.
- Same isolation, read-only mounts, source limitations, journal/log bounds and
  independent watchdogs. Same static admission and post-model evaluator: one
  process, one CPU, 128 MiB and two seconds. No cooling, firmware or power change.
- One new API attempt. Preserve response/code or failure evidence, inspect exact
  model container and four host helper PIDs independently, and any evaluator
  handle/PID if it ran. Retain stopped containers. No code application or retry.

**159 offline runtime/integration checks passed.** Exact 87/90 boundaries,
continued operation within the warning band, one warning receipt, latched fault,
unchanged CPU/power/VRAM/RAM/throttle/freshness/lease/deadline stops, child watchdog
activation, CLI approval and historical evidence were checked without inference.
The original frozen helpers and every previous attempt remain hash verified.

Scope: `one-fibonacci-246-input-gpu-warn-above87-stop90-other-limits-unchanged`.
Review SHA256: 1359b55a4774dd2283e9c5887b8c4746bff033b87fb27211365d66df8ca4080d.
Fresh execution namespaces: `.runtime/strata-fibonacci-gpu90-model`,
`strata-fibonacci-gpu90-operation`, `strata-fibonacci-gpu90-launch`.
New operational decision: `containers/model-runtime/simple-function-gpu90-approval.json`.
Read-only review: `python -B local_worker.py review-gpu90-fibonacci-test`.
Authorized one-run entry: `python -B local_worker.py run-gpu90-fibonacci-test`.
The evidence packet records the live outcome after independent shutdown checks.

## Executed outcome

Ran once under the bound owner approval. `HOST_RAM_HIGH` stopped it at
30,757.52734375 MiB used (limit 30,720), during prompt processing; no complete API
response or correctness evaluation. GPU peak 64 C, CPU peak 96 C. The 90 C GPU
stop and above-87 C warning were not reached. Model exit 137, stopped/PID 0;
all four host helpers independently exited. Stop took 2.175 seconds within the
unchanged five-second budget. No code applied or retry. Nineteen attempts consumed.

Execution preservation SHA256:
`d1220dff69b31336e5a0cb374cdb30c63f6d059ba1aa30a3c6abf597f3731231`.
Result SHA256:
`12dcef2dfbffe99958dc2b41738439ef10cbbe08feebfcb2d9efd2ea90c07246`.
The frozen review, its pre-run checkpoint and all prior evidence remain intact.
