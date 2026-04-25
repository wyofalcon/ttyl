"""Shared pytest fixtures for TTYL tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def timers_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cache-timers"
    d.mkdir()
    return d


@pytest.fixture
def make_session(timers_dir: Path):
    """Factory: write a session JSON file and return its path."""

    def _make(
        session_id: str = "abc",
        state: str = "idle",
        epoch: int = 1_745_510_000,
        cwd: str = "/c/Users/w/projects/demo",
        project_name: str = "demo",
        pid: int = 12345,
        started_at: int = 1_745_509_000,
        last_update: int | None = None,
        hook_event: str = "Stop",
    ) -> Path:
        path = timers_dir / f"{session_id}.json"
        path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "state": state,
                    "epoch": epoch,
                    "cwd": cwd,
                    "project_name": project_name,
                    "pid": pid,
                    "started_at": started_at,
                    "last_update": last_update if last_update is not None else epoch,
                    "hook_event": hook_event,
                }
            )
        )
        return path

    return _make
