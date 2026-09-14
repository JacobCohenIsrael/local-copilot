# Local Copilot

## Goal

Create a local copilot that can suggest code and provide code reviews.

## Initial success criteria

- Run on the user's machine and work with a local code repository.
- Suggest relevant code using the current file and surrounding project context.
- Review code changes and return actionable findings with file and line references, explanations, and suggested fixes.
- Let the user inspect suggestions before applying them.
- Provide clear setup instructions and a repeatable demonstration of both code suggestions and code review.

## Implementation decisions

- Interface: command-line tool, with human-readable and JSON output.
- Model runtime: local Ollama; portable Windows setup disables cloud features.
- Verified model: Qwen2.5-Coder 7B. The smaller 1.5B model failed the review demonstration.
- Initial validation language: JavaScript. Other text-based languages depend on model capability and need project-specific evaluation.
- Hardware used: Windows, Node.js 24, NVIDIA RTX 3080 Ti Laptop GPU with 16 GB VRAM. Loaded-model demonstration requests took approximately two seconds each.

## Initial milestones

1. Choose the interface and model runtime, and define a small end-to-end example.
2. Implement code suggestions with relevant repository context.
3. Implement review of local diffs with actionable findings.
4. Validate both workflows on representative examples and document setup and limitations.

## Current status

Implemented a TypeScript CLI backed by a loopback Ollama service. Source, demo, and tests use strict TypeScript and compile to `dist/`; the compiled Node.js CLI has no runtime package dependencies.

- `suggest`: insertion suggestions using target-file and related repository context.
- `review`: staged or unstaged Git diff reviews with validated file/line references.
- `doctor`: local service and installed-model discovery.
- Setup instructions and a repeatable model demonstration are in README.md.
- Five automated tests passed on Windows, covering the CLI and Git workflows against a local API stub.
- TypeScript migration verified with `npm run typecheck`, `npm test`, and `npm run demo` against the installed local model.

Real inference is verified with the 7B model on the local service at http://127.0.0.1:11435. The generated insertion passed functional checks, and both the demonstration and user-facing review command identified the introduced bug at the correct line with an actionable fix. See VALIDATION.md for evidence and limits.
