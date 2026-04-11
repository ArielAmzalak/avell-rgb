"""Config file I/O. Single source of truth location, defaults, and JSON parsing."""

from __future__ import annotations

import json
import os
from pathlib import Path

from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "avell-rgb"
    return Path.home() / ".config" / "avell-rgb"


CONFIG_PATH: Path = _config_dir() / "config.json"


DEFAULT_CONFIG: Config = Config(
    version=1,
    mode="schedule",
    manual_paused=False,
    manual_state=None,
    presets={
        "trabalho": DeviceState(
            keyboard=KeyboardSolid(color="#00FFFF", brightness=30),
            lightbar=LightbarState(color="#00FFFF", brightness=80),
        ),
        "noite": DeviceState(
            keyboard=KeyboardSolid(color="#FF3300", brightness=10),
            lightbar=LightbarState(color="#FF3300", brightness=20),
        ),
        "off": DeviceState(
            keyboard=KeyboardOff(),
            lightbar=LightbarState(color="#000000", brightness=0),
        ),
    },
    schedule=[
        ScheduleBand(start="07:00", end="19:00", preset="trabalho"),
        ScheduleBand(start="19:00", end="07:00", preset="noite"),
    ],
    solar=SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",
        night_color="#FF6600",
        day_brightness=50,
        night_brightness=20,
        apply_to=("keyboard", "lightbar"),
    ),
)


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Load config from `path`. If the file doesn't exist, writes the default
    and returns it. Raises JSONDecodeError if the file is malformed."""
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return DEFAULT_CONFIG
    text = path.read_text()
    data = json.loads(text)
    return Config.from_dict(data)


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    """Write `config` to `path` as pretty-printed JSON. Creates parent dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config.to_dict(), indent=2, sort_keys=False)
    # atomic-ish: write to temp, then replace
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text + "\n")
    tmp.replace(path)
