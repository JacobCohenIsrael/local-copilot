# Local Copilot

A local TypeScript command-line assistant that suggests code using repository context and reviews Git changes for actionable bugs. Output is printed for inspection; the tool does not edit your code or execute generated suggestions.

## From a fresh clone to a working copilot

### 1. Install prerequisites and clone

Install [Node.js](https://nodejs.org/) **22 or newer** (including npm) and [Git](https://git-scm.com/downloads). The portable setup below requires **Windows x64 and PowerShell**. For macOS, Linux, or an existing Ollama installation, use the alternative model setup below.

```powershell
git clone git@github.com:JacobCohenIsrael/local-copilot.git
cd local-copilot
node --version
npm --version
git --version
```

SSH requires a GitHub SSH key configured on your machine. For HTTPS authentication, clone with `git clone https://github.com/JacobCohenIsrael/local-copilot.git` instead, then enter the directory.

### 2. Install locked dependencies and build

```powershell
npm ci
npm run build
npm run typecheck
npm test
```

`npm ci` installs the exact dependencies from `package-lock.json`. TypeScript and Node.js types are development dependencies; the compiled CLI has no runtime package dependencies. Keep development dependencies installed to build and test. The build writes JavaScript and source maps to `dist/`.

All seven tests should pass. They use a local API stub and temporary Git repositories, so they do not require Ollama or model downloads.

### 3. Install and start the local model (Windows)

From the project directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-local-model.ps1
```

This permits the setup script for this PowerShell process only. The script:

- Downloads portable Ollama 0.34.0 and verifies its published SHA-256 checksum.
- Extracts Ollama into `.runtime/ollama` and downloads `qwen2.5-coder:7b` into `.runtime/models`.
- Starts a hidden service at **http://127.0.0.1:11435** with cloud features disabled.

Initial downloads total approximately **6.2 GB** (1.47 GB runtime archive plus 4.7 GB model); extraction needs additional disk space. Internet access is needed for installation; local inference can run offline. Ollama may create standard identity files in your user profile. Model speed and memory requirements depend on your hardware; this model was validated on a GPU with 16 GB VRAM.

### 4. Verify both workflows

```powershell
npm start -- doctor --host http://127.0.0.1:11435 --model qwen2.5-coder:7b
npm run demo
```

`doctor` should report an available service and list `qwen2.5-coder:7b`. The demo creates a disposable repository under `.runtime`, requests a division-by-zero guard, introduces a multiplication bug, and reviews it. Expect a code insertion and a finding at `math.js:2` recommending division. Outputs and timings are saved in the demo's `results.json`. It exits with an error if the review misses the changed line.

The copilot is ready to use on your repository. `npm start -- <command>` builds automatically. For JSON output without npm's banners, use `node dist/src/cli.js <command> --json` after building.

## JetBrains plugin (WebStorm and Rider 2026)

An initial plugin reuses this backend for suggestions from selected code, unsaved editor text, open files you attach, and explicit file lists. Responses can be reviewed and applied as undoable edits, with a stale-document check. See [plugin build, installation, and usage](jetbrains-plugin/README.md). Compilation was validated against WebStorm 2026.2.1; interactive IDE testing and Rider compatibility verification remain outstanding. Automatic inline completions are not included.

## Use on your code

Run from the local-copilot directory, replacing repository and file paths with your own. These examples use the portable service on port 11435.

### Suggest code

```powershell
npm start -- suggest --repo C:\path\to\your-repo --file src/math.ts --line 2 --task "Add a division-by-zero guard" --host http://127.0.0.1:11435 --model qwen2.5-coder:7b
```

The suggestion is code to **insert before** the specified 1-based line, plus an explanation. The file must exist, and its path is relative to `--repo`. Omitting `--line` appends at the end. Inspect the result and copy the desired code into your editor. This version provides requested suggestions, without inline editor completions or automatic refactoring.

### Review changes

```powershell
npm start -- review --repo C:\path\to\your-repo --host http://127.0.0.1:11435 --model qwen2.5-coder:7b
npm start -- review --repo C:\path\to\your-repo --staged --host http://127.0.0.1:11435 --model qwen2.5-coder:7b
```

Default review covers unstaged tracked changes; `--staged` covers staged changes, including newly added files. Stage untracked files to include them. Findings contain severity, file, changed-line number, old/new side, explanation, and suggested fix. Invalid locations cause a visible error. An empty findings list does not prove the code correct.

All commands support `--json`; see `npm start -- --help` for options. Set `LOCAL_COPILOT_MODEL` instead of passing `--model` if desired. The CLI defaults to port 11434, so keep passing `--host` for the portable service on 11435.

## Alternative: existing Ollama or macOS/Linux

Complete clone, `npm ci`, and build first. Install [Ollama](https://ollama.com/download) for your operating system if needed. Start its service:

```text
ollama serve
```

Leave that terminal running, or use an already running Ollama application; do not start a second service on the same port. In another terminal, from this project directory:

```text
ollama pull qwen2.5-coder:7b
npm start -- doctor --host http://127.0.0.1:11434 --model qwen2.5-coder:7b
```

Use `--host http://127.0.0.1:11434` for suggestions and reviews. The demo defaults to port 11435; override it for this setup:

```powershell
# PowerShell
$env:LOCAL_COPILOT_HOST = 'http://127.0.0.1:11434'
npm run demo
```

```sh
# macOS/Linux shell
LOCAL_COPILOT_HOST=http://127.0.0.1:11434 npm run demo
```

`LOCAL_COPILOT_HOST` is a demo setting; the CLI uses `--host`. Set `LOCAL_COPILOT_MODEL` to test another installed model. Configure existing Ollama installations for local inference; see [disabling cloud features](https://docs.ollama.com/faq). The client accepts only loopback origins, disables redirects, and rejects models advertised as remote. It uses Ollama's [structured chat API](https://docs.ollama.com/api/chat).

## Restarting, updating, and troubleshooting

- **After reboot:** rerun the portable setup script; existing runtime and model downloads are reused.
- **GPU memory after tasks:** CLI and demo requests unload the model after each response by default. Add `--keep-cache` to CLI suggestions or reviews to keep it loaded for five minutes after each response, reducing reload latency. The IDE defaults to caching, with a **Keep model cached (5 minutes idle)** checkbox to disable it. Caching expires after five minutes without another request; it does not pin the model indefinitely. The service and downloaded files remain available. `npm test` uses a stub and never loads or unloads a real model. Other applications or clients sharing Ollama may affect memory usage.
- **Stop the portable service:** run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local-model.ps1`. Logs and the service PID are in `.runtime`.
- **After pulling updates:** run `npm ci` and `npm run build` again.
- **Cannot reach the service:** start Ollama, check `.runtime/ollama.stderr.log` for portable setup, and confirm port 11435 versus 11434.
- **Model missing:** rerun portable setup or use `ollama pull` with your existing service, then run `doctor`.
- **No eligible changes:** confirm `--repo` points to a Git repository and select unstaged or `--staged` appropriately.
- **Invalid output or missed bugs:** retry or evaluate another model. The 7B model passed the example; the 1.5B model missed its known bug.
- **Timeout:** requests time out after three minutes. Reduce request size or use a model suited to your hardware.

## What belongs in Git

Commit TypeScript source and tests, setup scripts, documentation, `package.json`, **`package-lock.json`**, and `tsconfig.json`. The lockfile makes installs reproducible.

`.gitignore` excludes dependencies (`node_modules/`), builds (`dist/`), downloaded runtimes and model weights (`.runtime/`), coverage, caches, logs, local environment files, private keys, and personal IDE/OS files. A fresh clone recreates generated files through install/build/setup. Environment example files may be committed if they contain no secrets.

## Context and limitations

Suggestions include the target file and up to six related files selected by directory, filename, and project documentation. Git-ignored files are excluded from automatic context; explicit targets can be Git-ignored. Common secret files, generated directories, binaries, files over 128 KiB, and paths resolving outside the repository are excluded. These filename rules are not a general secret scanner.

Target files are limited to 30,000 characters, related suggestion context to 10,000 characters, and review diffs to 48,000 characters. Large reviews fail explicitly so you can stage smaller changes. Context is bounded and does not index the entire repository. Language support comes from your model; evaluate it on your code. Quality and latency depend on model and hardware.

See [VALIDATION.md](VALIDATION.md) for checks and limits. Automated tests exercise application behavior with a model API stub; the demo additionally checks real inference.
