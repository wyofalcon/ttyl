"""Frameless pill window that displays one TTYL session's state."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from ttyl.state import TimerState, compute


_PALETTE = {
    "gray": QColor("#6b7280"),
    "blue": QColor("#2563eb"),
    "green": QColor("#16a34a"),
    "yellow": QColor("#ca8a04"),
    "red": QColor("#dc2626"),
}


class TimerWindow(QWidget):
    focus_requested = pyqtSignal(dict)
    position_changed = pyqtSignal(int, int)

    _flash_counter = 0

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
        self._drag_origin = None

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

    def flash_count(self) -> int:
        return self._flash_counter

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        origin = self._drag_origin
        self._drag_origin = None
        if origin is None:
            super().mouseReleaseEvent(event)
            return
        released = event.globalPosition().toPoint()
        end_top_left = released - origin
        moved = (end_top_left - self.frameGeometry().topLeft()).manhattanLength() > 4
        if moved:
            self.position_changed.emit(self.pos().x(), self.pos().y())
        else:
            try:
                data = json.loads(self._json_path.read_text())
                self.focus_requested.emit(data)
            except (OSError, json.JSONDecodeError):
                pass
        super().mouseReleaseEvent(event)

    def _play_finish_animation(self) -> None:
        self._flash_counter += 1

        geo = self.geometry()
        big = QRect(geo.x() - 14, geo.y() - 3, geo.width() + 28, geo.height() + 6)
        small = QRect(geo.x() + 3, geo.y() + 1, geo.width() - 6, geo.height() - 2)

        scale = QSequentialAnimationGroup(self)
        up = QPropertyAnimation(self, b"geometry", self)
        up.setStartValue(geo)
        up.setEndValue(big)
        up.setDuration(180)
        up.setEasingCurve(QEasingCurve.Type.OutBack)
        down = QPropertyAnimation(self, b"geometry", self)
        down.setStartValue(big)
        down.setEndValue(small)
        down.setDuration(240)
        down.setEasingCurve(QEasingCurve.Type.InOutSine)
        settle = QPropertyAnimation(self, b"geometry", self)
        settle.setStartValue(small)
        settle.setEndValue(geo)
        settle.setDuration(180)
        settle.setEasingCurve(QEasingCurve.Type.OutCubic)
        scale.addAnimation(up)
        scale.addAnimation(down)
        scale.addAnimation(settle)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(_PALETTE[self._current.color].lighter(130))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        glow = QSequentialAnimationGroup(self)
        for _ in range(3):
            up_g = QPropertyAnimation(shadow, b"blurRadius", self)
            up_g.setStartValue(0)
            up_g.setEndValue(40)
            up_g.setDuration(200)
            down_g = QPropertyAnimation(shadow, b"blurRadius", self)
            down_g.setStartValue(40)
            down_g.setEndValue(0)
            down_g.setDuration(200)
            glow.addAnimation(up_g)
            glow.addAnimation(down_g)

        combo = QParallelAnimationGroup(self)
        combo.addAnimation(scale)
        combo.addAnimation(glow)
        combo.finished.connect(lambda: self.setGraphicsEffect(None))
        combo.start()

    def _apply(self, state: TimerState) -> None:
        prev = self._current
        self._current = state
        self._label.setText(state.label)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, _PALETTE[state.color])
        self.setPalette(palette)

        if prev is not None and TimerState.is_finish_transition(prev, state):
            self._play_finish_animation()
