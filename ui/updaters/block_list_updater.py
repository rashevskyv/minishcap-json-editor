# --- START OF FILE ui/updaters/block_list_updater.py ---
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from utils.utils import log_debug

from .base_ui_updater import BaseUIUpdater

class BlockListUpdater(BaseUIUpdater):
    def __init__(self, main_window, data_processor):
        super().__init__(main_window, data_processor)

    def populate_blocks(self):
        log_debug("[BlockListUpdater] populate_blocks called.")
        current_selection_block_idx = self.mw.block_list_widget.currentRow()
        self.mw.block_list_widget.clear()
        if not self.mw.data: 
            log_debug("[BlockListUpdater] populate_blocks: No original data.")
            return
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()

        for i in range(len(self.mw.data)):
            base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
            
            block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}
            
            if isinstance(self.mw.data[i], list):
                for data_string_idx in range(len(self.mw.data[i])):
                    data_string_text, _ = self.data_processor.get_current_string_text(i, data_string_idx) 
                    if data_string_text is not None:
                        logical_sublines = str(data_string_text).split('\n')
                        for subline_local_idx in range(len(logical_sublines)):
                            problem_key = (i, data_string_idx, subline_local_idx)
                            subline_problems = self.mw.problems_per_subline.get(problem_key, set())
                            for problem_id in subline_problems:
                                if problem_id in block_problem_counts:
                                    block_problem_counts[problem_id] += 1
            
            display_name_with_issues = base_display_name
            issue_texts = []
            
            sorted_problem_ids_for_display = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )

            for problem_id in sorted_problem_ids_for_display:
                count = block_problem_counts[problem_id]
                if count > 0:
                    problem_name_from_def = problem_definitions.get(problem_id, {}).get("name", problem_id)
                    problem_name_short = problem_name_from_def.split(" ")[0].lower()
                    if "empty" in problem_name_short and "odd" in problem_name_short:
                        problem_name_short = "emptyOdd"
                    elif "width" in problem_name_short or "ширин" in problem_name_short : 
                        problem_name_short = "width"
                    elif "short" in problem_name_short or "корот" in problem_name_short: 
                        problem_name_short = "short"
                    else: 
                        problem_name_short = problem_name_short[:5]

                    issue_texts.append(f"{count} {problem_name_short}")
            
            if issue_texts:
                display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
                
            item = self.mw.block_list_widget.create_item(display_name_with_issues, i)
            self.mw.block_list_widget.addItem(item)

        if 0 <= current_selection_block_idx < self.mw.block_list_widget.count():
            self.mw.block_list_widget.setCurrentRow(current_selection_block_idx)
        self.mw.block_list_widget.viewport().update()
        log_debug(f"[BlockListUpdater] populate_blocks: Added {self.mw.block_list_widget.count()} items.")

    def update_block_item_text_with_problem_count(self, block_idx: int):
        if not hasattr(self.mw, 'block_list_widget') or not (0 <= block_idx < self.mw.block_list_widget.count()):
            return
        
        item = self.mw.block_list_widget.item(block_idx)
        if not item: return

        base_display_name = self.mw.block_names.get(str(block_idx), f"Block {block_idx}")
        
        problem_definitions = {}
        if self.mw.current_game_rules:
            problem_definitions = self.mw.current_game_rules.get_problem_definitions()
        
        block_problem_counts = {pid: 0 for pid in problem_definitions.keys()}

        if block_idx < len(self.mw.data) and isinstance(self.mw.data[block_idx], list):
            for data_string_idx in range(len(self.mw.data[block_idx])):
                data_string_text, _ = self.data_processor.get_current_string_text(block_idx, data_string_idx)
                if data_string_text is not None:
                    logical_sublines = str(data_string_text).split('\n')
                    for subline_local_idx in range(len(logical_sublines)):
                        problem_key = (block_idx, data_string_idx, subline_local_idx)
                        subline_problems = self.mw.problems_per_subline.get(problem_key, set())
                        for problem_id in subline_problems:
                            if problem_id in block_problem_counts:
                                block_problem_counts[problem_id] += 1
        
        display_name_with_issues = base_display_name
        issue_texts = []

        sorted_problem_ids_for_display = sorted(
            block_problem_counts.keys(),
            key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
        )

        for problem_id in sorted_problem_ids_for_display:
            count = block_problem_counts[problem_id]
            if count > 0:
                problem_name_from_def = problem_definitions.get(problem_id, {}).get("name", problem_id)
                problem_name_short = problem_name_from_def.split(" ")[0].lower()
                if "empty" in problem_name_short and "odd" in problem_name_short:
                    problem_name_short = "emptyOdd"
                elif "width" in problem_name_short or "ширин" in problem_name_short:
                    problem_name_short = "width"
                elif "short" in problem_name_short or "корот" in problem_name_short:
                    problem_name_short = "short"
                else:
                    problem_name_short = problem_name_short[:5]
                issue_texts.append(f"{count} {problem_name_short}")
        
        if issue_texts:
            display_name_with_issues = f"{base_display_name} ({', '.join(issue_texts)})"
        
        if item.text() != display_name_with_issues:
            item.setText(display_name_with_issues)
        
        self.mw.block_list_widget.viewport().update()

    def clear_all_problem_block_highlights_and_text(self): 
        if not hasattr(self.mw, 'block_list_widget'): return
        for i in range(self.mw.block_list_widget.count()):
            item = self.mw.block_list_widget.item(i)
            if item:
                base_display_name = self.mw.block_names.get(str(i), f"Block {i}")
                if item.text() != base_display_name: 
                    item.setText(base_display_name)
        if hasattr(self.mw, 'block_list_widget'):
            self.mw.block_list_widget.viewport().update()
        log_debug("[BlockListUpdater] Cleared all problem/warning/width/short block highlights and count texts.")