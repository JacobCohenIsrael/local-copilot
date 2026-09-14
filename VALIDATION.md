# Validation — 2026-09-14

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
