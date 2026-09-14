package dev.localcopilot;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.intellij.execution.configurations.GeneralCommandLine;
import com.intellij.execution.process.CapturingProcessHandler;
import com.intellij.execution.process.ProcessOutput;
import com.intellij.ide.util.PropertiesComponent;
import com.intellij.openapi.Disposable;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.command.WriteCommandAction;
import com.intellij.openapi.editor.Document;
import com.intellij.openapi.editor.Editor;
import com.intellij.openapi.fileChooser.FileChooser;
import com.intellij.openapi.fileChooser.FileChooserDescriptor;
import com.intellij.openapi.fileEditor.FileDocumentManager;
import com.intellij.openapi.fileEditor.FileEditorManager;
import com.intellij.openapi.project.DumbAware;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.vfs.LocalFileSystem;
import com.intellij.openapi.vfs.VirtualFile;
import com.intellij.openapi.wm.ToolWindow;
import com.intellij.openapi.wm.ToolWindowFactory;
import com.intellij.openapi.wm.ToolWindowManager;
import com.intellij.ui.content.Content;
import org.jetbrains.annotations.NotNull;

import javax.swing.*;
import java.awt.BorderLayout;
import java.awt.GridLayout;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

public final class CopilotToolWindowFactory implements ToolWindowFactory, DumbAware {
    @Override
    public void createToolWindowContent(@NotNull Project project, @NotNull ToolWindow toolWindow) {
        Panel panel = new Panel(project);
        Content content = toolWindow.getContentManager().getFactory().createContent(panel, "", false);
        content.setDisposer(panel);
        toolWindow.getContentManager().addContent(content);
    }

    private static final class Panel extends JPanel implements Disposable {
        private final Project project;
        private final Gson gson = new Gson();
        private final JTextField node = new JTextField("node");
        private final JTextField bridge = new JTextField();
        private final JTextField host = new JTextField("http://127.0.0.1:11435");
        private final JTextField model = new JTextField("qwen2.5-coder:7b");
        private final JCheckBox keepCache = new JCheckBox("Keep model cached (5 minutes idle)");
        private final JTextArea paths = new JTextArea(4, 25);
        private final JTextArea task = new JTextArea(3, 25);
        private final JTextArea explanation = new JTextArea(3, 25);
        private final JTextArea code = new JTextArea(12, 25);
        private final JLabel status = new JLabel("Select code in an editor, then enter a task.");
        private final JButton send = new JButton("Suggest");
        private final JButton cancel = new JButton("Cancel");
        private final JButton apply = new JButton("Apply suggestion");
        private volatile CapturingProcessHandler running;
        private volatile boolean disposed;
        private volatile long generation;
        private Snapshot pending;

        Panel(Project project) {
            super(new BorderLayout(6, 6));
            this.project = project;
            PropertiesComponent settings = PropertiesComponent.getInstance(project);
            JTextField[] fields = {node, bridge, host, model};
            String[] keys = {"node", "bridge", "host", "model"};
            String[] labels = {"Node executable", "Full path to dist/src/ide-cli.js", "Ollama host", "Local model"};
            JPanel config = new JPanel(new GridLayout(0, 1, 2, 2));
            for (int i = 0; i < fields.length; i++) {
                fields[i].setText(settings.getValue("localCopilot." + keys[i], fields[i].getText()));
                config.add(new JLabel(labels[i]));
                config.add(fields[i]);
            }
            JPanel input = new JPanel();
            keepCache.setSelected(settings.getBoolean("localCopilot.keepCache", true));
            keepCache.addActionListener(e -> settings.setValue("localCopilot.keepCache", keepCache.isSelected(), true));
            config.add(keepCache);
            input.setLayout(new BoxLayout(input, BoxLayout.Y_AXIS));
            input.add(config);
            input.add(new JLabel("Context paths (one project-relative file per line)"));
            input.add(new JScrollPane(paths));
            JPanel attachments = new JPanel();
            JButton choose = new JButton("Choose files");
            JButton open = new JButton("Add open files");
            JButton clear = new JButton("Clear files");
            attachments.add(choose); attachments.add(open); attachments.add(clear);
            input.add(attachments);
            input.add(new JLabel("Task (current file and selection included automatically)"));
            task.setLineWrap(true); task.setWrapStyleWord(true);
            input.add(new JScrollPane(task));
            JPanel actions = new JPanel();
            actions.add(send); actions.add(cancel); actions.add(apply);
            input.add(actions);
            explanation.setEditable(false); explanation.setLineWrap(true); explanation.setWrapStyleWord(true);
            JPanel result = new JPanel(new BorderLayout(4, 4));
            result.add(new JScrollPane(explanation), BorderLayout.NORTH);
            result.add(new JScrollPane(code), BorderLayout.CENTER);
            JSplitPane split = new JSplitPane(JSplitPane.VERTICAL_SPLIT, new JScrollPane(input), result);
            split.setResizeWeight(0.55);
            add(split, BorderLayout.CENTER); add(status, BorderLayout.SOUTH);
            apply.setEnabled(false); cancel.setEnabled(false);
            choose.addActionListener(e -> FileChooser.chooseFiles(new FileChooserDescriptor(true, false, false, false, false, true), project, null,
                files -> addFiles(files)));
            open.addActionListener(e -> addFiles(List.of(FileEditorManager.getInstance(project).getOpenFiles())));
            clear.addActionListener(e -> paths.setText(""));
            send.addActionListener(e -> suggest());
            cancel.addActionListener(e -> { stop(); status.setText("Cancelled."); });
            apply.addActionListener(e -> apply());
        }

