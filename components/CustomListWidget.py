# --- START OF FILE components/CustomListWidget.py ---
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from .CustomListItemDelegate import CustomListItemDelegate

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.setUniformItemSizes(False) 
        
        delegate = CustomListItemDelegate(self)
        self.setItemDelegate(delegate)

        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
            # Можна додати більше кольорів тут
        }

    def _create_color_icon(self, color: QColor, size: int = 12) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen) 
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)

    def create_item(self, text, data, role=Qt.UserRole):
        item = QListWidgetItem(text)
        item.setData(role, data)
        return item
    
    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        if not item:
            return

        self.setCurrentItem(item)
        block_idx = item.data(Qt.UserRole)
        main_window = self.window()
        block_name = item.text()
        if hasattr(main_window, 'block_names'):
            block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}")

        menu = QMenu(self)

        rename_action = menu.addAction(f"Rename '{block_name}'")
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            rename_action.triggered.connect(lambda checked=False, item_to_rename=item: main_window.list_selection_handler.rename_block(item_to_rename))

        menu.addSeparator()

        current_markers = main_window.get_block_color_markers(block_idx)
        for color_name, q_color in self.color_marker_definitions.items():
            action = QAction(self._create_color_icon(q_color), f"Mark {color_name.capitalize()}", menu)
            action.setCheckable(True)
            action.setChecked(color_name in current_markers)
            action.triggered.connect(lambda checked, b_idx=block_idx, c_name=color_name: main_window.toggle_block_color_marker(b_idx, c_name))
            menu.addAction(action)

        menu.addSeparator()

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Issues in '{block_name}'")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.rescan_issues_for_single_block(idx))

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'calculate_widths_for_block_action'):
            calc_widths_action = menu.addAction(f"Calculate Line Widths for Block '{block_name}'")
            calc_widths_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.app_action_handler.calculate_widths_for_block_action(idx))

        # Spellcheck action
        spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
        if spellchecker_manager and spellchecker_manager.enabled:
            menu.addSeparator()
            spellcheck_action = menu.addAction(f"Spellcheck Block '{block_name}'")
            spellcheck_action.triggered.connect(lambda checked=False, idx=block_idx: self._open_spellcheck_for_block(idx))

        translator = getattr(main_window, 'translation_handler', None)
        if translator:
            menu.addSeparator()

            progress = translator.translation_progress.get(block_idx)
            if progress and progress['completed_chunks'] and len(progress['completed_chunks']) < progress['total_chunks']:
                resume_action = menu.addAction(f"Resume Translation for '{block_name}'")
                resume_action.triggered.connect(lambda checked=False, idx=block_idx: translator.resume_block_translation(idx))
            else:
                translate_block = menu.addAction(f"AI Translate Block '{block_name}' (UA)")
                translate_block.triggered.connect(lambda checked=False, idx=block_idx: translator.translate_current_block(idx))

            generate_glossary = menu.addAction(f"AI Build Glossary for '{block_name}'")
            generate_glossary.triggered.connect(lambda checked=False, idx=block_idx: main_window.build_glossary_with_ai(idx))
        menu.exec_(self.mapToGlobal(pos))

    def _open_spellcheck_for_block(self, block_idx: int):
        """Open spellcheck dialog for a specific block."""
        main_window = self.window()
        spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)
        if not spellchecker_manager:
            return

        # Get all lines from the block
        if not hasattr(main_window, 'data') or block_idx >= len(main_window.data):
            return

        block_data = main_window.data[block_idx]
        if not isinstance(block_data, list):
            return

        # Get edited text for each line
        edited_data = getattr(main_window, 'edited_data', {})
        text_parts = []
        for string_idx in range(len(block_data)):
            key = f"{block_idx}_{string_idx}"
            if key in edited_data:
                text_parts.append(edited_data[key])
            else:
                # Fall back to original data
                text_parts.append(str(block_data[string_idx]))

        text_to_check = '\n'.join(text_parts)
        if not text_to_check.strip():
            return

        # Import and open dialog
        from dialogs.spellcheck_dialog import SpellcheckDialog
        dialog = SpellcheckDialog(self, text_to_check, spellchecker_manager, starting_line_number=0)
        if dialog.exec_():
            corrected_text = dialog.get_corrected_text()
            corrected_lines = corrected_text.split('\n')

            # Apply corrections back to edited_data
            for string_idx, corrected_line in enumerate(corrected_lines):
                if string_idx < len(block_data):
                    key = f"{block_idx}_{string_idx}"
                    if corrected_line != text_parts[string_idx]:
                        # Update edited_data
                        edited_data[key] = corrected_line
                        main_window.unsaved_changes = True
                        main_window.unsaved_block_indices.add(block_idx)

            # Refresh UI
            if hasattr(main_window, 'ui_updater'):
                main_window.ui_updater.populate_strings_for_block(block_idx)
                main_window.ui_updater.update_text_views()
                main_window.ui_updater.update_block_item_text_with_problem_count(block_idx)