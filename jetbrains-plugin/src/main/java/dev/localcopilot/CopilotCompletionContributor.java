package dev.localcopilot;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.intellij.codeInsight.completion.*;
import com.intellij.codeInsight.lookup.LookupElementBuilder;
import com.intellij.codeInsight.lookup.AutoCompletionPolicy;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.process.CapturingProcessHandler;
import com.intellij.execution.process.ProcessOutput;
import com.intellij.ide.util.PropertiesComponent;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.application.ReadAction;
import com.intellij.openapi.diagnostic.Logger;
import com.intellij.openapi.editor.Editor;
import com.intellij.openapi.fileEditor.FileDocumentManager;
import com.intellij.openapi.fileEditor.FileEditorManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.util.Key;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.wm.StatusBar;
import org.jetbrains.annotations.NotNull;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/** Completion callbacks only capture snapshots or return cached results. Never wait under their read lock. */
public final class CopilotCompletionContributor extends CompletionContributor {
    private static final Logger LOG = Logger.getInstance(CopilotCompletionContributor.class);
    private static final Key<Job> JOB = Key.create("localCopilot.completionJob");
    private static final class Job {
        final long stamp;
        final int offset;
        final String model, script, node, host;
        final boolean keepCache;
        volatile String code;
        Job(long stamp, int offset, PropertiesComponent settings) {
            this.stamp = stamp; this.offset = offset;
            model = settings.getValue("localCopilot.completionModel", "qwen2.5-coder:1.5b");
            script = settings.getValue("localCopilot.bridge", "");
            node = settings.getValue("localCopilot.node", "node");
            host = settings.getValue("localCopilot.host", "http://127.0.0.1:11435");
            keepCache = settings.getBoolean("localCopilot.keepCache", true);
        }
        boolean matches(Job other) {
            return stamp == other.stamp && offset == other.offset && model.equals(other.model)
                && script.equals(other.script) && node.equals(other.node) && host.equals(other.host) && keepCache == other.keepCache;
        }
    }

    @Override public void fillCompletionVariants(@NotNull CompletionParameters parameters, @NotNull CompletionResultSet result) {
        Project project = parameters.getOriginalFile().getProject();
        PropertiesComponent settings = PropertiesComponent.getInstance(project);
        if (!settings.getBoolean("localCopilot.autocomplete", false) || parameters.getCompletionType() != CompletionType.BASIC) return;
        result.restartCompletionOnAnyPrefixChange();
        Editor editor = parameters.getEditor();
        if (editor.getCaretModel().getCaretCount() != 1 || editor.getSelectionModel().hasSelection()) return;
        VirtualFile file = FileDocumentManager.getInstance().getFile(editor.getDocument());
        String base = project.getBasePath();
        if (file == null || !file.isInLocalFileSystem() || file.getFileType().isBinary() || base == null
            || editor.getDocument().getTextLength() > 30000) return;
        Job job = new Job(editor.getDocument().getModificationStamp(), parameters.getOffset(), settings);
        synchronized (editor) {
            Job previous = editor.getUserData(JOB);
            if (previous != null && previous.matches(job)) {
                if (previous.code != null && !previous.code.isBlank()) {
                    String prefix = result.getPrefixMatcher().getPrefix();
                    result.addElement(AutoCompletionPolicy.NEVER_AUTOCOMPLETE.applyPolicy(
                        LookupElementBuilder.create(prefix + previous.code)
                            .withPresentableText((prefix + previous.code).replace('\n', ' '))
                            .withTypeText("Local Copilot · " + job.model, true)));
                }
                return;
            }
            editor.putUserData(JOB, job);
        }
        String text = editor.getDocument().getText();
        String filePath = file.getPath();
        // Queue via the EDT so the background job inherits neither the completion read lock nor its cancellation context.
        ApplicationManager.getApplication().invokeLater(() -> {
            if (current(project, editor, job)) ApplicationManager.getApplication().executeOnPooledThread(
                () -> generate(project, editor, job, base, filePath, text));
        });
    }

