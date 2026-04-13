"""Config file I/O with v1->v2 migration. Single source of truth."""

from __future__ import annotations

import json
import os
from pathlib import Path

from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "avell-rgb"
    return Path.home() / ".config" / "avell-rgb"


CONFIG_PATH: Path = _config_dir() / "config.json"

DEFAULT_CONFIG: Config = Config(
    version=2,
    mode="fixed",
    color="#00FFFF",
    brightness=30,
    independent_colors=False,
    keyboard_color="#00FFFF",
    keyboard_brightness=30,
    lightbar_color="#00FFFF",
    lightbar_brightness=80,
    effect=EffectConfig(name="breathing", color="#00FFFF", speed=5),
    solar=SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#8FF0A4",
        night_color="#FF7800",
        day_brightness=50,
        night_brightness=20,
    ),
    presets={
        "trabalho": Preset(color="#00FFFF", brightness=30),
        "noite": Preset(color="#FF3300", brightness=10),
    },
)


def migrate_v1_to_v2(d: dict) -> dict:
    first_preset = next(iter(d.get("presets", {}).values()), None)
    color = "#FFFFFF"
    brightness = 30
    if first_preset:
        kb = first_preset.get("keyboard", {})
        color = kb.get("color", color)
        brightness = kb.get("brightness", brightness)

    presets = {}
    for name, state in d.get("presets", {}).items():
        kb = state.get("keyboard", {})
        presets[name] = {
            "color": kb.get("color", "#FFFFFF"),
            "brightness": kb.get("brightness", 30),
        }

    solar_v1 = d.get("solar", {})
    solar = {
        "latitude": solar_v1.get("latitude", -23.55),
        "longitude": solar_v1.get("longitude", -46.63),
        "day_color": solar_v1.get("day_color", "#8FF0A4"),
        "night_color": solar_v1.get("night_color", "#FF7800"),
        "day_brightness": solar_v1.get("day_brightness", 50),
        "night_brightness": solar_v1.get("night_brightness", 20),
    }

    mode = d.get("mode", "fixed")
    if mode == "schedule":
        mode = "fixed"

    return {
        "version": 2,
        "mode": mode,
        "color": color,
        "brightness": brightness,
        "independent_colors": False,
        "keyboard_color": color,
        "keyboard_brightness": brightness,
        "lightbar_color": color,
        "lightbar_brightness": min(100, brightness * 2),
        "effect": {"name": "breathing", "color": color, "speed": 5},
        "solar": solar,
        "presets": presets,
    }


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return DEFAULT_CONFIG
    text = path.read_text()
    data = json.loads(text)
    if data.get("version", 1) < 2:
        data = migrate_v1_to_v2(data)
        cfg = Config.from_dict(data)
        save_config(cfg, path)
        return cfg
    return Config.from_dict(data)


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config.to_dict(), indent=2, sort_keys=False)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(text + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
