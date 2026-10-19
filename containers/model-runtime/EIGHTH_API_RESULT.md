# Eighth API test: admission expired before Strata startup

19 October 2026, approximately 08:07–08:10 Israel time. **One approved attempt
consumed; FAULT latched, never-started container retained, all four host processes
confirmed exited. No model request or answer.**

The owner approved the exact [eighth review](EIGHTH_API_REVIEW.md), including
coordinated startup/status handling and the documented source/cancellation
limitations. CPU admission remained **94°C for ten seconds**, CPU stop **97°C**;
all resource, GPU, timing and placement limits stayed unchanged. Frozen review,
77 helpers, three inputs, seven-attempt preservation and original configurations
passed verification. Windows administrator consent and the included tiny no-GPU
capacity/swap probe succeeded; that probe exited and was removed as reviewed.

The guard waited the full 90-second admission window, then latched
`BASELINE_NOT_MET`. The journal contains WAITING_BASELINE followed by FAULT;
there was no ARMED/RUNNING transition or start receipt. Docker inspection confirms
the model container remains **created**, PID 0, never started, no OOM or daemon
error. Strata/API/model execution and request count are therefore **false/zero**.
Docker logs are empty. The startup/status correction was **not exercised live**;
its existing 436 offline tests remain its validation evidence.

## Recorded admission conditions

| Observation | Value |
| --- | --- |
| CPU samples | 89; 91–95°C |
| CPU above 94°C admission | 45 samples |
| Longest consecutive CPU sample span at or below 94°C | About 6.022 seconds |
| Maximum CPU query time | 0.0349 seconds |
| GPU samples | 68; 58–60°C |
| Maximum GPU power / used device VRAM | 41.34 W / 2,066 MiB |
| GPU power above 40 W admission | Five samples |
| Host free RAM | 10,113.89–10,513.27 MiB |
| Maximum GPU query time | 0.2394 seconds |

Both CPU temperature and occasional GPU power readings interrupted admission.
GPU temperature/VRAM and free RAM met their admission thresholds throughout the
saved GPU samples. No CPU/GPU stop threshold was reached. The CPU span uses
consecutive recorded sample endpoints; it is not a continuous temperature
measurement or an exact replay of the guard's monotonic clock. CPU firmware
freshness/calibration and throttle remain subject to the accepted limitations.

The recorded stop confirmation took **0.188 seconds**. This confirms the owned
container was not running; it does not demonstrate stopping a loaded model.
Parent, watchdog, CPU reader and administrator wrapper were all confirmed gone.
All seven earlier model containers, the retained build container and deferred
private-engine capsule were still not running. No retry, fault reset, policy or
affinity change, compilation, download/import, OpenCode task, original
configuration edit or global Docker/WSL stop occurred.

## Preserved evidence and next step

- Review SHA: `5e7f1a40d21c24bd64fa495d8b821994def2e8e3c189318c3175b432de42b8d1`.
- Policy SHA: `578ca27e5ba15466544c3f520a1ba9c00efe0d3969b3ef0842fe495d37fde5e2`.
- Session: `abf6b5a425194c6a810e2be67d944ee4`.
- Retained container: `2cb055083d4d0e4b5d4a76e38dac8d19fd077dccb076dc6ca20dbef434bad72e`.
- Attempt: `.runtime/model-api-8/`; launcher: `.runtime/model-api-launch-8/`.
- CPU reader: `.runtime/compiler-guard/94ea3e40a128435c8b8b4047cb2ee02f/`.
- Probe: `.runtime/image-storage/439426cc29b84ab4a1393feeed6253a1/`.
- Execution result SHA: `a4afeef4e0f56de8ee88fc677e5895f56f0135169f32261e0385ab488294f690`.
- Preservation SHA: `4f8e1671e9c02b07b63728e7922c0f41b849e0f2f6264970a9f5a11966d4e07c`.

Execution result/inventory, owner decision, consent records and frozen review
remain under `.runtime/model-api-startup-review/<review SHA>/`. They preserve the
raw CPU/GPU readings, state journal, process checks, inspection and bounded
logs/events. Post-verification confirms all seven prior attempts/build evidence,
source/runtime/model identities and original Docker/WSL/Strata settings unchanged.
The separate read-only analysis `.runtime/model-api-8-admission-analysis.json`
has SHA `42e2bfb09714cb27be1b5e0b039c7938091fce8e279317751127bd60e1e12212`;
it does not alter the finalized attempt inventory.

All eight approvals are spent. No ninth packet or approval exists. The next
functional step remains a fresh bounded API attempt with the same startup
correction when admission conditions permit; another live attempt needs its own
review/approval. This result does not validate the startup correction or justify
silently changing thresholds. Keep 94/97°C and other limits unchanged. After a
real text answer, connect the staged one-file OpenCode edit and return its patch
to Codex with confirmed shutdown. The fourth run remains the latest proof of GPU
model/API readiness; successful generated text and useful coding are unproven.
