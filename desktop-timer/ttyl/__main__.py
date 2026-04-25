"""TTYL entry point - tray, watcher, timer windows, vdesk pinning."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ttyl import vdesk
from ttyl.config import Config
from ttyl.timer_window import TimerWindow
from ttyl.watcher import CacheTimersWatcher


APPDATA = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "ttyl"
CONFIG_PATH = APPDATA / "config.json"


def _timers_dir() -> Path:
    return Path(os.path.expanduser("~/.claude/cache-timers"))


class TtylApp:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.windows: Dict[str, TimerWindow] = {}
        self.config = Config(CONFIG_PATH)
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

        cwd = self._cwd_for(path)
        pos = None
        if self.config.position_mode == "remember" and cwd:
            pos = self.config.get_position(cwd)

        if pos is not None:
            w.move(*pos)
        else:
            idx = len(self.windows)
            screen = self.qapp.primaryScreen().availableGeometry()
            w.move(screen.right() - 180, screen.top() + 20 + idx * 40)

        w.refresh()
        w.show()
        self.windows[sid] = w
        w.focus_requested.connect(self._on_focus_request)
        w.position_changed.connect(lambda x, y, p=path: self._persist_position(p, x, y))
        w.dismiss_requested.connect(self._on_dismiss)

    def _cwd_for(self, path: str) -> str:
        try:
            return json.loads(Path(path).read_text()).get("cwd", "")
        except (OSError, json.JSONDecodeError):
            return ""

    def _on_dismiss(self, sid: str) -> None:
        path = _timers_dir() / f"{sid}.json"
        try:
            path.unlink()
        except OSError:
            pass

    def _persist_position(self, path: str, x: int, y: int) -> None:
        if self.config.position_mode != "remember":
            return
        cwd = self._cwd_for(path)
        if cwd:
            self.config.set_position(cwd, x, y)

    def _on_focus_request(self, row: dict) -> None:
        from ttyl import vscode_finder
        hwnd = vscode_finder.find_hwnd(
            pid=int(row.get("pid") or 0),
            cwd=row.get("cwd", ""),
            project_name=row.get("project_name", ""),
        )
        if hwnd:
            vscode_finder.focus(hwnd)

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

    mode_menu = menu.addMenu("Position mode")
    remember = QAction("Remember per project", mode_menu, checkable=True)
    cascade = QAction("Cascade in corner", mode_menu, checkable=True)
    remember.setChecked(ttyl.config.position_mode == "remember")
    cascade.setChecked(ttyl.config.position_mode == "cascade")

    def _set_mode(value):
        ttyl.config.position_mode = value
        remember.setChecked(value == "remember")
        cascade.setChecked(value == "cascade")

    remember.triggered.connect(lambda: _set_mode("remember"))
    cascade.triggered.connect(lambda: _set_mode("cascade"))
    mode_menu.addAction(remember)
    mode_menu.addAction(cascade)

    menu.addSeparator()

    from ttyl.config import install_startup, remove_startup, is_startup_installed

    startup = QAction("Start on login", menu, checkable=True)
    startup.setChecked(is_startup_installed())

    def _toggle_startup():
        if startup.isChecked():
            install_startup(sys.executable)
        else:
            remove_startup()

    startup.triggered.connect(_toggle_startup)
    menu.addAction(startup)

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
