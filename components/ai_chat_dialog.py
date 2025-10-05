# --- START OF FILE components/ai_chat_dialog.py ---
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QTextBrowser,
    QPlainTextEdit, QComboBox, QPushButton, QHBoxLayout, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QObject
from PyQt5.QtGui import QTextCursor


class _ChatInputEventFilter(QObject):
    def __init__(self, parent):
        super().__init__(parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                obj.parent().message_sent.emit()
                return True
        return super().eventFilter(obj, event)


class _ChatTab(QWidget):
    message_sent = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        controls_layout = QHBoxLayout()
        self.model_combo = QComboBox(self)
        controls_layout.addWidget(self.model_combo)
        layout.addLayout(controls_layout)

        self.history_view = QTextBrowser(self)
        self.history_view.setOpenExternalLinks(True)
        layout.addWidget(self.history_view, 1)

        input_layout = QHBoxLayout()
        self.input_edit = QPlainTextEdit(self)
        self.input_edit.setFixedHeight(100)
        self.input_edit.setPlaceholderText("Enter your message... (Ctrl+Enter to send)")
        input_layout.addWidget(self.input_edit)

        self.send_button = QPushButton("Send", self)
        self.send_button.setFixedSize(80, 100)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #003c6c;
            }
        """)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)

        self._event_filter = _ChatInputEventFilter(self)
        self.input_edit.installEventFilter(self._event_filter)
        self.send_button.clicked.connect(self.message_sent.emit)

    def populate_models(self, providers_data: dict):
        self.model_combo.clear()
        for provider_key, provider_info in providers_data.items():
            display_name = provider_info.get('display_name', provider_key)
            self.model_combo.addItem(f"{display_name}: {provider_info['model']}", provider_key)


class AIChatDialog(QDialog):
    message_sent = pyqtSignal(int, str, str)  # tab_index, message, provider_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Chat")
        self.resize(700, 800)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        main_layout.addWidget(self.tabs)

        self.tabs.tabBar().installEventFilter(self)

        self.add_tab_button = QPushButton("+")
        self.add_tab_button.setToolTip("New Chat Session")
        self.tabs.setCornerWidget(self.add_tab_button, Qt.TopLeftCorner)
        
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        
        self._set_theme_styles()

    def _set_theme_styles(self):
        is_dark = self.palette().window().color().lightness() < 128
        user_bg = "#2E2E2E" if is_dark else "#F0F0F0"
        ai_bg = "#383838" if is_dark else "#F9F9F9"
        
        style = f"""
            .user-message {{
                background-color: {user_bg};
                border-radius: 5px;
                padding: 8px;
                margin-bottom: 8px;
            }}
            .ai-message {{
                background-color: {ai_bg};
                border-radius: 5px;
                padding: 8px;
                margin-bottom: 8px;
            }}
        """
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, _ChatTab):
                tab.history_view.document().setDefaultStyleSheet(style)

    def eventFilter(self, obj, event):
        if obj == self.tabs.tabBar() and event.type() == QEvent.MouseButtonPress and event.button() == Qt.MiddleButton:
            tab_index = obj.tabAt(event.pos())
            if tab_index != -1:
                self.remove_tab(tab_index)
                return True
        return super().eventFilter(obj, event)

    def add_new_tab(self):
        tab_index = self.tabs.count()
        new_tab = _ChatTab(self)
        self.tabs.addTab(new_tab, f"Chat {tab_index + 1}")
        
        self._set_theme_styles()
        
        new_tab.message_sent.connect(lambda: self._emit_message_sent(self.tabs.indexOf(new_tab)))
        self.tabs.setCurrentIndex(tab_index)
        return new_tab

    def remove_tab(self, index: int):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            self.close()

    def _emit_message_sent(self, tab_index):
        if tab_index < 0: return
        tab = self.tabs.widget(tab_index)
        if isinstance(tab, _ChatTab):
            message = tab.input_edit.toPlainText().strip()
            provider_key = tab.model_combo.currentData()
            if message and provider_key:
                self.message_sent.emit(tab_index, message, provider_key)
                tab.input_edit.clear()

    def append_to_history(self, tab_index: int, html_text: str):
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.history_view.append(html_text)
    
    def start_ai_message(self, tab_index: int):
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.history_view.append("<div class='ai-message'><b>AI:</b><br>")

    def append_stream_chunk(self, tab_index: int, chunk: str):
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                cursor = tab.history_view.textCursor()
                cursor.movePosition(QTextCursor.End)
                cursor.insertText(chunk.replace('\n', '<br>'))
                tab.history_view.ensureCursorVisible()

    def finalize_ai_message(self, tab_index: int):
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                cursor = tab.history_view.textCursor()
                cursor.movePosition(QTextCursor.End)
                cursor.insertHtml("</div>")
                tab.history_view.ensureCursorVisible()


    def set_thinking_state(self, tab_index: int, is_thinking: bool):
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.input_edit.setReadOnly(is_thinking)
                tab.send_button.setEnabled(not is_thinking)