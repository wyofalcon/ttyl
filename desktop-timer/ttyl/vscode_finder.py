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


def _title_match(project_name: str) -> Optional[int]:
    if win32gui is None or not project_name:
        return None
    needle = project_name.lower()
    match: list[int] = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = (win32gui.GetWindowText(hwnd) or "").lower()
        if needle in title and "visual studio code" in title:
            match.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return match[0] if match else None


def find_hwnd(pid: int, cwd: str, project_name: str) -> Optional[int]:
    """Return the best-guess HWND for the VSCode window owning this session."""
    vscode_pid = _walk_to_vscode(pid)
    if vscode_pid is not None:
        hwnds = _hwnds_for_pid(vscode_pid)
        if hwnds:
            return hwnds[0]
    return _title_match(project_name)


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
