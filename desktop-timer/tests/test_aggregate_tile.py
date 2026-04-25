"""Tests for ttyl.aggregate_tile - one tile, many rows."""

from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import Qt

from ttyl.aggregate_tile import AggregateTile


@pytest.fixture
def tile(qtbot):
    # Default fixture: no foreground (returns "" from title fn).
    t = AggregateTile(foreground_title_fn=lambda: "")
    qtbot.addWidget(t)
    return t


def test_tile_is_frameless_and_top(tile):
    flags = tile.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_tile_starts_hidden(tile):
    assert not tile.isVisible()


def test_add_row_shows_tile_and_creates_row(tile, make_session):
    path = make_session(session_id="s1", state="idle", project_name="alpha")
    row = tile.add_row("s1", path)
    row.refresh()
    assert "s1" in tile.rows()
    assert tile.isVisible()
    assert "alpha" in row.label_text()


def test_remove_last_row_hides_tile(tile, make_session):
    path = make_session(session_id="s1", project_name="alpha")
    tile.add_row("s1", path)
    assert tile.isVisible()
    tile.remove_row("s1")
    assert "s1" not in tile.rows()
    assert not tile.isVisible()


def test_remove_one_of_many_rows_keeps_tile_visible(tile, make_session):
    p1 = make_session(session_id="s1", project_name="alpha")
    p2 = make_session(session_id="s2", project_name="beta")
    tile.add_row("s1", p1)
    tile.add_row("s2", p2)
    tile.remove_row("s1")
    assert "s2" in tile.rows()
    assert "s1" not in tile.rows()
    assert tile.isVisible()


def test_update_row_reloads_from_disk(tile, make_session):
    path = make_session(session_id="s1", state="active", project_name="alpha")
    row = tile.add_row("s1", path)
    row.refresh()
    assert "active" in row.label_text()

    data = json.loads(path.read_text())
    data["state"] = "none"
    path.write_text(json.dumps(data))
    tile.update_row("s1")
    assert "no cache" in row.label_text()


def test_replace_row_keeps_widget_instance(tile, make_session):
    p1 = make_session(session_id="old", project_name="alpha")
    p2 = make_session(session_id="new", project_name="alpha")
    row_before = tile.add_row("old", p1)
    tile.replace_row("old", "new", p2)
    rows = tile.rows()
    assert "old" not in rows
    assert rows["new"] is row_before
    assert row_before.json_path == p2


def test_row_click_propagates_through_tile(tile, make_session, qtbot):
    path = make_session(session_id="click1", project_name="alpha")
    row = tile.add_row("click1", path)
    row.refresh()
    tile.show()
    qtbot.waitExposed(tile)
    with qtbot.waitSignal(tile.focus_requested, timeout=500) as sig:
        qtbot.mouseClick(row, Qt.MouseButton.LeftButton)
    assert sig.args[0]["session_id"] == "click1"


def test_dismiss_signal_propagates_through_tile(tile, make_session):
    path = make_session(session_id="dis1", project_name="alpha")
    row = tile.add_row("dis1", path)
    received = []
    tile.dismiss_requested.connect(received.append)
    row.dismiss_requested.emit("dis1")
    assert received == ["dis1"]


def test_tile_marks_only_matching_row_as_foreground(make_session, qtbot):
    """When the OS foreground window matches one row's session, only
    that row gets is_foreground()=True. Other rows clear their flag.
    """
    fake_title = ["alpha - Visual Studio Code"]

    def matches(title, cwd, project_name):
        # Trivial matcher: project_name in title.
        return project_name and project_name.lower() in title.lower()

    t = AggregateTile(
        foreground_title_fn=lambda: fake_title[0],
        title_matches_fn=matches,
    )
    qtbot.addWidget(t)
    p1 = make_session(session_id="r1", project_name="alpha")
    p2 = make_session(session_id="r2", project_name="beta")
    t.add_row("r1", p1)
    t.add_row("r2", p2)
    qtbot.waitUntil(
        lambda: t.rows()["r1"].is_foreground() and not t.rows()["r2"].is_foreground(),
        timeout=2000,
    )

    fake_title[0] = "beta - Visual Studio Code"
    qtbot.waitUntil(
        lambda: not t.rows()["r1"].is_foreground() and t.rows()["r2"].is_foreground(),
        timeout=2000,
    )

    fake_title[0] = ""  # nothing focused
    qtbot.waitUntil(
        lambda: not t.rows()["r1"].is_foreground() and not t.rows()["r2"].is_foreground(),
        timeout=2000,
    )


def test_tile_ticks_rows_every_second(tile, make_session, qtbot, monkeypatch):
    """The tile must call refresh() on each row at ~1Hz so the countdown
    label advances even between hook events (when the file mtime is
    stable and the watcher emits no session_updated).
    """
    path = make_session(session_id="tick1", project_name="alpha")
    row = tile.add_row("tick1", path)

    counter = {"n": 0}
    real_refresh = row.refresh

    def counted_refresh():
        counter["n"] += 1
        real_refresh()

    monkeypatch.setattr(row, "refresh", counted_refresh)
    qtbot.waitUntil(lambda: counter["n"] >= 2, timeout=3000)


def test_multiple_rows_stack_vertically(tile, make_session, qtbot):
    p1 = make_session(session_id="s1", project_name="alpha")
    p2 = make_session(session_id="s2", project_name="beta")
    p3 = make_session(session_id="s3", project_name="gamma")
    r1 = tile.add_row("s1", p1)
    r2 = tile.add_row("s2", p2)
    r3 = tile.add_row("s3", p3)
    tile.show()
    qtbot.waitExposed(tile)
    qtbot.waitUntil(lambda: r3.y() > r2.y() > r1.y(), timeout=500)
