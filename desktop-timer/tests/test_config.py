"""Tests for ttyl.config."""

from __future__ import annotations

from pathlib import Path

from ttyl.config import Config


def test_defaults(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    assert cfg.tile_position is None
    assert cfg.flash_on_finish is True


def test_roundtrip_tile_position(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    cfg.tile_position = (100, 200)
    cfg2 = Config(tmp_path / "cfg.json")
    assert cfg2.tile_position == (100, 200)


def test_clear_tile_position(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    cfg.tile_position = (10, 20)
    cfg.tile_position = None
    cfg2 = Config(tmp_path / "cfg.json")
    assert cfg2.tile_position is None


def test_toggle_flash_on_finish(tmp_path: Path):
    cfg = Config(tmp_path / "cfg.json")
    cfg.flash_on_finish = False
    cfg2 = Config(tmp_path / "cfg.json")
    assert cfg2.flash_on_finish is False


def test_old_config_with_position_mode_does_not_crash(tmp_path: Path):
    """A leftover position_mode key from older versions is silently ignored."""
    p = tmp_path / "cfg.json"
    p.write_text('{"position_mode": "remember", "positions": {"x": [1, 2]}}')
    cfg = Config(p)
    assert cfg.tile_position is None
