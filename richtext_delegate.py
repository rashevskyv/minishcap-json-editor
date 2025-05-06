from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtGui import QTextDocument
from PyQt5.QtCore import QSize

class RichTextDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()
        doc = QTextDocument()
        doc.setHtml(text)
        painter.save()
        doc.setTextWidth(option.rect.width())
        painter.translate(option.rect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        text = index.data()
        doc = QTextDocument()
        doc.setHtml(text)
        doc.setTextWidth(option.rect.width())
        return QSize(doc.idealWidth(), doc.size().height())