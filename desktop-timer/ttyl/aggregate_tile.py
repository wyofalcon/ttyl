"""Single floating tile that aggregates all active TTYL session rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from ttyl.timer_row import TimerRow


def _default_foreground_title() -> str:
    from ttyl import vscode_finder
    return vscode_finder.get_foreground_window_title()


def _default_title_matches(title: str, cwd: str, project_name: str) -> bool:
    from ttyl import vscode_finder
    return vscode_finder.title_matches_session(title, cwd, project_name)


class AggregateTile(QWidget):
    focus_requested = pyqtSignal(dict)
    dismiss_requested = pyqtSignal(str)
    position_changed = pyqtSignal(int, int)

    TILE_WIDTH = 224

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        foreground_title_fn: Callable[[], str] = _default_foreground_title,
        title_matches_fn: Callable[[str, str, str], bool] = _default_title_matches,
        ttl: int = 300,
    ):
        super().__init__(parent)
        self._foreground_title_fn = foreground_title_fn
        self._title_matches_fn = title_matches_fn
        self._ttl = ttl
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        self.setPalette(palette)

        self._rows: Dict[str, TimerRow] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self._layout = layout
        self.setFixedWidth(self.TILE_WIDTH)
        self.hide()

        # Tick every second so countdown labels advance even when the
        # underlying state file isn't being written (between hook events).
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._tick_all)
        self._tick.start()

    def _tick_all(self) -> None:
        for row in self._rows.values():
            row.refresh()
        self._update_foreground_marker()

    def _update_foreground_marker(self) -> None:
        title = self._foreground_title_fn()
        if not title:
            for row in self._rows.values():
                row.set_foreground(False)
            return
        for row in self._rows.values():
            cwd, project_name = self._row_metadata(row)
            row.set_foreground(self._title_matches_fn(title, cwd, project_name))

    @staticmethod
    def _row_metadata(row: TimerRow) -> tuple[str, str]:
        try:
            data = json.loads(row.json_path.read_text())
        except (OSError, json.JSONDecodeError):
            return ("", "")
        return data.get("cwd", "") or "", data.get("project_name", "") or ""

    def add_row(self, sid: str, json_path: Path) -> TimerRow:
        if sid in self._rows:
            return self._rows[sid]
        row = TimerRow(json_path=json_path, ttl=self._ttl, parent=self)
        row.focus_requested.connect(self.focus_requested.emit)
        row.dismiss_requested.connect(self.dismiss_requested.emit)
        row.drag_finished.connect(self._emit_position)
        self._layout.addWidget(row)
        self._rows[sid] = row
        self.adjustSize()
        if not self.isVisible():
            self.show()
        return row

    def remove_row(self, sid: str) -> None:
        row = self._rows.pop(sid, None)
        if row is None:
            return
        self._layout.removeWidget(row)
        row.deleteLater()
        self.adjustSize()
        if not self._rows:
            self.hide()

    def update_row(self, sid: str) -> None:
        row = self._rows.get(sid)
        if row is not None:
            row.refresh()

    def replace_row(self, old_sid: str, new_sid: str, new_path: Path) -> None:
        row = self._rows.pop(old_sid, None)
        if row is None:
            return
        row.rebind(new_path)
        self._rows[new_sid] = row

    def rows(self) -> Dict[str, TimerRow]:
        return dict(self._rows)

    def _emit_position(self) -> None:
        self.position_changed.emit(self.pos().x(), self.pos().y())
