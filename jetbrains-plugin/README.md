# Local Copilot for JetBrains

Initial tool-window plugin for WebStorm and Rider 2026.1–2026.2 (platform builds 261–262). Reuses this repository's TypeScript model client and local Ollama service. Compiled against WebStorm 2026.2.1; interactive IDE behavior and Rider compatibility still require the smoke checks below.

## Build and install on Windows

From the local-copilot repository:

```powershell
npm ci
npm run build
powershell -NoProfile -ExecutionPolicy Bypass -File .\jetbrains-plugin\build-local.ps1 -IdePath 'C:\Program Files\JetBrains\WebStorm 2026.2.1'
```

The packaging script uses the installed IDE's compiler and platform libraries; it needs `jbr/bin/javac.exe`. Output: `jetbrains-plugin/build/local-copilot-0.1.1.zip`.

In WebStorm or Rider, open **Settings → Plugins → gear menu → Install Plugin from Disk**, select that ZIP, and restart if prompted. The plugin is not published to Marketplace.

Alternatively, with Gradle installed and a compatible JDK 21+, run `gradle buildPlugin` or `gradle runIde` from this folder. This downloads the SDK declared in `build.gradle.kts`. The Gradle build has not been validated here; no Gradle wrapper is included.

## Use

1. Start Ollama using the repository setup instructions. The portable setup uses port **11435**.
2. Open your code project and **View → Tool Windows → Local Copilot**.
3. Set **Node executable** to `node` or its full path. Set **Full path to dist/src/ide-cli.js** to your built backend, for example `C:\Users\yaki_\Desktop\Projects\local-copilot\dist\src\ide-cli.js`. Set the host and installed model. These four preferences are saved per project.
4. Select code in an editor, or position the caret for an insertion. The current document is included, with unsaved edits. Use a single caret.
5. Attach context with **Choose files**, **Add open files**, or project-relative paths, one per line. Remove lines or use **Clear files** to exclude attachments. Open files are attached only when you choose that action. Unsaved document contents are captured when you click **Suggest**.
6. Enter a task and click **Suggest**. Selected code is the replacement range; without a selection, the caret is the insertion point. **Cancel** stops the backend process.
7. Review the explanation and editable replacement code. **Apply suggestion** updates the original document as an undoable edit. If that document changed or moved during generation, applying is refused; request a fresh suggestion. Apply does not save the file.

Each request launches a Node child process and sends JSON over stdin; no additional server is needed. The existing client restricts model calls to loopback Ollama. Generated code is not executed. Chat history, automatic inline completions, multi-file edits, and a Git review UI are not implemented.

**Keep model cached (5 minutes idle)** is enabled by default and saved per project. Each response renews the five-minute retention period. Uncheck it to unload after subsequent requests; the next request then pays the model reload cost. The bridge accepts an optional boolean `keepCache`, defaulting to `true` for existing IDE clients. Rebuild the backend to apply this default; rebuild and reinstall the plugin ZIP to get the checkbox.

## Context limits

If version 0.1.0 reports **The pipe has been ended**, check the backend path: it must end in `dist/src/ide-cli.js`, not `dist/src/cli.js`. The regular CLI exits without reading editor requests. Version 0.1.1 validates this setting and displays backend startup diagnostics in the result panel.

The target and each snapshot must be at most 30,000 UTF-16 code units. Additional context is limited to 20 files and 20,000 total code units; tasks to 8,000. Oversized requests fail visibly. Only existing local project files are supported: save a newly created file before using it; subsequent edits need not be saved.

The backend checks canonical paths with the existing `readSource` function. It excludes common sensitive filenames, generated directories, binaries, files above 128 KiB on disk, and symlinks escaping the project. Explicitly attached Git-ignored files can be included subject to those checks. Filename exclusions are not a general secret scanner. The IDE workflow includes only the target and explicit attachments, without heuristic repository context.

## Verification

`npm test` covers the JSON bridge with a local model stub, unsaved target/context text, UTF-16 selection offsets, invalid paths and limits, plus the original suggestion/review workflows. `build-local.ps1` compiles against the installed platform and packages the ZIP.

Interactive smoke checks still needed in each IDE:

- Request a selection replacement using unsaved target and attached files; verify the response reflects those edits.
- Apply and Undo; verify only the selection changes. Repeat with a caret insertion.
- Edit the target during generation and verify Apply refuses the stale result.
- Cancel, then request again; verify UI responsiveness and correct result routing.
- Attach a missing file, `.env`, or oversized file, and test with Ollama stopped; verify visible errors.

The plugin uses JetBrains' documented [tool-window APIs](https://plugins.jetbrains.com/docs/intellij/tool-windows.html) and [editor Document/selection APIs](https://plugins.jetbrains.com/docs/intellij/working-with-text.html), with the shared platform module to avoid language-specific dependencies.
