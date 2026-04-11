# Avell RGB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GTK4/libadwaita Linux utility that unifies RGB control of the Avell STORM 570 TI keyboard (ITE 8291) and light bar (ITE 8233), with named presets, time-of-day schedules, and solar gradient mode.

**Architecture:** Two processes share a JSON config file. A tiny `asyncio` daemon (systemd user service) reads the config, computes the desired state (by schedule or solar interpolation), and applies it via subprocess (`ite8291r3-ctl`) and sysfs writes (`/sys/class/leds/rgb:lightbar/`). The GTK4 GUI edits the config and signals the daemon to reload via `SIGHUP`. Backends are isolated behind thin interfaces so the pure logic can be tested with fakes.

**Tech Stack:** Python 3.11+ · `dataclasses` · `astral` (solar calcs) · `PyGObject` (GTK4 + libadwaita) · `pytest` · `systemd --user`. No web, no DB, no network.

**Pre-existing system dependencies (already configured on target machine):**
- `ite8291r3-ctl` in PATH (via pipx, patched to include product ID `0x600b`)
- Kernel module `ite_8291_lb` loaded at boot
- `/sys/class/leds/rgb:lightbar/{brightness,multi_intensity}` writable by group `users`
- `python3-gi` and `gir1.2-adw-1` will be installed as part of Task 1

---

## File Map

```
avell-rgb/
├── pyproject.toml                          # Task 1
├── LICENSE                                 # Task 1
├── avell_rgb/
│   ├── __init__.py                         # Task 1
│   ├── state.py                            # Task 2 — dataclasses
│   ├── config.py                           # Task 3 — load/save/defaults
│   ├── scheduler.py                        # Task 4 — time bands
│   ├── solar.py                            # Task 5 — astral interpolation
│   ├── backends/
│   │   ├── __init__.py                     # Task 6
│   │   ├── keyboard.py                     # Task 6 — ite8291r3-ctl wrapper
│   │   └── lightbar.py                     # Task 7 — sysfs writer
│   ├── daemon/
│   │   ├── __init__.py                     # Task 8
│   │   └── main.py                         # Task 8 — loop + signals + entry
│   └── gui/
│       ├── __init__.py                     # Task 10
│       ├── main.py                         # Task 10 — entry
│       ├── app.py                          # Task 10 — AdwApplication
│       ├── window.py                       # Task 10 — AdwApplicationWindow
│       ├── color_helpers.py                # Task 11 — hex/rgb utilities
│       ├── page_now.py                     # Task 11
│       ├── page_presets.py                 # Task 12
│       ├── page_schedule.py                # Task 13
│       └── page_preferences.py             # Task 14
├── tests/
│   ├── __init__.py                         # Task 1
│   ├── conftest.py                         # Task 6 — fake backends
│   ├── test_state.py                       # Task 2
│   ├── test_config.py                      # Task 3
│   ├── test_scheduler.py                   # Task 4
│   ├── test_solar.py                       # Task 5
│   ├── test_keyboard_backend.py            # Task 6
│   ├── test_lightbar_backend.py            # Task 7
│   └── test_daemon_loop.py                 # Task 9
├── data/
│   ├── avell-rgb-daemon.service            # Task 15
│   ├── io.github.avellrgb.Avell.desktop    # Task 15
│   └── io.github.avellrgb.Avell.svg        # Task 15
└── scripts/
    └── install-user.sh                     # Task 15
```

---

## Task 1: Project scaffolding + pyproject + empty package

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `avell_rgb/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Install system packages for GTK bindings and astral**

Run:
```bash
sudo apt install -y python3-gi gir1.2-adw-1 python3-astral python3-pytest
```

Expected: packages install; no-op if already installed.

- [ ] **Step 2: Write `pyproject.toml`**

Create `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "avell-rgb"
version = "0.1.0"
description = "Unified RGB control for Avell STORM 570 TI (keyboard + light bar)"
requires-python = ">=3.11"
dependencies = [
    "astral>=3.2",
]

