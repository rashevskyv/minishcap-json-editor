from PyQt5.QtGui import QColor

# --- Ідентифікатори Проблем ---
PROBLEM_TAG_WARNING = "ZMC_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZMC_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZMC_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = "ZMC_EMPTY_ODD_SUBLINE_LOGICAL"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZMC_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = "ZMC_SINGLE_WORD_SUBLINE" # Новий ID

# --- Пріоритети Проблем (менше значення = вищий пріоритет) ---
PRIORITY_TAG_CRITICAL = 1 # Залишаємо, якщо потрібен для критичних тегів
PRIORITY_TAG_WARNING = 2
PRIORITY_WIDTH_EXCEEDED = 3
PRIORITY_EMPTY_ODD = 4
PRIORITY_SINGLE_WORD_SUBLINE = 5 # Пріоритет для нової проблеми
PRIORITY_SHORT_LINE = 6
PRIORITY_DEFAULT = 99

# --- Кольори для проблем ---
COLOR_CRITICAL_TAG = QColor(255, 192, 203, 255)
COLOR_WARNING_TAG = QColor(255, 255, 0, 0) # Жовтий, непрозорий для тегів
COLOR_WIDTH_EXCEEDED = QColor(255, 0, 0, 255)
COLOR_EMPTY_ODD = QColor(255, 165, 0, 255)
COLOR_SHORT_LINE = QColor(0, 200, 0, 255)
COLOR_SINGLE_WORD_SUBLINE = QColor(0, 0, 255, 128) # Синій, 50% прозорості (128/255 приблизно 0.5)

# --- Визначення Проблем (Назви, Кольори, Пріоритети) ---
PROBLEM_DEFINITIONS = {
    PROBLEM_TAG_WARNING: {
        "name": "Попередження тегів",
        "color": COLOR_WARNING_TAG, # Використовуємо непрозорий жовтий для тегів
        "priority": PRIORITY_TAG_WARNING,
        "description": "Невідповідність кількості тегів {...} або нелегітимний тег."
    },
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Перевищення ширини підрядка",
        "color": COLOR_WIDTH_EXCEEDED,
        "priority": PRIORITY_WIDTH_EXCEEDED,
        "description": "Підрядок довший за встановлений ліміт ширини."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: {
        "name": "Порожній непарний логічний підрядок",
        "color": COLOR_EMPTY_ODD,
        "priority": PRIORITY_EMPTY_ODD,
        "description": "Логічний непарний підрядок (якщо їх більше одного в рядку даних) порожній або містить '0' без тегів."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: {
        "name": "Порожній непарний відображуваний підрядок",
        "color": COLOR_EMPTY_ODD,
        "priority": PRIORITY_EMPTY_ODD,
        "description": "Відображуваний непарний підрядок (QTextBlock) порожній або містить '0' без тегів (якщо це не єдиний підрядок в документі)."
    },
    PROBLEM_SHORT_LINE: {
        "name": "Короткий підрядок",
        "color": COLOR_SHORT_LINE,
        "priority": PRIORITY_SHORT_LINE,
        "description": "Підрядок не закінчується розділовим знаком і має достатньо місця для першого слова наступного підрядка."
    },
    PROBLEM_SINGLE_WORD_SUBLINE: { # Нове визначення
        "name": "Підрядок з одним словом",
        "color": COLOR_SINGLE_WORD_SUBLINE,
        "priority": PRIORITY_SINGLE_WORD_SUBLINE,
        "description": "Підрядок складається лише з одного слова (та можливих розділових знаків)."
    }
}