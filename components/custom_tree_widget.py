# --- START OF FILE components/custom_tree_widget.py ---
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor

from utils.logging_utils import log_debug, log_error

class CustomTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.SingleSelection)

        self.color_marker_definitions = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
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

    def create_item(self, text, block_idx=None, role=Qt.UserRole):
        item = QTreeWidgetItem([text])
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item
    
    def show_context_menu(self, pos: QPoint):
        item = self.itemAt(pos)
        main_window = self.window()
        menu = QMenu(self)

        # "Add Block" and "Add Directory" options
        if hasattr(main_window, 'project_manager') and main_window.project_manager:
            add_block_action = menu.addAction("Add Block...")
            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'import_block_action'):
                add_block_action.triggered.connect(main_window.app_action_handler.import_block_action)

            add_dir_action = menu.addAction("Import Directory...")
            if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'import_directory_action'):
                add_dir_action.triggered.connect(main_window.app_action_handler.import_directory_action)
            elif hasattr(main_window, 'project_action_handler') and hasattr(main_window.project_action_handler, 'import_directory_action'):
                add_dir_action.triggered.connect(main_window.project_action_handler.import_directory_action)

            menu.addSeparator()

        if not item:
            menu.exec_(self.mapToGlobal(pos))
            return

        self.setCurrentItem(item)
        
        # Check if it's a file block (has UserRole data)
        block_idx = item.data(0, Qt.UserRole)
        
        if block_idx is None:
            # It's a directory node
            menu.exec_(self.mapToGlobal(pos))
            return

        block_name = item.text(0)
        if hasattr(main_window, 'block_names'):
             block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}")

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
        log_debug(f"CustomTreeWidget: _open_spellcheck_for_block called for block_idx={block_idx}")

        try:
            main_window = self.window()
            spellchecker_manager = getattr(main_window, 'spellchecker_manager', None)

            if not spellchecker_manager:
                return

            if not hasattr(main_window, 'data') or block_idx >= len(main_window.data):
                return

            block_data = main_window.data[block_idx]

            if not isinstance(block_data, list):
                return

            edited_data = getattr(main_window, 'edited_data', {})
            edited_file_data = getattr(main_window, 'edited_file_data', [])

            all_translated_lines = []

            for string_idx in range(len(block_data)):
                key = (block_idx, string_idx)
                text = None

                if key in edited_data:
                    text = edited_data[key]
                elif edited_file_data and block_idx < len(edited_file_data):
                    edited_block = edited_file_data[block_idx]
                    if isinstance(edited_block, list) and string_idx < len(edited_block):
                        text = edited_block[string_idx]

                if text and text.strip():
                    all_translated_lines.append((string_idx, text))

            import re
            word_pattern = re.compile(r'[a-zA-Zа-яА-ЯіїІїЄєґҐ\']+')

            text_parts = []
            line_numbers = []

            for string_idx, text in all_translated_lines:
                text_with_spaces = text.replace('·', ' ')
                has_misspellings = False
                for match in word_pattern.finditer(text_with_spaces):
                    word = match.group(0).strip("'")
                    if word and spellchecker_manager.is_misspelled(word):
                        has_misspellings = True
                        break

                if has_misspellings:
                    text_parts.append(text)
                    subline_count = text.count('\n') + 1
                    for _ in range(subline_count):
                        line_numbers.append(string_idx)

            text_to_check = '\n'.join(text_parts)
            if not text_to_check.strip():
                from PyQt5.QtWidgets import QMessageBox
                if len(all_translated_lines) == 0:
                    QMessageBox.information(self, "Spellcheck", "Немає перекладеного тексту для перевірки.\nСпочатку перекладіть текст у цьому блоці.")
                else:
                    QMessageBox.information(self, "Spellcheck", f"Орфографічні помилки не знайдено!\nПеревірено {len(all_translated_lines)} перекладених рядків.")
                return

            from dialogs.spellcheck_dialog import SpellcheckDialog
            dialog = SpellcheckDialog(self, text_to_check, spellchecker_manager,
                                     starting_line_number=0, line_numbers=line_numbers)

            if dialog.exec_():
                corrected_text = dialog.get_corrected_text()
                corrected_lines = corrected_text.split('\n')

                for i, corrected_line in enumerate(corrected_lines):
                    if i < len(line_numbers):
                        string_idx = line_numbers[i]
                        key = (block_idx, string_idx)
                        if corrected_line != text_parts[i]:
                            edited_data[key] = corrected_line
                            main_window.unsaved_changes = True
                            if hasattr(main_window, 'unsaved_block_indices'):
                                main_window.unsaved_block_indices.add(block_idx)

                current_block_idx = getattr(main_window, 'current_block_idx', -1)
                if current_block_idx == block_idx and hasattr(main_window, 'ui_updater'):
                    main_window.ui_updater.populate_strings_for_block(block_idx)
                    main_window.ui_updater.update_text_views()
                    main_window.ui_updater.update_block_item_text_with_problem_count(block_idx)

        except Exception as e:
            log_error(f"CustomTreeWidget: Error in _open_spellcheck_for_block: {e}", exc_info=True)
