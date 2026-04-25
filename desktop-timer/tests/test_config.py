"""Tests for ttyl.config."""

from __future__ import annotations

from pathlib import Path

from ttyl.config import Config


def test_defaults(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    assert cfg.position_mode == "remember"
    assert cfg.get_position("/c/u/p/demo") is None


def test_roundtrip_position(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    cfg.set_position("/c/u/p/demo", 100, 200)
    cfg2 = Config(tmp_path / "cfg.json")
    assert cfg2.get_position("/c/u/p/demo") == (100, 200)


def test_toggle_position_mode(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    cfg.position_mode = "cascade"
    cfg2 = Config(tmp_path / "cfg.json")
    assert cfg2.position_mode == "cascade"
