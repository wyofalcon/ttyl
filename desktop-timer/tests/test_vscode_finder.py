"""Tests for ttyl.vscode_finder - mocks psutil and win32gui."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ttyl.vscode_finder import find_hwnd


def _proc(pid: int, name: str, parent=None):
    p = MagicMock()
    p.pid = pid
    p.name.return_value = name
    p.parent.return_value = parent
    return p


def test_pid_walk_finds_code_exe_parent():
    leaf = _proc(1, "bash.exe")
    mid = _proc(2, "claude.exe")
    code = _proc(3, "Code.exe")
    leaf.parent.return_value = mid
    mid.parent.return_value = code
    code.parent.return_value = None

    with patch("ttyl.vscode_finder.psutil.Process", return_value=leaf), \
         patch("ttyl.vscode_finder._hwnds_for_pid", return_value=[111]):
        hwnd = find_hwnd(pid=1, cwd="/c/u/p/demo", project_name="demo")
    assert hwnd == 111


def test_pid_walk_falls_back_to_title_match():
    leaf = _proc(1, "bash.exe")
    leaf.parent.return_value = None

    def fake_enum(callback, arg):
        callback(222, arg)

    def fake_title(hwnd):
        return "main.py - demo - Visual Studio Code"

    with patch("ttyl.vscode_finder.psutil.Process", return_value=leaf), \
         patch("ttyl.vscode_finder.win32gui.EnumWindows", side_effect=fake_enum), \
         patch("ttyl.vscode_finder.win32gui.GetWindowText", side_effect=fake_title), \
         patch("ttyl.vscode_finder.win32gui.IsWindowVisible", return_value=True):
        hwnd = find_hwnd(pid=1, cwd="/c/u/p/demo", project_name="demo")
    assert hwnd == 222


def test_returns_none_when_nothing_matches():
    leaf = _proc(1, "bash.exe")
    leaf.parent.return_value = None
    with patch("ttyl.vscode_finder.psutil.Process", return_value=leaf), \
         patch("ttyl.vscode_finder.win32gui.EnumWindows", side_effect=lambda cb, a: None):
        hwnd = find_hwnd(pid=1, cwd="/c/u/p/demo", project_name="demo")
    assert hwnd is None
