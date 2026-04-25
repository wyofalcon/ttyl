"""Tests for ttyl.timer_row - per-session row widget."""

from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import Qt

from ttyl.timer_row import TimerRow


@pytest.fixture
def row(make_session, qtbot):
    path = make_session(session_id="s1", state="idle", epoch=1000, project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 1050, ttl=300)
    qtbot.addWidget(r)
    r.refresh()
    return r


def test_row_renders_countdown_text(row):
    assert "4:10" in row.label_text()
    assert "demo" in row.label_text()


def test_row_color_is_green_for_long_remaining(row):
    assert row.current_color() == "green"


def test_row_switches_to_red_when_expired(make_session, qtbot):
    path = make_session(session_id="s2", state="idle", epoch=1000, project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 5000, ttl=300)
    qtbot.addWidget(r)
    r.refresh()
    assert r.current_color() == "red"
    assert "cache cold" in r.label_text()


def test_row_reloads_state_from_disk(make_session, qtbot):
    path = make_session(session_id="s3", state="none", project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 1000, ttl=300)
    qtbot.addWidget(r)
    r.refresh()
    assert "no cache" in r.label_text()

    data = json.loads(path.read_text())
    data["state"] = "active"
    path.write_text(json.dumps(data))
    r.refresh()
    assert "active" in r.label_text()
    assert r.current_color() == "blue"


def test_flash_animation_triggers_on_active_to_idle(make_session, qtbot):
    path = make_session(session_id="flash1", state="active", project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 1000, ttl=300)
    qtbot.addWidget(r)
    r.refresh()
    assert r.flash_count() == 0

    data = json.loads(path.read_text())
    data["state"] = "idle"
    data["epoch"] = 1000
    path.write_text(json.dumps(data))
    r.refresh()

    assert r.flash_count() == 1


def test_flash_does_not_trigger_on_idle_to_idle(make_session, qtbot):
    path = make_session(session_id="flash2", state="idle", epoch=1000, project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 1000, ttl=300)
    qtbot.addWidget(r)
    r.refresh()
    r.refresh()
    assert r.flash_count() == 0


def test_foreground_flag_defaults_off(make_session, qtbot):
    path = make_session(session_id="fg0", project_name="demo")
    r = TimerRow(json_path=path)
    qtbot.addWidget(r)
    assert r.is_foreground() is False


def test_set_foreground_toggles_state_and_repaints(make_session, qtbot):
    path = make_session(session_id="fg1", project_name="demo")
    r = TimerRow(json_path=path)
    qtbot.addWidget(r)
    r.show()
    qtbot.waitExposed(r)

    r.set_foreground(True)
    assert r.is_foreground() is True

    # Idempotent — calling with the same value doesn't toggle
    r.set_foreground(True)
    assert r.is_foreground() is True

    r.set_foreground(False)
    assert r.is_foreground() is False


def test_click_emits_focus_request(make_session, qtbot):
    path = make_session(session_id="click1", project_name="demo")
    r = TimerRow(json_path=path, now_fn=lambda: 1050, ttl=300)
    qtbot.addWidget(r)
    r.show()
    r.refresh()
    with qtbot.waitSignal(r.focus_requested, timeout=500) as sig:
        qtbot.mouseClick(r, Qt.MouseButton.LeftButton)
    assert sig.args[0]["project_name"] == "demo"
