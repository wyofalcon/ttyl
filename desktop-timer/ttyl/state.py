"""Pure-function state computation for TTYL pill windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


MAX_PROJECT_CHARS = 18


def _truncate(name: str) -> str:
    if len(name) <= MAX_PROJECT_CHARS:
        return name
    return name[: MAX_PROJECT_CHARS - 1] + "…"


def _format_mmss(seconds: int) -> str:
    seconds = max(0, seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass(frozen=True)
class TimerState:
    """Snapshot of a session's display state at a single moment."""

    raw_state: str
    color: str
    label: str
    remaining: Optional[int]
    project_name: str

    @staticmethod
    def is_finish_transition(prev: "TimerState", curr: "TimerState") -> bool:
        """True when Claude just finished a turn (active -> idle)."""
        return prev.raw_state == "active" and curr.raw_state == "idle"


def compute(row: dict, *, now: int, ttl: int = 300) -> TimerState:
    """Turn a cache-timers JSON row into a display-ready TimerState."""
    state = row.get("state", "none")
    project = _truncate(row.get("project_name") or "?")

    if state == "none":
        return TimerState("none", "gray", f"no cache · {project}", None, project)
    if state == "active":
        return TimerState("active", "blue", f"active · {project}", None, project)

    epoch = int(row.get("epoch", now))
    remaining = max(0, ttl - (now - epoch))
    if remaining == 0:
        return TimerState("idle", "red", f"cache cold · {project}", 0, project)
    if remaining < 60:
        color = "red"
    elif remaining <= 120:
        color = "yellow"
    else:
        color = "green"
    return TimerState(
        "idle", color, f"{_format_mmss(remaining)} · {project}", remaining, project
    )
