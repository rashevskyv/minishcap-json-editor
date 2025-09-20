# --- START OF FILE components/session_bootstrap_dialog.py ---
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)


class SessionBootstrapDialog(QDialog):
    """Dialog that shows the system prompt and collects optional session instructions."""

    def __init__(self, parent, system_prompt: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI переклад – початок сесії")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        intro_label = QLabel(
            "Ознайомтеся з системним промптом перед початком діалогу. "
            "За потреби додайте власні інструкції для всієї сесії."
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        system_view = QPlainTextEdit(self)
        system_view.setReadOnly(True)
        system_view.setPlainText(system_prompt)
        system_view.setMinimumHeight(240)
        layout.addWidget(system_view)

        instructions_label = QLabel("Додаткові інструкції (опційно):", self)
        instructions_label.setWordWrap(True)
        layout.addWidget(instructions_label)

        self._instructions_edit = QPlainTextEdit(self)
        self._instructions_edit.setPlaceholderText("Напишіть, що слід враховувати упродовж сесії...")
        self._instructions_edit.setMinimumHeight(120)
        layout.addWidget(self._instructions_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_instructions(self) -> str:
        return self._instructions_edit.toPlainText().strip()
