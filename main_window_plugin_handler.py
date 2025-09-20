# --- START OF FILE main_window_plugin_handler.py ---
import sys
import importlib
from PyQt5.QtWidgets import QAction, QMenu
from PyQt5.QtGui import QKeySequence
from utils.logging_utils import log_debug
from plugins.base_game_rules import BaseGameRules

class MainWindowPluginHandler:
    def __init__(self, main_window):
        self.mw = main_window
        log_debug(f"PluginHandler '{self.__class__.__name__}' initialized.")

    def setup_plugin_ui(self):
        if not self.mw.current_game_rules:
            return
            
        self.mw.tag_checker_handler = self.mw.current_game_rules.get_tag_checker_handler()
        if self.mw.tag_checker_handler:
            log_debug(f"TagCheckerHandler of type {type(self.mw.tag_checker_handler).__name__} was provided by the plugin.")

        plugin_actions_data = self.mw.current_game_rules.get_plugin_actions()
        for action_data in plugin_actions_data:
            action_name = action_data.get('name')
            if not action_name: continue
            
            action = QAction(action_data.get('text', action_name), self.mw)
            if 'tooltip' in action_data: action.setToolTip(action_data['tooltip'])
            if 'shortcut' in action_data: action.setShortcut(QKeySequence(action_data['shortcut']))
            if 'handler' in action_data: action.triggered.connect(action_data['handler'])
            
            self.mw.plugin_actions[action_name] = action

            if action_data.get('menu'):
                menu_name = action_data.get('menu')
                target_menu = self.mw.menuBar().findChild(QMenu, f"&{menu_name}")
                if not target_menu:
                    target_menu = self.mw.menuBar().addMenu(f"&{menu_name}")
                target_menu.addAction(action)

            if action_data.get('toolbar'):
                if hasattr(self.mw, 'main_toolbar'):
                    self.mw.main_toolbar.addAction(action)

    def load_game_plugin(self):
        log_debug("--> MainWindowPluginHandler: load_game_plugin called.")
        
        plugin_name_to_load = self.mw.active_game_plugin
        log_debug(f"    Attempting to load plugin: '{plugin_name_to_load}'")

        try:
            module_path = f"plugins.{plugin_name_to_load}.rules"
            log_debug(f"    Importing module: {module_path}")
            if module_path in sys.modules:
                del sys.modules[module_path]
                if f"plugins.{plugin_name_to_load}.config" in sys.modules: 
                    del sys.modules[f"plugins.{plugin_name_to_load}.config"]
                if f"plugins.{plugin_name_to_load}.tag_checker_handler" in sys.modules:
                    del sys.modules[f"plugins.{plugin_name_to_load}.tag_checker_handler"]

            game_rules_module = importlib.import_module(module_path)
            
            if hasattr(game_rules_module, 'GameRules') and issubclass(getattr(game_rules_module, 'GameRules'), BaseGameRules):
                GameRulesClass = getattr(game_rules_module, 'GameRules')
                self.mw.current_game_rules = GameRulesClass(main_window_ref=self.mw)
                log_debug(f"    Successfully loaded and instantiated game rules: {GameRulesClass.__name__} from {module_path}")
            else:
                log_debug(f"    ERROR: Class 'GameRules' not found or not a subclass of BaseGameRules in module {module_path}")
                self._load_fallback_rules()

        except ImportError as e:
            log_debug(f"    ERROR: Could not import game plugin module {module_path}: {e}")
            self._load_fallback_rules()
        except Exception as e:
            log_debug(f"    ERROR: Unexpected error loading game plugin {module_path}: {e}")
            self._load_fallback_rules()
        if hasattr(self.mw, 'translation_handler'):
            self.mw.translation_handler.initialize_glossary_highlighting()

        log_debug("<-- MainWindowPluginHandler: load_game_plugin finished.")

    def _load_fallback_rules(self):
        log_debug("    --> MainWindowPluginHandler: _load_fallback_rules called.")
        try:
            from plugins.base_game_rules import BaseGameRules 
            self.mw.current_game_rules = BaseGameRules(main_window_ref=self.mw)
            log_debug("        Loaded fallback BaseGameRules.")
        except Exception as e:
            log_debug(f"        CRITICAL ERROR: Could not load fallback game rules: {e}")
            self.mw.current_game_rules = None 
        log_debug("    <-- MainWindowPluginHandler: _load_fallback_rules finished.")

    def trigger_check_tags_action(self):
        if self.mw.tag_checker_handler:
            self.mw.tag_checker_handler.start_or_continue_check()