import json
from pathlib import Path

import pytest

from avell_rgb.config import (
    CONFIG_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
)
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)


def test_default_config_is_valid_config():
    cfg = DEFAULT_CONFIG
    assert cfg.version == 1
    assert cfg.mode == "schedule"
    assert "trabalho" in cfg.presets
    assert len(cfg.schedule) >= 1


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    save_config(DEFAULT_CONFIG, path)
    loaded = load_config(path)
    assert loaded == DEFAULT_CONFIG


def test_load_missing_file_returns_default(tmp_path):
    path = tmp_path / "nonexistent.json"
    loaded = load_config(path)
    assert loaded == DEFAULT_CONFIG
    assert path.exists(), "missing config file should be created with defaults"


def test_load_malformed_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        load_config(path)


def test_save_is_human_readable(tmp_path):
    path = tmp_path / "config.json"
    save_config(DEFAULT_CONFIG, path)
    text = path.read_text()
    assert "\n" in text, "json should be pretty-printed"
    assert '"version": 1' in text


def test_config_path_under_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Re-import to recompute CONFIG_PATH
    import importlib

    import avell_rgb.config as config_mod

    importlib.reload(config_mod)
    assert config_mod.CONFIG_PATH == tmp_path / "avell-rgb" / "config.json"