[project.scripts]
avell-rgb-daemon = "avell_rgb.daemon.main:main"
avell-rgb-gui = "avell_rgb.gui.main:main"

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[tool.setuptools.packages.find]
include = ["avell_rgb*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Write `LICENSE` (MIT)**

Create `LICENSE`:
```
MIT License

Copyright (c) 2026 ALC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create empty package init files**

Create `avell_rgb/__init__.py`:
```python
__version__ = "0.1.0"
```

Create `tests/__init__.py` (empty):
```python
```

- [ ] **Step 5: Verify package layout builds**

Run:
```bash
cd ~/src/avell-rgb && python -m py_compile avell_rgb/__init__.py
```

Expected: exit 0, no output.

- [ ] **Step 6: Commit**

```bash
cd ~/src/avell-rgb
git add pyproject.toml LICENSE avell_rgb/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding + pyproject"
```

---

## Task 2: State dataclasses + serialization

**Files:**
- Create: `avell_rgb/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing test for `KeyboardSolid` round-trip**

Create `tests/test_state.py`:
```python
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardEffect,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)


def test_keyboard_solid_round_trip():
    k = KeyboardSolid(color="#00FFFF", brightness=30)
    d = k.to_dict()
    assert d == {"type": "solid", "color": "#00FFFF", "brightness": 30}
    assert KeyboardSolid.from_dict(d) == k


def test_keyboard_effect_round_trip():
    k = KeyboardEffect(
        effect="wave", color="rainbow", speed=5, direction="right", brightness=50
    )
    d = k.to_dict()
    assert d["type"] == "effect"
    from_back = KeyboardEffect.from_dict(d)
    assert from_back == k


def test_keyboard_off_round_trip():
    k = KeyboardOff()
    assert k.to_dict() == {"type": "off"}
    assert KeyboardOff.from_dict({"type": "off"}) == k


def test_device_state_with_solid_kb():
    state = DeviceState(
        keyboard=KeyboardSolid(color="#FF0000", brightness=20),
        lightbar=LightbarState(color="#00FF00", brightness=50),
    )
    d = state.to_dict()
    assert d["keyboard"]["type"] == "solid"
    assert d["lightbar"]["color"] == "#00FF00"
    back = DeviceState.from_dict(d)
    assert back == state


def test_device_state_with_effect_kb():
    state = DeviceState(
        keyboard=KeyboardEffect(
            effect="breathing", color="purple", speed=3, direction=None, brightness=40
        ),
        lightbar=LightbarState(color="#FFFFFF", brightness=100),
    )
    back = DeviceState.from_dict(state.to_dict())
    assert back == state


def test_schedule_band_round_trip():
    b = ScheduleBand(start="07:00", end="18:00", preset="trabalho")
    assert b.to_dict() == {"start": "07:00", "end": "18:00", "preset": "trabalho"}
    assert ScheduleBand.from_dict(b.to_dict()) == b


def test_solar_config_round_trip():
    s = SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",
        night_color="#FF6600",
        day_brightness=50,
        night_brightness=20,
        apply_to=("keyboard", "lightbar"),
    )
    back = SolarConfig.from_dict(s.to_dict())
    assert back == s


def test_config_round_trip():
    cfg = Config(
        version=1,
        mode="schedule",
        manual_paused=False,
        manual_state=None,
        presets={
            "trabalho": DeviceState(
                keyboard=KeyboardSolid(color="#00FFFF", brightness=30),
                lightbar=LightbarState(color="#00FFFF", brightness=80),
            ),
            "off": DeviceState(
                keyboard=KeyboardOff(),
                lightbar=LightbarState(color="#000000", brightness=0),
            ),
        },
        schedule=[ScheduleBand(start="07:00", end="18:00", preset="trabalho")],
        solar=SolarConfig(
            latitude=0.0,
            longitude=0.0,
            day_color="#FFFFFF",
            night_color="#000000",
            day_brightness=50,
            night_brightness=10,
            apply_to=("keyboard", "lightbar"),
        ),
    )
    back = Config.from_dict(cfg.to_dict())
    assert back == cfg


def test_config_mode_must_be_valid():
    import pytest
    with pytest.raises(ValueError):
        Config.from_dict(
            {
                "version": 1,
                "mode": "bogus",
                "manual_paused": False,
                "manual_state": None,
                "presets": {},
                "schedule": [],
                "solar": SolarConfig(
                    latitude=0.0,
                    longitude=0.0,
                    day_color="#000000",
                    night_color="#000000",
                    day_brightness=0,
                    night_brightness=0,
                    apply_to=(),
                ).to_dict(),
            }
        )
```

- [ ] **Step 2: Run test, confirm ImportError (module missing)**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_state.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'avell_rgb.state'`.

- [ ] **Step 3: Implement `state.py`**

Create `avell_rgb/state.py`:
```python
"""Immutable dataclasses for the entire config model, with JSON round-trip."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

VALID_MODES = ("schedule", "solar")
VALID_EFFECTS = (
    "breathing",
    "wave",
    "random",
    "rainbow",
    "ripple",
    "marquee",
    "raindrop",
    "aurora",
    "fireworks",
)


@dataclass(frozen=True)
class KeyboardSolid:
    color: str  # "#RRGGBB"
    brightness: int  # 0-50 (ite8291r3-ctl accepts 0-50)

    def to_dict(self) -> dict:
        return {"type": "solid", "color": self.color, "brightness": self.brightness}

    @classmethod
    def from_dict(cls, d: dict) -> "KeyboardSolid":
        return cls(color=d["color"], brightness=int(d["brightness"]))


@dataclass(frozen=True)
class KeyboardEffect:
    effect: str  # one of VALID_EFFECTS
    color: str  # palette name ("rainbow", "random", "red"...) or "#RRGGBB"
    speed: int  # 0-10
    direction: Optional[str]  # "left" | "right" | "up" | "down" | None
    brightness: int  # 0-50

    def to_dict(self) -> dict:
        return {
            "type": "effect",
            "effect": self.effect,
            "color": self.color,
            "speed": self.speed,
            "direction": self.direction,
            "brightness": self.brightness,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KeyboardEffect":
        return cls(
            effect=d["effect"],
            color=d["color"],
            speed=int(d["speed"]),
            direction=d.get("direction"),
            brightness=int(d["brightness"]),
        )


@dataclass(frozen=True)
class KeyboardOff:
    def to_dict(self) -> dict:
        return {"type": "off"}

    @classmethod
    def from_dict(cls, d: dict) -> "KeyboardOff":
        return cls()


KeyboardState = Union[KeyboardSolid, KeyboardEffect, KeyboardOff]


def keyboard_from_dict(d: dict) -> KeyboardState:
    t = d.get("type")
    if t == "solid":
        return KeyboardSolid.from_dict(d)
    if t == "effect":
        return KeyboardEffect.from_dict(d)
    if t == "off":
        return KeyboardOff.from_dict(d)
    raise ValueError(f"unknown keyboard state type: {t!r}")


@dataclass(frozen=True)
class LightbarState:
    color: str  # "#RRGGBB"
    brightness: int  # 0-100

    def to_dict(self) -> dict:
        return {"color": self.color, "brightness": self.brightness}

    @classmethod
    def from_dict(cls, d: dict) -> "LightbarState":
        return cls(color=d["color"], brightness=int(d["brightness"]))


@dataclass(frozen=True)
class DeviceState:
    keyboard: KeyboardState
    lightbar: LightbarState

    def to_dict(self) -> dict:
        return {
            "keyboard": self.keyboard.to_dict(),
            "lightbar": self.lightbar.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DeviceState":
        return cls(
            keyboard=keyboard_from_dict(d["keyboard"]),
            lightbar=LightbarState.from_dict(d["lightbar"]),
        )


@dataclass(frozen=True)
class ScheduleBand:
    start: str  # "HH:MM"
    end: str  # "HH:MM"
    preset: str  # preset key

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "preset": self.preset}

    @classmethod
    def from_dict(cls, d: dict) -> "ScheduleBand":
        return cls(start=d["start"], end=d["end"], preset=d["preset"])


@dataclass(frozen=True)
class SolarConfig:
    latitude: float
    longitude: float
    day_color: str
    night_color: str
    day_brightness: int
    night_brightness: int
    apply_to: tuple[str, ...]  # subset of ("keyboard", "lightbar")

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "day_color": self.day_color,
            "night_color": self.night_color,
            "day_brightness": self.day_brightness,
            "night_brightness": self.night_brightness,
            "apply_to": list(self.apply_to),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SolarConfig":
        return cls(
            latitude=float(d["latitude"]),
            longitude=float(d["longitude"]),
            day_color=d["day_color"],
            night_color=d["night_color"],
            day_brightness=int(d["day_brightness"]),
            night_brightness=int(d["night_brightness"]),
            apply_to=tuple(d["apply_to"]),
        )


@dataclass(frozen=True)
class Config:
    version: int
    mode: Literal["schedule", "solar"]
    manual_paused: bool
    manual_state: Optional[DeviceState]
    presets: dict[str, DeviceState]
    schedule: list[ScheduleBand]
    solar: SolarConfig

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "mode": self.mode,
            "manual_paused": self.manual_paused,
            "manual_state": self.manual_state.to_dict() if self.manual_state else None,
            "presets": {k: v.to_dict() for k, v in self.presets.items()},
            "schedule": [b.to_dict() for b in self.schedule],
            "solar": self.solar.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        mode = d["mode"]
        if mode not in VALID_MODES:
            raise ValueError(f"invalid mode: {mode!r}")
        return cls(
            version=int(d["version"]),
            mode=mode,
            manual_paused=bool(d["manual_paused"]),
            manual_state=(
                DeviceState.from_dict(d["manual_state"])
                if d.get("manual_state") is not None
                else None
            ),
            presets={k: DeviceState.from_dict(v) for k, v in d["presets"].items()},
            schedule=[ScheduleBand.from_dict(b) for b in d["schedule"]],
            solar=SolarConfig.from_dict(d["solar"]),
        )
```

- [ ] **Step 4: Run tests, all pass**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_state.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/state.py tests/test_state.py
git commit -m "feat(state): add dataclasses with JSON round-trip"
```

---

## Task 3: Config load/save/defaults

**Files:**
- Create: `avell_rgb/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run, confirm failure**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'avell_rgb.config'`.

- [ ] **Step 3: Implement `config.py`**

Create `avell_rgb/config.py`:
```python
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
```

- [ ] **Step 4: Run tests, all pass**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_config.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/config.py tests/test_config.py
git commit -m "feat(config): load/save/defaults with XDG path"
```

---

## Task 4: Scheduler (time bands)

**Files:**
- Create: `avell_rgb/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:
```python
from datetime import datetime, time

import pytest

from avell_rgb.scheduler import (
    resolve_schedule,
    seconds_until_next_schedule_boundary,
)
from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
)


def _p(name: str, color: str = "#FFFFFF") -> DeviceState:
    return DeviceState(
        keyboard=KeyboardSolid(color=color, brightness=20),
        lightbar=LightbarState(color=color, brightness=50),
    )


def test_resolve_inside_single_band():
    presets = {"work": _p("work", "#00FFFF")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 12, 0)
    assert resolve_schedule(schedule, presets, now) == presets["work"]


def test_resolve_at_start_boundary_is_inside():
    presets = {"work": _p("work")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 7, 0)
    assert resolve_schedule(schedule, presets, now) == presets["work"]


def test_resolve_at_end_boundary_is_outside():
    presets = {"work": _p("work"), "off": _p("off", "#000000")}
    schedule = [
        ScheduleBand(start="07:00", end="18:00", preset="work"),
        ScheduleBand(start="18:00", end="07:00", preset="off"),
    ]
    now = datetime(2026, 4, 10, 18, 0)
    assert resolve_schedule(schedule, presets, now) == presets["off"]


def test_resolve_outside_all_bands_returns_none():
    presets = {"work": _p("work")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 20, 0)
    assert resolve_schedule(schedule, presets, now) is None


def test_resolve_midnight_crossing_band_morning():
    presets = {"night": _p("night")}
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 3, 0)
    assert resolve_schedule(schedule, presets, now) == presets["night"]


def test_resolve_midnight_crossing_band_evening():
    presets = {"night": _p("night")}
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 23, 30)
    assert resolve_schedule(schedule, presets, now) == presets["night"]


def test_resolve_first_band_wins_on_overlap():
    presets = {"a": _p("a", "#FF0000"), "b": _p("b", "#00FF00")}
    schedule = [
        ScheduleBand(start="07:00", end="18:00", preset="a"),
        ScheduleBand(start="10:00", end="12:00", preset="b"),
    ]
    now = datetime(2026, 4, 10, 11, 0)
    assert resolve_schedule(schedule, presets, now) == presets["a"]


def test_resolve_unknown_preset_in_band_raises():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="missing")]
    now = datetime(2026, 4, 10, 12, 0)
    with pytest.raises(KeyError):
        resolve_schedule(schedule, {}, now)


def test_next_boundary_from_inside_band():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 12, 0)
    # 18:00 - 12:00 = 6h
    assert seconds_until_next_schedule_boundary(schedule, now) == 6 * 3600


def test_next_boundary_from_outside_all_bands():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 20, 0)
    # next boundary = tomorrow 07:00 = 11h later
    assert seconds_until_next_schedule_boundary(schedule, now) == 11 * 3600


def test_next_boundary_midnight_crossing_band():
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 2, 0)
    # end = today 07:00, 5h away
    assert seconds_until_next_schedule_boundary(schedule, now) == 5 * 3600


def test_next_boundary_empty_schedule_returns_infinity():
    from math import isinf

    assert isinf(seconds_until_next_schedule_boundary([], datetime(2026, 4, 10, 12, 0)))
```

- [ ] **Step 2: Run, confirm failure**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_scheduler.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `scheduler.py`**

Create `avell_rgb/scheduler.py`:
```python
"""Time-band scheduler. Pure functions — no I/O, no clock calls."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta
from typing import Optional

from avell_rgb.state import DeviceState, ScheduleBand


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _time_to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def _band_contains(band: ScheduleBand, now_t: time) -> bool:
    start = _parse_hhmm(band.start)
    end = _parse_hhmm(band.end)
    if start == end:
        return False  # zero-length band matches nothing
    if start < end:
        return start <= now_t < end
    # crosses midnight: inside if now >= start OR now < end
    return now_t >= start or now_t < end


def resolve_schedule(
    schedule: list[ScheduleBand],
    presets: dict[str, DeviceState],
    now: datetime,
) -> Optional[DeviceState]:
    """Return the DeviceState for the first band containing `now`, or None
    if no band matches. Raises KeyError if a band references an unknown preset."""
    t = now.time()
    for band in schedule:
        if _band_contains(band, t):
            return presets[band.preset]
    return None


def seconds_until_next_schedule_boundary(
    schedule: list[ScheduleBand],
    now: datetime,
) -> float:
    """Seconds until the next boundary (start or end) across all bands.
    Returns math.inf if schedule is empty."""
    if not schedule:
        return math.inf
    now_s = _time_to_seconds(now.time())
    candidates: list[int] = []
    for band in schedule:
        for point in (_parse_hhmm(band.start), _parse_hhmm(band.end)):
            boundary_s = _time_to_seconds(point)
            delta = boundary_s - now_s
            if delta <= 0:
                delta += 24 * 3600  # wrap to tomorrow
            candidates.append(delta)
    return float(min(candidates))
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_scheduler.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): time-band resolution + next-boundary calculation"
```

---

## Task 5: Solar interpolation

**Files:**
- Create: `avell_rgb/solar.py`
- Create: `tests/test_solar.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_solar.py`:
```python
from datetime import datetime, timezone

import pytest

from avell_rgb.solar import (
    hex_to_rgb,
    interpolate_solar,
    rgb_to_hex,
    solar_t_from_elevation,
)
from avell_rgb.state import DeviceState, SolarConfig


def test_hex_to_rgb_parses_six_chars():
    assert hex_to_rgb("#FF0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("#000000") == (0, 0, 0)
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)


def test_rgb_to_hex_uppercase():
    assert rgb_to_hex((255, 0, 0)) == "#FF0000"
    assert rgb_to_hex((0, 128, 255)) == "#0080FF"


def test_solar_t_nadir_is_zero():
    assert solar_t_from_elevation(-90) == 0.0


def test_solar_t_zenith_is_one():
    assert solar_t_from_elevation(90) == 1.0


