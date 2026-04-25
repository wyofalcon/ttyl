"""Frameless pill window that displays one TTYL session's state."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QLabel, QWidget

from ttyl.state import TimerState, compute


_PALETTE = {
    "gray": QColor("#6b7280"),
    "blue": QColor("#2563eb"),
    "green": QColor("#16a34a"),
    "yellow": QColor("#ca8a04"),
    "red": QColor("#dc2626"),
}


class TimerWindow(QWidget):
    def __init__(
        self,
        json_path: Path,
        now_fn: Callable[[], int] = lambda: int(time.time()),
        ttl: int = 300,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._json_path = Path(json_path)
        self._now_fn = now_fn
        self._ttl = ttl
        self._current: Optional[TimerState] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(160, 34)
        self.setAutoFillBackground(True)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setGeometry(0, 0, 160, 34)
        self._label.setStyleSheet("color: white; font: 600 11pt 'Segoe UI';")

    def label_text(self) -> str:
        return self._label.text()

    def current_color(self) -> str:
        return self._current.color if self._current else "gray"

    def refresh(self) -> None:
        try:
            data = json.loads(self._json_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        new_state = compute(data, now=self._now_fn(), ttl=self._ttl)
        self._apply(new_state)

    def rebind(self, new_path: Path) -> None:
        """Switch the window to watching a different session JSON file."""
        self._json_path = Path(new_path)
        self._current = None  # suppress a false finish-transition on next refresh

    def _apply(self, state: TimerState) -> None:
        self._current = state
        self._label.setText(state.label)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, _PALETTE[state.color])
        self.setPalette(palette)
