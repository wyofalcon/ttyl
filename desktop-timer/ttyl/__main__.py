"""TTYL entry point - tray, watcher, timer windows, vdesk pinning."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ttyl import vdesk
from ttyl.timer_window import TimerWindow
from ttyl.watcher import CacheTimersWatcher


def _timers_dir() -> Path:
    return Path(os.path.expanduser("~/.claude/cache-timers"))


class TtylApp:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.windows: Dict[str, TimerWindow] = {}
        self.watcher = CacheTimersWatcher(_timers_dir())
        self.watcher.session_added.connect(self._on_added)
        self.watcher.session_updated.connect(self._on_updated)
        self.watcher.session_removed.connect(self._on_removed)
        self.watcher.session_replaced.connect(self._on_replaced)

        self.pin_timer = QTimer(self.qapp)
        self.pin_timer.setInterval(1000)
        self.pin_timer.timeout.connect(self._pin_all)
        self.pin_timer.start()

    def _sid_from_path(self, path: str) -> str:
        return Path(path).stem

    def _on_added(self, path: str) -> None:
        sid = self._sid_from_path(path)
        if sid in self.windows:
            return
        w = TimerWindow(json_path=Path(path))
        idx = len(self.windows)
        screen = self.qapp.primaryScreen().availableGeometry()
        w.move(screen.right() - 180, screen.top() + 20 + idx * 40)
        w.refresh()
        w.show()
        self.windows[sid] = w

    def _on_updated(self, path: str) -> None:
        sid = self._sid_from_path(path)
        w = self.windows.get(sid)
        if w is not None:
            w.refresh()

    def _on_removed(self, sid: str) -> None:
        w = self.windows.pop(sid, None)
        if w is not None:
            w.close()
            w.deleteLater()

    def _on_replaced(self, old_sid: str, new_sid: str) -> None:
        w = self.windows.pop(old_sid, None)
        if w is None:
            return
        new_path = _timers_dir() / f"{new_sid}.json"
        w.rebind(new_path)
        w.refresh()
        self.windows[new_sid] = w

    def _pin_all(self) -> None:
        for w in self.windows.values():
            hwnd = int(w.winId())
            if not vdesk.is_on_current_desktop(hwnd):
                vdesk.move_to_current_desktop(hwnd)


def _build_tray(qapp: QApplication, ttyl: TtylApp) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon.fromTheme("appointment"))
    tray.setToolTip("TTYL")
    menu = QMenu()

    show_all = QAction("Show all timers", menu)
    show_all.triggered.connect(lambda: [w.show() for w in ttyl.windows.values()])
    hide_all = QAction("Hide all timers", menu)
    hide_all.triggered.connect(lambda: [w.hide() for w in ttyl.windows.values()])
    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(qapp.quit)

    for a in (show_all, hide_all):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()
    return tray


def main() -> int:
    QCoreApplication.setApplicationName("TTYL")
    QCoreApplication.setOrganizationName("TTYL")
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    ttyl = TtylApp(qapp)
    tray = _build_tray(qapp, ttyl)
    _ = tray
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