def test_solar_t_horizon_is_half():
    # at elevation 0 (horizon), t should be 0.5
    assert solar_t_from_elevation(0) == pytest.approx(0.5, abs=0.05)


def test_solar_t_clamps_below_minus_six():
    assert solar_t_from_elevation(-30) == 0.0


def test_solar_t_clamps_above_six():
    assert solar_t_from_elevation(45) == 1.0


def _solar_cfg() -> SolarConfig:
    return SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",  # 255,255,255
        night_color="#000000",  # 0,0,0
        day_brightness=100,
        night_brightness=0,
        apply_to=("keyboard", "lightbar"),
    )


def test_interpolate_at_noon_sp_gives_day_color():
    cfg = _solar_cfg()
    # Apr 10, noon São Paulo (-03:00). Using tz-aware datetime.
    from datetime import timedelta

    noon_sp = datetime(2026, 4, 10, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, noon_sp)
    # At noon, sun elevation in SP is ~70°+, so t should be 1.0
    # keyboard solid, color close to #FFFFFF
    from avell_rgb.state import KeyboardSolid
    assert isinstance(state.keyboard, KeyboardSolid)
    assert state.keyboard.color == "#FFFFFF"
    assert state.lightbar.color == "#FFFFFF"
    assert state.keyboard.brightness >= 40  # scale applied (keyboard uses 0-50)
    assert state.lightbar.brightness == 100


def test_interpolate_at_midnight_sp_gives_night_color():
    cfg = _solar_cfg()
    from datetime import timedelta

    midnight_sp = datetime(2026, 4, 10, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, midnight_sp)
    from avell_rgb.state import KeyboardSolid
    assert isinstance(state.keyboard, KeyboardSolid)
    assert state.keyboard.color == "#000000"
    assert state.lightbar.color == "#000000"
    assert state.lightbar.brightness == 0


def test_interpolate_respects_apply_to_keyboard_only():
    cfg = SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",
        night_color="#000000",
        day_brightness=100,
        night_brightness=0,
        apply_to=("keyboard",),  # lightbar excluded
    )
    from datetime import timedelta

    noon_sp = datetime(2026, 4, 10, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, noon_sp)
    # keyboard interpolated; lightbar gets off (brightness=0)
    assert state.lightbar.brightness == 0
```

- [ ] **Step 2: Run, confirm failure**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_solar.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `solar.py`**

Create `avell_rgb/solar.py`:
```python
"""Solar gradient interpolation. Uses astral for sun elevation."""

from __future__ import annotations

from datetime import datetime

from astral import LocationInfo, sun

from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    SolarConfig,
)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def solar_t_from_elevation(elevation_deg: float) -> float:
    """Map sun elevation in degrees to a normalized blend factor t in [0, 1].
    - elevation <= -6° (past civil twilight): t = 0 (full night)
    - elevation >=  6°: t = 1 (full day)
    - between: linear interpolation"""
    if elevation_deg <= -6:
        return 0.0
    if elevation_deg >= 6:
        return 1.0
    return (elevation_deg + 6) / 12


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _lerp_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


def interpolate_solar(cfg: SolarConfig, now: datetime) -> DeviceState:
    """Compute the DeviceState for the given moment, blending between day
    and night colors using the real sun elevation at (lat, lon, now)."""
    loc = LocationInfo(latitude=cfg.latitude, longitude=cfg.longitude)
    elevation = sun.elevation(loc.observer, now)
    t = solar_t_from_elevation(elevation)

    night_rgb = hex_to_rgb(cfg.night_color)
    day_rgb = hex_to_rgb(cfg.day_color)
    blended_rgb = _lerp_rgb(night_rgb, day_rgb, t)
    blended_hex = rgb_to_hex(blended_rgb)

    kb_brightness = round(cfg.night_brightness + (cfg.day_brightness - cfg.night_brightness) * t)
    bar_brightness = kb_brightness  # same scale intent; 0-100

    # Keyboard brightness in ite8291r3-ctl is 0-50. Scale from the 0-100 user input.
    kb_brightness_scaled = min(50, round(kb_brightness * 50 / 100))

    if "keyboard" in cfg.apply_to:
        kb_state = KeyboardSolid(color=blended_hex, brightness=kb_brightness_scaled)
    else:
        kb_state = KeyboardOff()

    if "lightbar" in cfg.apply_to:
        bar_state = LightbarState(color=blended_hex, brightness=bar_brightness)
    else:
        bar_state = LightbarState(color="#000000", brightness=0)

    return DeviceState(keyboard=kb_state, lightbar=bar_state)
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_solar.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/solar.py tests/test_solar.py
git commit -m "feat(solar): astral-based day/night interpolation"
```

---

## Task 6: Keyboard backend + test fakes

**Files:**
- Create: `avell_rgb/backends/__init__.py`
- Create: `avell_rgb/backends/keyboard.py`
- Create: `tests/conftest.py`
- Create: `tests/test_keyboard_backend.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyboard_backend.py`:
```python
from unittest.mock import patch

import pytest

from avell_rgb.backends.keyboard import KeyboardBackend


@pytest.fixture
def backend():
    return KeyboardBackend()


def test_available_true_when_binary_present(backend, monkeypatch):
    monkeypatch.setattr(
        "avell_rgb.backends.keyboard.shutil.which",
        lambda name: "/usr/bin/" + name,
    )
    assert backend.available() is True


def test_available_false_when_binary_missing(backend, monkeypatch):
    monkeypatch.setattr(
        "avell_rgb.backends.keyboard.shutil.which", lambda name: None
    )
    assert backend.available() is False


