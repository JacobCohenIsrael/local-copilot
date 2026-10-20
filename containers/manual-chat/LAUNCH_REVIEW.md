# Proposed manual session: offline review only

20 October 2026. This is a fresh manual-chat workstream. Fifteen previous model
attempts and their approvals remain consumed. **No new model attempt, sensor
query, Docker operation, retry, fault reset or policy activation ran here.**

Scope: `one-manual-strata-session-16k-512-input-up-to-4096-output-150s-300s-no-readiness`.
The frozen packet is selected by `.runtime/strata-manual-chat-review/candidate.json`;
`chat.py review` checks its hash, source bindings, staged guest inputs and command.
The final review identity and offline results are recorded in
[OFFLINE_VALIDATION.md](OFFLINE_VALIDATION.md).

## Proposed operation

One launch of the existing pinned Strata Linux build and installed
`qwen3.8-flash-next-coder-iq1_m` model in one newly owned Docker container. No
OpenCode worker or coding patch path. The user enters every inference prompt.
The terminal communicates through a fixed Docker-exec mailbox to container-local
loopback HTTP, with no published port, external network or writable host bind.
Only text is accepted; returned text is displayed, never executed.

| Bound | Proposed value |
| --- | --- |
| Context allocation | 16,384 tokens |
| Actual input | At most 512 rendered tokens, including template/history; no padding |
| Output | Up to 4,096 tokens per request; user may lower the cap |
| Requests / automatic retries | At most three explicit submissions / zero |
| Startup / request / native silence | 180 / 150 / 75 seconds |
| Model / outer lifetime | 300 / 410 seconds, unchanged |
| CPU stop | 97 C |
| GPU temperature / power / VRAM stops | 75 C / 100 W / 14,336 MiB |
| Host used-RAM crossing | 30,720 MiB (30 GiB) |
| Startup | Ten seconds valid telemetry; advisory targets and saved warnings |
| Telemetry freshness / both host leases | 2.5 / 2.5 seconds |
| Owned stop confirmation bound | Five seconds; stopped container retained |
| WSL | One CPU, 6 GiB, no swap; checked, never changed |
| Model container | One CPU, 4 GiB, no extra swap, 128 PIDs |
| Input / reply / raw SSE bytes | 8,192 / 98,304 / 524,288 per request |

CPU 94 C, GPU 60 C / 40 W / 4,096 MiB and free host RAM 8,192 MiB remain
advisory startup targets. There is no additional readiness or free-RAM gate.
The existing source limitation (ASUS firmware freshness/calibration and CPU
throttle status unverified) remains in the packet and proposed decision.

The existing single-use API adapter disables native engine startup retries and
reloads. A separate host watchdog owns real telemetry, admission, contract
inspection and exact-ID stopping. Both host pulses are checked inside the guest
while the API is busy. The shared CPU-reader lock prevents concurrent admitted
model workloads that use these guards. Controller/watchdog loss, stale telemetry,
emergency thresholds, request/lifetime deadline, API failure or invalid output
end the owned session and preserve the fault. No second operation is approved.

Live preflight reuses image/VM/driver and the existing small cached no-GPU
capacity/swap probe; that probe is part of the proposed operation, not an offline
check. No import, download, global Docker/WSL stop/restart or private-engine disk /
unstarted-container action is included. Preflight failure cannot start the model.
The exclusive manual-session namespace consumes the approval before the first
live preflight operation, including the no-GPU probe. It is never deleted or
reset by this feature. A failed preflight cannot reuse that decision.

## Timing and interpretation

These finite durations deliberately preserve the current 150-second request and
300-second model limits in this first manual proposal. This is suited to short
manual exchanges, not a measured 512-input/4K-output throughput claim. The last
23-input/32-output run spent approximately 95 seconds on native prompt/decode
work. Full 4K generation would exceed this request deadline at that observed
rate. A request can also run out of model lifetime after startup/typing. The
terminal reports the remaining lifetime and begins owned shutdown with five
seconds left. It does not extend time for progress or keepalives.

16K allocation, Unicode handling on the actual Linux runtime, long replies,
streaming on this installation and manual-session shutdown remain unproven live.
Offline mocked tests do not establish hardware safety, thermal fit, throughput,
correct answers, 16K capacity or physical shutdown during a host/daemon failure.
Known driver/host/suspend failure limitations remain explicit in the packet.

## Approval and launch boundary

There is no manual `approval.json`. The packet contains an **unapproved** decision
template, never a spent decision. A fresh owner instruction must approve this
exact frozen scope before a matching decision may be written at
`containers/manual-chat/approval.json`. The decision must bind the review hash,
policy hash, all limits and retained source limitations, with one attempt and
model launch true. The feature never creates approval itself.

After fresh approval, the concrete command is
`& .\containers\manual-chat\launch.ps1 run` from an administrator PowerShell
terminal in the checkout. `/stop` or `chat.py stop` can end only the owned session.
The session returns success only after the controller confirms stopped/PID 0
by a separate exact-ID inspection, the watchdog exits, its CPU reader is confirmed
exited and no fault is latched. Logs and stopped containers remain retained.
After exit, the launcher also records that the controller command returned.
Any changed helper or reviewed settings makes launch stale and requires a new
offline packet; that is not authority to retry or reset a consumed session.
