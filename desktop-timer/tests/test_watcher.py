"""Integration tests for ttyl.watcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from ttyl.watcher import CacheTimersWatcher


@pytest.fixture
def watcher(timers_dir: Path, qtbot):
    w = CacheTimersWatcher(timers_dir, poll_interval_ms=50, stale_seconds=10)
    return w


def test_emits_session_added_on_new_file(watcher, make_session, qtbot):
    with qtbot.waitSignal(watcher.session_added, timeout=1000) as sig:
        make_session(session_id="new1")
    assert sig.args[0].endswith("new1.json")


def test_emits_session_updated_on_modification(watcher, make_session, qtbot, timers_dir):
    path = make_session(session_id="upd1", state="none")
    qtbot.wait(150)
    with qtbot.waitSignal(watcher.session_updated, timeout=1000):
        path.write_text(path.read_text().replace('"none"', '"active"'))


def test_emits_session_removed_on_delete(watcher, make_session, qtbot):
    path = make_session(session_id="del1")
    qtbot.wait(150)
    with qtbot.waitSignal(watcher.session_removed, timeout=1000) as sig:
        path.unlink()
    assert sig.args[0] == "del1"


def test_gc_deletes_stale_files(watcher, make_session, qtbot, timers_dir):
    # File stale from birth — watcher GCs it on next scan; no session_removed
    # signal because the sid was never tracked.
    make_session(session_id="stale1", last_update=0)
    qtbot.waitUntil(lambda: not (timers_dir / "stale1.json").exists(), timeout=2000)


def test_gc_emits_session_removed_for_previously_known_file(
    watcher, make_session, qtbot, timers_dir
):
    # File starts fresh (known), then goes stale; watcher GCs it AND emits
    # session_removed because it was in _known.
    path = make_session(session_id="stale2")
    qtbot.wait(150)  # let the watcher learn about it
    with qtbot.waitSignal(watcher.session_removed, timeout=2000) as sig:
        import json as _json

        row = _json.loads(path.read_text())
        row["last_update"] = 0
        path.write_text(_json.dumps(row))
    assert sig.args[0] == "stale2"


def test_session_replaced_when_same_cwd_new_id(watcher, make_session, qtbot):
    make_session(session_id="old", cwd="/c/p/demo", project_name="demo")
    qtbot.wait(150)
    with qtbot.waitSignal(watcher.session_replaced, timeout=1000) as sig:
        make_session(session_id="new", cwd="/c/p/demo", project_name="demo")
        Path(str(watcher._dir / "old.json")).unlink()
    assert list(sig.args) == ["old", "new"]
