# Task 2: 30-GiB attempt returned incomplete code; shutdown confirmed

19 October 2026. The owner-approved [review](CODING_TASK_2_RAM30_REVIEW.md) ran
**once**, with a 30,720-MiB used-host-RAM stop, no added readiness gate and all
other limits unchanged. One API request returned a response; the strict
validator rejected it before editing. **No patch was produced or applied; no
retry or fault reset occurred.** Task 2 remains unfinished.

## Result and bounded execution

The native engine read 23 prompt tokens in 38.798 seconds and generated 32
tokens in 56.072 seconds, about **94.9 seconds** combined, within the unchanged
150-second request deadline. Native prompt progress and generation occurred;
there was no engine-silence or RAM fault in this attempt.

The returned content began with a Python code fence and `def solve(n: int) -> int:`,
then checked `n < 0`. It was not the requested single guard for `maximum`.
The response ended without closing the fence, with `finish_reason: "length"`.
The validator raised `MODEL_OUTPUT_INCOMPLETE` before publishing an edit to
OpenCode. The exact raw response, usage, timings and retained model logs are
preserved; nothing was repaired or completed by the host.

The model supervisor completed normally and stopped its container with exit 0.
The worker stopped with exit 70 after response rejection; the outer operation
exited 3. This is a successful bounded API execution and rejected coding result,
not a completed coding task. General native tool calling remains unproven.

| Saved telemetry | Observed |
| --- | ---: |
| CPU samples / GPU-host samples | 178 / 142 |
| CPU temperature | 92–96 C |
| GPU temperature | 58–71 C |
| GPU peak power / VRAM | 87.48 W / 6,243 MiB |
| Host peak used RAM | 23,338.27 MiB (22.79 GiB) |
| Host minimum available RAM | 9,050.41 MiB |

The only recorded startup warning was CPU 95 C against the advisory 94 C
target. Emergency stops stayed enforced. RAM remained below both the old
28-GiB and new 30-GiB crossings, so this run does not establish that raising
the crossing caused completion. The model/worker reported no OOM kill.

## Independent shutdown and preservation

After the operation exited, independent Docker inspection confirmed both exact
owned container IDs stopped with **Running false / PID 0**:

- Model: `9ab7de46d5f548d1fc19fd5b6ee0a4d544949e21f3e3084806e59cb80850be01`.
- Worker: `cfe1f9caf1be28162ce30f219bd78cdfcecd2898fcc554a2b9580e73dd239c4b`.

Independent process inspection confirmed parent 83012, watchdog 73924,
reader 104856 and administrator wrapper 36624 all exited. Containers remain
retained. No global Docker/WSL stop or private-disk action occurred.

The selected repository source and staged originals retain SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
The complete earlier failure chain and deferred, never-run readiness snapshot
were verified unchanged. All prior approvals remain spent; this approved
operation and model attempt are now consumed, bringing the total to **15 model
attempts**. The earlier Docker-unavailable worker dispatch remains separate.

Frozen review and execution evidence:
`.runtime/strata-coding-2-ram30-review/4b1d0a4a15eec7f180a13d52ce23c68b4d2860fbe903960c645cfabc27937875/`.

- Execution preservation SHA256:
  `ee0da137ccc41fa58afa3a7734c79741d4d9e1631bd92d97739939d037136da2`.
- Execution result SHA256:
  `6924304785c5439052fccf2dd63a97ce783c5b5906506d80496d2a7828cf882b`.
- Fresh approval SHA256:
  `89f0b791456715157b3a9822909b97559d99a609ef56aac0de0ea83337dc3bd8`.
- Original preparation preservation SHA256:
  `552bfeb96deae9b34f36fe45d5281bbf5258fb2b4432fa33142c664d8e5986fc`.

The preserved inventory includes exact executed helpers, the approval and
dispatch, API response, native logs, raw readings, stopped-container inspections,
independent process observations, staging, worker/model/reader/launcher records
and capacity-probe evidence. The 128 passing offline checks are separate from
this real run. No further live attempt or changed limit is authorized.

## Offline follow-up, 20 October 2026

The repeated truncation has a confirmed mechanical cause: the request retained
`max_tokens: 32`, native logs report 32 generated tokens, and the API reports
`finish_reason: length`. Re-encoding the entire saved answer with the pinned
ASCII template/BPE procedure reproduces exactly 32 tokens and the same text.
The pinned server passes this output allowance to the engine and reports length
unless generation ends through a stop condition. The cap was reached after
94.87 seconds of native prompt/decode work; neither the 150-second deadline,
engine-silence guard, context capacity nor RAM stop caused this cutoff. This
is an output-token limit, not a byte/file budget or host-side text clipping.

The earlier completed task-2 response also used all 32 tokens and ended as
length, with a fenced `max_value(values)` function. The latest fenced `solve(n)`
response repeated that general failure pattern despite a different short prompt.
It was not the same response text. Fresh processes, disabled prompt/conversation
caching and zero reused native prompt tokens provide no evidence of stale
conversation reuse.

There is also a concrete weakness in our preparation: compacting the prompt
from 34 to 23 tokens removed **"one line, no function or markdown"**, while
the strict validator kept those requirements. The RAM30 scope preserved that
compact prompt exactly. "Python guard only" still expresses the intended task,
but it leaves the format less explicit. This is a plausible contributor to the
function-shaped response, not proof of why this model chose it. The more explicit
34-token attempt never returned an answer, so its instruction following remains
unproven.

The host deliberately submits a small guard-generation request instead of
forwarding OpenCode's full tool request. Offline rendering confirms that Strata
received the short user instruction, including `maximum`, with thinking disabled.
It received neither `task_bundle.py`, `bounded_read`, the staged source, nor the
full OpenCode edit task. It therefore could not use that file context. The
template did not substitute `n` or insert `solve`; those appeared in the answer.

The intended guard `if maximum < 0: raise ValueError` fits in **eight tokens**.
This is an offline illustration, not a model-produced answer. Thus 32 tokens
can accommodate the intended response, but not guarantee that the model will
choose that response or stop. Increasing the allowance alone might only extend
the wrong function. Replay also confirms that marking the same text complete
would still fail the single-statement validator. The correct guard is admitted;
the actual incomplete answer remains rejected. No validator was relaxed.

Next correction to review: make the model-facing format and task constraints
explicit and consistent with admission, then separately assess any proposed
token/time change. No proposed prompt has been activated, no new execution scope
or approval was created, and no live test was run by this review. This evidence
does not distinguish prompt sensitivity from model/quantization or native-engine
quality issues, nor establish that more tokens would yield correct code.

Audit and assertions are preserved separately under
`.runtime/strata-coding-2-ram30-output-analysis/`. They verify all 141 sealed review
files, the source/tokenizer identities and unchanged selected repository file;
reproduce both completed responses' token counts; and replay admission offline.
The tokenizer procedure is restricted to the audited ASCII inputs and makes no
full Unicode compatibility claim. An initial audit-script alias error and its
source were retained before correction; it affected no production code or live
operation. The sealed execution snapshot and all previous failures remain intact.
