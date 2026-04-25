"""Tests for ttyl.state - pure state computation."""

from ttyl.state import TimerState, compute


def _base(state: str = "idle", epoch: int = 1000, project: str = "demo") -> dict:
    return {
        "session_id": "s",
        "state": state,
        "epoch": epoch,
        "cwd": f"/c/u/w/projects/{project}",
        "project_name": project,
        "pid": 1,
        "started_at": epoch,
        "last_update": epoch,
        "hook_event": "Stop",
    }


def test_none_produces_no_cache_gray():
    out = compute(_base(state="none"), now=1000, ttl=300)
    assert out.label.startswith("no cache")
    assert out.color == "gray"
    assert out.remaining is None


def test_active_produces_active_blue():
    out = compute(_base(state="active"), now=1000, ttl=300)
    assert out.label.startswith("active")
    assert out.color == "blue"
    assert out.remaining is None


def test_idle_over_2min_green():
    out = compute(_base(state="idle", epoch=1000), now=1050, ttl=300)
    assert out.color == "green"
    assert out.remaining == 250
    assert "4:10" in out.label


def test_idle_under_2min_yellow():
    out = compute(_base(state="idle", epoch=1000), now=1180, ttl=300)
    assert out.color == "yellow"
    assert out.remaining == 120


def test_idle_under_1min_red():
    out = compute(_base(state="idle", epoch=1000), now=1260, ttl=300)
    assert out.color == "red"
    assert out.remaining == 40


def test_idle_expired_is_cache_cold():
    out = compute(_base(state="idle", epoch=1000), now=2000, ttl=300)
    assert out.color == "red"
    assert out.remaining == 0
    assert "cache cold" in out.label


def test_label_truncates_long_project_name():
    row = _base(state="idle", epoch=1000, project="this-is-a-very-long-project-name")
    out = compute(row, now=1050, ttl=300)
    assert "this-is-a-very-lo" in out.label
    assert "…" in out.label or "..." in out.label


def test_is_transition_active_to_idle():
    prev = compute(_base(state="active"), now=1000, ttl=300)
    curr = compute(_base(state="idle", epoch=1000), now=1000, ttl=300)
    assert TimerState.is_finish_transition(prev, curr)


def test_is_transition_idle_to_idle_is_not_finish():
    prev = compute(_base(state="idle", epoch=1000), now=1050, ttl=300)
    curr = compute(_base(state="idle", epoch=1000), now=1060, ttl=300)
    assert not TimerState.is_finish_transition(prev, curr)
