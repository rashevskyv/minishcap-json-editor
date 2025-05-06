from PyQt5.QtWidgets import QStyledItemDelegate, QStyle
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import QRect, Qt

class CustomListItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        # Малюємо фон для виділеного елемента
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#e6f0ff"))
        # Малюємо сіру область для номера
        number_rect = QRect(option.rect.left(), option.rect.top(), 36, option.rect.height())
        painter.fillRect(number_rect, QColor("#f0f0f0"))
        painter.setPen(QColor("#888"))
        painter.drawText(number_rect, Qt.AlignCenter, str(index.row() + 1))
        # Малюємо текст справа (HTML не підтримується тут, тільки plain text)
        text_rect = QRect(option.rect.left() + 40, option.rect.top(), option.rect.width() - 40, option.rect.height())
        painter.setPen(option.palette.text().color())
        text = index.data(Qt.DisplayRole)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.restore()