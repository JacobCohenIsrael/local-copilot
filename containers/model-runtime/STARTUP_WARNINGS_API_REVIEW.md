# Strata Docker API: startup targets are warnings

19 October 2026. Owner authorized this policy change and moving forward with a real Docker answer, then Codex integration. One bounded API attempt, no automatic retry or fault reset.

Startup targets (CPU 94 C; GPU 60 C, 40 W, 4096 MiB used; host free RAM 8192 MiB) produce recorded warnings. Ten seconds of valid monitored samples are required, without resetting that interval for target exceedances. Hard stop and validity checks run before any start grant and throughout startup/running.

Emergency stops remain exactly as in the eighth attempt: CPU >=97 C; GPU >=75 C or >=100 W; device VRAM >=14336 MiB; host RAM used >=28672 MiB. AC, throttle, fresh telemetry, cancellation, independent leases, start/status deadlines, source/integrity/isolation checks and owned shutdown remain enforced. CPU-source calibration/throttle and shared-Docker cancellation limitations remain as documented in the eighth review. Software stops cannot guarantee host/driver survival.

Use the existing verified executable/library, staged API/Python dependencies and read-only model data. No rebuild, download, firmware/power/fan change or original configuration change. WSL stays one CPU/6 GiB/no swap; container one CPU/4 GiB/no extra swap. Request: Reply with READY. No explanation. Context 512; output <=8 tokens; response <=16 KiB; exactly one request; engine silence 75 s; hard request 90 s; API readiness 180 s; model/container 300 s; outer 410 s. Stop confirmation <=5 s. No OpenCode worker in this first attempt.

76 offline runtime checks passed; these simulate hardware and establish no real inference result. Eight prior attempts/build histories verified. The earlier unapproved 95/98 C proposal remains preserved and inactive.

Review: `9213527ebc1861f5ee83004a9a1393c1b9903d3184fba118453c023efd48cad9`. Policy: `64149541b130eeb0cfc91c8fd37ed7665518283e71f120d7709a419f6560ed1e`.
Packet: `.runtime/model-api-startup-warnings-review/9213527ebc1861f5ee83004a9a1393c1b9903d3184fba118453c023efd48cad9/review.json`.
Fresh attempt: `.runtime/model-api-9`; launcher `.runtime/model-api-launch-9`.
Approval: `model-api-9-warnings-approval.json`, recording the owner's current message. Frozen helper count: 77; inputs: 3. Keep stopped container, logs and raw readings.

After a real answer and confirmed shutdown, connect the bounded OpenCode worker to Strata, submit one disposable file edit from Codex and return its patch. This API packet itself enables no worker.
