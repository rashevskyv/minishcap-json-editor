# --- START OF FILE components/custom_tree_widget.py ---
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAction, QMessageBox, QTreeWidgetItemIterator, QApplication, QInputDialog, QToolTip
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter
from pathlib import Path

from utils.logging_utils import log_debug, log_error

class CustomTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.viewport().setMouseTracking(True)
        self.setMouseTracking(True)
        
        # Enable tooltips
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.viewport().setAttribute(Qt.WA_AlwaysShowToolTips)
        
        from .custom_list_item_delegate import CustomListItemDelegate
        self.setItemDelegate(CustomListItemDelegate(self))
        self.setIndentation(15)
        
        self.setHeaderHidden(True)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        
        # Drag and Drop support
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        
        # Ensure the selected item retains a prominent highlight even when the widget loses focus (e.g. to the text editor)
        self.setStyleSheet("""
            QTreeWidget::item:selected {
                background-color: #0078D7 !important;
                color: white !important;
            }
            QTreeWidget::item:selected:!active {
                background-color: #0078D7 !important;
                color: white !important;
            }
            QTreeWidget::item:hover {
                background-color: #37373d;
            }
        """)

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
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        if block_idx is not None:
            item.setData(0, role, block_idx)
        return item

    def select_block_by_index(self, block_idx: int):
        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == block_idx:
                self.setCurrentItem(item)
                item.setSelected(True)
                self.scrollToItem(item)
                return True
            iterator += 1
        return False
    
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
        folder_id = item.data(0, Qt.UserRole + 1)
        
        if block_idx is None and folder_id:
            # It's a directory node (virtual folder)
            rename_folder_action = menu.addAction("Rename Folder...")
            rename_folder_action.triggered.connect(lambda: self._rename_folder(item))
            
            delete_folder_action = menu.addAction("Delete Folder")
            delete_folder_action.triggered.connect(lambda: self._delete_folder(item))
            
            menu.addSeparator()
            create_subfolder_action = menu.addAction("Create Subfolder...")
            create_subfolder_action.triggered.connect(lambda: self._create_subfolder(item))
            
            menu.exec_(self.mapToGlobal(pos))
            return
        
        if block_idx is None:
            # It's a directory node (legacy/physical fallback)
            menu.exec_(self.mapToGlobal(pos))
            return

        block_name = item.text(0)
        if hasattr(main_window, 'block_names'):
             block_name = main_window.block_names.get(str(block_idx), f"Block {block_idx}")

        rename_action = menu.addAction(f"Rename '{block_name}'")
        if hasattr(main_window, 'list_selection_handler') and hasattr(main_window.list_selection_handler, 'rename_block'):
            rename_action.triggered.connect(lambda checked=False, item_to_rename=item: main_window.list_selection_handler.rename_block(item_to_rename))

        menu.addSeparator()

        reveal_menu = menu.addMenu("Reveal in Explorer")
        
        orig_action = reveal_menu.addAction("Original")
        orig_action.triggered.connect(lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=False))
        
        trans_action = reveal_menu.addAction("Translation")
        trans_action.triggered.connect(lambda checked=False, idx=block_idx: self._reveal_in_explorer(idx, is_translation=True))

        menu.addSeparator()

        marker_definitions = {}
        if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            marker_definitions = main_window.current_game_rules.get_color_marker_definitions()

        current_markers = main_window.block_handler.get_block_color_markers(block_idx)
        for color_name, q_color in self.color_marker_definitions.items():
            label = marker_definitions.get(color_name, color_name.capitalize())
            action = QAction(self._create_color_icon(q_color), f"Mark '{label}'", menu)
            action.setCheckable(True)
            action.setChecked(color_name in current_markers)
            action.triggered.connect(lambda checked, b_idx=block_idx, c_name=color_name: main_window.block_handler.toggle_block_color_marker(b_idx, c_name))
            menu.addAction(action)

        menu.addSeparator()

        if hasattr(main_window, 'app_action_handler') and hasattr(main_window.app_action_handler, 'rescan_issues_for_single_block'):
            rescan_action = menu.addAction(f"Rescan Issues in '{block_name}'")
            rescan_action.triggered.connect(lambda checked=False, idx=block_idx: main_window.issue_scan_handler.rescan_issues_for_single_block(idx))

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

    def _rename_folder(self, item):
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "Enter new folder name:", text=item.text(0))
        if ok and new_name:
            folder_id = item.data(0, Qt.UserRole + 1)
            main_window = self.window()
            if main_window.project_manager.find_virtual_folder(folder_id):
                folder = main_window.project_manager.find_virtual_folder(folder_id)
                folder.name = new_name
                main_window.project_manager.save()
                item.setText(0, new_name)

    def _delete_folder(self, item):
        folder_id = item.data(0, Qt.UserRole + 1)
        main_window = self.window()
        project = main_window.project_manager.project
        
        # Move blocks to parent or root
        folder = main_window.project_manager.find_virtual_folder(folder_id)
        if not folder: return
        
        # Find parent folder list
        parent_children_list = project.virtual_folders
        if folder.parent_id:
            parent = main_window.project_manager.find_virtual_folder(folder.parent_id)
            if parent: parent_children_list = parent.children

        # Remove folder and relocate its blocks/children
        for i, f in enumerate(parent_children_list):
            if f.id == folder_id:
                # Add children blocks to root metadata or parent
                for b_id in folder.block_ids:
                    main_window.project_manager.move_block_to_folder(b_id, folder.parent_id)
                # Move subfolders up
                for child in folder.children:
                    child.parent_id = folder.parent_id
                    parent_children_list.append(child)
                
                parent_children_list.pop(i)
                break
        
        main_window.project_manager.save()
        main_window.ui_updater.populate_blocks()

    def _create_subfolder(self, item):
        folder_id = item.data(0, Qt.UserRole + 1)
        new_name, ok = QInputDialog.getText(self, "New Subfolder", "Enter subfolder name:")
        if ok and new_name:
            main_window = self.window()
            main_window.project_manager.create_virtual_folder(new_name, parent_id=folder_id)
            main_window.ui_updater.populate_blocks()

    def dragMoveEvent(self, event):
        """Allow dropping ON items (including blocks) to trigger special logic."""
        item = self.itemAt(event.pos())
        if item:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        target_item = self.itemAt(event.pos())
        selected_items = self.selectedItems()
        
        # 1. Special case: Dropping file(s) ON another file -> Create folder
        if target_item and selected_items and target_item not in selected_items:
            indicator = self.dropIndicatorPosition()
            target_b_idx = target_item.data(0, Qt.UserRole)
            
            if indicator == QTreeWidget.OnItem and target_b_idx is not None:
                # Target is a block. Check if source is also blocks or folders.
                main_window = self.window()
                pm = main_window.project_manager
                if not pm or not pm.project:
                    super().dropEvent(event)
                    return

                # Determine parent of target to place the new folder
                target_block_id = pm.project.blocks[target_b_idx].id
                target_parent_id = None
                parent_item = target_item.parent()
                if parent_item:
                    target_parent_id = parent_item.data(0, Qt.UserRole + 1)

                # Create "(Unnamed)" folder
                new_folder = pm.create_virtual_folder("(Unnamed)", parent_id=target_parent_id)
                
                # Move target block to new folder
                pm.move_block_to_folder(target_block_id, new_folder.id)
                
                # Move all dragged items to new folder
                for item in selected_items:
                    b_idx = item.data(0, Qt.UserRole)
                    f_id = item.data(0, Qt.UserRole + 1)
                    
                    if b_idx is not None:
                        pm.move_block_to_folder(pm.project.blocks[b_idx].id, new_folder.id)
                    elif f_id:
                        # Move folder to new folder
                        folder = pm.find_virtual_folder(f_id)
                        if folder:
                            # Remove from current parent
                            pm._remove_folder_from_anywhere(f_id)
                            # Add to new folder
                            folder.parent_id = new_folder.id
                            new_folder.children.append(folder)
                
                pm.save()
                main_window.ui_updater.populate_blocks()
                event.accept()
                log_debug("Grouped items into new (Unnamed) folder via drag-drop.")
                return

        # 2. Default behavior
        super().dropEvent(event)
        self.sync_tree_to_project_manager()

    def sync_tree_to_project_manager(self):
        """Update virtual structure in project manager based on current tree layout."""
        main_window = self.window()
        if not hasattr(main_window, 'project_manager') or not main_window.project_manager or not main_window.project_manager.project:
            return
            
        project = main_window.project_manager.project
        
        def rebuild_from_item(tree_item, parent_id=None):
            folders = []
            block_ids = []
            for i in range(tree_item.childCount()):
                child = tree_item.child(i)
                f_id = child.data(0, Qt.UserRole + 1)
                b_idx = child.data(0, Qt.UserRole)
                merged_ids = child.data(0, Qt.UserRole + 2)
                text = child.text(0)
                
                if merged_ids and isinstance(merged_ids, list) and len(merged_ids) > 0:
                    # Reconstruct compacted chain
                    parts = text.split(" / ")
                    is_block_item = b_idx is not None
                    folder_names = parts[:-1] if is_block_item else parts
                    
                    curr_p_id = parent_id
                    chain_top = None
                    chain_bottom = None
                    
                    for f_idx, folder_id in enumerate(merged_ids):
                        f_name = folder_names[f_idx] if f_idx < len(folder_names) else "Unknown"
                        folder_obj = main_window.project_manager.find_virtual_folder(folder_id)
                        if not folder_obj:
                            from core.project_models import VirtualFolder
                            folder_obj = VirtualFolder(id=folder_id, name=f_name, parent_id=curr_p_id)
                        else:
                            folder_obj.name = f_name
                            folder_obj.parent_id = curr_p_id
                        
                        folder_obj.children = []
                        folder_obj.block_ids = []

                        if not chain_top: chain_top = folder_obj
                        if chain_bottom: chain_bottom.children = [folder_obj]
                        chain_bottom = folder_obj
                        curr_p_id = folder_id

                    if is_block_item:
                        if b_idx < len(project.blocks):
                            chain_bottom.block_ids = [project.blocks[b_idx].id]
                    else:
                        sub_f, sub_b = rebuild_from_item(child, f_id)
                        chain_bottom.children = sub_f
                        chain_bottom.block_ids = sub_b
                    
                    folders.append(chain_top)

                elif f_id:
                    # Standard folder
                    folder_obj = main_window.project_manager.find_virtual_folder(f_id)
                    if folder_obj:
                        folder_obj.name = text
                        folder_obj.parent_id = parent_id
                        folder_obj.children, folder_obj.block_ids = rebuild_from_item(child, f_id)
                        folders.append(folder_obj)
                elif b_idx is not None:
                    # Standard block
                    if b_idx < len(project.blocks):
                        block_ids.append(project.blocks[b_idx].id)
            return folders, block_ids

        root_item = self.invisibleRootItem()
        project.virtual_folders, root_block_ids = rebuild_from_item(root_item)
        project.metadata['root_block_ids'] = root_block_ids
        
        main_window.project_manager.save()
        log_debug("Virtual folders structure updated.")

    def move_current_item_up(self):
        item = self.currentItem()
        if not item: return
        parent = item.parent() or self.invisibleRootItem()
        index = parent.indexOfChild(item)
        if index > 0:
            parent.takeChild(index)
            parent.insertChild(index - 1, item)
            self.setCurrentItem(item)
            self.sync_tree_to_project_manager()

    def move_current_item_down(self):
        item = self.currentItem()
        if not item: return
        parent = item.parent() or self.invisibleRootItem()
        index = parent.indexOfChild(item)
        if index < parent.childCount() - 1:
            parent.takeChild(index)
            parent.insertChild(index + 1, item)
            self.setCurrentItem(item)
            self.sync_tree_to_project_manager()

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            log_debug(f"CustomTreeWidget: event() ToolTip received")
        return super().event(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            # System ToolTip event
            log_debug(f"CustomTreeWidget: viewport ToolTip event at {event.pos()}")
        elif event.type() == QEvent.MouseMove:
            # Trigger our custom tooltip logic
            index = self.indexAt(event.pos())
            if index.isValid():
                delegate = self.itemDelegate(index)
                if delegate and hasattr(delegate, 'handle_tooltip'):
                    option = self.viewOptions()
                    option.rect = self.visualRect(index)
                    delegate.handle_tooltip(event, self, option, index)
            else:
                QToolTip.hideText()
        return super().viewportEvent(event)

    def _reveal_in_explorer(self, block_idx: int, is_translation: bool = False):
        main_window = self.window()
        if not hasattr(main_window, 'project_manager') or not main_window.project_manager:
            # Fallback for single file mode
            path_to_reveal = main_window.edited_json_path if is_translation else main_window.json_path
            if path_to_reveal and Path(path_to_reveal).exists():
                self._open_explorer_at_path(path_to_reveal)
            return
            
        project = main_window.project_manager.project
        if not project:
            return

        # Use mapping if available (for multi-block files), otherwise 1:1
        project_block_idx = block_idx
        if hasattr(main_window, 'block_to_project_file_map'):
            project_block_idx = main_window.block_to_project_file_map.get(block_idx, block_idx)

        if project_block_idx >= len(project.blocks):
            return
            
        block = project.blocks[project_block_idx]
        if is_translation:
            abs_path = main_window.project_manager.get_absolute_path(block.translation_file, is_translation=True)
        else:
            abs_path = main_window.project_manager.get_absolute_path(block.source_file)
        
        if abs_path and Path(abs_path).exists():
            self._open_explorer_at_path(abs_path)

    def _open_explorer_at_path(self, abs_path: str):
        import subprocess
        import platform
        abs_path_obj = Path(abs_path)
        if abs_path_obj.exists():
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', '/select,', str(abs_path_obj)])
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-R', str(abs_path_obj)])
            else:
                subprocess.Popen(['xdg-open', str(abs_path_obj.parent)])
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Reveal", f"File not found:\n{abs_path}")

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
