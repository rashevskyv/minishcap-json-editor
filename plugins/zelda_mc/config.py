from PyQt5.QtGui import QColor

# --- Ідентифікатори Проблем ---
PROBLEM_TAG_WARNING = "ZMC_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZMC_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZMC_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = "ZMC_EMPTY_ODD_SUBLINE_LOGICAL"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZMC_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_BLUE_RULE = "ZMC_BLUE_RULE"

# --- Пріоритети Проблем (менше значення = вищий пріоритет) ---
PRIORITY_BLUE_RULE = 1
PRIORITY_TAG_CRITICAL = 1
PRIORITY_TAG_WARNING = 2
PRIORITY_WIDTH_EXCEEDED = 3
PRIORITY_EMPTY_ODD = 4 # Однаковий для логічної та дисплейної
PRIORITY_SHORT_LINE = 6
PRIORITY_DEFAULT = 99 # Для проблем без явно вказаного пріоритету

# --- Кольори для проблем ---
COLOR_CRITICAL_TAG = QColor(255, 192, 203, 255)   # Світло-рожевий (Pink)
COLOR_WARNING_TAG = QColor(255, 255, 0, 0)        # Жовтий (Yellow)
COLOR_WIDTH_EXCEEDED = QColor(255, 0, 0, 255)     # Червоний (Red)
COLOR_EMPTY_ODD = QColor(255, 165, 0, 255)        # Помаранчевий (Orange)
COLOR_BLUE_RULE = QColor(0, 0, 255, 255)          # Синій (Blue)
COLOR_SHORT_LINE = QColor(0, 200, 0, 255)         # Зелений (Green)

# --- Визначення Проблем (Назви, Кольори, Пріоритети) ---
PROBLEM_DEFINITIONS = {
    PROBLEM_TAG_WARNING: {
        "name": "Попередження тегів",
        "color": COLOR_WARNING_TAG,
        "priority": PRIORITY_TAG_WARNING, # Використовуємо константу
        "description": "Невідповідність кількості тегів {...}."
    },
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Перевищення ширини підрядка",
        "color": COLOR_WIDTH_EXCEEDED,
        "priority": PRIORITY_WIDTH_EXCEEDED, # Використовуємо константу
        "description": "Підрядок довший за встановлений ліміт ширини."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL: { 
        "name": "Порожній непарний логічний підрядок",
        "color": COLOR_EMPTY_ODD, 
        "priority": PRIORITY_EMPTY_ODD, # Використовуємо константу
        "description": "Логічний непарний підрядок (якщо їх більше одного в рядку даних) порожній або містить '0' без тегів."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: { 
        "name": "Порожній непарний відображуваний підрядок",
        "color": COLOR_EMPTY_ODD, 
        "priority": PRIORITY_EMPTY_ODD, # Використовуємо константу
        "description": "Відображуваний непарний підрядок (QTextBlock) порожній або містить '0' без тегів (якщо це не єдиний підрядок в документі)."
    },
    PROBLEM_BLUE_RULE: {
        "name": "Порушення \"синього\" правила",
        "color": COLOR_BLUE_RULE, 
        "priority": PRIORITY_BLUE_RULE, # Використовуємо константу
        "description": "Непарний підрядок починається з малої літери, закінчується розділовим знаком, а наступний підрядок не порожній."
    },
    PROBLEM_SHORT_LINE: {
        "name": "Короткий підрядок",
        "color": COLOR_SHORT_LINE, 
        "priority": PRIORITY_SHORT_LINE, # Використовуємо константу
        "description": "Підрядок не закінчується розділовим знаком і має достатньо місця для першого слова наступного підрядка."
    }
}