# First real Codex / Strata / OpenCode coding patch

19 October 2026. **Completed with real inference and a returned patch.**

Codex staged one disposable `example.py`, containing `VALUE = 1`. OpenCode made
a real provider request. The host broker launched Strata in Docker and asked it
to set VALUE to 2. Strata returned:

```python
VALUE = 2
```

The actual model response included a surrounding Python code fence. The adapter
removed that fence and passed the generated text unchanged to OpenCode's edit
tool. OpenCode reported `Edited example.py (1 replacement)`. The edited bytes
matched the generated code and its response hash. A **113-byte patch** returned
to Codex, and `git apply --check` passed against the untouched disposable original.
No patch was applied to original files; the selected original and unselected
fixture remained unchanged.

```diff
-VALUE = 1
+VALUE = 2
```

One real model request used **29 prompt tokens and 10 completion tokens**. Native
prompt processing took 59.6897 seconds and generation 22.7602 seconds, within
the unchanged 90-second request deadline. The model retained a 512-token context,
one CPU / 4 GiB memory and the existing runtime, resource and emergency limits.
The coding scope permitted 32 output tokens; the earlier READY scope permitted 8.
Startup warnings allowed the recorded CPU 95 C target exceedance. No emergency
stop fired; CPU stop stayed 97 C, GPU stop stayed 75 C, all other stops enforced.
No rebuild, download, hardware/power/firmware or original configuration change.

Model container `7ee87732572077f6b6021894b73ef548dddd5045c070b89419da46786540aa80`
and worker `e389c934e95a09a2bf44cd6fb77261b1bed8557a2983526629e5c257dcc13360`
both exited **0**, retained stopped with PID 0. Stop confirmation took 0.2093 s
for the model and 0.1902 s for the worker. Parent, watchdog, CPU reader and
administrator wrapper were independently confirmed exited. The model ran
08:40:46-08:43:15 Israel time and stopped before delivery/application completed.

This is a **narrow live host-brokered code-to-edit adapter** on a synthetic input
file, using genuine model inference and a genuine OpenCode edit. The large
OpenCode tool prompt is translated into the fixed compact coding request. A
local acknowledgement follows the applied edit. Native Strata tool calling,
general interactive OpenCode behavior, arbitrary tasks and useful-task quality
remain unproven. The base file collector's `offline-only` flags describe its own
file operation; the combined live result and raw model/worker receipts establish
what actually ran.

81 offline runtime/integration checks passed separately from the real execution.
A later offline-only cleanup made handoff file publication atomic and added
recorded completion to the main status command. Frozen live helpers preserve the
exact version that executed; those later changes were not another live test.

Evidence:

- Review: `256f8be8d82772d044da1964b3d65286975d5c33dd8789b7684ab7936ca3477f`.
- Returned patch: `.runtime/strata-coding-1-review/256f8be8d82772d044da1964b3d65286975d5c33dd8789b7684ab7936ca3477f/returned.patch`.
- Execution result and inventory: same directory, `execution-result.json` and
  `execution-preservation.json`.
- Preservation SHA256: `2d98e87203e1bfabecbdc303e0b6eaf0c225fd1154a49459d4802f95bffdb23a`.
- Real response SHA256: `a669b04ce6899135c8eef1b06f85c8bc033da6d22171d1c2fedf07c80cb07e70`.
- Raw live request, actual OpenCode tool events, edited output, patch receipt,
  originals, CPU/GPU readings, native logs and stopped/process inspections retained.
  Docker events are an explicitly marked bounded excerpt.

All nine preceding model attempts and build/model/configuration evidence were
verified unchanged. Ten model attempts (nine API and one coding) are now consumed;
no retry/reset or further live workload is approved. Read the recorded outcome
with `python -B local_worker.py review-coding-task` or `status`; neither starts
hardware. Next review the pilot and choose a useful small task before expanding
this adapter.