        private Path root() {
            if (project.getBasePath() == null) throw new IllegalStateException("Open a local project first.");
            return Path.of(project.getBasePath()).toAbsolutePath().normalize();
        }

        private String relative(VirtualFile file) {
            if (!file.isInLocalFileSystem() || file.isDirectory()) throw new IllegalArgumentException("Choose local text files.");
            Path absolute = Path.of(file.getPath()).toAbsolutePath().normalize();
            if (!absolute.startsWith(root())) throw new IllegalArgumentException("File is outside the project: " + file.getName());
            return root().relativize(absolute).toString().replace('\\', '/');
        }

        private void addFiles(List<VirtualFile> files) {
            LinkedHashSet<String> selected = new LinkedHashSet<>(paths.getText().lines().filter(s -> !s.isBlank()).toList());
            int skipped = 0;
            for (VirtualFile file : files) {
                try { selected.add(relative(file)); }
                catch (IllegalArgumentException ex) { skipped++; }
            }
            paths.setText(String.join("\n", selected));
            status.setText(selected.size() + " attached paths; " + skipped + " non-project files skipped.");
        }

        private Map<String, Object> snapshot(VirtualFile file, Document document) {
            if (document == null || file.getFileType().isBinary()) throw new IllegalArgumentException("Not a text document: " + file.getName());
            if (document.getTextLength() > 30000) throw new IllegalArgumentException("File exceeds 30,000 characters: " + file.getName());
            return Map.of("file", relative(file), "text", document.getText());
        }

