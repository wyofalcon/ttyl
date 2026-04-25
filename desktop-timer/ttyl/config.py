"""Persistent config for TTYL - positions, toggles, start-on-login."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class Config:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._data: dict = {
            "position_mode": "remember",  # or "cascade"
            "positions": {},
            "flash_on_finish": True,
            "chime_on_finish": False,
        }
        if self._path.exists():
            try:
                self._data.update(json.loads(self._path.read_text()))
            except (OSError, json.JSONDecodeError):
                pass

    @property
    def position_mode(self) -> str:
        return self._data["position_mode"]

    @position_mode.setter
    def position_mode(self, value: str) -> None:
        assert value in ("remember", "cascade")
        self._data["position_mode"] = value
        self._save()

    @property
    def flash_on_finish(self) -> bool:
        return bool(self._data.get("flash_on_finish", True))

    @flash_on_finish.setter
    def flash_on_finish(self, value: bool) -> None:
        self._data["flash_on_finish"] = bool(value)
        self._save()

    def get_position(self, cwd: str) -> Optional[tuple[int, int]]:
        pos = self._data["positions"].get(cwd)
        if pos is None:
            return None
        return int(pos[0]), int(pos[1])

    def set_position(self, cwd: str, x: int, y: int) -> None:
        self._data["positions"][cwd] = [int(x), int(y)]
        self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def install_startup(target_exe: str) -> bool:
    """Create a Startup folder shortcut to target_exe. Returns True on success."""
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
        link_path = _startup_dir() / "TTYL.lnk"
        _startup_dir().mkdir(parents=True, exist_ok=True)
        shortcut = shell.CreateShortcut(str(link_path))
        shortcut.TargetPath = target_exe
        shortcut.WorkingDirectory = str(Path(target_exe).parent)
        shortcut.IconLocation = target_exe
        shortcut.save()
        return True
    except Exception:
        return False


def remove_startup() -> bool:
    link_path = _startup_dir() / "TTYL.lnk"
    try:
        link_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def is_startup_installed() -> bool:
    return (_startup_dir() / "TTYL.lnk").exists()
