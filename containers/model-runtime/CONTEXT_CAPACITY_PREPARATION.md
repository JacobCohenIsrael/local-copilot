> Current direction (20 October): follow [VIABILITY_POC.md](../../VIABILITY_POC.md). One real
> coding task within 30 minutes; new coding scopes use resource warnings/trends.
> The notes below describe historical or deferred work, not next-step instructions.
> Their strict thresholds, pending approvals and context ladders do not override
> the current contract. Preserve historical evidence and CPU-build policies.

# Offline context-capacity preparation

**20 October latest direction:** start at **16,384 context / up to 4,096 output**,
with a simple function request using a **roughly 512-token input budget**, then
double input and add task requirements based on observations. Do not pad a short
request. Fibonacci and dynamic programming were examples. The prior
[64-output proposal](CONTEXT_16K_REVIEW.md) remains preserved, superseded and
unrun. A new task/acceptance contract, actual token count, response-byte allowance
and finite timing review are needed before a fresh runnable scope and approval.
No settings, time limits, safety stops or live workload are changed by this plan.

With 16K context, 4K output and eight-token slack, input can reach at most
**12,280 tokens**, including the complete rendered template and instructions.
An input of 512 leaves 11,768 tokens unused in that allocation; unused context
need not be filled. The output ceiling need not be consumed. At the last short
request's generation rate, 4,096 output tokens alone would take about two hours;
that is an extrapolation, not a forecast for a new task. Current 150-second
request/300-second model limits may end a trial earlier and cannot establish
full 4K output capability. Do not silently extend them or weaken safety stops.

Near-window capacity and Hermes remain unproven. Header metadata declares
262,144 context tokens; the pinned ASCII template/BPE audit is available for
counting the new request. Unicode compatibility and full-window behavior remain
unproven. The older plan below is historical; its 1K configured-context checkpoint
and unresolved host-tokenizer note are not current blockers.

19 October 2026. Planning only; **no capacity operation approved or executed**.
Continue the [Hermes context plan](HERMES_CONTEXT_PLAN.md) after reviewing the
useful-task result and independently confirming shutdown.

The pinned upstream `serve/server.py` (SHA256
`6c45c639e28a873b854606719d9ce2bb2e0df666f105164e78e2735878b9aa8f`)
defines `CTX_SLACK = 8`. Its request preparation checks actual tokenized input
against `effective context - 8 - reserved output`, rejects overflow and says
requests are never truncated. Our config leaves `fit_max_tokens` disabled,
uses one session and fixes `--max-context 512`; no flag was changed here.

With a 32-token output reserve, the maximum prompt allocations would be:

| Effective context | Maximum input tokens | Approval state |
| ---: | ---: | --- |
| 512 | 472 | Only the separately reviewed useful task is proposed |
| 1,024 | 984 | Unapproved candidate, not selected for execution |
| 65,536 | 65,496 | Future gate; capacity remains unproven |

The pilot measured 29 input / 10 output tokens; that proves no near-limit
capacity. The useful task's 121-byte rendered ASCII upper bound also cannot
prove full 512-token capacity. Do not relabel either as a capacity test.

Before preparing a capacity workload for approval:

1. Read the selected model's GGUF/pack context and architecture metadata offline;
   distinguish supported/trained context from the requested and engine-reported
   effective context. No extrapolation or automatic RoPE changes.
2. Use the exact pinned template/tokenizer to count the full proposed request,
   including instructions and special tokens. Preserve rendered text, token IDs,
   tokenizer identities, input count, output reserve and eight-token margin.
   The current host Python installations lack `jinja2` and `regex`; their Linux
   runtime copies do not establish a working Windows tokenizer. Resolve offline
   counting without loading the engine; a byte bound is not a measured count.
3. Review architecture-specific KV/recurrent-state memory and scratch allocation
   at the candidate size. The 4-GiB model envelope is fixed. Pilot peak VRAM
   6,966 MiB and host free RAM minimum 5,076.75 MiB are **historical whole-run
   observations**, not available KV capacity or a current admission reading.
4. Plan prompt use across early/middle/late sections, with an expected answer
   that requires all three. Near-limit allocation and a correct useful result
   are required; a short answer in a large configured window does not pass.
5. Use the pilot's 59.6897 s prefill / 22.7602 s generation as a caution about
   timing, not a linear capacity forecast. Decide whether the candidate can fit
   the reviewed 90-second request / 300-second model budgets. Any proposed budget,
   resource or safety change must be explicit in a new review and approval.
6. Freeze one candidate packet only after these checks and the preceding real
   result. Require fresh scope-specific approval, then one attempt, measured
   effective context/usage, correct result and independently confirmed shutdown.

No candidate batch, model change, retry, package installation, context flag,
hardware observation or Hermes integration is authorized by this document.
