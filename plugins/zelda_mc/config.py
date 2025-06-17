from PyQt5.QtGui import QColor

PROBLEM_TAG_WARNING = "ZMC_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "ZMC_WIDTH_EXCEEDED"
PROBLEM_SHORT_LINE = "ZMC_SHORT_LINE"
PROBLEM_EMPTY_ODD_SUBLINE_LOGICAL = "ZMC_EMPTY_ODD_SUBLINE_LOGICAL"
PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = "ZMC_EMPTY_ODD_SUBLINE_DISPLAY"
PROBLEM_SINGLE_WORD_SUBLINE = "ZMC_SINGLE_WORD_SUBLINE" 

PRIORITY_TAG_CRITICAL = 1 
PRIORITY_TAG_WARNING = 2
PRIORITY_WIDTH_EXCEEDED = 3
PRIORITY_EMPTY_ODD = 4
PRIORITY_SINGLE_WORD_SUBLINE = 5 
PRIORITY_SHORT_LINE = 6
PRIORITY_DEFAULT = 99

COLOR_CRITICAL_TAG = QColor(255, 192, 203, 255)
COLOR_WARNING_TAG = QColor(255, 255, 0, 0) 
COLOR_WIDTH_EXCEEDED = QColor(255, 0, 0, 255)
COLOR_EMPTY_ODD = QColor(255, 165, 0, 255)
COLOR_SHORT_LINE = QColor(0, 200, 0, 255)
COLOR_SINGLE_WORD_SUBLINE = QColor(0, 0, 255, 128) 

PROBLEM_DEFINITIONS = {
    PROBLEM_TAG_WARNING: {
        "name": "Попередження тегів",
        "color": COLOR_WARNING_TAG, 
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
    PROBLEM_SINGLE_WORD_SUBLINE: { 
        "name": "Підрядок з одним словом",
        "color": COLOR_SINGLE_WORD_SUBLINE,
        "priority": PRIORITY_SINGLE_WORD_SUBLINE,
        "description": "Підрядок складається лише з одного слова (та можливих розділових знаків)."
    }
}

DEFAULT_TAG_MAPPINGS_ZMC = {
    "[red]": "{Color:Red}",
    "[blue]": "{Color:Blue}",
    "[green]": "{Color:Green}",
    "[038]": "{Sound:00:92}",
    "[0101]": "{01:01}",
    "[036]": "{Sound:00:90}",
    "[034]": "{Sound:00:8E}",
    "[033]": "{Sound:00:8D}",
    "[/c]": "{Color:White}",
    "[unk10]": "{Symbol:10}",
    "[037]": "{Sound:00:91}",
    "[3024]": "{Sound:02:03}",
    "[3025]": "{Sound:02:04}",
    "[3021]": "{Sound:02:00}",
    "[3022]": "{Sound:02:01}",
    "[3023]": "{Sound:02:02}",
    "[30130]": "{Sound:01:FA}",
    "{Sound:01:F7}": "{Sound:01:FA}",
    "[30128]": "{Sound:01:F8}",
    "[30132]": "{Sound:01:FC}",
    "[30131]": "{Sound:01:FB}",
    "[30133]": "{Sound:01:FD}",
    "[30134]": "{Sound:01:FE}",
    "[30135]": "{Sound:01:FF}",
    "[30212]": "{Sound:02:0C}",
    "[30129]": "{Sound:01:F9}",
    "[0318]": "{Sound:00:B0}",
    "[0330]": "{Sound:00:D3}",
    "[30111]": "{Sound:01:E4}",
    "[3011]": "{01:02}",
    "[3012]": "{01:04}",
    "[0105]": "{01:05}",
    "[3026]": "{Sound:02:05}",
    "[unk101]": "{Symbol:0B}",
    "[30126]": "{Sound:01:F6}",
    "[3029]": "{Sound:02:08}",
    "[30122]": "{Sound:01:F0}",
    "[30121]": "{Sound:01:EF}",
    "[30120]": "{Sound:01:EE}",
    "[30119]": "{Sound:01:EC}",
    "[30118]": "{Sound:01:EB}",
    "[30127]": "{Sound:01:F7}",
    "[3028]": "{Sound:02:07}",
    "[30117]": "{Sound:01:EA}",
    "[30123]": "{Sound:01:F1}",
    "[30124]": "{Sound:01:F2}",
    "[0327]": "{Sound:00:D0}",
    "[0317]": "{Sound:00:AE}",
    "[3013]": "{Sound:01:B7}",
    "[3014]": "{Sound:01:B8}",
    "[3015]": "{Sound:01:B9}",
    "[0328]": "{Sound:00:D1}",
    "[0332]": "{Sound:00:D5}",
    "[0410]": "{04:10:00}",
    "[30211]": "{Sound:02:0A}",
    "[0412]": "{04:10:0E}",
    "[30116]": "{Sound:01:E9}",
    "[0313]": "{Sound:00:A3}",
    "[0315]": "{Sound:00:A9}",
    "[0316]": "{Sound:00:AA}",
    "№": "",
    "'": "`",
    "’": "`",
    "[->54]": "{Choice:03:17}",
    "[->1]": "{Choice:FF}",
    "[052]": "{Choice:03:22}",
    "[04122]": "{04:12}",
    "[30215]": "{Sound:02:1A}",
    "[->23]": "{Choice:20:14}",
    "[R]": "{Key:Right}",
    "[unk11]": "{07:25:02}",
    "[unk20]": "{07:31:28}",
    "[unk21]": "{07:31:29}",
    "[unk22]": "{07:31:2A}",
    "[0415]": "{04:15}",
    "[count]": "{Var:1}",
    "[0414]": "{04:14}",
    "[->68]": "{Choice:3C:03}",
    "[0326]": "{Sound:00:CC}",
    "[->81]": "{Choice:46:03}",
    "[->82]": "{Choice:46:0B}",
    "[D-pad]": "{Key:Dpad}",
    "[->85]": "{Choice:46:24}",
    "[->86]": "{Choice:46:2D}",
    "[->88]": "{Choice:46:3F}",
    "[unk39]": "{07:49:02}"
}