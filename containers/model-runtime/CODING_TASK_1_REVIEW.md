# One real Codex -> Strata -> OpenCode patch

19 October 2026. Owner authorized this integration after the successful real Docker answer. One new bounded model generation and one OpenCode worker; no automatic retries or fault resets.

Codex submits: `Only change example.py from VALUE = 1 to VALUE = 2. Do not run commands or access other files.`. Only disposable `example.py`, initially `VALUE = 1`, is selected. Original and unselected files stay outside both containers. OpenCode first makes a genuine provider request. The host then starts the existing guarded Strata Docker path and sends this compact code-generation prompt:

```
Set VALUE to 2. Return only the updated code:
VALUE = 1
```

The adapter avoids sending OpenCode's large tool schema to this 512-token model context. Strata generates the replacement text; the host relays that real response to OpenCode's edit tool without inventing replacement code. A local acknowledgement follows confirmed application. This tests a narrow live, host-brokered code-to-edit adapter, not Strata's native tool-calling compatibility or a general interactive coding agent.

Model: unchanged one CPU/4 GiB, WSL one CPU/6 GiB/no swap, context 512, one request, response <=16 KiB. Coding output cap is **32 tokens** (the earlier READY smoke test used eight); prompt plus output must fit 512. Single call still <=90 s, inner silence 75 s, model/container <=300 s, outer <=410 s. Startup targets warn; all ninth emergency limits remain identical, including CPU 97 C/GPU 75 C. Monitoring, startup/status coordination, independent host/guest leases and owned stopping are reused.

Worker: pinned OpenCode 2.0.26 and already staged libraries in the existing pinned Python image, 0.5 CPU/512 MiB/no extra swap, read-only root and input, 64-MiB tmpfs, no GPU/network/host ports/socket/credentials, only selected-file read/edit permissions. No shell/delegation/downloads/MCP. It accepts at most two OpenCode requests <=64 KiB; one Strata request. Generated code is <=128 bytes and checked against this task. Worker lifetime <=410 s, independent guest host-lease <=2.5 s; explicit owned stopping and retention. The model stops after generation, before the worker completes application.

All nine earlier model attempts and the build/source/model/configuration identities are preserved and verified. The successful READY attempt is spent and not restarted. No firmware, power, WSL, Docker, model-file or original Strata configuration change. No downloads/builds. 81 offline runtime/integration checks passed; only the live run can establish a real coding result.

Success requires the real Strata response hash to match the code passed to OpenCode, the actual edited file to match that generated text, a bounded returned patch, originals unchanged, and both containers stopped with host helpers exited.

Review: `256f8be8d82772d044da1964b3d65286975d5c33dd8789b7684ab7936ca3477f`. Packet: `.runtime/strata-coding-1-review/256f8be8d82772d044da1964b3d65286975d5c33dd8789b7684ab7936ca3477f/review.json`. Worker source, model inputs and helper hashes are bound in that packet. Approval: `coding-task-1-approval.json`, recording the current owner message. Fresh model: `.runtime/strata-coding-1-model`; worker: `.runtime/strata-coding-1-worker`; launcher: `.runtime/strata-coding-1-launch`.