    private static boolean current(Project project, Editor editor, Job job) {
        return ReadAction.compute(() -> !project.isDisposed() && !editor.isDisposed()
            && editor.getUserData(JOB) == job && editor.getDocument().getModificationStamp() == job.stamp
            && editor.getCaretModel().getOffset() == job.offset && !editor.getSelectionModel().hasSelection()
            && PropertiesComponent.getInstance(project).getBoolean("localCopilot.autocomplete", false)
            && job.matches(new Job(job.stamp, job.offset, PropertiesComponent.getInstance(project))));
    }

    private static void status(Project project, Editor editor, Job job, String message) {
        ApplicationManager.getApplication().invokeLater(() -> {
            if (current(project, editor, job)) StatusBar.Info.set("Local Copilot: " + message, project);
        });
    }

    private static void generate(Project project, Editor editor, Job job, String base, String filePath, String text) {
        CapturingProcessHandler handler = null;
        try {
            Thread.sleep(300);
            if (!current(project, editor, job)) return;
            if (job.script.isBlank() || !Path.of(job.script).isAbsolute() || !Files.isRegularFile(Path.of(job.script))
                || !Path.of(job.script).getFileName().toString().equals("ide-cli.js"))
                throw new IllegalArgumentException("Set the full path to dist/src/ide-cli.js in the Local Copilot panel.");
            Path root = Path.of(base).toAbsolutePath().normalize(), absolute = Path.of(filePath).toAbsolutePath().normalize();
            if (!absolute.startsWith(root)) return;
            String relative = root.relativize(absolute).toString().replace('\\', '/');
            Gson gson = new Gson();
            String request = gson.toJson(Map.of("version", 1, "command", "complete", "root", root.toString(),
                "host", job.host, "model", job.model, "keepCache", job.keepCache,
                "target", Map.of("file", relative, "text", text, "start", job.offset)));
            status(project, editor, job, "Generating autocomplete with " + job.model + "…");
            handler = new CapturingProcessHandler(new GeneralCommandLine(job.node, job.script).withCharset(StandardCharsets.UTF_8));
            handler.startNotify();
            try (var stdin = handler.getProcess().getOutputStream()) { stdin.write(request.getBytes(StandardCharsets.UTF_8)); }
            long deadline = System.nanoTime() + 15_000_000_000L;
            while (!handler.waitFor(50)) {
                if (!current(project, editor, job)) return;
                if (System.nanoTime() > deadline) throw new IllegalStateException("Autocomplete timed out; try a faster model.");
            }
            if (!current(project, editor, job)) return;
            ProcessOutput output = handler.runProcess(1000, true);
            if (output.getExitCode() != 0) throw new IllegalStateException(output.getStderr());
            JsonObject response = gson.fromJson(output.getStdout(), JsonObject.class);
            if (response == null || response.get("version").getAsInt() != 1 || response.get("start").getAsInt() != job.offset
                || !response.get("file").getAsString().equals(relative)) throw new IllegalStateException("Invalid completion response.");
            job.code = response.get("code").getAsString().replace("\r\n", "\n").replace('\r', '\n');
            status(project, editor, job, job.code.isBlank() ? "No autocomplete suggestion at this caret." : "Autocomplete ready — look for Local Copilot in the completion popup.");
            if (!job.code.isBlank()) ApplicationManager.getApplication().invokeLater(() -> {
                if (current(project, editor, job) && FileEditorManager.getInstance(project).getSelectedTextEditor() == editor
                    && editor.getContentComponent().isFocusOwner()) {
                    new CodeCompletionHandlerBase(CompletionType.BASIC, false, true, false).invokeCompletion(project, editor, 0);
                }
            });
        } catch (InterruptedException ex) { Thread.currentThread().interrupt(); }
        catch (Exception ex) {
            job.code = "";
            LOG.warn("Local Copilot autocomplete failed", ex);
            status(project, editor, job, "Autocomplete failed: " + ex.getMessage());
        } finally {
            if (handler != null && !handler.isProcessTerminated()) handler.destroyProcess();
            if (job.code == null) ApplicationManager.getApplication().invokeLater(() -> {
                if (!editor.isDisposed()) synchronized (editor) {
                    if (editor.getUserData(JOB) == job) editor.putUserData(JOB, null);
                }
            });
        }
    }
}
