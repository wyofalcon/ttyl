"""Locate the VSCode HWND that owns a given Claude session.

Strategy:
1. Walk the PID tree from the session's recorded pid upward. If an
   ancestor's exe name matches Code.exe, enumerate its top-level
   HWNDs and return the first visible one.
2. If no VSCode ancestor found (e.g. Claude was started outside the
   VSCode integrated terminal), fall back to matching the project
   name in top-level window titles.
3. Return None if neither strategy succeeds.
"""

from __future__ import annotations

from pathlib import PureWindowsPath
from typing import Optional

import psutil

try:
    import win32gui  # type: ignore
    import win32process  # type: ignore
except ImportError:
    win32gui = None  # type: ignore
    win32process = None  # type: ignore


VSCODE_EXE_NAMES = {"code.exe", "code - insiders.exe"}


def _hwnds_for_pid(target_pid: int) -> list[int]:
    if win32gui is None:
        return []
    result: list[int] = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == target_pid and win32gui.GetWindowText(hwnd):
            result.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return result


def _walk_to_vscode(start_pid: int) -> Optional[int]:
    try:
        proc = psutil.Process(start_pid)
    except psutil.Error:
        return None
    for _ in range(12):
        if proc is None:
            return None
        try:
            name = (proc.name() or "").lower()
        except psutil.Error:
            return None
        if name in VSCODE_EXE_NAMES:
            return proc.pid
        try:
            proc = proc.parent()
        except psutil.Error:
            return None
    return None


def _cwd_needles(cwd: str, project_name: str) -> list[str]:
    """Return path-segment candidates from deepest to shallowest plus
    project_name, deduped, lowercased, drive letters and root markers
    omitted. The deepest segments are the most specific and tried first.
    """
    needles: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip().lower()
        if not s or s in seen or s.endswith(":"):
            return
        seen.add(s)
        needles.append(s)

    if project_name:
        add(project_name)
    if cwd:
        # Use PureWindowsPath so backslashes parse correctly on any OS.
        p = PureWindowsPath(cwd)
        for part in reversed(p.parts):
            add(part)
    return needles


def _title_match(project_name: str, cwd: str = "") -> Optional[int]:
    if win32gui is None:
        return None
    needles = _cwd_needles(cwd, project_name)
    if not needles:
        return None

    # Collect all visible VSCode windows once, then pick the first whose
    # title matches a needle in priority order (deepest segment first).
    candidates: list[tuple[int, str]] = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = (win32gui.GetWindowText(hwnd) or "").lower()
        if "visual studio code" in title:
            candidates.append((hwnd, title))

    win32gui.EnumWindows(cb, None)

    for needle in needles:
        for hwnd, title in candidates:
            if needle in title:
                return hwnd
    return None


def get_foreground_window_title() -> str:
    """Return the title of the OS foreground window, or '' if unavailable."""
    if win32gui is None:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ""
        return win32gui.GetWindowText(hwnd) or ""
    except Exception:
        return ""


def title_matches_session(title: str, cwd: str, project_name: str) -> bool:
    """True if the given window title looks like the VSCode window for this
    session — i.e., contains 'visual studio code' and any cwd path segment.
    """
    if not title:
        return False
    title_l = title.lower()
    if "visual studio code" not in title_l:
        return False
    for needle in _cwd_needles(cwd, project_name):
        if needle in title_l:
            return True
    return False


def find_hwnd(pid: int, cwd: str, project_name: str) -> Optional[int]:
    """Return the best-guess HWND for the VSCode window owning this session."""
    if pid > 1:
        vscode_pid = _walk_to_vscode(pid)
        if vscode_pid is not None:
            hwnds = _hwnds_for_pid(vscode_pid)
            if hwnds:
                return hwnds[0]
    return _title_match(project_name, cwd)


def focus(hwnd: int) -> bool:
    """Bring the given HWND to the foreground. Returns True on success."""
    if win32gui is None:
        return False
    try:
        win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE - unminimize if needed
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False
