"""Filesystem watcher for ~/.claude/cache-timers/.

Emits Qt signals when session JSON files appear, change, disappear, or are
replaced (same cwd, new session_id). Also garbage-collects files whose
last_update is older than stale_seconds.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


def _default_pid_alive(pid: int) -> bool:
    # pid <= 1 means "unknown" (PPID may not be recorded reliably under
    # Git Bash on Windows); treat as alive so we never falsely evict.
    if pid <= 1:
        return True
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        # Any failure (psutil missing, permissions, etc.) → assume alive
        # so we degrade to time-based GC instead of evicting incorrectly.
        return True


class CacheTimersWatcher(QObject):
    session_added = pyqtSignal(str)
    session_updated = pyqtSignal(str)
    session_removed = pyqtSignal(str)
    session_replaced = pyqtSignal(str, str)

    def __init__(
        self,
        directory: Path,
        poll_interval_ms: int = 1000,
        stale_seconds: int = 3600,
        pid_alive_fn: Callable[[int], bool] = _default_pid_alive,
    ):
        super().__init__()
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._stale = stale_seconds
        self._pid_alive = pid_alive_fn
        self._known: Dict[str, tuple[float, str]] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._scan)
        self._timer.start()
        # Defer the first scan so that consumers constructed after the
        # watcher have time to connect signals before any session_added
        # fires for files that already exist at startup.
        QTimer.singleShot(0, self._scan)

    def _scan(self) -> None:
        now = time.time()
        current: Dict[str, tuple[float, str]] = {}

        for path in self._dir.glob("*.json"):
            # Read mtime BEFORE the file contents. If we read first and stat
            # second, a write landing between the two would record a newer
            # mtime than the data we parsed — and on the next scan the mtime
            # comparison would say "unchanged" and we'd never re-emit
            # session_updated for the version we missed. Stat-then-read at
            # worst causes a spurious extra emit, never a missed one.
            try:
                mtime = path.stat().st_mtime
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            sid = data.get("session_id") or path.stem
            # Explicit None check — last_update=0 is a valid "unix epoch zero",
            # a common sentinel meaning "this file is stale on purpose".
            lu = data.get("last_update")
            if lu is None:
                lu = data.get("epoch", 0)
            last = int(lu)
            cwd = data.get("cwd", "")
            if (now - last) > self._stale:
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            pid = data.get("pid")
            if isinstance(pid, int) and not self._pid_alive(pid):
                # Owning Claude process is gone (crash / hard kill / closed
                # terminal) and the SessionEnd hook never ran. Drop the file
                # so the tile can remove the row promptly.
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            current[sid] = (mtime, cwd)

        replaced_old: set[str] = set()
        replaced_new: set[str] = set()
        for sid, (_, cwd) in current.items():
            if sid in self._known:
                continue
            for old_sid, (_, old_cwd) in self._known.items():
                if old_cwd and old_cwd == cwd and old_sid not in current:
                    self.session_replaced.emit(old_sid, sid)
                    replaced_old.add(old_sid)
                    replaced_new.add(sid)
                    break

        for sid, (mtime, _cwd) in current.items():
            abs_path = str(self._dir / f"{sid}.json")
            if sid not in self._known and sid not in replaced_new:
                self.session_added.emit(abs_path)
            elif sid in self._known and self._known[sid][0] != mtime:
                self.session_updated.emit(abs_path)

        for sid in self._known:
            if sid not in current and sid not in replaced_old:
                self.session_removed.emit(sid)

        self._known = current