def test_apply_solid_calls_monocolor(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_solid((0, 255, 255), 30)
        args = run.call_args.args[0]
        assert args[0].endswith("ite8291r3-ctl")
        assert "monocolor" in args
        assert "--rgb" in args
        assert "0,255,255" in args
        assert "-b" in args
        assert "30" in args


def test_apply_effect_calls_effect(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="wave",
            color="rainbow",
            speed=5,
            direction="right",
            brightness=40,
        )
        args = run.call_args.args[0]
        assert "effect" in args
        assert "wave" in args
        assert "-c" in args
        assert "rainbow" in args
        assert "-s" in args
        assert "5" in args
        assert "-d" in args
        assert "right" in args
        assert "-b" in args
        assert "40" in args


def test_apply_effect_without_direction_omits_flag(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="breathing",
            color="purple",
            speed=3,
            direction=None,
            brightness=25,
        )
        args = run.call_args.args[0]
        assert "-d" not in args


def test_off_calls_off_subcommand(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.off()
        args = run.call_args.args[0]
        assert args[-1] == "off"


def test_nonzero_exit_does_not_raise(backend, caplog):
    import subprocess

    with patch(
        "avell_rgb.backends.keyboard.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "ite8291r3-ctl"),
    ):
        backend.off()  # must not raise
```

- [ ] **Step 2: Run, confirm failure**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_keyboard_backend.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `keyboard.py`**

Create `avell_rgb/backends/__init__.py` (empty):
```python
```

Create `avell_rgb/backends/keyboard.py`:
```python
"""Keyboard backend: wraps the ite8291r3-ctl CLI."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

BINARY = "ite8291r3-ctl"


class KeyboardBackend:
    def available(self) -> bool:
        return shutil.which(BINARY) is not None

    def apply_solid(self, rgb: tuple[int, int, int], brightness: int) -> None:
        rgb_str = "{},{},{}".format(*rgb)
        cmd = [BINARY, "monocolor", "--rgb", rgb_str, "-b", str(brightness)]
        self._run(cmd)

    def apply_effect(
        self,
        effect: str,
        color: str,
        speed: int,
        direction: Optional[str],
        brightness: int,
    ) -> None:
        cmd = [
            BINARY,
            "effect",
            effect,
            "-c",
            color,
            "-s",
            str(speed),
            "-b",
            str(brightness),
        ]
        if direction is not None:
            cmd.extend(["-d", direction])
        self._run(cmd)

    def off(self) -> None:
        self._run([BINARY, "off"])

    def _run(self, cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            log.warning("ite8291r3-ctl not found; keyboard command skipped")
        except subprocess.CalledProcessError as e:
            log.warning("ite8291r3-ctl exited %d: %s", e.returncode, e.stderr or "")
```

Create `tests/conftest.py`:
```python
"""Shared test fixtures. Fake backends for daemon-loop tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FakeKeyboardBackend:
    """Records every call; used by daemon-loop tests."""

    available_returns: bool = True
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def available(self) -> bool:
        return self.available_returns

    def apply_solid(self, rgb, brightness):
        self.calls.append(("apply_solid", (rgb, brightness)))

    def apply_effect(self, effect, color, speed, direction, brightness):
        self.calls.append(("apply_effect", (effect, color, speed, direction, brightness)))

    def off(self):
        self.calls.append(("off", ()))


@dataclass
class FakeLightbarBackend:
    available_returns: bool = True
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def available(self) -> bool:
        return self.available_returns

    def apply(self, rgb, brightness):
        self.calls.append(("apply", (rgb, brightness)))

    def off(self):
        self.calls.append(("off", ()))
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_keyboard_backend.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/backends/__init__.py avell_rgb/backends/keyboard.py tests/conftest.py tests/test_keyboard_backend.py
git commit -m "feat(backends): keyboard via ite8291r3-ctl + test fakes"
```

---

## Task 7: Lightbar backend

**Files:**
- Create: `avell_rgb/backends/lightbar.py`
- Create: `tests/test_lightbar_backend.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_lightbar_backend.py`:
```python
import os
from pathlib import Path

import pytest

from avell_rgb.backends.lightbar import LightbarBackend


@pytest.fixture
def fake_sysfs(tmp_path: Path) -> Path:
    sysfs = tmp_path / "rgb_lightbar"
    sysfs.mkdir()
    (sysfs / "brightness").write_text("0\n")
    (sysfs / "multi_intensity").write_text("255 255 255\n")
    return sysfs


def test_available_false_when_sysfs_missing(tmp_path):
    bad = tmp_path / "nope"
    b = LightbarBackend(sysfs=bad)
    assert b.available() is False


def test_available_true_with_writable_sysfs(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    assert b.available() is True


def test_apply_writes_color_and_brightness(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    b.apply((0, 255, 255), 80)
    assert (fake_sysfs / "multi_intensity").read_text().strip() == "0 255 255"
    assert (fake_sysfs / "brightness").read_text().strip() == "80"


def test_off_sets_brightness_zero(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    b.off()
    assert (fake_sysfs / "brightness").read_text().strip() == "0"


def test_apply_handles_permission_denied_gracefully(fake_sysfs, monkeypatch):
    b = LightbarBackend(sysfs=fake_sysfs)

    def deny(*args, **kwargs):
        raise PermissionError("no write")

    monkeypatch.setattr(Path, "write_text", deny)
    # Must not raise
    b.apply((255, 0, 0), 50)
```

- [ ] **Step 2: Run, confirm failure**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_lightbar_backend.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `lightbar.py`**

Create `avell_rgb/backends/lightbar.py`:
```python
"""Lightbar backend: writes to the kernel sysfs LED interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_SYSFS = Path("/sys/class/leds/rgb:lightbar")


class LightbarBackend:
    def __init__(self, sysfs: Path = DEFAULT_SYSFS):
        self.sysfs = sysfs

    def available(self) -> bool:
        brightness = self.sysfs / "brightness"
        multi = self.sysfs / "multi_intensity"
        if not (brightness.exists() and multi.exists()):
            return False
        return os.access(brightness, os.W_OK) and os.access(multi, os.W_OK)

    def apply(self, rgb: tuple[int, int, int], brightness: int) -> None:
        r, g, b = rgb
        try:
            (self.sysfs / "multi_intensity").write_text(f"{r} {g} {b}\n")
            (self.sysfs / "brightness").write_text(f"{int(brightness)}\n")
        except (PermissionError, FileNotFoundError, OSError) as e:
            log.warning("lightbar write failed: %s", e)

    def off(self) -> None:
        try:
            (self.sysfs / "brightness").write_text("0\n")
        except (PermissionError, FileNotFoundError, OSError) as e:
            log.warning("lightbar off failed: %s", e)
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_lightbar_backend.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/backends/lightbar.py tests/test_lightbar_backend.py
git commit -m "feat(backends): lightbar via /sys/class/leds"
```

---

## Task 8: Daemon module skeleton

**Files:**
- Create: `avell_rgb/daemon/__init__.py`
- Create: `avell_rgb/daemon/main.py`

This task lays out the daemon class without the event loop. Task 9 adds the loop and tests it.

- [ ] **Step 1: Create empty init**

Create `avell_rgb/daemon/__init__.py` (empty):
```python
```

- [ ] **Step 2: Implement `DaemonCore` (pure, no asyncio)**

Create `avell_rgb/daemon/main.py`:
```python
"""Daemon: reads config, computes desired state, applies via backends.
The event loop lives in `run()`; `DaemonCore` is the pure side for testing."""

from __future__ import annotations

import asyncio
import logging
import math
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Protocol

from avell_rgb.config import CONFIG_PATH, load_config
from avell_rgb.scheduler import (
    resolve_schedule,
    seconds_until_next_schedule_boundary,
)
from avell_rgb.solar import interpolate_solar
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardEffect,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
)

log = logging.getLogger("avell_rgb.daemon")


class KeyboardProto(Protocol):
    def available(self) -> bool: ...
    def apply_solid(self, rgb: tuple[int, int, int], brightness: int) -> None: ...
    def apply_effect(
        self,
        effect: str,
        color: str,
        speed: int,
        direction: Optional[str],
        brightness: int,
    ) -> None: ...
    def off(self) -> None: ...


class LightbarProto(Protocol):
    def available(self) -> bool: ...
    def apply(self, rgb: tuple[int, int, int], brightness: int) -> None: ...
    def off(self) -> None: ...


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class DaemonCore:
    """Pure decision engine. No I/O except the injected backends and clock."""

    def __init__(
        self,
        config: Config,
        keyboard: KeyboardProto,
        lightbar: LightbarProto,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.keyboard = keyboard
        self.lightbar = lightbar
        self.clock = clock

    def compute_desired_state(self) -> Optional[DeviceState]:
        """Resolve which DeviceState should be applied right now."""
        if self.config.manual_state is not None:
            return self.config.manual_state
        now = self.clock()
        if self.config.mode == "solar":
            return interpolate_solar(self.config.solar, now)
        # mode == schedule
        return resolve_schedule(self.config.schedule, self.config.presets, now)

    def apply(self, state: Optional[DeviceState]) -> None:
        if state is None:
            log.info("no schedule band matches — leaving hardware as-is")
            return
        self._apply_keyboard(state)
        self._apply_lightbar(state.lightbar)

    def _apply_keyboard(self, state: DeviceState) -> None:
        if not self.keyboard.available():
            log.debug("keyboard backend unavailable")
            return
        kb = state.keyboard
        if isinstance(kb, KeyboardSolid):
            self.keyboard.apply_solid(_hex_to_rgb(kb.color), kb.brightness)
        elif isinstance(kb, KeyboardEffect):
            self.keyboard.apply_effect(
                effect=kb.effect,
                color=kb.color,
                speed=kb.speed,
                direction=kb.direction,
                brightness=kb.brightness,
            )
        elif isinstance(kb, KeyboardOff):
            self.keyboard.off()

    def _apply_lightbar(self, bar: LightbarState) -> None:
        if not self.lightbar.available():
            log.debug("lightbar backend unavailable")
            return
        if bar.brightness == 0:
            self.lightbar.off()
        else:
            self.lightbar.apply(_hex_to_rgb(bar.color), bar.brightness)

    def seconds_until_next_change(self) -> float:
        if self.config.manual_state is not None:
            return math.inf
        if self.config.mode == "solar":
            return 300.0  # re-tick every 5 minutes
        return seconds_until_next_schedule_boundary(self.config.schedule, self.clock())


def main() -> int:
    """Entry point. Wires real backends + asyncio loop. See Task 9 for the loop."""
    from avell_rgb.backends.keyboard import KeyboardBackend
    from avell_rgb.backends.lightbar import LightbarBackend

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    config = load_config()
    core = DaemonCore(
        config=config,
        keyboard=KeyboardBackend(),
        lightbar=LightbarBackend(),
    )

    async def run():
        reload_event = asyncio.Event()

        def on_sighup(*_):
            log.info("SIGHUP received — reload queued")
            reload_event.set()

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP, on_sighup)
        loop.add_signal_handler(signal.SIGTERM, lambda: sys.exit(0))
        loop.add_signal_handler(signal.SIGINT, lambda: sys.exit(0))

        while True:
            state = core.compute_desired_state()
            core.apply(state)
            delay = core.seconds_until_next_change()
            if math.isinf(delay):
                await reload_event.wait()
            else:
                try:
                    await asyncio.wait_for(reload_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
            if reload_event.is_set():
                log.info("reloading config")
                core.config = load_config()
                reload_event.clear()

    try:
        asyncio.run(run())
    except SystemExit:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Smoke-test imports**

Run:
```bash
cd ~/src/avell-rgb && python -c "from avell_rgb.daemon.main import DaemonCore; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add avell_rgb/daemon/__init__.py avell_rgb/daemon/main.py
git commit -m "feat(daemon): DaemonCore + asyncio loop skeleton"
```

---

## Task 9: Daemon loop tests

**Files:**
- Create: `tests/test_daemon_loop.py`

- [ ] **Step 1: Write tests using `DaemonCore` and fakes**

Create `tests/test_daemon_loop.py`:
```python
from datetime import datetime
from math import isinf

import pytest

from avell_rgb.config import DEFAULT_CONFIG
from avell_rgb.daemon.main import DaemonCore
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)
from tests.conftest import FakeKeyboardBackend, FakeLightbarBackend


def _simple_config(
    mode: str = "schedule",
    manual_state=None,
    schedule=None,
    presets=None,
) -> Config:
    return Config(
        version=1,
        mode=mode,
        manual_paused=False,
        manual_state=manual_state,
        presets=presets
        or {
            "work": DeviceState(
                keyboard=KeyboardSolid(color="#00FFFF", brightness=30),
                lightbar=LightbarState(color="#00FFFF", brightness=80),
            ),
            "off": DeviceState(
                keyboard=KeyboardOff(),
                lightbar=LightbarState(color="#000000", brightness=0),
            ),
        },
        schedule=schedule
        or [
            ScheduleBand(start="07:00", end="18:00", preset="work"),
            ScheduleBand(start="18:00", end="07:00", preset="off"),
        ],
        solar=SolarConfig(
            latitude=0.0,
            longitude=0.0,
            day_color="#FFFFFF",
            night_color="#000000",
            day_brightness=50,
            night_brightness=10,
            apply_to=("keyboard", "lightbar"),
        ),
    )


def test_manual_state_overrides_schedule():
    manual = DeviceState(
        keyboard=KeyboardSolid(color="#FF00FF", brightness=40),
        lightbar=LightbarState(color="#FF00FF", brightness=90),
    )
    cfg = _simple_config(manual_state=manual)
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    state = core.compute_desired_state()
    assert state == manual


def test_schedule_applied_at_noon():
    cfg = _simple_config()
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls[-1][0] == "apply_solid"
    assert kb.calls[-1][1] == ((0, 255, 255), 30)
    assert bar.calls[-1][0] == "apply"
    assert bar.calls[-1][1] == ((0, 255, 255), 80)


def test_schedule_applied_at_night_keyboard_off_lightbar_off():
    cfg = _simple_config()
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 22, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls[-1][0] == "off"
    assert bar.calls[-1][0] == "off"


def test_seconds_until_next_change_manual_is_infinity():
    manual = DeviceState(
        keyboard=KeyboardOff(),
        lightbar=LightbarState(color="#000000", brightness=0),
    )
    cfg = _simple_config(manual_state=manual)
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    assert isinf(core.seconds_until_next_change())


def test_seconds_until_next_change_solar_is_300():
    cfg = _simple_config(mode="solar")
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    assert core.seconds_until_next_change() == 300.0


def test_seconds_until_next_change_schedule_is_boundary():
    cfg = _simple_config()
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    # nearest boundary from 12:00 is 18:00 (6h)
    assert core.seconds_until_next_change() == 6 * 3600


def test_unavailable_keyboard_does_not_crash():
    cfg = _simple_config()
    kb = FakeKeyboardBackend(available_returns=False)
    bar = FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls == []
    assert bar.calls[-1][0] == "apply"  # lightbar still applied


def test_solar_mode_produces_some_state():
    cfg = _simple_config(mode="solar")
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    state = core.compute_desired_state()
    assert state is not None
    assert state.lightbar.color.startswith("#")
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest tests/test_daemon_loop.py -v
```

Expected: 8 passed.

- [ ] **Step 3: Run full test suite sanity check**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest -v
```

Expected: all passing (state: 9 + config: 6 + scheduler: 12 + solar: 10 + keyboard backend: 7 + lightbar backend: 5 + daemon loop: 8 = 57 tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_daemon_loop.py
git commit -m "test(daemon): core decision + apply behavior"
```

---

## Task 10: GUI bootstrap — AdwApplication + empty window

**Files:**
- Create: `avell_rgb/gui/__init__.py`
- Create: `avell_rgb/gui/main.py`
- Create: `avell_rgb/gui/app.py`
- Create: `avell_rgb/gui/window.py`

This task gets a window on screen with the sidebar. Pages are stubbed until tasks 11–14 fill them in.

- [ ] **Step 1: Create empty init**

Create `avell_rgb/gui/__init__.py` (empty):
```python
```

- [ ] **Step 2: Implement `app.py`**

Create `avell_rgb/gui/app.py`:
```python
"""AdwApplication subclass."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from avell_rgb.gui.window import AvellWindow


class AvellApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.avellrgb.Avell")
        self.window: AvellWindow | None = None

    def do_activate(self):
        if self.window is None:
            self.window = AvellWindow(application=self)
        self.window.present()
```

- [ ] **Step 3: Implement `window.py` with sidebar + stub pages**

Create `avell_rgb/gui/window.py`:
```python
"""Main application window. Sidebar + content stack with 4 pages."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402


def _stub_page(title: str) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_top(48)
    box.set_margin_bottom(48)
    box.set_margin_start(48)
    box.set_margin_end(48)
    label = Gtk.Label(label=title)
    label.add_css_class("title-1")
    box.append(label)
    box.append(Gtk.Label(label="(em construção)"))
    return box


class AvellWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(application=application)
        self.set_default_size(900, 620)
        self.set_title("Avell RGB")

        split = Adw.NavigationSplitView()
        self.set_content(split)

        # Sidebar
        sidebar = Adw.NavigationPage()
        sidebar.set_title("Avell RGB")
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_header = Adw.HeaderBar()
        sidebar_header.add_css_class("flat")
        sidebar_box.append(sidebar_header)

        self.stack = Adw.ViewStack()
        self.stack.add_titled(_stub_page("Agora"), "now", "Agora")
        self.stack.add_titled(_stub_page("Presets"), "presets", "Presets")
        self.stack.add_titled(_stub_page("Agenda"), "schedule", "Agenda")
        self.stack.add_titled(_stub_page("Preferências"), "preferences", "Preferências")

        sidebar_list = Adw.ViewSwitcher()
        sidebar_list.set_stack(self.stack)
        sidebar_list.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        sidebar_box.append(sidebar_list)
        sidebar.set_child(sidebar_box)
        split.set_sidebar(sidebar)

        # Content
        content = Adw.NavigationPage()
        content.set_title("Avell RGB")
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_header = Adw.HeaderBar()
        content_box.append(content_header)
        content_box.append(self.stack)
        content.set_child(content_box)
        split.set_content(content)
```

- [ ] **Step 4: Implement `main.py` entry point**

Create `avell_rgb/gui/main.py`:
```python
"""GUI entry point."""

from __future__ import annotations

import sys

from avell_rgb.gui.app import AvellApp


def main() -> int:
    app = AvellApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Smoke-test imports + launch**

Run:
```bash
cd ~/src/avell-rgb && python -c "from avell_rgb.gui.app import AvellApp; print('ok')"
```

Expected: `ok`.

Then launch briefly (manual):
```bash
cd ~/src/avell-rgb && python -m avell_rgb.gui.main &
sleep 2
wmctrl -l | grep -i "Avell RGB" && echo "WINDOW_OPEN"
pkill -f "avell_rgb.gui.main"
```

Expected: `WINDOW_OPEN` printed. (If `wmctrl` missing, open manually to verify window appears with sidebar.)

- [ ] **Step 6: Commit**

```bash
git add avell_rgb/gui/__init__.py avell_rgb/gui/main.py avell_rgb/gui/app.py avell_rgb/gui/window.py
git commit -m "feat(gui): AdwApplication + window shell with stub pages"
```

---

## Task 11: GUI "Agora" page — live controls with preview

**Files:**
- Create: `avell_rgb/gui/color_helpers.py`
- Create: `avell_rgb/gui/page_now.py`
- Modify: `avell_rgb/gui/window.py:48-52` (replace the stub for "now")

- [ ] **Step 1: Implement `color_helpers.py`**

Create `avell_rgb/gui/color_helpers.py`:
```python
"""Color conversion helpers shared by GUI pages."""

from __future__ import annotations

from gi.repository import Gdk


def hex_to_rgba(hex_str: str) -> Gdk.RGBA:
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    rgba = Gdk.RGBA()
    rgba.red = r / 255
    rgba.green = g / 255
    rgba.blue = b / 255
    rgba.alpha = 1.0
    return rgba


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    r = round(rgba.red * 255)
    g = round(rgba.green * 255)
    b = round(rgba.blue * 255)
    return "#{:02X}{:02X}{:02X}".format(r, g, b)
```

- [ ] **Step 2: Implement `page_now.py`**

Create `avell_rgb/gui/page_now.py`:
```python
"""Page 'Agora' — direct preview controls that write manual_state."""

from __future__ import annotations

import subprocess
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardEffect,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    VALID_EFFECTS,
)


def _reload_daemon() -> None:
    """Send SIGHUP to the daemon via systemctl --user."""
    try:
        subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", "avell-rgb-daemon.service"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # systemctl missing in test env


class NowPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config: Config = load_config()
        self._suspend_events = False

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        # Keyboard group
        kb_group = Adw.PreferencesGroup(title="Teclado")
        outer.append(kb_group)
        self._build_keyboard_rows(kb_group)

        # Lightbar group
        bar_group = Adw.PreferencesGroup(title="Barra inferior")
        outer.append(bar_group)
        self._build_lightbar_rows(bar_group)

        # Apply current state into the widgets on load
        self._load_from_config()

    # ---------- build ----------

    def _build_keyboard_rows(self, group: Adw.PreferencesGroup) -> None:
        mode_row = Adw.ComboRow(title="Modo")
        self.kb_mode_model = Gtk.StringList.new(["Cor sólida", "Efeito", "Desligado"])
        mode_row.set_model(self.kb_mode_model)
        mode_row.connect("notify::selected", self._on_kb_mode_changed)
        group.add(mode_row)
        self.kb_mode_row = mode_row

        color_row = Adw.ActionRow(title="Cor")
        self.kb_color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self.kb_color_btn.set_dialog(dlg)
        self.kb_color_btn.set_valign(Gtk.Align.CENTER)
        self.kb_color_btn.connect("notify::rgba", self._on_kb_color_changed)
        color_row.add_suffix(self.kb_color_btn)
        group.add(color_row)
        self.kb_color_row = color_row

        eff_row = Adw.ComboRow(title="Efeito")
        self.kb_effect_model = Gtk.StringList.new(list(VALID_EFFECTS))
        eff_row.set_model(self.kb_effect_model)
        eff_row.connect("notify::selected", self._on_kb_settings_changed)
        group.add(eff_row)
        self.kb_effect_row = eff_row

        speed_row = Adw.ActionRow(title="Velocidade")
        self.kb_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 10, 1)
        self.kb_speed.set_value(5)
        self.kb_speed.set_size_request(200, -1)
        self.kb_speed.set_valign(Gtk.Align.CENTER)
        self.kb_speed.connect("value-changed", self._on_kb_settings_changed)
        speed_row.add_suffix(self.kb_speed)
        group.add(speed_row)
        self.kb_speed_row = speed_row

        bright_row = Adw.ActionRow(title="Brilho")
        self.kb_brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 50, 1
        )
        self.kb_brightness.set_value(30)
        self.kb_brightness.set_size_request(200, -1)
        self.kb_brightness.set_valign(Gtk.Align.CENTER)
        self.kb_brightness.connect("value-changed", self._on_kb_settings_changed)
        bright_row.add_suffix(self.kb_brightness)
        group.add(bright_row)

    def _build_lightbar_rows(self, group: Adw.PreferencesGroup) -> None:
        color_row = Adw.ActionRow(title="Cor")
        self.bar_color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self.bar_color_btn.set_dialog(dlg)
        self.bar_color_btn.set_valign(Gtk.Align.CENTER)
        self.bar_color_btn.connect("notify::rgba", self._on_bar_changed)
        color_row.add_suffix(self.bar_color_btn)
        group.add(color_row)

        bright_row = Adw.ActionRow(title="Brilho")
        self.bar_brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.bar_brightness.set_value(80)
        self.bar_brightness.set_size_request(200, -1)
        self.bar_brightness.set_valign(Gtk.Align.CENTER)
        self.bar_brightness.connect("value-changed", self._on_bar_changed)
        bright_row.add_suffix(self.bar_brightness)
        group.add(bright_row)

    # ---------- load / save ----------

    def _load_from_config(self) -> None:
        self._suspend_events = True
        state = self.config.manual_state
        if state is None:
            # Use first preset as a starting point
            if self.config.presets:
                state = next(iter(self.config.presets.values()))
        if state is not None:
            kb = state.keyboard
            bar = state.lightbar
            if isinstance(kb, KeyboardSolid):
                self.kb_mode_row.set_selected(0)
                self.kb_color_btn.set_rgba(hex_to_rgba(kb.color))
                self.kb_brightness.set_value(kb.brightness)
            elif isinstance(kb, KeyboardEffect):
                self.kb_mode_row.set_selected(1)
                for i, name in enumerate(VALID_EFFECTS):
                    if name == kb.effect:
                        self.kb_effect_row.set_selected(i)
                        break
                self.kb_speed.set_value(kb.speed)
                self.kb_brightness.set_value(kb.brightness)
            else:
                self.kb_mode_row.set_selected(2)
            self.bar_color_btn.set_rgba(hex_to_rgba(bar.color))
            self.bar_brightness.set_value(bar.brightness)
        self._update_row_visibility()
        self._suspend_events = False

    def _current_device_state(self) -> DeviceState:
        idx = self.kb_mode_row.get_selected()
        if idx == 0:
            kb = KeyboardSolid(
                color=rgba_to_hex(self.kb_color_btn.get_rgba()),
                brightness=int(self.kb_brightness.get_value()),
            )
        elif idx == 1:
            effect_idx = self.kb_effect_row.get_selected()
            kb = KeyboardEffect(
                effect=VALID_EFFECTS[effect_idx],
                color=rgba_to_hex(self.kb_color_btn.get_rgba()),
                speed=int(self.kb_speed.get_value()),
                direction=None,
                brightness=int(self.kb_brightness.get_value()),
            )
        else:
            kb = KeyboardOff()
        bar = LightbarState(
            color=rgba_to_hex(self.bar_color_btn.get_rgba()),
            brightness=int(self.bar_brightness.get_value()),
        )
        return DeviceState(keyboard=kb, lightbar=bar)

    def _write_and_reload(self) -> None:
        if self._suspend_events:
            return
        state = self._current_device_state()
        self.config = load_config()  # pick up anything else changed externally
        from dataclasses import replace

        self.config = replace(self.config, manual_state=state)
        save_config(self.config)
        _reload_daemon()

    # ---------- signals ----------

    def _on_kb_mode_changed(self, *args) -> None:
        self._update_row_visibility()
        self._write_and_reload()

    def _on_kb_color_changed(self, *args) -> None:
        self._write_and_reload()

    def _on_kb_settings_changed(self, *args) -> None:
        self._write_and_reload()

    def _on_bar_changed(self, *args) -> None:
        self._write_and_reload()

    def _update_row_visibility(self) -> None:
        idx = self.kb_mode_row.get_selected()
        is_solid = idx == 0
        is_effect = idx == 1
        self.kb_color_row.set_visible(is_solid or is_effect)
        self.kb_effect_row.set_visible(is_effect)
        self.kb_speed_row.set_visible(is_effect)
```

- [ ] **Step 3: Wire `NowPage` into the window**

Edit `avell_rgb/gui/window.py`:

Replace:
```python
        self.stack.add_titled(_stub_page("Agora"), "now", "Agora")
```

With:
```python
        from avell_rgb.gui.page_now import NowPage

        self.stack.add_titled(NowPage(), "now", "Agora")
```

- [ ] **Step 4: Smoke test: launch, click stuff, close**

Run (in a graphical session):
```bash
cd ~/src/avell-rgb && python -m avell_rgb.gui.main
```

Expected: window opens on "Agora" page; keyboard + lightbar sections visible; changing the color picker updates the hardware (keyboard/bar reflect the change via daemon — if daemon not yet running, writes config but no visible effect).

Close the window after checking. Dev can verify `~/.config/avell-rgb/config.json` now has a `manual_state`.

- [ ] **Step 5: Commit**

```bash
git add avell_rgb/gui/color_helpers.py avell_rgb/gui/page_now.py avell_rgb/gui/window.py
git commit -m "feat(gui): Agora page with live preview via manual_state"
```

---

## Task 12: GUI "Presets" page

**Files:**
- Create: `avell_rgb/gui/page_presets.py`
- Modify: `avell_rgb/gui/window.py` (add presets page + on-window-close cleanup)

- [ ] **Step 1: Implement `page_presets.py`**

Create `avell_rgb/gui/page_presets.py`:
```python
"""Presets page: list, add, edit, remove named DeviceStates."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
)


class PresetsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config = load_config()

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_hexpand(True)
        title = Gtk.Label(label="Presets")
        title.add_css_class("title-2")
        title.set_xalign(0)
        title.set_hexpand(True)
        header.append(title)

        add_btn = Gtk.Button(label="+ Novo preset")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_clicked)
        header.append(add_btn)
        outer.append(header)

        self.group = Adw.PreferencesGroup()
        outer.append(self.group)

        self._refresh_list()

    def _refresh_list(self) -> None:
        # Remove existing rows
        child = self.group.get_first_child()
        # Adw.PreferencesGroup children accessible via internal list; rebuild by clearing:
        # Simpler: recreate the whole group
        parent = self.group.get_parent()
        parent.remove(self.group)
        self.group = Adw.PreferencesGroup()
        parent.append(self.group)

        self.config = load_config()
        for name, state in self.config.presets.items():
            row = self._make_row(name, state)
            self.group.add(row)

    def _make_row(self, name: str, state: DeviceState) -> Adw.ActionRow:
        row = Adw.ActionRow(title=name)
        # Color swatches
        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        kb_swatch = self._swatch_for_keyboard(state)
        bar_swatch = Gtk.Frame()
        bar_swatch.set_size_request(24, 24)
        bar_swatch.set_valign(Gtk.Align.CENTER)
        bar_swatch.set_tooltip_text(f"Barra: {state.lightbar.color}")
        css = Gtk.CssProvider()
        css.load_from_data(
            f"frame {{ background: {state.lightbar.color}; }}".encode()
        )
        bar_swatch.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        swatches.append(kb_swatch)
        swatches.append(bar_swatch)
        row.add_suffix(swatches)

        menu_btn = Gtk.MenuButton(icon_name="view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)

        popover = Gtk.Popover()
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_top(6)
        menu_box.set_margin_bottom(6)
        menu_box.set_margin_start(6)
        menu_box.set_margin_end(6)
        edit = Gtk.Button(label="Editar")
        edit.set_has_frame(False)
        edit.connect("clicked", lambda _b, n=name: self._on_edit(n))
        menu_box.append(edit)
        dup = Gtk.Button(label="Duplicar")
        dup.set_has_frame(False)
        dup.connect("clicked", lambda _b, n=name: self._on_duplicate(n))
        menu_box.append(dup)
        rem = Gtk.Button(label="Remover")
        rem.set_has_frame(False)
        rem.connect("clicked", lambda _b, n=name: self._on_remove(n))
        menu_box.append(rem)
        popover.set_child(menu_box)
        menu_btn.set_popover(popover)

        row.add_suffix(menu_btn)
        return row

    def _swatch_for_keyboard(self, state: DeviceState) -> Gtk.Widget:
        frame = Gtk.Frame()
        frame.set_size_request(24, 24)
        frame.set_valign(Gtk.Align.CENTER)
        kb = state.keyboard
        if isinstance(kb, KeyboardSolid):
            color = kb.color
            tip = f"Teclado: {color}"
        elif isinstance(kb, KeyboardOff):
            color = "#222222"
            tip = "Teclado: desligado"
        else:
            color = "#666666"
            tip = f"Teclado: efeito {getattr(kb, 'effect', '?')}"
        frame.set_tooltip_text(tip)
        css = Gtk.CssProvider()
        css.load_from_data(f"frame {{ background: {color}; }}".encode())
        frame.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        return frame

    # ---------- actions ----------

    def _on_add_clicked(self, _btn) -> None:
        self._open_editor(name=None)

    def _on_edit(self, name: str) -> None:
        self._open_editor(name=name)

    def _on_duplicate(self, name: str) -> None:
        self.config = load_config()
        src = self.config.presets[name]
        new_name = name + "_copy"
        i = 2
        while new_name in self.config.presets:
            new_name = f"{name}_copy{i}"
            i += 1
        new_presets = dict(self.config.presets)
        new_presets[new_name] = src
        self.config = replace(self.config, presets=new_presets)
        save_config(self.config)
        self._refresh_list()

    def _on_remove(self, name: str) -> None:
        self.config = load_config()
        new_presets = {k: v for k, v in self.config.presets.items() if k != name}
        self.config = replace(self.config, presets=new_presets)
        save_config(self.config)
        self._refresh_list()

    def _open_editor(self, name: str | None) -> None:
        self.config = load_config()
        dialog = Adw.Window()
        dialog.set_modal(True)
        dialog.set_transient_for(self.get_root())
        dialog.set_default_size(480, 420)
        dialog.set_title("Editar preset" if name else "Novo preset")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Nome do preset")
        if name is not None:
            name_entry.set_text(name)
            name_entry.set_editable(False)
        box.append(name_entry)

        kb_color_btn = Gtk.ColorDialogButton()
        kb_color_btn.set_dialog(Gtk.ColorDialog())
        box.append(Gtk.Label(label="Cor do teclado", xalign=0))
        box.append(kb_color_btn)

        kb_bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 50, 1)
        box.append(Gtk.Label(label="Brilho do teclado", xalign=0))
        box.append(kb_bri)

        bar_color_btn = Gtk.ColorDialogButton()
        bar_color_btn.set_dialog(Gtk.ColorDialog())
        box.append(Gtk.Label(label="Cor da barra", xalign=0))
        box.append(bar_color_btn)

        bar_bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        box.append(Gtk.Label(label="Brilho da barra", xalign=0))
        box.append(bar_bri)

        if name is not None:
            state = self.config.presets[name]
            if isinstance(state.keyboard, KeyboardSolid):
                kb_color_btn.set_rgba(hex_to_rgba(state.keyboard.color))
                kb_bri.set_value(state.keyboard.brightness)
            bar_color_btn.set_rgba(hex_to_rgba(state.lightbar.color))
            bar_bri.set_value(state.lightbar.brightness)
        else:
            kb_color_btn.set_rgba(hex_to_rgba("#FFFFFF"))
            kb_bri.set_value(30)
            bar_color_btn.set_rgba(hex_to_rgba("#FFFFFF"))
            bar_bri.set_value(80)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dialog.close())
        btns.append(cancel)
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")

        def on_save(_b):
            self.config = load_config()
            new_name = name_entry.get_text().strip() or "novo"
            new_state = DeviceState(
                keyboard=KeyboardSolid(
                    color=rgba_to_hex(kb_color_btn.get_rgba()),
                    brightness=int(kb_bri.get_value()),
                ),
                lightbar=LightbarState(
                    color=rgba_to_hex(bar_color_btn.get_rgba()),
                    brightness=int(bar_bri.get_value()),
                ),
            )
            new_presets = dict(self.config.presets)
            new_presets[new_name] = new_state
            self.config = replace(self.config, presets=new_presets)
            save_config(self.config)
            self._refresh_list()
            dialog.close()

        save.connect("clicked", on_save)
        btns.append(save)
        box.append(btns)

        dialog.set_content(box)
        dialog.present()
```

- [ ] **Step 2: Wire into window**

Edit `avell_rgb/gui/window.py`:

Replace:
```python
        self.stack.add_titled(_stub_page("Presets"), "presets", "Presets")
```

With:
```python
        from avell_rgb.gui.page_presets import PresetsPage

        self.stack.add_titled(PresetsPage(), "presets", "Presets")
```

- [ ] **Step 3: Smoke test**

Launch the GUI, navigate to Presets, add a preset, verify it saves in `~/.config/avell-rgb/config.json`.

- [ ] **Step 4: Commit**

```bash
git add avell_rgb/gui/page_presets.py avell_rgb/gui/window.py
git commit -m "feat(gui): Presets page with add/edit/duplicate/remove"
```

---

## Task 13: GUI "Agenda" page

**Files:**
- Create: `avell_rgb/gui/page_schedule.py`
- Modify: `avell_rgb/gui/window.py`

- [ ] **Step 1: Implement `page_schedule.py`**

Create `avell_rgb/gui/page_schedule.py`:
```python
"""Schedule page: time-band editor + solar mode."""

from __future__ import annotations

import subprocess
from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import ScheduleBand, SolarConfig


def _reload_daemon() -> None:
    try:
        subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", "avell-rgb-daemon.service"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


class SchedulePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.config = load_config()

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        mode_group = Adw.PreferencesGroup(title="Modo automático")
        self.mode_row = Adw.ComboRow(title="Modo")
        self.mode_row.set_model(
            Gtk.StringList.new(["Por faixa horária", "Seguir o sol"])
        )
        self.mode_row.set_selected(0 if self.config.mode == "schedule" else 1)
        self.mode_row.connect("notify::selected", self._on_mode_changed)
        mode_group.add(self.mode_row)
        outer.append(mode_group)

        # Schedule bands
        self.bands_group = Adw.PreferencesGroup(title="Faixas horárias")
        outer.append(self.bands_group)
        add_row = Adw.ActionRow()
        add_btn = Gtk.Button(label="+ Adicionar faixa")
        add_btn.set_valign(Gtk.Align.CENTER)
        add_btn.connect("clicked", self._on_add_band)
        add_row.add_suffix(add_btn)
        self.bands_group.add(add_row)
        self._refresh_bands()

        # Solar config
        self.solar_group = Adw.PreferencesGroup(title="Configuração solar")
        outer.append(self.solar_group)
        self._build_solar_rows()

        self._update_sections_visibility()

    # ---------- bands ----------

    def _refresh_bands(self) -> None:
        self.config = load_config()
        parent = self.bands_group.get_parent()
        parent.remove(self.bands_group)
        self.bands_group = Adw.PreferencesGroup(title="Faixas horárias")
        parent.prepend(self.bands_group)  # keep above solar
        # Re-add button
        add_row = Adw.ActionRow()
        add_btn = Gtk.Button(label="+ Adicionar faixa")
        add_btn.set_valign(Gtk.Align.CENTER)
        add_btn.connect("clicked", self._on_add_band)
        add_row.add_suffix(add_btn)
        self.bands_group.add(add_row)
        for i, band in enumerate(self.config.schedule):
            row = self._make_band_row(i, band)
            self.bands_group.add(row)

    def _make_band_row(self, idx: int, band: ScheduleBand) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=f"{band.start} – {band.end}",
            subtitle=f"Preset: {band.preset}",
        )
        rm = Gtk.Button(icon_name="edit-delete-symbolic")
        rm.set_valign(Gtk.Align.CENTER)
        rm.set_has_frame(False)
        rm.connect("clicked", lambda _b, i=idx: self._on_remove_band(i))
        row.add_suffix(rm)
        return row

    def _on_add_band(self, _btn) -> None:
        self._open_band_editor(None)

    def _on_remove_band(self, idx: int) -> None:
        self.config = load_config()
        new_sched = list(self.config.schedule)
        del new_sched[idx]
        self.config = replace(self.config, schedule=new_sched)
        save_config(self.config)
        _reload_daemon()
        self._refresh_bands()

    def _open_band_editor(self, idx: int | None) -> None:
        self.config = load_config()
        dialog = Adw.Window()
        dialog.set_modal(True)
        dialog.set_transient_for(self.get_root())
        dialog.set_default_size(400, 300)
        dialog.set_title("Nova faixa" if idx is None else "Editar faixa")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        start_entry = Gtk.Entry(placeholder_text="HH:MM início (ex: 07:00)")
        end_entry = Gtk.Entry(placeholder_text="HH:MM fim (ex: 18:00)")
        preset_row = Adw.ComboRow(title="Preset")
        preset_names = list(self.config.presets.keys()) or ["(sem presets)"]
        preset_row.set_model(Gtk.StringList.new(preset_names))

        box.append(start_entry)
        box.append(end_entry)
        box.append(preset_row)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dialog.close())
        btns.append(cancel)
        save_btn = Gtk.Button(label="Salvar")
        save_btn.add_css_class("suggested-action")

        def on_save(_b):
            try:
                start = start_entry.get_text().strip()
                end = end_entry.get_text().strip()
                p_idx = preset_row.get_selected()
                preset = preset_names[p_idx]
                new_band = ScheduleBand(start=start, end=end, preset=preset)
            except Exception:
                return
            self.config = load_config()
            new_sched = list(self.config.schedule)
            new_sched.append(new_band)
            self.config = replace(self.config, schedule=new_sched)
            save_config(self.config)
            _reload_daemon()
            self._refresh_bands()
            dialog.close()

        save_btn.connect("clicked", on_save)
        btns.append(save_btn)
        box.append(btns)

        dialog.set_content(box)
        dialog.present()

    # ---------- solar ----------

    def _build_solar_rows(self) -> None:
        solar = self.config.solar
        lat_row = Adw.ActionRow(title="Latitude")
        self.lat_entry = Gtk.Entry()
        self.lat_entry.set_text(str(solar.latitude))
        self.lat_entry.set_valign(Gtk.Align.CENTER)
        self.lat_entry.connect("changed", self._on_solar_changed)
        lat_row.add_suffix(self.lat_entry)
        self.solar_group.add(lat_row)

        lon_row = Adw.ActionRow(title="Longitude")
        self.lon_entry = Gtk.Entry()
        self.lon_entry.set_text(str(solar.longitude))
        self.lon_entry.set_valign(Gtk.Align.CENTER)
        self.lon_entry.connect("changed", self._on_solar_changed)
        lon_row.add_suffix(self.lon_entry)
        self.solar_group.add(lon_row)

        day_row = Adw.ActionRow(title="Cor de dia")
        self.day_color = Gtk.ColorDialogButton()
        self.day_color.set_dialog(Gtk.ColorDialog())
        self.day_color.set_rgba(hex_to_rgba(solar.day_color))
        self.day_color.set_valign(Gtk.Align.CENTER)
        self.day_color.connect("notify::rgba", self._on_solar_changed)
        day_row.add_suffix(self.day_color)
        self.solar_group.add(day_row)

        night_row = Adw.ActionRow(title="Cor de noite")
        self.night_color = Gtk.ColorDialogButton()
        self.night_color.set_dialog(Gtk.ColorDialog())
        self.night_color.set_rgba(hex_to_rgba(solar.night_color))
        self.night_color.set_valign(Gtk.Align.CENTER)
        self.night_color.connect("notify::rgba", self._on_solar_changed)
        night_row.add_suffix(self.night_color)
        self.solar_group.add(night_row)

    def _on_solar_changed(self, *_a) -> None:
        try:
            lat = float(self.lat_entry.get_text())
            lon = float(self.lon_entry.get_text())
        except ValueError:
            return
        self.config = load_config()
        new_solar = SolarConfig(
            latitude=lat,
            longitude=lon,
            day_color=rgba_to_hex(self.day_color.get_rgba()),
            night_color=rgba_to_hex(self.night_color.get_rgba()),
            day_brightness=self.config.solar.day_brightness,
            night_brightness=self.config.solar.night_brightness,
            apply_to=self.config.solar.apply_to,
        )
        self.config = replace(self.config, solar=new_solar)
        save_config(self.config)
        _reload_daemon()

    # ---------- mode ----------

    def _on_mode_changed(self, *_a) -> None:
        idx = self.mode_row.get_selected()
        new_mode = "schedule" if idx == 0 else "solar"
        self.config = load_config()
        self.config = replace(self.config, mode=new_mode)
        save_config(self.config)
        _reload_daemon()
        self._update_sections_visibility()

    def _update_sections_visibility(self) -> None:
        is_schedule = self.mode_row.get_selected() == 0
        self.bands_group.set_visible(is_schedule)
        self.solar_group.set_visible(not is_schedule)
