# --- START OF FILE plugins/zelda_mc/config.py ---
from PyQt5.QtGui import QColor

PROBLEM_TAG_WARNING = "ZMC_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZMC_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZMC_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZMC_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = "ZMC_SINGLE_WORD_SUBLINE"

PRIORITY_TAG_CRITICAL = 1
PRIORITY_TAG_WARNING = 2
PRIORITY_WIDTH_EXCEEDED = 3
PRIORITY_EMPTY_ODD = 4
PRIORITY_SINGLE_WORD_SUBLINE = 5
PRIORITY_SHORT_LINE = 6
PRIORITY_DEFAULT = 99

COLOR_CRITICAL_TAG = QColor(255, 192, 203, 100)
COLOR_WARNING_TAG = QColor(255, 255, 0, 80)
COLOR_WIDTH_EXCEEDED = QColor(255, 0, 0, 100)
COLOR_EMPTY_ODD = QColor(255, 165, 0, 180)
COLOR_SHORT_LINE = QColor(0, 200, 0, 100)
COLOR_SINGLE_WORD_SUBLINE = QColor(0, 0, 255, 120)

# Default number of lines per page (for page separator lines and empty line detection)
DEFAULT_LINES_PER_PAGE = 4

PROBLEM_DEFINITIONS = {
    PROBLEM_TAG_WARNING: {
        "name": "Tag Warning",
        "color": COLOR_WARNING_TAG,
        "priority": PRIORITY_TAG_WARNING,
        "description": "Tag count mismatch for {...} or an illegitimate tag."
    },
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Subline Width Exceeded",
        "color": COLOR_WIDTH_EXCEEDED,
        "priority": PRIORITY_WIDTH_EXCEEDED,
        "description": "The subline is longer than the set width limit."
    },
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: {
        "name": "Empty First Line of Page",
        "color": COLOR_EMPTY_ODD,
        "priority": PRIORITY_EMPTY_ODD,
        "description": "The first line of a page (1, N+1, 2N+1, ...) is empty or contains '0'."
    },
    PROBLEM_SHORT_LINE: {
        "name": "Short Subline",
        "color": COLOR_SHORT_LINE,
        "priority": PRIORITY_SHORT_LINE,
        "description": "The subline does not end with a punctuation mark and has enough space for the first word of the next subline."
    },
    PROBLEM_SINGLE_WORD_SUBLINE: {
        "name": "Single Word Subline",
        "color": COLOR_SINGLE_WORD_SUBLINE,
        "priority": PRIORITY_SINGLE_WORD_SUBLINE,
        "description": "The subline consists of only one word (and possible punctuation)."
    }
}

DEFAULT_DETECTION_SETTINGS = {
    PROBLEM_TAG_WARNING: True,
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: True,
    PROBLEM_SINGLE_WORD_SUBLINE: True
}

DEFAULT_AUTOFIX_SETTINGS = {
    PROBLEM_TAG_WARNING: False,
    PROBLEM_WIDTH_EXCEEDED: True,
    PROBLEM_SHORT_LINE: True,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: True,
    PROBLEM_SINGLE_WORD_SUBLINE: False
}