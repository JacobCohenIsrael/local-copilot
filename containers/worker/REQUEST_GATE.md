# Request gate: offline budget logic

This change adds the decision-making core between OpenCode and a future Strata
connection. It decides whether a request fits a task's remaining allowance.
It does **not** create a server, connect to a model, load a tokenizer, start a
container, or change an approved policy. Admissions explicitly say
`ADMITTED_OFFLINE` and `executionEnabled: false`.

## Implemented and tested

`request_gate.py` handles one task and one outstanding model call at a time.
It rejects unknown request fields, a different model, malformed/oversized JSON,
duplicate keys, nonfinite numbers, image messages and invalid output caps.
The injected token counter receives messages, tool history, tool definitions
and the capped output request. It must account for the model's rendered chat
template and special tokens. There is no character/word-count fallback.
The CLI supplies a labelled **synthetic fixed count**.

Admission charges prompt tokens plus maximum requested output against the
whole task, including repeated history on every call. Output reservations are
never refunded from backend usage claims. Missing output caps are injected;
excessive caps are rejected. There are no automatic retries.

Monotonic deadline checks, budget exhaustion, invalid clocks/token counts,
counter/transport failure and cancellation latch the first fault. Stale call
IDs cannot finish a newer call. Snapshots contain counts/codes, not task or
response text. There is no reset operation.

These are fixed **simulation limits**, not approved live policy:

| Budget | Test ceiling |
| --- | ---: |
| Model calls | 2, sequential |
| Context per call, including output and reserve | 8,192 tokens |
| Context reserve | 256 tokens |
| Prompt + reserved output across task | 8,192 tokens |
| Output requested per call | 512 tokens |
| Incoming and normalized request | 64 KiB |
| Raw response per call, including stream framing | 64 KiB |
| Task duration | 60 seconds |
| Single call duration, within task deadline | 15 seconds |

## Run and inspect

From the project root:

```powershell
python -B containers/worker/request_gate.py --scenario success
python -B containers/worker/request_gate.py --scenario call-limit
python -B -m unittest discover -s containers/worker -p test_request_gate.py -v
```

Other scenarios: `context-limit`, `deadline`, `oversized-response`, `cancel`.
Exit 0 indicates simulated completion; exit 3 indicates a simulated fault.
Every scenario prints JSON and starts no upstream worker. Fifteen tests passed,
covering boundaries, tool-history accounting, reservations, concurrent-call
rejection, silent-call deadlines, byte limits, clock/counter errors and faults.

## Remaining before live use

- An HTTP proxy must serialize access, authenticate the task, validate supported
  request/tool shapes, enforce socket/body deadlines and prevent network bypass.
  The core accepts streaming requests and meters raw chunks; it does not parse
  SSE or demonstrate OpenCode compatibility. Parsing is a narrow admission
  subset, not full protocol validation. Unknown fields are rejected.
- The proxy must poll `check()` during silence and call `output()` before relay.
  A fault with an outstanding call sets `upstreamStopRequired: true`: a stop
  obligation, **not cleanup confirmation**. Blocking tokenizer/network work is
  not interrupted here; counter elapsed time is checked after it returns.
- Admission needs the exact engine/tokenizer/template identity. Response bytes
  are not generated token counts. A requested token cap does not prove engine
  compliance. Actual token enforcement, cancellation and stream handling need
  separate verification. Two calls bound accepted raw responses to 128 KiB.
- The independent watchdog, durable global FAULT journal, restart recovery and
  owner-approved live policy remain required. This in-memory state is lost on
  restart and must never serve as a live reset. No live-enable switch exists.