```

- [ ] **Step 2: Wire into window**

Edit `avell_rgb/gui/window.py`:

Replace:
```python
        self.stack.add_titled(_stub_page("Agenda"), "schedule", "Agenda")
```

With:
```python
        from avell_rgb.gui.page_schedule import SchedulePage

        self.stack.add_titled(SchedulePage(), "schedule", "Agenda")
```

- [ ] **Step 3: Smoke test**

Launch GUI, switch between schedule/solar, add a band, verify config updates.

- [ ] **Step 4: Commit**

```bash
git add avell_rgb/gui/page_schedule.py avell_rgb/gui/window.py
git commit -m "feat(gui): Agenda page with time bands and solar mode"
```

---

## Task 14: GUI "Preferências" page + window close cleanup

**Files:**
- Create: `avell_rgb/gui/page_preferences.py`
- Modify: `avell_rgb/gui/window.py`

- [ ] **Step 1: Implement `page_preferences.py`**

Create `avell_rgb/gui/page_preferences.py`:
```python
"""Preferences page: simple toggles + about info."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from avell_rgb import __version__
from avell_rgb.config import CONFIG_PATH, load_config, save_config


class PreferencesPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.config = load_config()

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        group = Adw.PreferencesGroup(title="Comportamento")

        autostart_row = Adw.SwitchRow(
            title="Iniciar daemon no login",
            subtitle="Habilita o serviço systemd de usuário",
        )
        autostart_row.set_active(self._is_daemon_enabled())
        autostart_row.connect("notify::active", self._on_autostart_toggled)
        group.add(autostart_row)

        pause_row = Adw.SwitchRow(
            title="Manter estado manual ao fechar",
            subtitle="Quando ligado, fechar a janela não limpa o preview ao vivo",
        )
        pause_row.set_active(self.config.manual_paused)
        pause_row.connect("notify::active", self._on_pause_toggled)
        group.add(pause_row)

        open_row = Adw.ActionRow(title="Abrir config.json no editor")
        open_btn = Gtk.Button(label="Abrir")
        open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.connect("clicked", self._on_open_config)
        open_row.add_suffix(open_btn)
        group.add(open_row)

        outer.append(group)

        about = Adw.PreferencesGroup(title="Sobre")
        version_row = Adw.ActionRow(title="Versão", subtitle=__version__)
        about.add(version_row)
        license_row = Adw.ActionRow(title="Licença", subtitle="MIT")
        about.add(license_row)
        outer.append(about)

    def _is_daemon_enabled(self) -> bool:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-enabled", "avell-rgb-daemon.service"],
                capture_output=True,
                text=True,
            )
            return r.stdout.strip() == "enabled"
        except FileNotFoundError:
            return False

    def _on_autostart_toggled(self, row, _pspec) -> None:
        action = "enable" if row.get_active() else "disable"
        try:
            subprocess.run(
                ["systemctl", "--user", action, "--now", "avell-rgb-daemon.service"],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass

    def _on_pause_toggled(self, row, _pspec) -> None:
        self.config = load_config()
        self.config = replace(self.config, manual_paused=row.get_active())
        save_config(self.config)

    def _on_open_config(self, _btn) -> None:
        try:
            subprocess.Popen(["xdg-open", str(CONFIG_PATH)])
        except FileNotFoundError:
            pass
```

- [ ] **Step 2: Wire into window + add close handler**

Edit `avell_rgb/gui/window.py`. Replace:
```python
        self.stack.add_titled(_stub_page("Preferências"), "preferences", "Preferências")
```

With:
```python
        from avell_rgb.gui.page_preferences import PreferencesPage

        self.stack.add_titled(PreferencesPage(), "preferences", "Preferências")
```

Add at the bottom of `AvellWindow.__init__`:
```python
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, *_args) -> bool:
        """On window close, clear manual_state unless user opted into 'keep'."""
        from dataclasses import replace

        from avell_rgb.config import load_config, save_config
        from avell_rgb.gui.page_now import _reload_daemon

        cfg = load_config()
        if not cfg.manual_paused and cfg.manual_state is not None:
            cfg = replace(cfg, manual_state=None)
            save_config(cfg)
            _reload_daemon()
        return False  # allow close
```

- [ ] **Step 3: Smoke test**

Launch GUI. Toggle each switch. Close the window — if "Manter estado manual" is off, `manual_state` should be cleared from `config.json`.

- [ ] **Step 4: Commit**

```bash
git add avell_rgb/gui/page_preferences.py avell_rgb/gui/window.py
git commit -m "feat(gui): Preferências page + window close cleans manual_state"
```

---

## Task 15: Packaging — systemd unit, .desktop, install script, icon

**Files:**
- Create: `data/avell-rgb-daemon.service`
- Create: `data/io.github.avellrgb.Avell.desktop`
- Create: `data/io.github.avellrgb.Avell.svg`
- Create: `scripts/install-user.sh`

- [ ] **Step 1: Create `data/avell-rgb-daemon.service`**

```ini
[Unit]
Description=Avell RGB daemon (keyboard + lightbar scheduler)
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/avell-rgb-daemon
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Create `data/io.github.avellrgb.Avell.desktop`**

```
[Desktop Entry]
Type=Application
Name=Avell RGB
Comment=Control keyboard and light bar RGB on Avell laptops
Exec=avell-rgb-gui
Icon=io.github.avellrgb.Avell
Terminal=false
Categories=Utility;GTK;
StartupNotify=true
```

- [ ] **Step 3: Create `data/io.github.avellrgb.Avell.svg`**

A placeholder SVG icon (simple "A" on gradient):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#00FFFF"/>
      <stop offset="50%" stop-color="#9933FF"/>
      <stop offset="100%" stop-color="#FF3366"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="112" height="112" rx="24" fill="url(#g)"/>
  <text x="64" y="90" font-family="Sans" font-size="72" font-weight="bold"
        fill="white" text-anchor="middle">A</text>
</svg>
```

- [ ] **Step 4: Create `scripts/install-user.sh`**

```bash
#!/bin/sh
set -e

cd "$(dirname "$0")/.."

echo "==> Instalando avell-rgb via pipx"
pipx install --force --system-site-packages .

echo "==> Instalando .desktop entry e ícone"
install -Dm644 data/io.github.avellrgb.Avell.desktop \
    "$HOME/.local/share/applications/io.github.avellrgb.Avell.desktop"
install -Dm644 data/io.github.avellrgb.Avell.svg \
    "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.avellrgb.Avell.svg"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "==> Instalando systemd user service"
install -Dm644 data/avell-rgb-daemon.service \
    "$HOME/.config/systemd/user/avell-rgb-daemon.service"
systemctl --user daemon-reload
systemctl --user enable --now avell-rgb-daemon.service

echo
echo "==> Pronto. Abra 'Avell RGB' no menu de aplicações."
echo "==> Daemon status: $(systemctl --user is-active avell-rgb-daemon.service)"
```

Make it executable:
```bash
chmod +x scripts/install-user.sh
```

- [ ] **Step 5: Install and verify**

Run:
```bash
cd ~/src/avell-rgb && ./scripts/install-user.sh
```

Expected output shows pipx install ok, desktop entry installed, systemd service active.

Verify:
```bash
systemctl --user is-active avell-rgb-daemon.service
```

Expected: `active`.

- [ ] **Step 6: Commit**

```bash
git add data/ scripts/install-user.sh
git commit -m "chore: packaging — systemd unit, .desktop, install script"
```

---

## Task 16: End-to-end verification checklist

This task runs the manual verification from the spec (§11.2). No code changes unless a check fails — if it does, stop and fix, then resume.

- [ ] **Step 1: Verify daemon is running**

Run:
```bash
systemctl --user status avell-rgb-daemon.service | head -10
```

Expected: `Active: active (running)`.

- [ ] **Step 2: Check daemon applied default config on first start**

Run:
```bash
journalctl --user -u avell-rgb-daemon.service -n 20 --no-pager
```

Expected: logs show "schedule" resolution or similar; no tracebacks.

- [ ] **Step 3: Open GUI from application menu**

Manual: Super key → search "Avell RGB" → launch.

Expected: window opens on "Agora" page.

- [ ] **Step 4: Live preview test**

In the "Agora" page, move the keyboard color picker to a new color. Watch the physical keyboard.

Expected: keyboard changes color within ~1 second.

- [ ] **Step 5: Create a preset**

Go to Presets → + Novo preset → name it "Teste" → pick a distinct color → Salvar.

Expected: preset appears in the list. `~/.config/avell-rgb/config.json` contains `"teste"`.

- [ ] **Step 6: Add a near-term schedule band**

Go to Agenda → add band `<current_minute+1>:<current_second>` → `<current_minute+3>:00` → preset Teste → Salvar.

Wait 1 minute. Expected: physical keyboard and lightbar switch to the Teste colors automatically.

- [ ] **Step 7: Solar mode test**

Switch mode to "Seguir o sol" → enter your lat/lon → set day color cyan, night color orange.

Expected: hardware applies an interpolated color based on current sun position.

- [ ] **Step 8: GUI close cleanup**

Close the window. Verify `manual_state` in config is either `null` (if "Manter estado manual" is off) or preserved (if on).

- [ ] **Step 9: Restart daemon, state persists**

Run:
```bash
systemctl --user restart avell-rgb-daemon.service
```

Expected: hardware stays on correct colors (daemon re-applies from config).

- [ ] **Step 10: Full test suite still green**

Run:
```bash
cd ~/src/avell-rgb && python -m pytest -v
```

Expected: all 57 tests pass.

- [ ] **Step 11: Final commit marker**

```bash
cd ~/src/avell-rgb
git tag v0.1.0
git log --oneline
```

Expected: linear history of ~15 commits, tagged v0.1.0.

---

## Done criteria

- All 16 tasks completed and committed.
- `systemctl --user is-active avell-rgb-daemon.service` returns `active`.
- GUI opens via application menu and all four pages function.
- `pytest` passes all tests.
- Manual checklist in Task 16 all green.
- `git log` shows linear, descriptive history tagged `v0.1.0`.

---

## Deferred for v0.2 (minor polish items from spec not in v0.1)

These are small convenience features mentioned in the spec but left out of the v0.1 plan to keep tasks focused. All are implementable as additive tasks without touching core logic:

1. **"Salvar como preset..." button on the Agora page** (spec §8.2). Currently preset creation is only via the Presets page ("+ Novo preset"). Adding the shortcut is ~20 lines in `page_now.py` that opens the same modal from `page_presets.py`.

2. **`apply_to` checkboxes on the Agenda solar section** (spec §8.4: "Aplicar a: [x] Teclado [x] Barra"). Currently the config field exists and the daemon respects it, but there's no GUI editor — users must edit `config.json` directly. Adding two `Adw.SwitchRow` widgets is ~15 lines.

3. **"Pausar agendamento" toggle on the Agora header** (spec §8.2). The same functionality exists on the Preferências page as "Manter estado manual ao fechar", but the spec wanted it one click away on Agora too.

4. **Toast feedback** (spec §8.6). No `AdwToast` calls are wired up — saves are silent. ~5 lines per save point.

5. **Effect color combobox on Agora** (spec §8.2). Today `page_now.py` uses a single `Gtk.ColorDialogButton` for both solid and effect modes. The spec called for a dropdown of palette names (`rainbow`, `random`, `red`, ...) when in effect mode. Current behavior works (hex color is passed through) but doesn't expose the palette names.

Any of these can be picked up as mini-tasks after v0.1 ships. None block the v0.1 "done" criteria above.
