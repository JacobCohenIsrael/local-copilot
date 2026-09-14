# Validation — 2026-09-14

## Template-string completion repair

Qwen2.5-Coder autocomplete now uses `/api/generate` with `raw: true` and its native fill-in-the-middle tokens, preserving the exact bounded source prefix and suffix. Models outside that named family retain the instruction-based fallback. Local-model validation, cache settings, and response limits apply to both paths. The design follows [Qwen's tokenizer definitions](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct/blob/main/tokenizer_config.json) and [Ollama's generation API](https://docs.ollama.com/api/generate).

All 11 tests pass, including exact UTF-16 caret splitting in a template string, insertion reconstruction without duplicating suffix code, Qwen routing without chat messages, cache settings, empty output, malformed responses, and cloud-model rejection. Live checks using the current CLI source and both installed Qwen2.5-Coder 1.5B and 7B returned `{safe(errorMessage(error))}` when the caret followed the `$` in the incomplete `safeMessage` template literal. This validates the reported example, not general completion quality.

## Manual autocomplete preview (plugin 0.2.2)

Added a dedicated Autocomplete tab with Generate autocomplete, model/target details, an editable preview, visible failure/empty states, and an undoable Insert at captured caret action. Manual generation uses the existing `complete` bridge command and separate autocomplete model without requiring the automatic-completion setting or task text. It shares the panel's cancellation and request-generation guards; insertion checks the original document modification stamp, path, and writability. Compilation and packaging against the installed WebStorm SDK passed. Interactive button, cancellation, insertion/Undo, and stale-document smoke checks remain pending after installation.

## Autocomplete repair (plugin 0.2.1)

The installed WebStorm 2026.2.2 log identified `Synchronous execution under ReadAction` in the 0.2.0 completion contributor. Inference now runs in a separate pooled task, with a cache-only completion callback, stale-request cancellation, and a popup refresh when a result arrives. The plugin compiles against the installed SDK. All 10 backend tests pass, including new cases for accepting a single Markdown code fence and rejecting mixed prose/fences. A real 1.5B-model completion returned through the bridge; it produced a whole function for an insertion prompt, so completion quality remains model-dependent. Interactive verification of the repaired popup is still pending after installing 0.2.1.

## Chat and autocomplete (plugin 0.2.0)

`npm test` passed all 10 tests, including the original seven workflows, plain-text chat and history validation, interactive CLI history/reset, one-shot JSON chat, and completion model routing with bounded unsaved caret context. The test runner required permission to spawn Node/Git subprocesses outside the Windows sandbox. A real CLI chat request against the local `qwen2.5-coder:7b` service on port 11435 returned a greeting successfully.

`build-local.ps1` compiled the tool window, completion contributor, and typed handler against installed WebStorm 2026.2.1 and produced `local-copilot-0.2.0.zip`. Chat and automatic popup completion still require interactive smoke tests in WebStorm and Rider: acceptance/Undo, cancellation while typing, stale results, settings changes, and multi-turn chat. No live IDE interaction or real-model autocomplete quality benchmark was performed. The older validation sections below describe earlier milestones.

## Fresh-install verification

Before the first project push, the staged source snapshot was exported to an empty directory without `node_modules`, `dist`, or model files. `npm ci`, `npm run build`, `npm run typecheck`, and `npm test` all passed; all five tests passed. `npm run demo` also passed using the existing local Ollama service on port 11435. This verifies reconstruction of the application from committed files; the previously validated portable runtime download was not repeated for this check.

## TypeScript conversion

All application modules, the demo, and the test suite now use strict TypeScript. `npm run typecheck` passed; `npm test` compiled the project and passed all five tests. `npm start -- --help` and the compiled `doctor` command also passed.

`npm run demo` passed against the installed Qwen2.5-Coder 7B model after conversion. The generated zero guard was correct, and review identified the arithmetic regression at `math.js:2` with the correct fix. The compiled demo wrote evidence to the project-level `.runtime/demo-FWDtWx/results.json`, confirming that the new build layout preserves runtime paths. Recorded times were 4.13 seconds for the suggestion and 2.05 seconds for review.

The sections below preserve the original implementation validation. Its direct source-JavaScript commands are historical; current usage is documented in README.md.

## Environment

Windows x64, Node.js 24.20.0, Git, portable Ollama 0.34.0, Qwen2.5-Coder 7B. Ollama detected an NVIDIA RTX 3080 Ti Laptop GPU with 16 GB VRAM. The project service listens on 127.0.0.1:11435 with cloud features disabled. Its runtime and model files are stored under `.runtime`.

## Verified behavior

- `npm test`: five tests passed. Coverage includes cursor-aware suggestions, relevant repository context, unchanged source files, staged and unstaged reviews, rejection of nonexistent and unchanged-line findings, excluded files, path containment, deletion-side locations, CLI JSON output, service discovery, and invalid CLI arguments. The model API is stubbed in these tests.
- `node scripts/demo.js`: passed against the real 7B model. The suggestion inserted a zero-divisor guard before line 2. Review identified that `return a * b` incorrectly replaced division, cited `math.js:2` on the new side, and recommended restoring `return a / b`.
- The exact generated insertion was inspected and executed in a test function. `divide(6, 2)` returned 3, `divide(0, 2)` returned 0, and `divide(6, 0)` threw the expected Error.
- The user-facing `review --json` command also returned the correct finding against the real model.
- `doctor` successfully discovered the installed local model service.

Raw successful demonstration evidence is in `.runtime/demo-iYsJ2O/results.json`. Loaded-model timings were 1.83 seconds for the suggestion and 2.07 seconds for review. These are individual measurements on this machine, not latency guarantees.

## Quality limits

The 1.5B model missed the introduced bug. The initial 7B review identified it but cited a nearby line; the implementation now supplies explicitly numbered changed lines and rejects findings anchored to unchanged lines. The final real-model check passed with this correction.

This verifies a working local suggestion and review workflow on a small JavaScript example. It is not a broad model-quality benchmark. Larger repositories, other languages, complex bugs, and different hardware require further evaluation. Output remains a proposal for human inspection. Editor integration, automatic edits, and full-repository semantic indexing are outside the current implementation.
