"""Widget tests for ttyl.timer_window - non-interactive rendering only."""

from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import Qt

from ttyl.timer_window import TimerWindow


@pytest.fixture
def window(make_session, qtbot):
    path = make_session(session_id="s1", state="idle", epoch=1000, project_name="demo")
    w = TimerWindow(json_path=path, now_fn=lambda: 1050, ttl=300)
    qtbot.addWidget(w)
    w.refresh()
    return w


def test_window_is_frameless_and_top(window):
    flags = window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_window_renders_countdown_text(window):
    assert "4:10" in window.label_text()
    assert "demo" in window.label_text()


def test_window_color_is_green_for_long_remaining(window):
    assert window.current_color() == "green"


def test_window_switches_to_red_when_expired(make_session, qtbot):
    path = make_session(session_id="s2", state="idle", epoch=1000, project_name="demo")
    w = TimerWindow(json_path=path, now_fn=lambda: 5000, ttl=300)
    qtbot.addWidget(w)
    w.refresh()
    assert w.current_color() == "red"
    assert "cache cold" in w.label_text()


def test_window_reloads_state_from_disk(make_session, qtbot):
    path = make_session(session_id="s3", state="none", project_name="demo")
    w = TimerWindow(json_path=path, now_fn=lambda: 1000, ttl=300)
    qtbot.addWidget(w)
    w.refresh()
    assert "no cache" in w.label_text()

    data = json.loads(path.read_text())
    data["state"] = "active"
    path.write_text(json.dumps(data))
    w.refresh()
    assert "active" in w.label_text()
    assert w.current_color() == "blue"
