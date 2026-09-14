# Local Copilot for JetBrains

Initial tool-window plugin for WebStorm and Rider 2026.1–2026.2 (platform builds 261–262). Reuses this repository's TypeScript model client and local Ollama service. Compiled against WebStorm 2026.2.1; interactive IDE behavior and Rider compatibility still require the smoke checks below.

## Build and install on Windows

From the local-copilot repository:

```powershell
npm ci
npm run build
powershell -NoProfile -ExecutionPolicy Bypass -File .\jetbrains-plugin\build-local.ps1 -IdePath 'C:\Program Files\JetBrains\WebStorm 2026.2.1'
```

The packaging script uses the installed IDE's compiler and platform libraries; it needs `jbr/bin/javac.exe`. Output: `jetbrains-plugin/build/local-copilot-0.2.2.zip`.

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

Each request launches a Node child process and sends JSON over stdin; no additional server is needed. The existing client restricts model calls to loopback Ollama. Generated code is not executed. Multi-file edits and a Git review UI are not implemented.

### Chat

Enter a message in the task/message box and click **Send chat**. Replies appear in the **Chat** tab. Follow-up messages include previous successful turns. **New chat** clears the in-memory conversation, and **Cancel** stops the current request. Chat uses **Chat / suggestion model** and works without an open editor. It sends only messages, not the selected file or attachments. History is not saved across project closes. At 20 user turns or 30,000 characters, start a new chat.

### Automatic autocomplete

To try autocomplete directly, open the **Autocomplete** tab in the Local Copilot panel:

1. Place a single caret in a saved project source file, with no selection.
2. Click **Generate autocomplete**. No task text is needed. This uses the **Autocomplete model** and works even with automatic completion disabled.
3. The tab shows the model, target file/line, and generated code. Failures and empty responses appear here too. Use **Cancel** to stop a pending request.
4. Review or edit the preview, then click **Insert at captured caret**. The insertion goes into the original document at the captured position and supports Undo. If the document changed or moved, generate again. Nothing is inserted automatically.

Each click makes a fresh request using the same completion backend as the automatic popup. The preview contains one candidate; click Generate again to request another. You can use this tab independently of all built-in IDE completion features.

For models named `qwen2.5-coder` (including their size tags), autocomplete uses native fill-in-the-middle generation: the source before and after the caret surrounds the missing insertion. This avoids the conversational/JSON prompt used by earlier backend versions. Other models retain an instruction-based completion fallback; their insertion quality varies. Chat and requested suggestions keep using the chat API. Rebuild the backend after updating; this change does not require reinstalling the plugin.

Set **Autocomplete model (installed locally)** to the name of a model installed in your Ollama service, then check **Enable automatic code completion**. Both settings save immediately per project. The default model name is `qwen2.5-coder:1.5b`; install it separately if you want to use it, or enter another installed model. Chat and requested suggestions continue to use their own model field.

Type in a saved project text file. Short suggestions appear in the normal completion popup, labeled **Local Copilot** and the model name. Select one and accept with the IDE's usual completion key (Enter/Tab); Escape dismisses the popup. Basic completion can also be invoked manually. This is popup completion, not inline ghost text. Automatic completion is disabled until you enable it.

Requests debounce for 300 ms, send up to 6,000 characters before and 2,000 after the caret from the unsaved document, and request at most 128 output tokens. Model inference runs outside the completion callback; that callback immediately returns cached results. A ready result refreshes the popup if the editor is still focused. Changed documents/carets discard stale results and stop their bridge processes. Slow requests time out after 15 seconds overall. The status bar reports generating, ready, empty results, and failures; errors are also logged. Files over 30,000 characters, selections, and multiple carets are skipped. Explicit attachment paths are not included in autocomplete. Model speed and language support vary; Rider language integration still needs interactive verification.

Version 0.2.1 fixes 0.2.0's synchronous process wait inside an IDE read action, which WebStorm reported as an error. Reinstall the new ZIP and restart the IDE. The backend also accepts completions wrapped in a single Markdown code fence; rebuild it with `npm run build` when updating source.

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
- Send two chat messages without an editor open; verify the second reply remembers the first. Test New chat and Cancel.
- Enable autocomplete with a separately installed model; type, accept a popup suggestion, and Undo. Keep typing during inference and verify stale completions disappear.
- Change the autocomplete model and disable autocomplete; verify subsequent requests follow those settings without affecting chat.
- With automatic completion disabled and the task box empty, generate from the Autocomplete tab. Verify model/target details, preview, insertion and Undo. Edit the target before inserting and verify the stale result is refused. Test Cancel, an unavailable model, and an empty response.

The plugin uses JetBrains' documented [tool-window APIs](https://plugins.jetbrains.com/docs/intellij/tool-windows.html) and [editor Document/selection APIs](https://plugins.jetbrains.com/docs/intellij/working-with-text.html), with the shared platform module to avoid language-specific dependencies.
