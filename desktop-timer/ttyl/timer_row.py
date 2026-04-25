"""One row inside the AggregateTile - one Claude session."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from ttyl.state import TimerState, compute


_PALETTE = {
    "gray": QColor("#6b7280"),
    "blue": QColor("#2563eb"),
    "green": QColor("#16a34a"),
    "yellow": QColor("#ca8a04"),
    "red": QColor("#dc2626"),
}

_FOREGROUND_BORDER_COLOR = QColor("#fde047")  # yellow-300, "you are here"
_FOREGROUND_BORDER_WIDTH = 2


class TimerRow(QWidget):
    focus_requested = pyqtSignal(dict)
    dismiss_requested = pyqtSignal(str)
    drag_finished = pyqtSignal()

    ROW_WIDTH = 220
    ROW_HEIGHT = 30

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
        self._press_global = None
        self._press_tile_pos = None
        self._dragging = False
        self._flash_counter = 0
        self._is_foreground = False

        self.setFixedSize(self.ROW_WIDTH, self.ROW_HEIGHT)
        self.setAutoFillBackground(True)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setGeometry(0, 0, self.ROW_WIDTH, self.ROW_HEIGHT)
        self._label.setStyleSheet("color: white; font: 600 11pt 'Segoe UI';")

    @property
    def json_path(self) -> Path:
        return self._json_path

    def label_text(self) -> str:
        return self._label.text()

    def current_color(self) -> str:
        return self._current.color if self._current else "gray"

    def flash_count(self) -> int:
        return self._flash_counter

    def is_foreground(self) -> bool:
        return self._is_foreground

    def set_foreground(self, value: bool) -> None:
        if value == self._is_foreground:
            return
        self._is_foreground = value
        self.update()  # request a repaint

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._is_foreground:
            return
        painter = QPainter(self)
        try:
            pen = QPen(_FOREGROUND_BORDER_COLOR)
            pen.setWidth(_FOREGROUND_BORDER_WIDTH)
            painter.setPen(pen)
            inset = _FOREGROUND_BORDER_WIDTH // 2
            painter.drawRect(self.rect().adjusted(inset, inset, -inset, -inset))
        finally:
            painter.end()

    def refresh(self) -> None:
        try:
            data = json.loads(self._json_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        new_state = compute(data, now=self._now_fn(), ttl=self._ttl)
        self._apply(new_state)

    def rebind(self, new_path: Path) -> None:
        self._json_path = Path(new_path)
        self._current = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_tile_pos = self.window().pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_global is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = event.globalPosition().toPoint() - self._press_global
            if self._dragging or delta.manhattanLength() > 4:
                self._dragging = True
                self.window().move(self._press_tile_pos + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        was_dragging = self._dragging
        self._press_global = None
        self._press_tile_pos = None
        self._dragging = False
        if was_dragging:
            self.drag_finished.emit()
        else:
            try:
                data = json.loads(self._json_path.read_text())
                self.focus_requested.emit(data)
            except (OSError, json.JSONDecodeError):
                pass
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QApplication, QMenu

        menu = QMenu(self)
        dismiss = menu.addAction("Dismiss (delete state file)")
        copy_id = menu.addAction("Copy session ID")
        choice = getattr(menu, "exec")(event.globalPos())
        try:
            data = json.loads(self._json_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        if choice == dismiss:
            self.dismiss_requested.emit(data.get("session_id", self._json_path.stem))
        elif choice == copy_id:
            QApplication.clipboard().setText(data.get("session_id", ""))

    def _play_finish_animation(self) -> None:
        self._flash_counter += 1

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(_PALETTE[self._current.color].lighter(140))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        glow = QSequentialAnimationGroup(self)
        for _ in range(3):
            up = QPropertyAnimation(shadow, b"blurRadius", self)
            up.setStartValue(0)
            up.setEndValue(40)
            up.setDuration(200)
            down = QPropertyAnimation(shadow, b"blurRadius", self)
            down.setStartValue(40)
            down.setEndValue(0)
            down.setDuration(200)
            glow.addAnimation(up)
            glow.addAnimation(down)
        glow.finished.connect(lambda: self.setGraphicsEffect(None))
        glow.start()

    def _apply(self, state: TimerState) -> None:
        prev = self._current
        self._current = state
        self._label.setText(state.label)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, _PALETTE[state.color])
        self.setPalette(palette)
        if prev is not None and TimerState.is_finish_transition(prev, state):
            self._play_finish_animation()
