package dev.localcopilot;

import com.intellij.codeInsight.AutoPopupController;
import com.intellij.codeInsight.editorActions.TypedHandlerDelegate;
import com.intellij.ide.util.PropertiesComponent;
import com.intellij.openapi.editor.Editor;
import com.intellij.openapi.project.Project;
import com.intellij.psi.PsiFile;
import org.jetbrains.annotations.NotNull;

public final class CopilotTypedHandler extends TypedHandlerDelegate {
    @Override public @NotNull Result checkAutoPopup(char c, @NotNull Project project, @NotNull Editor editor, @NotNull PsiFile file) {
        if (PropertiesComponent.getInstance(project).getBoolean("localCopilot.autocomplete", false)
            && (Character.isJavaIdentifierPart(c) || c == '.' || c == ' ' || c == '=')) {
            AutoPopupController.getInstance(project).scheduleAutoPopup(editor);
        }
        return Result.CONTINUE;
    }
}
