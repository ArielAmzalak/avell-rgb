"""D-Bus interface for the daemon. Methods modify config and wake the loop."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Callable

from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig

VALID_DEVICES = ("keyboard", "lightbar")


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
        self._update(mode=mode)

    def SetColor(self, hex_color: str, brightness: int) -> None:
        self._update(
            mode="fixed",
            color=hex_color,
            brightness=brightness,
            independent_colors=False,
        )

    def SetDeviceColor(self, device: str, hex_color: str, brightness: int) -> None:
        if device not in VALID_DEVICES:
            raise ValueError(f"invalid device: {device!r}")
        fields = {
            f"{device}_color": hex_color,
            f"{device}_brightness": brightness,
        }
        self._update(mode="fixed", independent_colors=True, **fields)

    def SetEffect(self, name: str, color: str, speed: int, brightness: int) -> None:
        self._update(
            mode="effect",
            effect=EffectConfig(name=name, color=color, speed=speed, brightness=brightness),
        )

    def SetSolar(self, lat: float, lon: float, day_color: str, night_color: str, day_bri: int, night_bri: int) -> None:
        self._update(
            mode="solar",
            solar=SolarConfig(
                latitude=lat, longitude=lon,
                day_color=day_color, night_color=night_color,
                day_brightness=day_bri, night_brightness=night_bri,
            ),
        )

    def ApplyPreset(self, name: str) -> None:
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
