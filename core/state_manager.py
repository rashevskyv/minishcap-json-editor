from enum import Enum, auto
from typing import Set, ContextManager
from contextlib import contextmanager
from utils.logging_utils import log_debug

class AppState(Enum):
    """
    Enum representing all possible states of the application.
    This replaces the 46+ boolean flags in MainWindow:
    
    1. is_adjusting_cursor
    2. is_adjusting_selection
    3. is_programmatically_changing_text
    4. is_restart_in_progress
    5. is_closing
    6. is_loading_data
    7. is_saving_data
    8. is_reverting_data
    9. is_reloading_data
    10. is_pasting_block
    11. is_undoing_paste
    12. is_auto_fixing
    13. is_checking_tags
    14. is_renaming_block
    15. is_rebuilding_indices
    16. is_updating_ui
    17. is_updating_status_bar
    18. is_updating_title
    19. is_updating_block_list
    20. is_updating_preview
    21. is_updating_edited
    22. is_updating_highlighters
    23. is_updating_font
    24. is_updating_theme
    25. is_updating_settings
    26. is_updating_plugin
    27. is_updating_tag_mappings
    28. is_updating_tag_colors
    29. is_updating_tag_patterns
    30. is_updating_tag_checkers
    31. is_updating_text_fixers
    32. is_updating_problem_analyzers
    33. is_updating_import_rules
    34. is_updating_game_rules
    35. is_updating_search_panel
    36. is_updating_search_results
    37. is_updating_search_history
    38. is_updating_search_settings
    39. is_updating_search_state
    40. is_updating_search_ui
    41. is_updating_search_panel_ui
    42. is_updating_search_panel_state
    43. is_updating_search_panel_settings
    44. is_updating_search_panel_history
    45. is_updating_search_panel_results
    46. is_updating_search_panel_ui_state
    """
    # UI Interaction & Flow Control
    ADJUSTING_CURSOR = auto()
    ADJUSTING_SELECTION = auto()
    PROGRAMMATIC_TEXT_CHANGE = auto()
    RESTART_IN_PROGRESS = auto()
    CLOSING = auto()

    # Data Operations
    LOADING_DATA = auto()
    SAVING_DATA = auto()
    REVERTING_DATA = auto()
    RELOADING_DATA = auto()
    PASTING_BLOCK = auto()
    UNDOING_PASTE = auto()
    AUTO_FIXING = auto()
    CHECKING_TAGS = auto()
    RENAMING_BLOCK = auto()
    REBUILDING_INDICES = auto()

    # Generic UI Updates
    UPDATING_UI = auto()
    UPDATING_STATUS_BAR = auto()
    UPDATING_TITLE = auto()
    UPDATING_BLOCK_LIST = auto()
    UPDATING_PREVIEW = auto()
    UPDATING_EDITED = auto()
    UPDATING_HIGHLIGHTERS = auto()
    UPDATING_FONT = auto()
    UPDATING_THEME = auto()
    UPDATING_SETTINGS = auto()
    UPDATING_PLUGIN = auto()

    # Tag & Plugin Logic Updates
    UPDATING_TAG_MAPPINGS = auto()
    UPDATING_TAG_COLORS = auto()
    UPDATING_TAG_PATTERNS = auto()
    UPDATING_TAG_CHECKERS = auto()
    UPDATING_TEXT_FIXERS = auto()
    UPDATING_PROBLEM_ANALYZERS = auto()
    UPDATING_IMPORT_RULES = auto()
    UPDATING_GAME_RULES = auto()

    # Search Logic Updates
    UPDATING_SEARCH_PANEL = auto()
    UPDATING_SEARCH_RESULTS = auto()
    UPDATING_SEARCH_HISTORY = auto()
    UPDATING_SEARCH_SETTINGS = auto()
    UPDATING_SEARCH_STATE = auto()
    UPDATING_SEARCH_UI = auto()
    UPDATING_SEARCH_PANEL_UI = auto()
    UPDATING_SEARCH_PANEL_STATE = auto()
    UPDATING_SEARCH_PANEL_SETTINGS = auto()
    UPDATING_SEARCH_PANEL_HISTORY = auto()
    UPDATING_SEARCH_PANEL_RESULTS = auto()
    UPDATING_SEARCH_PANEL_UI_STATE = auto()

class StateManager:
    """
    Centralized manager for application states.
    Prevents recursive events and tracks long-running operations.
    """
    def __init__(self):
        self._active_states: Set[AppState] = set()

    @contextmanager
    def enter(self, state: AppState) -> ContextManager[None]:
        """
        Context manager to safely enter and exit a state.
        Usage: with state_manager.enter(AppState.LOADING): ...
        """
        self._active_states.add(state)
        # log_debug(f"StateManager: ENTERED {state.name}")
        try:
            yield
        finally:
            self._active_states.discard(state)
            # log_debug(f"StateManager: EXITED {state.name}")

    def is_active(self, state: AppState) -> bool:
        """Check if a specific state is currently active."""
        return state in self._active_states

    def any_of(self, *states: AppState) -> bool:
        """Check if any of the given states are active."""
        return any(state in self._active_states for state in states)
    
    def set_active(self, state: AppState, active: bool):
        """Manually set a state (use sparingly, context manager is preferred)."""
        if active:
            self._active_states.add(state)
        else:
            self._active_states.discard(state)

    def clear(self):
        """Reset all states."""
        self._active_states.clear()
