import json
from pathlib import Path

import pytest

from avell_rgb.config import (
    DEFAULT_CONFIG,
    load_config,
    migrate_v1_to_v2,
    save_config,
)
from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig


def test_default_config_is_v2():
    cfg = DEFAULT_CONFIG
    assert cfg.version == 2
    assert cfg.mode == "fixed"
    assert "trabalho" in cfg.presets
    assert isinstance(cfg.presets["trabalho"], Preset)


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    save_config(DEFAULT_CONFIG, path)
    loaded = load_config(path)
    assert loaded == DEFAULT_CONFIG


def test_load_missing_file_returns_default(tmp_path):
    path = tmp_path / "nonexistent.json"
    loaded = load_config(path)
    assert loaded == DEFAULT_CONFIG
    assert path.exists()


def test_load_malformed_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        load_config(path)


def test_save_is_human_readable(tmp_path):
    path = tmp_path / "config.json"
    save_config(DEFAULT_CONFIG, path)
    text = path.read_text()
    assert "\n" in text
    assert '"version": 2' in text


def test_migrate_v1_schedule_becomes_fixed():
    v1 = {
        "version": 1,
        "mode": "schedule",
        "manual_paused": False,
        "manual_state": None,
        "presets": {
            "work": {
                "keyboard": {"type": "solid", "color": "#00FFFF", "brightness": 30},
                "lightbar": {"color": "#00FFFF", "brightness": 80},
            }
        },
        "schedule": [{"start": "07:00", "end": "18:00", "preset": "work"}],
        "solar": {
            "latitude": -23.55, "longitude": -46.63,
            "day_color": "#8FF0A4", "night_color": "#FF7800",
            "day_brightness": 50, "night_brightness": 20,
            "apply_to": ["keyboard", "lightbar"],
        },
    }
    v2 = migrate_v1_to_v2(v1)
    assert v2["version"] == 2
    assert v2["mode"] == "fixed"
    assert v2["color"] == "#00FFFF"
    assert v2["brightness"] == 30
    assert "schedule" not in v2
    assert "manual_state" not in v2
    assert "manual_paused" not in v2
    assert v2["presets"]["work"] == {"color": "#00FFFF", "brightness": 30}


def test_migrate_v1_solar_mode_preserved():
    v1 = {
        "version": 1,
        "mode": "solar",
        "manual_paused": False,
        "manual_state": None,
        "presets": {},
        "schedule": [],
        "solar": {
            "latitude": 0, "longitude": 0,
            "day_color": "#FFF", "night_color": "#000",
            "day_brightness": 50, "night_brightness": 10,
            "apply_to": ["keyboard"],
        },
    }
    v2 = migrate_v1_to_v2(v1)
    assert v2["mode"] == "solar"


def test_migrate_v1_strips_apply_to_from_solar():
    v1 = {
        "version": 1, "mode": "solar",
        "manual_paused": False, "manual_state": None,
        "presets": {}, "schedule": [],
        "solar": {
            "latitude": 0, "longitude": 0,
            "day_color": "#FFF", "night_color": "#000",
            "day_brightness": 50, "night_brightness": 10,
            "apply_to": ["keyboard", "lightbar"],
        },
    }
    v2 = migrate_v1_to_v2(v1)
    assert "apply_to" not in v2["solar"]


def test_load_auto_migrates_v1(tmp_path):
    v1 = {
        "version": 1,
        "mode": "schedule",
        "manual_paused": False,
        "manual_state": None,
        "presets": {
            "work": {
                "keyboard": {"type": "solid", "color": "#00FFFF", "brightness": 30},
                "lightbar": {"color": "#00FFFF", "brightness": 80},
            }
        },
        "schedule": [{"start": "07:00", "end": "18:00", "preset": "work"}],
        "solar": {
            "latitude": -23.55, "longitude": -46.63,
            "day_color": "#8FF0A4", "night_color": "#FF7800",
            "day_brightness": 50, "night_brightness": 20,
            "apply_to": ["keyboard", "lightbar"],
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(v1))
    cfg = load_config(path)
    assert cfg.version == 2
    assert cfg.mode == "fixed"
    reloaded = json.loads(path.read_text())
    assert reloaded["version"] == 2
