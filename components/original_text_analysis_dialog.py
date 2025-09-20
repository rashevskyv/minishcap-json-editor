# -*- coding: utf-8 -*-
"""Interactive dialog for analysing original text width."""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence

from PyQt5.QtCore import QPoint, Qt, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from utils.utils import calculate_string_width, DEFAULT_CHAR_WIDTH_FALLBACK

BASE_BAR_COLOR = QColor(66, 135, 245, 220)
HIGHLIGHT_BAR_COLOR = QColor(244, 160, 0, 230)


class _BarItem(QGraphicsRectItem):
    """Bar item storing its index for selection syncing."""

    def __init__(self, index: int, *rect_args):
        super().__init__(*rect_args)
        self.index = index


class _AnalysisBarView(QGraphicsView):
    """Specialised bar chart view with zoom/pan and selection callback."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._panning = False
        self._pan_start = QPoint()
        self._bars: List[_BarItem] = []
        self._user_scaled = False
        self.on_bar_selected: Optional[Callable[[int], None]] = None

    def wheelEvent(self, event) -> None:  # noqa: D401 (inherit doc)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._user_scaled = True
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self._user_scaled = True
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: D401
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self._scroll(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: D401
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton and not self._panning:
            scene_pos = self.mapToScene(event.pos())
            item = self._scene.itemAt(scene_pos, self.transform())
            if isinstance(item, _BarItem) and self.on_bar_selected:
                self.on_bar_selected(item.index)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _scroll(self, delta) -> None:
        h_bar: QScrollBar = self.horizontalScrollBar()
        v_bar: QScrollBar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() - delta.x())
        v_bar.setValue(v_bar.value() - delta.y())

    def resizeEvent(self, event) -> None:  # noqa: D401
        super().resizeEvent(event)
        if not self._user_scaled:
            self._fit_view_to_scene()

    def set_entries(self, entries: Sequence[dict]) -> None:
        """Populate the scene with bar items."""
        self.resetTransform()
        self._user_scaled = False
        self._scene.clear()
        self._bars = []
        if not entries:
            self._scene.setSceneRect(0, 0, 1, 1)
            self._fit_view_to_scene()
            return

        bar_width = 24.0
        spacing = 12.0
        max_height = max(entry['width_pixels'] for entry in entries) or 1.0
        total_width = len(entries) * bar_width + (len(entries) - 1) * spacing

        axis_pen = QPen(QColor(140, 140, 140))
        axis_pen.setWidthF(0.8)
        self._scene.addLine(0.0, 0.0, total_width, 0.0, axis_pen)

        ticks = 5
        for idx in range(1, ticks + 1):
            value = max_height * idx / ticks
            y = -value
            tick_pen = QPen(QColor(200, 200, 200))
            tick_pen.setStyle(Qt.DashLine)
            tick_pen.setWidthF(0.6)
            self._scene.addLine(0.0, y, total_width, y, tick_pen)
            label = QGraphicsSimpleTextItem(f"{value:.1f} px")
            label.setBrush(QColor(90, 90, 90))
            label.setPos(-70.0, y - 10.0)
            self._scene.addItem(label)

        for idx, entry in enumerate(entries):
            bar_height = float(entry['width_pixels'])
            x = idx * (bar_width + spacing)
            rect = _BarItem(idx, x, -bar_height, bar_width, bar_height)
            rect.setBrush(BASE_BAR_COLOR)
            rect.setPen(QPen(Qt.NoPen))
            tooltip_lines: List[str] = [f"#{idx + 1}: {bar_height:.1f} px"]
            if entry.get('block_idx') is not None:
                tooltip_lines.append(
                    (
                        f"Block {entry['block_idx']}, string {entry['string_idx']}, "
                        f"line {entry['line_idx']}"
                    )
                )
            snippet = entry.get('text', '')
            if snippet:
                tooltip_lines.append(snippet)
            rect.setToolTip('\n'.join(tooltip_lines))
            self._scene.addItem(rect)
            self._bars.append(rect)

        padding = max_height * 0.1
        self._scene.setSceneRect(
            -bar_width,
            -(max_height + padding),
            total_width + bar_width * 2,
            max_height + padding * 2,
        )
        self._fit_view_to_scene()

    def highlight_bar(self, index: int) -> None:
        if not self._bars:
            return
        index = max(0, min(index, len(self._bars) - 1))
        for i, bar in enumerate(self._bars):
            bar.setBrush(HIGHLIGHT_BAR_COLOR if i == index else BASE_BAR_COLOR)
        self.centerOn(self._bars[index])

    def _fit_view_to_scene(self) -> None:
        if self._scene is None:
            return
        rect = self._scene.itemsBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = self._scene.sceneRect()
        if rect.width() <= 0 or rect.height() <= 0:
            rect = QRectF(rect.x(), rect.y(), 1.0, 1.0)
        margin = max(rect.width(), rect.height()) * 0.05
        if margin > 0:
            rect = QRectF(
                rect.x() - margin,
                rect.y() - margin,
                rect.width() + margin * 2,
                rect.height() + margin * 2,
            )
        self.fitInView(rect, Qt.KeepAspectRatio)


class OriginalTextAnalysisDialog(QDialog):
    """Dialog displaying the top 100 wide strings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Original Text Width Analysis")
        self.resize(960, 640)

        layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Font map:"))
        self._font_combo = QComboBox(self)
        selector_layout.addWidget(self._font_combo)
        selector_layout.addStretch(1)
        layout.addLayout(selector_layout)

        self._chart_view = _AnalysisBarView(self)
        layout.addWidget(self._chart_view)

        self._summary_label = QLabel("Ready")
        self._summary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._summary_label)

        self._table = QTableWidget(self)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["#", "Width (px)", "Block", "String", "Line", "Text"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(220)
        layout.addWidget(self._table)

        self._hint_label = QLabel(
            "Mouse wheel - zoom, middle button - pan; hover bars for details."
        )
        self._hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint_label)

        self._chart_view.on_bar_selected = self._handle_bar_selected
        self._table.itemSelectionChanged.connect(self._handle_table_selection)
        self._table.itemDoubleClicked.connect(self._handle_table_double_click)
        self._font_combo.currentTextChanged.connect(self._on_font_changed)

        self._entries: List[dict] = []
        self._raw_entries: List[dict] = []
        self._font_maps: dict = {}
        self._current_font_name: Optional[str] = None
        self.on_entry_activated: Optional[Callable[[dict], None]] = None
        self._default_char_width = DEFAULT_CHAR_WIDTH_FALLBACK
        self._max_entries = 100
        self._entries_cache: Dict[str, List[dict]] = {}

    def show_entries(
        self,
        raw_entries: Iterable[dict],
        font_maps: dict,
        initial_font: Optional[str],
        precomputed_entries: Optional[Sequence[dict]] = None,
    ) -> None:
        self._raw_entries = [dict(entry) for entry in raw_entries]
        self._font_maps = font_maps or {}
        self._entries_cache.clear()

        if precomputed_entries and initial_font:
            cached: List[dict] = []
            for entry in precomputed_entries:
                new_entry = dict(entry)
                width_val = float(new_entry.get('width_pixels', 0.0) or 0.0)
                new_entry['width_pixels'] = width_val
                cached.append(new_entry)
            cached.sort(key=lambda item: item.get('width_pixels', 0.0), reverse=True)
            self._entries_cache[initial_font] = cached[: self._max_entries]

        self._font_combo.blockSignals(True)
        self._font_combo.clear()
        for font_name in sorted(self._font_maps.keys()):
            self._font_combo.addItem(font_name)
        if self._font_combo.count() == 0:
            self._font_combo.addItem("No font maps")
            self._font_combo.setEnabled(False)
        else:
            self._font_combo.setEnabled(True)
        self._font_combo.blockSignals(False)

        if not self._raw_entries:
            self._entries = []
            self._render_entries([])
            return

        target_font = initial_font if initial_font in self._font_maps else None
        if target_font is None and self._font_combo.count() > 0 and self._font_combo.isEnabled():
            target_font = self._font_combo.itemText(0)

        if target_font:
            index = self._font_combo.findText(target_font)
            if index >= 0:
                self._font_combo.blockSignals(True)
                self._font_combo.setCurrentIndex(index)
                self._font_combo.blockSignals(False)
            self._apply_font(target_font)
        else:
            # Fallback: show provided entries without recalculating
            self._entries = [dict(entry) for entry in self._raw_entries]
            self._render_entries(self._entries)

    def _apply_font(self, font_name: str) -> None:
        self._current_font_name = font_name
        cached_entries = self._entries_cache.get(font_name)
        if cached_entries is not None:
            self._entries = list(cached_entries)
            self._render_entries(self._entries)
            return

        if not self._raw_entries:
            self._entries = []
            self._render_entries([])
            return

        font_map = self._font_maps.get(font_name, {})
        computed: List[dict] = []
        for entry in self._raw_entries:
            text = entry.get('text', '') or ''
            width = calculate_string_width(text, font_map, self._default_char_width)
            new_entry = dict(entry)
            new_entry['width_pixels'] = float(width)
            computed.append(new_entry)

        computed.sort(key=lambda item: item.get('width_pixels', 0.0), reverse=True)
        top_entries = computed[: self._max_entries]
        self._entries_cache[font_name] = list(top_entries)
        self._entries = list(top_entries)
        self._render_entries(self._entries)

    def _render_entries(self, entries: Sequence[dict]) -> None:
        self._chart_view.set_entries(entries)

        if not entries:
            self._summary_label.setText("No data")
            self._table.setRowCount(0)
            self.show()
            self.raise_()
            self.activateWindow()
            return

        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            width = float(entry.get('width_pixels', 0.0))
            block = entry.get('block_idx')
            string = entry.get('string_idx')
            line_idx = entry.get('line_idx')
            text = entry.get('text', '') or ''

            values = [
                str(row + 1),
                f"{width:.1f}",
                str(block) if block is not None else '-',
                str(string) if string is not None else '-',
                str(line_idx) if line_idx is not None else '-',
                text,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._table.setItem(row, col, item)

        top_entry = entries[0]
        font_hint = f"Font: {self._current_font_name}" if self._current_font_name else ""
        summary_parts = [f"Max width: {float(top_entry.get('width_pixels', 0.0)):.1f} px"]
        if top_entry.get('block_idx') is not None:
            summary_parts.append(
                (
                    f"Block {top_entry['block_idx']} / String {top_entry['string_idx']} / "
                    f"Line {top_entry['line_idx']}"
                )
            )
        if font_hint:
            summary_parts.append(font_hint)
        self._summary_label.setText(" - ".join(summary_parts))

        self._table.blockSignals(True)
        self._table.selectRow(0)
        self._table.blockSignals(False)
        self._chart_view.highlight_bar(0)

        self.show()
        self.raise_()
        self.activateWindow()

    def _handle_bar_selected(self, index: int) -> None:
        if not self._entries:
            return
        index = max(0, min(index, len(self._entries) - 1))
        self._table.blockSignals(True)
        self._table.selectRow(index)
        self._table.blockSignals(False)
        self._chart_view.highlight_bar(index)
        item = self._table.item(index, 0)
        if item:
            self._table.scrollToItem(item)

    def _handle_table_selection(self) -> None:
        if not self._entries:
            return
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        self._chart_view.highlight_bar(row)

    def _handle_table_double_click(self, item) -> None:
        row = item.row()
        if 0 <= row < len(self._entries) and self.on_entry_activated:
            self.on_entry_activated(self._entries[row])
        self.accept()

    def _on_font_changed(self, font_name: str) -> None:
        if not font_name or font_name not in self._font_maps:
            return
        self._apply_font(font_name)
