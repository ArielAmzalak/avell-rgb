"""D-Bus interface for the daemon. Methods modify config and wake the loop."""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from typing import Callable

from avell_rgb.state import (
    VALID_EFFECTS,
    VALID_MODES,
    Config,
    EffectConfig,
    Preset,
    SolarConfig,
)

VALID_DEVICES = ("keyboard", "lightbar")

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex(s: str) -> None:
    if not _HEX_RE.fullmatch(s):
        raise ValueError(f"invalid color: {s!r} (expected #RRGGBB)")


def _validate_range(what: str, value: float, lo: float, hi: float) -> None:
    if not lo <= value <= hi:
        raise ValueError(f"{what} must be between {lo} and {hi}, got {value}")


class DaemonDBusAPI:
    def __init__(
        self,
        config: Config,
        config_writer: Callable[[Config], None],
        wakeup_event: asyncio.Event,
    ):
        self.config = config
        self._write = config_writer
        self._wakeup = wakeup_event

    def _update(self, **kwargs) -> None:
        self.config = replace(self.config, **kwargs)
        self._write(self.config)
        self._wakeup.set()

    def SetMode(self, mode: str) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"invalid mode: {mode!r}")
        self._update(mode=mode)

    def SetColor(self, hex_color: str, brightness: int) -> None:
        _validate_hex(hex_color)
        _validate_range("brightness", brightness, 0, 50)
        self._update(
            mode="fixed",
            color=hex_color,
            brightness=brightness,
            independent_colors=False,
        )

    def SetDeviceColor(self, device: str, hex_color: str, brightness: int) -> None:
        if device not in VALID_DEVICES:
            raise ValueError(f"invalid device: {device!r}")
        _validate_hex(hex_color)
        _validate_range("brightness", brightness, 0, 50 if device == "keyboard" else 100)
        fields = {
            f"{device}_color": hex_color,
            f"{device}_brightness": brightness,
        }
        self._update(mode="fixed", independent_colors=True, **fields)

    def SetEffect(self, name: str, color: str, speed: int, brightness: int) -> None:
        if name not in VALID_EFFECTS:
            raise ValueError(f"invalid effect: {name!r}")
        _validate_hex(color)
        _validate_range("speed", speed, 0, 10)
        _validate_range("brightness", brightness, 0, 50)
        self._update(
            mode="effect",
            effect=EffectConfig(name=name, color=color, speed=speed, brightness=brightness),
        )

    def SetSolar(self, lat: float, lon: float, day_color: str, night_color: str, day_bri: int, night_bri: int) -> None:
        _validate_hex(day_color)
        _validate_hex(night_color)
        _validate_range("latitude", lat, -90, 90)
        _validate_range("longitude", lon, -180, 180)
        _validate_range("day brightness", day_bri, 0, 50)
        _validate_range("night brightness", night_bri, 0, 50)
        self._update(
            mode="solar",
            solar=SolarConfig(
                latitude=lat, longitude=lon,
                day_color=day_color, night_color=night_color,
                day_brightness=day_bri, night_brightness=night_bri,
            ),
        )

    def ApplyPreset(self, name: str) -> None:
        if name not in self.config.presets:
            raise ValueError(f"unknown preset: {name!r}")
        preset = self.config.presets[name]
        if preset.independent:
            self._update(
                mode="fixed",
                independent_colors=True,
                keyboard_color=preset.keyboard_color,
                keyboard_brightness=preset.keyboard_brightness,
                lightbar_color=preset.lightbar_color,
                lightbar_brightness=preset.lightbar_brightness,
            )
        else:
            self._update(
                mode="fixed",
                independent_colors=False,
                color=preset.color,
                brightness=preset.brightness,
            )

    def SavePreset(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("preset name must not be empty")
        c = self.config
        if c.independent_colors:
            preset = Preset(
                color=c.keyboard_color,
                brightness=c.keyboard_brightness,
                independent=True,
                keyboard_color=c.keyboard_color,
                keyboard_brightness=c.keyboard_brightness,
                lightbar_color=c.lightbar_color,
                lightbar_brightness=c.lightbar_brightness,
            )
        else:
            preset = Preset(color=c.color, brightness=c.brightness)
        presets = dict(c.presets)
        presets[name] = preset
        self._update(presets=presets)

    def DeletePreset(self, name: str) -> None:
        if name not in self.config.presets:
            return
        presets = dict(self.config.presets)
        del presets[name]
        self._update(presets=presets)

    def GetState(self) -> dict:
        c = self.config
        return {
            "mode": c.mode,
            "color": c.color,
            "brightness": c.brightness,
            "independent_colors": c.independent_colors,
            "keyboard_color": c.keyboard_color,
            "keyboard_brightness": c.keyboard_brightness,
            "lightbar_color": c.lightbar_color,
            "lightbar_brightness": c.lightbar_brightness,
            "effect": c.effect.to_dict(),
            "solar": c.solar.to_dict(),
        }

    def ListPresets(self) -> list[dict]:
        return [
            {"name": name, **p.to_dict()}
            for name, p in self.config.presets.items()
        ]
