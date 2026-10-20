# Strata coding runtime

Current direction: [one 30-minute real coding task](../../VIABILITY_POC.md).
The owner approved warnings rather than resource stops for new coding scopes.
`runtime_safety.viability_policy(base)` selects this explicit profile; `Gate`
records rolling 30-second observations, while `first_api` saves/reports them every
five seconds and includes them in final guard state. CPU/GPU temperatures, RAM,
power, VRAM and reported active throttling are advisory. Sustained crossings warn
as well. Invalid/missing monitoring, cancellation, deadlines, process failure,
isolation and owned shutdown remain enforced. Physical/container limits stay.

This is offline-tested support, not an executed coding workload. The new coding
handoff must bind the policy in both processes and honor the total 30-minute
budget. Default/historical policies remain strict; consumed approvals cannot be
reused. The fixed-guard adapter does not satisfy the new task contract.

Older notes below are historical, including pending approvals and READY tests.
Read [AGENTS.md](../../AGENTS.md) and [NEXT_STEPS.md](../../NEXT_STEPS.md) first.

## Historical API preparation

The Linux Strata binary is built. This directory prepares the next proof:
one real answer from that executable inside Docker, followed by confirmed stopping.
The OpenCode coding task comes after that proof.

See [the latest result](EIGHTH_API_RESULT.md). **All eight approvals are consumed.**
The eighth expired its 90-second admission window before startup: CPU 91–95°C,
45/89 samples above 94°C; five GPU samples above 40 W admission. Never-started
container retained, stop confirmed in 0.188 seconds, all four host pids gone.
No model execution or request. All eight attempts/settings preserved. The fourth
remains the latest GPU/API readiness proof,
with no successful text yet.

The [ninth review](NINTH_API_REVIEW.md) is prepared at the owner's request, changing
only CPU admission **94 -> 95°C** and CPU stop **97 -> 98°C**. Every other policy
value, resource, model argument, deadline and CPU placement stays unchanged.
CPU-build policy remains 92/97°C. Its template is disabled; actual ninth approval,
`.runtime/model-api-9` and `.runtime/model-api-launch-9` are absent. No live run.

The consumed [eighth review](EIGHTH_API_REVIEW.md) introduced the correction, which
coordinates one start so periodic inspect does not compete with it. During the
handoff telemetry, cancellation and leases continue; genuine faults still stop.
Start stays 1.5 seconds, periodic inspect one second, and the handoff uses the
existing 2.5-second lease bound. The 300-second host lifetime begins at the guard's
pre-start grant, preventing any extension. No retry or timeout suppression.

Resource/context/output/request limits and affinity remain unchanged. `.runtime/model-api-8`, actual `model-api-8-approval.json`
and launcher namespace are retained and spent; the startup correction was not
exercised live. The ninth scope needs exact live approval. All eight prior
inventories, decisions, frozen helpers/inputs, first
supplement and fifth consent history are preserved/checked. State uses immutable
`states/state-NNNN.json`; start completion uses one bounded same-identity receipt.

`native_iq_startup.py` hashes the pinned C++/API sources, checks the native/serve
requirements and runs only five pure upstream argument-builder functions on the
host plus the pinned engine-silence parser. No native engine, full API module import, Docker call, live CPU reader or
GPU query/workload runs in preparation. The minimum verification width is two;
without MTP/suffix drafting, the pinned serve loop selects one-token rounds.

- `prepare-model-api`: verify saved build, source, runtime and model identities;
  create a fresh disabled packet and read-only Linux configuration.
- `review-model-api`: show the current packet and approval status.
- `run-model-api`: refuse before live access unless the exact new owner decision
  is present; then run one supervised test with latched faults and no retries.
- `cancel-model-api`: request stopping only the fixed active session, without
  start approval. It cannot clear a terminal fault or remove old evidence.

Commands use `python -B local_worker.py <command>` from the repository root.
The prepared administrator wrapper is for the existing CPU reader; it changes
no driver, firmware, fan or power setting.

The test keeps one CPU, 4 GiB container memory and the current 6-GiB/no-swap WSL
envelope. The reviewed scope uses 512 context tokens, eight output tokens and a
300-second model/container deadline. Its GPU stop thresholds and model-scope
CPU-source acceptance were scope-specific for the consumed attempts.
Another scope requires a fresh exact decision. Memory fit
and successful request completion remain unproven; the fourth run reached GPU/API readiness.

`api_wrapper.py` uses the pinned upstream API, disables engine startup/reload
retries and mirrors bounded native logs. `container_test.py` checks actual kernel
limits before starting it, issues one private loopback request, and monitors both
host leases. `first_api.py` connects the existing host reader, pulses and bounded
owned stopping to the runtime gate. All outcomes retain the stopped container
and diagnostics; no full successful-build log removal is repeated here.

`runtime-dependencies.lock.json` pins the portable Linux Python distribution and
three API dependencies. The staging helper only downloads/verifies/unpacks files
inside `.runtime/`; it installs nothing globally and executes none of those bytes.
The bundle is already staged for this review. Archive links are flattened safely;
unused terminal-description data with Windows case aliases is excluded.

Validation: 77 offline runtime tests and all 365 existing supervisor tests pass.
Run runtime fixtures with `python -B -m unittest discover -s containers/model-runtime`.
They use fake Docker/hardware/engine processes; they cannot qualify model inference.
