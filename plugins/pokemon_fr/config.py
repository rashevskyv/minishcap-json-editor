from PyQt5.QtGui import QColor

P_NEWLINE_MARKER = "▶"
L_NEWLINE_MARKER = "▷"
P_VISUAL_EDITOR_MARKER = "▶" # PUA for Shift+Enter -> \p
L_VISUAL_EDITOR_MARKER = "▷" # PUA for Ctrl+Enter -> \l

PROBLEM_DEFINITIONS = {}

DEFAULT_TAG_MAPPINGS_POKEMON_FR = {
    "{PLAYER}": "{PLAYER}",
    "{RIVAL}": "{RIVAL}",
    "{DPAD_UPDOWN}": "{DPAD_UPDOWN}",
    "{A_BUTTON}": "{A_BUTTON}",
    "{B_BUTTON}": "{B_BUTTON}",
    "{DPAD_LEFTRIGHT}": "{DPAD_LEFTRIGHT}",
    "{PLUS}": "{PLUS}",
    "{START_BUTTON}": "{START_BUTTON}",
    "{NO}": "{NO}",
    "{LV_2}": "{LV_2}",
    "{ID}": "{ID}",
    "{PP}": "{PP}",
    "{ESCAPE 0x03}": "{ESCAPE 0x03}",
    "{ID}{NO}": "{ID}{NO}",
    "{PKMN}": "{PKMN}"
}