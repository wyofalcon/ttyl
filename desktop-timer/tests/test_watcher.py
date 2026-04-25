"""Integration tests for ttyl.watcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from ttyl.watcher import CacheTimersWatcher


@pytest.fixture
def watcher(timers_dir: Path, qtbot):
    # Stub pid liveness so these tests only exercise file-state logic;
    # otherwise the synthetic pid 12345 from make_session may collide
    # with reality and trip the dead-pid eviction path.
    w = CacheTimersWatcher(
        timers_dir,
        poll_interval_ms=50,
        stale_seconds=10,
        pid_alive_fn=lambda _pid: True,
    )
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


def test_emits_session_added_for_files_existing_before_watcher_starts(
    timers_dir, make_session, qtbot
):
    # Regression: the very first scan must not happen synchronously inside
    # __init__, otherwise consumers that connect signals after construction
    # never see existing files. This is the case in production startup.
    make_session(session_id="preexisting", project_name="alpha")
    w = CacheTimersWatcher(
        timers_dir,
        poll_interval_ms=1000,
        stale_seconds=3600,
        pid_alive_fn=lambda _pid: True,
    )
    with qtbot.waitSignal(w.session_added, timeout=1000) as sig:
        pass
    assert sig.args[0].endswith("preexisting.json")


def test_dead_pid_evicts_file(timers_dir, make_session, qtbot):
    # Hard-kill scenario: SessionEnd hook never fires, but the watcher's
    # pid liveness check catches it on the next scan. We inject a stub
    # pid_alive_fn so the test doesn't depend on real OS state.
    make_session(session_id="dead1", pid=424242)
    w = CacheTimersWatcher(
        timers_dir,
        poll_interval_ms=50,
        stale_seconds=3600,
        pid_alive_fn=lambda pid: pid != 424242,
    )
    qtbot.waitUntil(lambda: not (timers_dir / "dead1.json").exists(), timeout=2000)


def test_live_pid_keeps_file(timers_dir, make_session, qtbot):
    # Inverse: when pid_alive_fn says the process is alive, the file is
    # kept (here we'd otherwise expect the time-based GC to fire too).
    path = make_session(session_id="live1", pid=1234)
    w = CacheTimersWatcher(
        timers_dir,
        poll_interval_ms=50,
        stale_seconds=3600,
        pid_alive_fn=lambda pid: True,
    )
    qtbot.wait(200)
    assert path.exists()


def test_session_replaced_when_same_cwd_new_id(watcher, make_session, qtbot):
    make_session(session_id="old", cwd="/c/p/demo", project_name="demo")
    qtbot.wait(150)
    with qtbot.waitSignal(watcher.session_replaced, timeout=1000) as sig:
        make_session(session_id="new", cwd="/c/p/demo", project_name="demo")
        Path(str(watcher._dir / "old.json")).unlink()
    assert list(sig.args) == ["old", "new"]
