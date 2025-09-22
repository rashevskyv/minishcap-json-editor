# --- START OF FILE components/ai_status_dialog.py ---
import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget
from PyQt5.QtGui import QMovie, QFont, QPalette, QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QSize, QTimer

class AnimatedIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.setFixedSize(48, 48)

    def start(self):
        self.angle = 0
        self.timer.start(30)

    def stop(self):
        self.timer.stop()

    def update_animation(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        radius = min(self.width(), self.height()) / 2 - 4
        
        painter.translate(center)
        painter.rotate(self.angle)
        
        pen = QPen(self.palette().color(QPalette.Highlight), 4)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        
        painter.drawArc(int(-radius), int(-radius), int(radius * 2), int(radius * 2), 0 * 16, 90 * 16)
        
        pen.setColor(self.palette().color(QPalette.Highlight).lighter(120))
        painter.setPen(pen)
        painter.drawArc(int(-radius), int(-radius), int(radius * 2), int(radius * 2), 180 * 16, 90 * 16)

class AIStatusDialog(QDialog):
    STATUS_PENDING = 0
    STATUS_IN_PROGRESS = 1
    STATUS_DONE = 2
    STATUS_ERROR = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Operation in Progress")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)
        self.setSizeGripEnabled(False)

        self.steps = [
            "Підготовка запиту...",
            "Надсилання до ШІ...",
            "Очікування відповіді...",
            "Перевірка результату...",
            "Застосування змін..."
        ]
        self.step_labels: list[QLabel] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = QLabel("AI Translation", self)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)
        main_layout.addSpacing(10)

        steps_widget = QWidget(self)
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setContentsMargins(20, 10, 20, 10)
        steps_layout.setSpacing(8)

        for step_text in self.steps:
            label = QLabel(f"○ {step_text}", self)
            self.step_labels.append(label)
            steps_layout.addWidget(label)
        
        main_layout.addWidget(steps_widget)
        main_layout.addStretch(1)

        animation_layout = QHBoxLayout()
        animation_layout.addStretch(1)
        self.animation_widget = AnimatedIcon(self)
        animation_layout.addWidget(self.animation_widget)
        animation_layout.addStretch(1)
        
        main_layout.addLayout(animation_layout)
        main_layout.addStretch(1)

    def start(self, title: str):
        self.title_label.setText(title)
        for i, label in enumerate(self.step_labels):
            self._update_label_style(label, self.STATUS_PENDING, self.steps[i])
        self.animation_widget.start()
        self.show()

    def finish(self):
        self.animation_widget.stop()
        self.hide()

    def update_step(self, step_index: int, text: str, status: int):
        if 0 <= step_index < len(self.step_labels):
            for i in range(len(self.step_labels)):
                current_status = self.STATUS_PENDING
                current_text = self.steps[i]
                if i < step_index:
                    current_status = self.STATUS_DONE
                elif i == step_index:
                    current_status = status
                    current_text = text
                
                self._update_label_style(self.step_labels[i], current_status, current_text)

    def _update_label_style(self, label: QLabel, status: int, text: str):
        font = label.font()
        palette = label.palette()
        
        if status == self.STATUS_PENDING:
            font.setBold(False)
            palette.setColor(QPalette.WindowText, Qt.gray)
            prefix = "○"
        elif status == self.STATUS_IN_PROGRESS:
            font.setBold(True)
            palette.setColor(QPalette.WindowText, self.palette().color(QPalette.WindowText))
            prefix = "▶"
        elif status == self.STATUS_DONE:
            font.setBold(False)
            palette.setColor(QPalette.WindowText, Qt.gray)
            prefix = "✔"
        elif status == self.STATUS_ERROR:
            font.setBold(True)
            palette.setColor(QPalette.WindowText, Qt.red)
            prefix = "✖"
        else:
            prefix = "○"
            
        label.setFont(font)
        label.setPalette(palette)
        label.setText(f"{prefix} {text}")