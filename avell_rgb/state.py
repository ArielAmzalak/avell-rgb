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
