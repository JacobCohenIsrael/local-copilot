# HTTP request-gate rehearsal

**Tested:** real local HTTP requests now pass through the budget gate to a fake
model server. **Strata and OpenCode were not started.**

```text
Built-in test client -> authenticated local proxy -> owned fake model server
                              |
                       request-budget gate
```

`http_rehearsal.py` creates both servers on temporary `127.0.0.1` ports. It has
no upstream URL, arbitrary port, external bind, or live-mode option. The proxy
accepts only `POST /v1/chat/completions`, with an ephemeral bearer token.
Caller headers/credentials are not forwarded to the fake backend. Token
counting is the previous milestone's explicitly synthetic fixed counter.

The proxy bounds headers, request bodies and output; rejects ambiguous request
framing; and applies the gate before forwarding. It relays normal JSON and a
narrow subset of SSE streaming. Split stream frames are buffered and checked;
the final `[DONE]` marker is withheld until EOF confirms there is no trailing
data. Truncated/invalid streams close without a success marker. A stream that
already sent headers ends by closing its connection on fault, not by appending
a second HTTP response.

Incoming header/body reads, connects and writes have one-second wall-clock
limits. A same-process timer checks task/call deadlines during upstream
silence. Cancellation, client disconnect, overflow and backend failure close
the upstream socket and explicitly cancel only this fixture's owned fake jobs.
Faults remain latched. Socket closure alone is not treated as engine shutdown.

## Validation

Sixteen loopback tests passed: JSON/fragmented streams, authentication, model
and call limits, concurrent requests, ambiguous framing, oversized/incomplete
bodies, response overflow, silent-backend timeout, explicit cancellation,
client loss, backend error sanitization, truncated/trailing stream data, and
cleanup during an active request. Listener closure is checked after exit.
Windows sandbox networking rejected loopback connects, so these tests ran with
approved host socket access. No external host was contacted.

Two CLI smoke checks also passed:

| Scenario | Result | Cleanup |
| --- | --- | --- |
| `stream` | HTTP 200, COMPLETE, exit 0 | Both servers closed; no handler errors |
| `timeout` | HTTP 502, CALL_DEADLINE, exit 3 | Fake job cancelled; servers closed; no handler errors |

The timeout scenario accelerates the monotonic simulation clock 100 times:
15 simulated seconds take about 0.15 real seconds. It does not exercise heat.
Results are saved under `.runtime/worker-http/{stream,timeout}.json`.

```powershell
python -B containers/worker/http_rehearsal.py --scenario stream
python -B containers/worker/http_rehearsal.py --scenario timeout
python -B -m unittest discover -s containers/worker -p test_http_rehearsal.py -v
```

Other scenarios: `success`, `call-limit`, `oversized-response`, `cancel`,
`truncated`, `trailing`, `backend-error`. Every invocation is finite and closes
its servers before printing the result. Credentials/request contents are not
included in that report. No persistent daemon or fault reset is installed.

## Still pending

This is a fake-only integration fixture, not a deployable proxy. Its SSE
subset, protocol handling and fixed I/O limits do not establish OpenCode or
Strata compatibility. The timer shares the event loop and cannot protect
against process failure or blocked CPU work. Exact token accounting, actual
generation cancellation, durable fault/recovery state, independent watchdog,
Docker network isolation and live policy approval remain required. No engine,
container, hardware probe or downloaded executable ran in this milestone.

Next: stage and verify the pinned Linux OpenCode artifact, then check its
protocol/permissions against a fake backend in an isolated CPU-only fixture.
The Strata build and model-start safety gates remain unchanged.
