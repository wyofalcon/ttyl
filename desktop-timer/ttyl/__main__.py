"""TTYL entry point - tray, watcher, aggregate tile, vdesk pinning."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QSharedMemory, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ttyl import vdesk
from ttyl.aggregate_tile import AggregateTile
from ttyl.config import Config
from ttyl.watcher import CacheTimersWatcher


APPDATA = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "ttyl"
CONFIG_PATH = APPDATA / "config.json"


def _timers_dir() -> Path:
    return Path(os.path.expanduser("~/.claude/cache-timers"))


def _ttl_seconds() -> int:
    raw = os.environ.get("TTYL_TTL_SECONDS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 300


class TtylApp:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.config = Config(CONFIG_PATH)
        self.tile = AggregateTile(ttl=_ttl_seconds())
        self._restore_position()
        self.tile.focus_requested.connect(self._on_focus_request)
        self.tile.dismiss_requested.connect(self._on_dismiss)
        self.tile.position_changed.connect(self._on_position_changed)

        self.watcher = CacheTimersWatcher(_timers_dir())
        self.watcher.session_added.connect(self._on_added)
        self.watcher.session_updated.connect(self._on_updated)
        self.watcher.session_removed.connect(self._on_removed)
        self.watcher.session_replaced.connect(self._on_replaced)

        self.pin_timer = QTimer(self.qapp)
        self.pin_timer.setInterval(1000)
        self.pin_timer.timeout.connect(self._pin_tile)
        self.pin_timer.start()

    def _restore_position(self) -> None:
        pos = self.config.tile_position
        if pos is not None:
            self.tile.move(*pos)
        else:
            screen = self.qapp.primaryScreen().availableGeometry()
            self.tile.move(
                screen.right() - self.tile.TILE_WIDTH - 8,
                screen.top() + 20,
            )

    def _sid_from_path(self, path: str) -> str:
        return Path(path).stem

    def _on_added(self, path: str) -> None:
        sid = self._sid_from_path(path)
        row = self.tile.add_row(sid, Path(path))
        row.refresh()

    def _on_updated(self, path: str) -> None:
        self.tile.update_row(self._sid_from_path(path))

    def _on_removed(self, sid: str) -> None:
        self.tile.remove_row(sid)

    def _on_replaced(self, old_sid: str, new_sid: str) -> None:
        new_path = _timers_dir() / f"{new_sid}.json"
        self.tile.replace_row(old_sid, new_sid, new_path)
        self.tile.update_row(new_sid)

    def _on_focus_request(self, row: dict) -> None:
        from ttyl import vscode_finder
        hwnd = vscode_finder.find_hwnd(
            pid=int(row.get("pid") or 0),
            cwd=row.get("cwd", ""),
            project_name=row.get("project_name", ""),
        )
        if hwnd:
            vscode_finder.focus(hwnd)

    def _on_dismiss(self, sid: str) -> None:
        path = _timers_dir() / f"{sid}.json"
        try:
            path.unlink()
        except OSError:
            pass

    def _on_position_changed(self, x: int, y: int) -> None:
        self.config.tile_position = (x, y)

    def _pin_tile(self) -> None:
        if not self.tile.isVisible():
            return
        hwnd = int(self.tile.winId())
        if not vdesk.is_on_current_desktop(hwnd):
            vdesk.move_to_current_desktop(hwnd)


def _build_tray(qapp: QApplication, ttyl: TtylApp) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon.fromTheme("appointment"))
    tray.setToolTip("TTYL")
    menu = QMenu()

    show_tile = QAction("Show tile", menu)
    show_tile.triggered.connect(ttyl.tile.show)
    hide_tile = QAction("Hide tile", menu)
    hide_tile.triggered.connect(ttyl.tile.hide)
    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(qapp.quit)

    for a in (show_tile, hide_tile):
        menu.addAction(a)
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

    lock = QSharedMemory("ttyl-singleton-v1")
    if not lock.create(1):
        return 0

    qapp.setQuitOnLastWindowClosed(False)
    ttyl = TtylApp(qapp)
    tray = _build_tray(qapp, ttyl)
    _ = tray
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