        private void suggest() {
            try {
                Editor editor = FileEditorManager.getInstance(project).getSelectedTextEditor();
                if (editor == null) throw new IllegalArgumentException("Focus a project text editor first.");
                if (editor.getCaretModel().getCaretCount() != 1) throw new IllegalArgumentException("Use a single caret/selection.");
                if (task.getText().isBlank()) throw new IllegalArgumentException("Enter a task first.");
                Path bridgePath = Path.of(bridge.getText().trim());
                if (!bridgePath.isAbsolute() || !java.nio.file.Files.isRegularFile(bridgePath))
                    throw new IllegalArgumentException("Set the full path to the built dist/src/ide-cli.js.");
                if (!bridgePath.getFileName().toString().equals("ide-cli.js"))
                    throw new IllegalArgumentException("Select dist/src/ide-cli.js. The regular cli.js does not accept editor requests.");
                Document document = editor.getDocument();
                VirtualFile file = FileDocumentManager.getInstance().getFile(document);
                if (file == null) throw new IllegalArgumentException("Save this file in the project before using it.");
                Map<String, Object> target = new java.util.HashMap<>(snapshot(file, document));
                int start = editor.getSelectionModel().hasSelection() ? editor.getSelectionModel().getSelectionStart() : editor.getCaretModel().getOffset();
                int end = editor.getSelectionModel().hasSelection() ? editor.getSelectionModel().getSelectionEnd() : start;
                target.put("start", start); target.put("end", end);
                Snapshot captured = new Snapshot(file, document, document.getModificationStamp(), file.getPath(), start, end);
                List<Map<String, Object>> context = new ArrayList<>();
                for (String name : new LinkedHashSet<>(paths.getText().lines().filter(s -> !s.isBlank()).toList())) {
                    VirtualFile attached = LocalFileSystem.getInstance().findFileByNioFile(root().resolve(name).normalize());
                    if (attached == null) throw new IllegalArgumentException("Context file not found: " + name);
                    if (!attached.equals(file)) context.add(snapshot(attached, FileDocumentManager.getInstance().getDocument(attached)));
                }
                if (context.size() > 20) throw new IllegalArgumentException("Attach at most 20 context files.");
                String request = gson.toJson(Map.of("version", 1, "root", root().toString(), "task", task.getText(), "target", target,
                    "context", context, "host", host.getText().trim(), "model", model.getText().trim(), "keepCache", keepCache.isSelected()));
                String executable = node.getText().trim(), script = bridge.getText().trim();
                PropertiesComponent settings = PropertiesComponent.getInstance(project);
                settings.setValue("localCopilot.node", executable); settings.setValue("localCopilot.bridge", script);
                settings.setValue("localCopilot.host", host.getText()); settings.setValue("localCopilot.model", model.getText());
                long id = ++generation;
                pending = null; apply.setEnabled(false); send.setEnabled(false); cancel.setEnabled(true);
                code.setText(""); explanation.setText("");
                status.setText("Generating for " + relative(file) + " with " + context.size() + " attached files...");
                ApplicationManager.getApplication().executeOnPooledThread(() -> {
                    CapturingProcessHandler handler = null;
                    try {
                        handler = new CapturingProcessHandler(new GeneralCommandLine(executable, script).withCharset(StandardCharsets.UTF_8));
                        synchronized (this) {
                            if (disposed || generation != id) { handler.destroyProcess(); return; }
                            running = handler;
                        }
                        try (var stdin = handler.getProcess().getOutputStream()) {
                            stdin.write(request.getBytes(StandardCharsets.UTF_8));
                        } catch (java.io.IOException pipeError) {
                            // A startup failure may close stdin before we finish writing. Preserve
                            // the child process diagnostic instead of reporting only a broken pipe.
                            ProcessOutput failure = handler.runProcess(5000, true);
                            String detail = failure.getStderr().isBlank() ? failure.getStdout() : failure.getStderr();
                            throw new IllegalStateException("Backend closed its input. Check the Node executable and dist/src/ide-cli.js path. "
                                + (detail.isBlank() ? pipeError.getMessage() : detail.strip()));
                        }
                        ProcessOutput output = handler.runProcess(390000, true);
                        if (output.isTimeout()) throw new IllegalStateException("Request timed out.");
                        if (output.getExitCode() != 0) throw new IllegalStateException(output.getStderr().isBlank() ? "Backend failed." : output.getStderr());
                        JsonObject response = gson.fromJson(output.getStdout(), JsonObject.class);
                        if (response == null || response.get("version").getAsInt() != 1
                            || response.get("start").getAsInt() != start || response.get("end").getAsInt() != end
                            || !response.get("file").getAsString().equals(target.get("file"))) throw new IllegalStateException("Invalid backend response.");
                        String replacement = response.get("code").getAsString().replace("\r\n", "\n").replace('\r', '\n');
                        String detail = response.get("explanation").getAsString();
                        ui(id, () -> {
                            pending = captured; code.setText(replacement); explanation.setText(detail);
                            apply.setEnabled(true); status.setText("Review the replacement, then Apply. Undo is supported.");
                        });
                    } catch (Exception ex) {
                        ui(id, () -> showError(ex));
                    } finally {
                        if (handler != null && !handler.isProcessTerminated()) handler.destroyProcess();
                        synchronized (this) { if (running == handler) running = null; }
                        ui(id, () -> { send.setEnabled(true); cancel.setEnabled(false); });
                    }
                });
            } catch (Exception ex) { showError(ex); }
        }

        private void showError(Exception ex) {
            status.setText("Request failed; see details above.");
            explanation.setText("Error: " + ex.getMessage());
            explanation.setCaretPosition(0);
        }

        private void ui(long id, Runnable action) {
            if (!disposed && !project.isDisposed()) ToolWindowManager.getInstance(project).invokeLater(() -> {
                if (!disposed && !project.isDisposed() && generation == id) action.run();
            });
        }

        private void apply() {
            Snapshot captured = pending;
            if (captured == null) return;
            WriteCommandAction.runWriteCommandAction(project, () -> {
                if (!captured.file.isValid() || !captured.file.isWritable() || !captured.document.isWritable()
                    || !captured.file.getPath().equals(captured.path) || captured.document.getModificationStamp() != captured.stamp) {
                    status.setText("Target changed or is read-only. Request a fresh suggestion.");
                } else {
                    captured.document.replaceString(captured.start, captured.end, code.getText());
                    status.setText("Applied to " + captured.file.getName() + ". Use Undo to revert.");
                }
            });
            pending = null; apply.setEnabled(false);
        }

        private synchronized void stop() {
            generation++;
            CapturingProcessHandler handler = running;
            if (handler != null) handler.destroyProcess();
            send.setEnabled(true); cancel.setEnabled(false); apply.setEnabled(false); pending = null;
        }

        @Override public synchronized void dispose() { disposed = true; generation++; if (running != null) running.destroyProcess(); }
        private record Snapshot(VirtualFile file, Document document, long stamp, String path, int start, int end) {}
    }
}
