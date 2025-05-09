from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, 
    QCheckBox, QLabel, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

class SearchPanelWidget(QWidget):
    find_next_requested = pyqtSignal(str, bool, bool)
    find_previous_requested = pyqtSignal(str, bool, bool)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        self.search_query_edit = QLineEdit(self)
        self.search_query_edit.setPlaceholderText("Знайти...")
        
        self.find_next_button = QPushButton("Далі", self)
        self.find_previous_button = QPushButton("Назад", self)
        
        self.case_sensitive_checkbox = QCheckBox("Враховувати регістр", self)
        self.search_in_original_checkbox = QCheckBox("В оригіналі", self)
        
        self.status_label = QLabel("", self)
        self.status_label.setMinimumWidth(150)
        self.status_label.setAlignment(Qt.AlignCenter)

        self.close_search_panel_button = QPushButton("X", self)
        self.close_search_panel_button.setToolTip("Закрити панель пошуку")
        self.close_search_panel_button.setFixedSize(24, 24)

        left_layout = QHBoxLayout()
        left_layout.addWidget(self.search_query_edit)
        left_layout.addWidget(self.find_next_button)
        left_layout.addWidget(self.find_previous_button)
        
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.case_sensitive_checkbox)
        options_layout.addWidget(self.search_in_original_checkbox)
        options_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(options_layout, 2)
        main_layout.addWidget(self.status_label, 1)
        main_layout.addWidget(self.close_search_panel_button)

        self.find_next_button.clicked.connect(self._on_find_next)
        self.find_previous_button.clicked.connect(self._on_find_previous)
        self.search_query_edit.returnPressed.connect(self._on_find_next)
        self.close_search_panel_button.clicked.connect(self.close_requested)

    def _on_find_next(self):
        query = self.search_query_edit.text()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        if query:
            self.find_next_requested.emit(query, case_sensitive, search_in_original)

    def _on_find_previous(self):
        query = self.search_query_edit.text()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        if query:
            self.find_previous_requested.emit(query, case_sensitive, search_in_original)

    def get_search_parameters(self) -> tuple[str, bool, bool]:
        query = self.search_query_edit.text()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        search_in_original = self.search_in_original_checkbox.isChecked()
        return query, case_sensitive, search_in_original

    def set_status_message(self, message: str, is_error: bool = False):
        self.status_label.setText(message)
        if is_error:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("")
            
    def focus_search_input(self):
        self.search_query_edit.selectAll()
        self.search_query_edit.setFocus()

    def clear_status(self):
        self.status_label.setText("")
        self.status_label.setStyleSheet("")

    def get_query(self) -> str:
        return self.search_query_edit.text()

    def set_query(self, query: str):
        self.search_query_edit.setText(query)