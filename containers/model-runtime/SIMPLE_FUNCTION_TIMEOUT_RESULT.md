# First Fibonacci attempt: request deadline reached during input processing

20 October 2026. The [reviewed attempt](SIMPLE_FUNCTION_REVIEW.md) ran once with
explicit approval, 16K context, up to 4K output, 123 input tokens, a 150-second
request deadline and 300-second model lifetime. It returned no complete answer.

The server reported 16,384 context tokens at startup. Logs recorded input progress
at 32/123 tokens around 41 seconds, 64/123 around 83 seconds and 96/123 around
123 seconds. The last displayed progress was 96/123 at 144 seconds. The request
timed out, and the server reported zero generated tokens during cancellation.
No function was returned, admitted or evaluated. This is a timing failure,
not an output-token-cap failure or a demonstrated 16K capacity boundary.

The model container exited 70; independent inspection confirmed Running false,
PID 0 and OOMKilled false. Parent 108128, watchdog 112432, reader 111768 and
administrator wrapper 109012 were independently confirmed exited. The generic
engine-stop RAM hint is not proof of OOM: it accompanied owned stopping after the
request deadline, with no recorded RAM or thermal emergency stop.

Saved peaks: CPU 96 C, GPU 63 C / 48.35 W / 7,472 MiB VRAM, host RAM
26,647.84 MiB used, with 5,740.84 MiB available. There were 223 CPU and 169
GPU/host samples. Startup CPU 95 C produced an advisory warning.

Raw response/error, logs, readings, approval, exact executed sources and shutdown
proof remain sealed under
`.runtime/strata-simple-function-review/7d4942f8f036a09979bc014f956edc8528c1f1c43cf44e9f299b826c5953546d/`.

- Execution preservation SHA256:
  `be1454e34a0f6145fff5e10f7f6af02140f77a13f48250205eda845f6261b093`.
- Execution result SHA256:
  `885488525ae7be484f55070c2ecaff70ed1ffe720fbba6cd6ee6e3374cfc5800`.
- Separate report: `.runtime/strata-simple-function-report/notes.json`, with
  preservation SHA256 `ad6d8a36ac01ed3138015079b7fbc6969e96ac45ecb417c04101c1d53406149c`.

No source/documentation edit, patch application or retry occurred during the
approved run. Its operational approval record and runtime evidence were retained.
Sixteen model attempts and their executed approvals are consumed. The owner has
now requested a [fresh longer-duration review](FIBONACCI_EXTENDED_REVIEW.md);
that preparation does not authorize a new live run.
