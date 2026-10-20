# Hermes consideration gate: prove usable 64K context first

Decision recorded 19 October, updated by owner direction 20 October 2026.
**Preparation only; no new workload or automatic search batch approved.**

## Decision and purpose

Keep Nous Research's Hermes Agent as a possible future addition for coordinating
local subagents alongside the Strata/OpenCode worker. Before considering Hermes
for integration, prove that our Strata runtime can use at least 64K context tokens
within an explicitly reviewed resource and safety envelope.

The [Hermes quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart),
checked 19 October 2026, states a minimum of 64,000 context tokens and gives
65,536 as an example server configuration. Use **65,536 tokens** as this plan's
explicit 64K target. Recheck the requirements of the selected Hermes version
when that gate is reached.

This is context capacity: the prompt, instructions, tool definitions, conversation
and reserved generated output must fit in the effective per-session window.
It is not a request to generate 64K output tokens or raise output limits to 64K.

## Proven baseline and remaining gap

The [completed coding pilot](CODING_TASK_1_RESULT.md) used a configured 512-token
context, 29 prompt tokens and 10 completion tokens. Its output allowance was 32
tokens, request deadline 90 seconds and model lifetime 300 seconds, with one CPU
and 4 GiB for the model container. Real inference returned a patch and both
containers stopped successfully.

That short request does not prove that even the full 512-token window was used.
No larger context capacity, 64K execution or Hermes compatibility is established.
The narrow host-brokered edit also does not establish general model tool calling.

## Direct 16K start and result-driven search

1. Review the pilot and select a useful small coding task. Keep the existing
   supervisor, OpenCode worker, selected-file staging and returned-patch boundary.
2. Start directly at **16,384 context tokens**, one quarter of the 65,536 goal.
   The owner explicitly replaced the small-step ladder with doubling/halving.
   The owner subsequently selected **up to 4,096 output tokens** and an initial
   **roughly 512-token input budget**, using a simple function before adding
   requirements. Fibonacci/dynamic programming was an example. Use meaningful
   instructions/source rather than padding to an exact token count. The earlier
   [64-output proposal](CONTEXT_16K_REVIEW.md) is superseded, preserved and unrun.
   A fresh runnable scope is still needed. No readiness gate is added.
3. Begin with the simple task, then increase input budget 512 -> 1K -> 2K -> 4K
   -> 8K as results justify it, holding the 16K context and 4K output ceiling
   fixed. At this context the hard input maximum is 12,280 tokens including
   template/instructions, after reserving output and eight-token slack. When
   more context is needed, consider 32K then 64K; halve or refine a capacity
   bracket when evidence supports it. The owner rejected a small-step ladder
   for configured context, not small initial actual requests.
   Keep allocation, actual input use, response quality and timing results separate.
   A deadline or wrong answer is not proof of a memory-capacity boundary.
   The 4K output limit is a ceiling, not a requirement to generate 4K. Exact
   input counts, natural completion, correctness, timings and resource readings
   must be observed separately. The existing 150-second request/300-second model
   limits do not establish that 4K output can finish; review any time-budget
   change explicitly before execution.
4. For each approved operation, retain the exact model/runtime configuration,
   effective per-session context, actual prompt/output token counts, input and
   response evidence, resource/temperature readings, timings, task result and
   independently confirmed container/host-helper shutdown. Record failures too.
5. Stop progression when a step fails, exceeds its approved budget or cannot fit
   within the reviewed envelope. Preserve the fault and evidence; prepare any
   successor separately. Do not silently increase resources, deadlines or output
   budgets, truncate the prompt, substitute a model or reset a fault.

Each live operation requires fresh, explicit, scoped approval. This decision
approves documentation and preparation only. All executed approvals are
spent; none of the fifteen consumed model attempts may be reused. No automatic
retry, restart or fault reset is authorized.

## Evidence needed to pass the 64K gate

A server argument, advertised model maximum, successful startup, short answer in
a large configured window or simulated test is insufficient. Require a real
bounded request that exercises the effective 65,536-token per-session budget
with measured input and reserved output, without silent truncation or overflow.
Use verifiable task-relevant content distributed across the input so the result
can demonstrate that early, middle and late context remained accessible.

The response must satisfy the reviewed task criteria and finish inside its
approved resource, temperature, request and lifetime limits, followed by
confirmed owned shutdown. Define the exact input/output allocation and acceptance
checks in the operation review before execution. Until this evidence exists,
record 64K capacity as **unproven** and defer Hermes integration.

Passing the capacity gate only permits considering Hermes. Subsequent work must
also establish tool-calling/API compatibility, useful coding quality, task
isolation and practical paid-token savings. Multi-machine PC/Mac delegation
requires its own compatibility and lifecycle validation; 64K alone proves none
of these properties. Hermes need not replace OpenCode or the supervisor.

## Existing controls remain in force

Keep CPU emergency stop at 97 C, the owner-directed 30-GiB host RAM crossing,
and all other existing emergency stops, valid
startup telemetry, independent watchdogs, leases, task/file/output limits,
latched faults and evidence preservation. WSL remains one CPU / 6 GiB / no swap;
the model container remains one CPU / 4 GiB unless a separate change is explicitly
reviewed and approved. CPU-build admission/stop policy remains 92/97 C. Startup
targets remain advisory under the existing owner-approved policy.

No model, installation, historical setting, retained container, attached disk,
approval or raw evidence is changed by this plan. A future self-healing component
must not restart a model workload or clear an execution fault automatically.
