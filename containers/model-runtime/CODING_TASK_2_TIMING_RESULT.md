# Useful task 2: response received, code rejected, shutdown confirmed

19 October 2026. **One approved real attempt; no patch, no retry.**

The owner approved the frozen [150-second review](CODING_TASK_2_TIMING_REVIEW.md),
SHA256 `de616a03b071844ed67685744ebf461e865358ecc4b05709197b8225b15d01da`.
Docker readiness passed and the prepared administrator wrapper was dispatched
once. Only the request deadline changed from 90 to 150 seconds; all other
reviewed limits, task inputs, prompt, output cap and guards stayed unchanged.

Exactly one real API request returned a response in approximately **106 seconds**:
24 prompt tokens, 32 completion tokens, 56 total. Native timings report
46.122 seconds of prompt processing and 60.026 seconds of generation.
The API finished normally, with `finish_reason: length`, at the unchanged
32-token output cap. This resolves the preceding request timeout for this run;
it does not establish useful coding success.

The returned content was an unrelated, unfinished function:

```text
```python
def max_value(values):
    if not values:
        raise ValueError("empty sequence")
    maximum = values[0]
```

The response ends with indentation after the assignment and has no closing
Python fence. The adapter rejected it with `CODE_FENCE_INVALID` before supplying
an edit to OpenCode. Independently of that formatting error, the function does
not implement the requested `maximum < 0` guard. No output was repaired or
substituted. No patch was produced or applied; original, staged original and
unselected sentinel remain unchanged. The useful task remains unfinished.

## Deadline and progress semantics

The **150-second request deadline requires the completed API response**. It is
absolute and does not renew on progress or keepalive signals. This request uses
`stream: false`, so the caller receives the final response rather than streamed
tokens or progress events. The retained logs do show prompt and token counts.

The separate upstream engine-silence setting remains **75 seconds**. Actual
engine control output (tokens, prompt-progress and other lines) updates its
activity clock. Periodic server status text or HTTP keepalives alone do not
update that engine activity clock. The pinned upstream also retains its existing
prompt-chunk allowances; 75 seconds is its configured base, not a new universal
hard cutoff. See pinned `serve/server.py` lines 1875–1933 and 4044–4062 under
`.runtime/strata-build/1c9c3253/input/source/`.

Host/guest leases separately supervise controller health. The unchanged
300-second model lifetime, worker 400/410-second limits, emergency stops and
other guards can preempt the request deadline; none are extended by keepalives.

## Independent shutdown and observations

| Owned component | Independent finding |
| --- | --- |
| Model `1e9bda3ac7db039c0f233734e5c3516b156a8f343ded7af55237bae7a2c766ae` | Exited, Running false, PID 0, exit 0, OOMKilled false |
| Worker `b250121197ff31df93b17b042133cdd1a4dba4488158d4738c74f42d78385b09` | Exited, Running false, PID 0, exit 70, OOMKilled false |
| Parent PID 43076 / watchdog PID 53124 | Both independently confirmed exited |
| CPU reader PID 53668 / administrator wrapper PID 52872 | Both independently confirmed exited; wrapper recorded exit 3 |

The model ran 13:55:03–13:58:01 Israel time (10:55:03–10:58:01 UTC).
The worker ran 13:54:21–13:58:02 Israel time. Both containers are retained
stopped; the capacity probe confirmed cleanup and zero guest swap. Docker
Desktop remains running. No global Docker/WSL stop or retained-disk action occurred.

Recorded telemetry: 190 CPU samples, 152 GPU samples; CPU 92–96 C, GPU 60–73 C,
peak GPU power 85.69 W, peak VRAM 6,648 MiB, minimum host free RAM 6,439.12 MiB.
Startup recorded CPU 95 C as a target warning. No emergency stop fired; CPU
stop stayed 97 C. Existing sensor-source limitations remain. GPU utilization
is separate from VRAM headroom: `--vram-reserve-mib 4096` leaves memory available,
and does not reserve GPU execution time for host applications. The model
container's separate 4-GiB memory limit applies to system RAM.

## Preserved result and remaining work

Evidence directory:
`.runtime/strata-coding-2-timing-review/de616a03b071844ed67685744ebf461e865358ecc4b05709197b8225b15d01da/`.

It contains the exact review, frozen helpers, approved decision, bound request,
single dispatch, full response, raw logs/readings, integration rejection,
independent container/process inspections and hashed inventories covering the
model, worker, reader, launcher, probe, selected staging and task bundle.
No empty or invented `returned.patch` was created.

Execution-result SHA256:
`287ad06ab13a2df85c537cce82285a88df5e057fcd8c6e3d205a51137cc8c179`.
Preservation SHA256:
`25ba93d962c47fd3b46f2eb4747a25f4a5c586cf5166f50321036fb4d3b0d246`.

The earlier Docker-unavailable failure, 90-second timeout, their approvals and
all preceding model/build evidence were verified unchanged. Twelve model
attempts are now consumed; the earlier worker-only dispatch is additional.
This operation's approval and namespaces are spent. No retry, fault reset,
patch application, further limit change or new workload is authorized.

The **100 offline runtime/integration checks** were pre-execution validation;
they are separate from this real response and rejected coding result. The next
useful work is an offline review of task fidelity and output handling before
preparing any separately approved successor. Context capacity/Hermes remain
separate and deferred.
