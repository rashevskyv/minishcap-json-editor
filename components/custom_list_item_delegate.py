# --- START OF FILE components/custom_list_item_delegate.py ---
# --- START OF FILE components/CustomListItemDelegate.py ---
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolTip
from PyQt5.QtGui import QPainter, QColor, QPalette, QBrush, QPen, QFontMetrics, QFont, QIcon
from PyQt5.QtCore import QRect, Qt, QPoint, QSize, QModelIndex, QEvent
from utils.logging_utils import log_debug
from utils.constants import LT_PREVIEW_SELECTED_LINE_COLOR, DT_PREVIEW_SELECTED_LINE_COLOR

class CustomListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.list_widget = parent
        
        self.problem_indicator_strip_width = 3 
        self.problem_indicator_strip_spacing = 2 
        self.max_problem_indicators = 3 

        self.color_marker_size = 8 
        self.color_marker_spacing = 3
        self.max_color_markers = 0 
        
        self.fixed_number_area_width_base_font_size = 10
        self.fixed_number_area_width_base_pixels = 24
        
        self.padding_after_number_area = 3 
        self.padding_after_color_marker_zone = 2
        self.padding_after_problem_indicator_zone = 3 
        self.indicator_v_offset = 2 

        self.marker_qcolors = {
            "red": QColor(Qt.red),
            "green": QColor(Qt.green),
            "blue": QColor(Qt.blue),
        }


    def _get_current_number_area_width(self, option: QStyleOptionViewItem) -> int:
        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        current_font_size = font_for_metrics.pointSize()
        if current_font_size <= 0: current_font_size = self.fixed_number_area_width_base_font_size

        scaled_width = int(self.fixed_number_area_width_base_pixels * \
                           (current_font_size / self.fixed_number_area_width_base_font_size))
        return max(scaled_width, 20)

    def _get_problem_indicator_zone_width(self) -> int:
        if self.max_problem_indicators == 0: return 0
        return (self.problem_indicator_strip_width * self.max_problem_indicators) + \
               (self.problem_indicator_strip_spacing * (self.max_problem_indicators - 1))
    
    def _get_color_marker_zone_width(self) -> int:
        if self.max_color_markers == 0: return 0
        return (self.color_marker_size * self.max_color_markers) + \
               (self.color_marker_spacing * (self.max_color_markers -1))


    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        default_hint = super().sizeHint(option, index)

        font_to_use = option.font
        if not font_to_use.family():
            font_for_metrics = QFont()
        else:
            font_for_metrics = font_to_use

        fm = QFontMetrics(font_for_metrics)
        min_height = fm.height() + 6 

        current_number_area_width = self._get_current_number_area_width(option)
        problem_indicator_zone_total_width = self._get_problem_indicator_zone_width()
        color_marker_zone_total_width = self._get_color_marker_zone_width()

        calculated_width = current_number_area_width + \
                           self.padding_after_number_area + \
                           color_marker_zone_total_width + \
                           (self.padding_after_color_marker_zone if color_marker_zone_total_width > 0 else 0) + \
                           problem_indicator_zone_total_width + \
                           (self.padding_after_problem_indicator_zone if problem_indicator_zone_total_width > 0 else 0) + \
                           fm.horizontalAdvance(str(index.data(Qt.DisplayRole))) + 20

        return QSize(max(default_hint.width(), calculated_width), max(default_hint.height(), min_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = option.state & QStyle.State_Selected
        
        is_drag_hover = False
        if hasattr(self.list_widget, '_custom_drop_target') and self.list_widget._custom_drop_target:
            target_item, drop_pos = self.list_widget._custom_drop_target
            if drop_pos == "On" and target_item is self.list_widget.itemFromIndex(index):
                is_drag_hover = True
        
        if is_selected or is_drag_hover:
            highlight_color = option.palette.highlight().color() if is_selected else QColor("#0078D7")
            painter.fillRect(option.rect, highlight_color)
        else:
            is_alternate = option.features & QStyleOptionViewItem.Alternate
            bg_brush = option.palette.alternateBase() if is_alternate else option.palette.base()
            painter.fillRect(option.rect, bg_brush)
        
        main_window = self.list_widget.window() if self.list_widget else None
        theme = 'light'
        if main_window and hasattr(main_window, 'theme'):
            theme = main_window.theme

        item_rect = option.rect
        current_number_area_width = self._get_current_number_area_width(option)

        if theme == 'dark':
            if is_selected or is_drag_hover:
                number_area_bg = QColor("#0078D7").darker(110)
                number_text_color = option.palette.color(QPalette.HighlightedText)
            else:
                number_area_bg = QColor("#383838")
                number_text_color = QColor("#B0B0B0")
        else:
            if is_selected or is_drag_hover:
                number_area_bg = QColor("#0078D7").darker(105)
                number_text_color = QColor(Qt.white)
            else:
                number_area_bg = QColor("#F0F0F0")
                number_text_color = QColor(Qt.darkGray)
        
        active_color_markers_for_block = set()
        
        block_idx_data = index.data(Qt.UserRole)
        problem_definitions = {}
        block_problem_counts = {}
        has_unsaved_changes_in_block = False

        if main_window and block_idx_data is not None:
            if hasattr(main_window, 'unsaved_block_indices'):
                 has_unsaved_changes_in_block = block_idx_data in main_window.unsaved_block_indices
            
            if hasattr(main_window, 'block_handler') and hasattr(main_window.block_handler, 'get_block_color_markers'):
                active_color_markers_for_block = main_window.block_handler.get_block_color_markers(block_idx_data)

            if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                problem_definitions = main_window.current_game_rules.get_problem_definitions()

            if hasattr(main_window, 'ui_updater') and hasattr(main_window.ui_updater, '_get_aggregated_problems_for_block'):
                block_problem_counts = main_window.ui_updater._get_aggregated_problems_for_block(block_idx_data)


        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        painter.fillRect(number_rect, number_area_bg)
        painter.setPen(number_text_color)
        current_font = option.font
        if not current_font.family(): current_font = QFont()
        painter.setFont(current_font)
        
        number_text = f"* {index.row() + 1}" if has_unsaved_changes_in_block else str(index.row() + 1)
        painter.drawText(number_rect, Qt.AlignCenter | Qt.TextShowMnemonic, number_text)

        # Calculate fixed zones for alignment
        color_marker_zone_x_start = number_rect.right() + self.padding_after_number_area
        color_marker_zone_width = self._get_color_marker_zone_width()
        
        problem_indicator_zone_x_start = color_marker_zone_x_start + color_marker_zone_width + \
                                         (self.padding_after_color_marker_zone if color_marker_zone_width > 0 else 0)
        problem_indicator_zone_width = self._get_problem_indicator_zone_width()
        
        text_start_x = problem_indicator_zone_x_start + problem_indicator_zone_width + \
                       (self.padding_after_problem_indicator_zone if problem_indicator_zone_width > 0 else 0)

        # 1. Draw Color Markers
        current_color_marker_x = color_marker_zone_x_start
        sorted_active_markers = sorted(list(active_color_markers_for_block)) 

        for i, color_name in enumerate(sorted_active_markers):
            if i >= self.max_color_markers: break
            q_color = self.marker_qcolors.get(color_name)
            if q_color:
                marker_y = item_rect.top() + (item_rect.height() - self.color_marker_size) // 2
                painter.setBrush(q_color)
                painter.setPen(Qt.NoPen) 
                painter.drawEllipse(current_color_marker_x, marker_y, self.color_marker_size, self.color_marker_size)
                current_color_marker_x += self.color_marker_size + self.color_marker_spacing
        
        # 2. Draw Problem Indicators
        problem_indicator_colors_to_draw = []
        if problem_definitions and block_problem_counts:
            sorted_block_problem_ids = sorted(
                block_problem_counts.keys(),
                key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99)
            )
            for problem_id in sorted_block_problem_ids:
                if block_problem_counts[problem_id] > 0:
                    if len(problem_indicator_colors_to_draw) >= self.max_problem_indicators: break
                    problem_def = problem_definitions.get(problem_id)
                    if problem_def and "color" in problem_def:
                        indicator_color = QColor(problem_def["color"])
                        if indicator_color.alpha() < 120 and theme == 'dark':
                            indicator_color.setAlpha(180)
                        if indicator_color not in problem_indicator_colors_to_draw:
                            problem_indicator_colors_to_draw.append(indicator_color)
        
        current_problem_indicator_x = problem_indicator_zone_x_start
        for i, color in enumerate(problem_indicator_colors_to_draw):
            if i >= self.max_problem_indicators: break 
            indicator_rect = QRect(current_problem_indicator_x,
                                   item_rect.top() + self.indicator_v_offset,
                                   self.problem_indicator_strip_width,
                                   item_rect.height() - 2 * self.indicator_v_offset)
            painter.fillRect(indicator_rect, color)
            current_problem_indicator_x += self.problem_indicator_strip_width + self.problem_indicator_strip_spacing
        
        # Draw Icon if exists (DecorationRole)
        decoration = index.data(Qt.DecorationRole)
        compaction_type = index.data(Qt.UserRole + 3) # 1: Folder/Folder, 2: Folder/Block
        
        icon_size = 16
        style = main_window.style()
        
        if compaction_type in [1, 2]:
            # Draw composite icons
            folder_icon = style.standardIcon(QStyle.SP_DirIcon)
            
            # Start first icon at the same column as regular icons
            comp_icon_x = problem_indicator_zone_x_start
            folder_rect = QRect(comp_icon_x, item_rect.top() + (item_rect.height() - icon_size) // 2, icon_size, icon_size)
            folder_icon.paint(painter, folder_rect)
            
            # Second icon (very close to first, partial overlap is okay for 'compact' feel)
            second_icon = style.standardIcon(QStyle.SP_DirIcon if compaction_type == 1 else QStyle.SP_FileIcon)
            second_rect = QRect(folder_rect.right() - 4, item_rect.top() + (item_rect.height() - icon_size) // 2, icon_size, icon_size)
            second_icon.paint(painter, second_rect)
            
            # text_start_x for combined items starts after second icon
            text_start_x = second_rect.right() + 4
        else:
            if decoration:
                icon = QIcon(decoration)
                if not icon.isNull():
                    # Draw icon at the same column as problem indicator strips.
                    # icon_size(16) == strip_zone(13) + padding(3) → text stays aligned.
                    icon_rect = QRect(problem_indicator_zone_x_start,
                                      item_rect.top() + (item_rect.height() - icon_size) // 2,
                                      icon_size, icon_size)
                    icon.paint(painter, icon_rect)
            # text_start_x already = problem_indicator_zone_x_start + zone_width + padding
            # = problem_indicator_zone_x_start + 16 = icon_end → no extra shift needed

        # Draw String Count on the right
        string_count_text = ""
        count_width = 0
        if main_window and block_idx_data is not None and hasattr(main_window, 'data'):
            if 0 <= block_idx_data < len(main_window.data):
                block_data = main_window.data[block_idx_data]
                if isinstance(block_data, list):
                    string_count_text = f"[{len(block_data)}]"
                    metrics = QFontMetrics(current_font)
                    count_width = metrics.horizontalAdvance(string_count_text) + 10 # 5px padding on each side

        if string_count_text:
            count_rect = QRect(item_rect.right() - count_width, item_rect.top(), count_width, item_rect.height())
            painter.setPen(number_text_color) # Same subtle color as line numbers
            painter.drawText(count_rect, Qt.AlignCenter, string_count_text)
        
        # Calculate text area
        header_end = item_rect.right() - count_width - 4
        available_text_w = header_end - text_start_x
        
        # If icons push text too far right, squeeze them a bit or allow overlap 
        # but NEVER draw off-screen to the right.
        if available_text_w < 30:
            text_start_x = max(text_start_x - 20, number_rect.right() + 5)
            available_text_w = header_end - text_start_x

        text_rect = QRect(text_start_x, item_rect.top(), max(30, available_text_w), item_rect.height())
            
        painter.setPen(option.palette.color(QPalette.HighlightedText if (is_selected or is_drag_hover) else QPalette.Text))

        full_text = str(index.data(Qt.DisplayRole) or "")
        metrics = QFontMetrics(current_font)
        elided_text = metrics.elidedText(full_text, Qt.ElideRight, text_rect.width())

        if elided_text:
            painter.save()
            
            # Default color
            painter.setPen(option.palette.color(QPalette.HighlightedText if (is_selected or is_drag_hover) else QPalette.Text))
            
            # Special coloring for metadata parts (only if not selected)
            if not (is_selected or is_drag_hover):
                import re
                # 1. Folder counts: [f / b]
                count_match = re.search(r'(\s*\[\d+\s*/\s*\d+\])$', elided_text)
                # 2. Block details: (extra info)
                detail_match = re.search(r'(\s*\(.*\))$', elided_text)
                
                target_match = count_match or detail_match
                if target_match:
                    meta_str = target_match.group(1)
                    main_str = elided_text[:target_match.start()]
                    
                    # Draw main part
                    painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, main_str)
                    
                    # Draw meta part in grey
                    main_w = metrics.horizontalAdvance(main_str)
                    meta_rect = text_rect.adjusted(main_w, 0, 0, 0)
                    painter.setPen(QColor(140, 140, 140) if theme == 'light' else QColor(160, 160, 160))
                    painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, meta_str)
                else:
                    # Regular text or compacted path (no special grey for path as requested)
                    painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
            else:
                # Selected: draw everything in highlighted color
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
                
            painter.restore()

        painter.restore()

    def handle_tooltip(self, event, view, option, index):
        mouse_pos = event.pos()
        item_rect = option.rect
        
        # We only want to show tooltips if the mouse stays over the same area.
        # However, for debugging, let's just print every move to the console.
        # print(f"DEBUG: Delegate handle_tooltip at {mouse_pos}") 
        
        main_window = self.list_widget.window() if self.list_widget else None
        if not main_window: return

        # 1. Check Number Area
        current_number_area_width = self._get_current_number_area_width(option)
        number_rect = QRect(item_rect.left(), item_rect.top(), current_number_area_width, item_rect.height())
        
        if number_rect.contains(mouse_pos):
            block_idx = index.data(Qt.UserRole)
            if block_idx is not None:
                # Reuse logic from helpEvent or centralize it
                tooltip_text = self._get_problems_tooltip_text(main_window, block_idx)
                if tooltip_text:
                    QToolTip.showText(event.globalPos(), tooltip_text, view)
                    return
        
        # 2. Check Color Markers Area
        # ... logic for color markers ...
        active_color_markers = set()
        block_idx = index.data(Qt.UserRole)
        if main_window and block_idx is not None and hasattr(main_window, 'block_handler'):
            active_color_markers = main_window.block_handler.get_block_color_markers(block_idx)
        
        if active_color_markers:
            color_marker_zone_x_start = number_rect.right() + self.padding_after_number_area
            current_color_marker_x = color_marker_zone_x_start
            sorted_active_markers = sorted(list(active_color_markers))
            
            marker_definitions = {}
            if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
                marker_definitions = main_window.current_game_rules.get_color_marker_definitions()

            for i, color_name in enumerate(sorted_active_markers):
                if i >= self.max_color_markers: break
                
                marker_rect = QRect(current_color_marker_x, 
                                    item_rect.top() + (item_rect.height() - self.color_marker_size) // 2,
                                    self.color_marker_size, self.color_marker_size)
                
                if marker_rect.contains(mouse_pos):
                    desc = marker_definitions.get(color_name, color_name.capitalize())
                    QToolTip.showText(event.globalPos(), f"<b>{color_name.capitalize()} Marker</b><br>{desc}", view)
                    return
                
                current_color_marker_x += self.color_marker_size + self.color_marker_spacing

        # Default: hide if over text area or empty space
        # QToolTip.hideText() # This might be too aggressive if flickering occurs

    def _get_problems_tooltip_text(self, main_window, block_idx) -> str:
        problem_definitions = {}
        if hasattr(main_window, 'current_game_rules') and main_window.current_game_rules:
            problem_definitions = main_window.current_game_rules.get_problem_definitions()
        
        if hasattr(main_window, 'ui_updater') and hasattr(main_window.ui_updater, '_get_aggregated_problems_for_block'):
            block_problem_counts = main_window.ui_updater._get_aggregated_problems_for_block(block_idx)
            
            tooltip_lines = []
            if problem_definitions and block_problem_counts:
                sorted_ids = sorted(block_problem_counts.keys(), key=lambda pid: problem_definitions.get(pid, {}).get("priority", 99))
                for pid in sorted_ids:
                    count = block_problem_counts[pid]
                    if count > 0:
                        prob_def = problem_definitions.get(pid, {})
                        name = prob_def.get("name", pid)
                        desc = prob_def.get("description", "")
                        tooltip_lines.append(f"<b>{name}</b>: {count} sublines<br><i>{desc}</i>")
            
            if tooltip_lines:
                return "<br><br>".join(tooltip_lines)
        return ""

    def helpEvent(self, event, view, option, index) -> bool:
        if event.type() == QEvent.ToolTip:
            # We already have manual handling but let's keep this as fallback/bridge
            self.handle_tooltip(event, view, option, index)
            return True
        return super().helpEvent(event, view, option, index)
