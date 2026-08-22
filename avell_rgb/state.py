"""Immutable dataclasses for Config v2, with JSON round-trip."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VALID_MODES = ("fixed", "solar", "effect", "off")
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
class Preset:
    color: str
    brightness: int
    independent: bool = False
    keyboard_color: str = ""
    keyboard_brightness: int = 0
    lightbar_color: str = ""
    lightbar_brightness: int = 0

    def to_dict(self) -> dict:
        d = {"color": self.color, "brightness": self.brightness}
        if self.independent:
            d.update(
                independent=True,
                keyboard_color=self.keyboard_color,
                keyboard_brightness=self.keyboard_brightness,
                lightbar_color=self.lightbar_color,
                lightbar_brightness=self.lightbar_brightness,
            )
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Preset":
        return cls(
            color=d["color"],
            brightness=int(d["brightness"]),
            independent=bool(d.get("independent", False)),
            keyboard_color=d.get("keyboard_color", ""),
            keyboard_brightness=int(d.get("keyboard_brightness", 0)),
            lightbar_color=d.get("lightbar_color", ""),
            lightbar_brightness=int(d.get("lightbar_brightness", 0)),
        )


@dataclass(frozen=True)
class EffectConfig:
    name: str
    color: str
    speed: int
    brightness: int = 25

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": self.color,
            "speed": self.speed,
            "brightness": self.brightness,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EffectConfig":
        return cls(
            name=d["name"],
            color=d["color"],
            speed=int(d["speed"]),
            brightness=int(d.get("brightness", 25)),
        )


@dataclass(frozen=True)
class SolarConfig:
    latitude: float
    longitude: float
    day_color: str
    night_color: str
    day_brightness: int
    night_brightness: int

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "day_color": self.day_color,
            "night_color": self.night_color,
            "day_brightness": self.day_brightness,
            "night_brightness": self.night_brightness,
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
        )


@dataclass(frozen=True)
class Config:
    version: int
    mode: str
    color: str
    brightness: int
    independent_colors: bool
    keyboard_color: str
    keyboard_brightness: int
    lightbar_color: str
    lightbar_brightness: int
    effect: EffectConfig
    solar: SolarConfig
    presets: dict[str, Preset]

    def resolved_colors(self) -> tuple[str, int, str, int]:
        if self.independent_colors:
            return (
                self.keyboard_color,
                self.keyboard_brightness,
                self.lightbar_color,
                self.lightbar_brightness,
            )
        return (
            self.color,
            self.brightness,
            self.color,
            min(100, self.brightness * 2),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "mode": self.mode,
            "color": self.color,
            "brightness": self.brightness,
            "independent_colors": self.independent_colors,
            "keyboard_color": self.keyboard_color,
            "keyboard_brightness": self.keyboard_brightness,
            "lightbar_color": self.lightbar_color,
            "lightbar_brightness": self.lightbar_brightness,
            "effect": self.effect.to_dict(),
            "solar": self.solar.to_dict(),
            "presets": {k: v.to_dict() for k, v in self.presets.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        mode = d["mode"]
        if mode not in VALID_MODES:
            raise ValueError(f"invalid mode: {mode!r}")
        return cls(
            version=int(d["version"]),
            mode=mode,
            color=d["color"],
            brightness=int(d["brightness"]),
            independent_colors=bool(d["independent_colors"]),
            keyboard_color=d["keyboard_color"],
            keyboard_brightness=int(d["keyboard_brightness"]),
            lightbar_color=d["lightbar_color"],
            lightbar_brightness=int(d["lightbar_brightness"]),
            effect=EffectConfig.from_dict(d["effect"]),
            solar=SolarConfig.from_dict(d["solar"]),
            presets={k: Preset.from_dict(v) for k, v in d["presets"].items()},
        )
