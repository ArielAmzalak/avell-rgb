"""D-Bus interface for the daemon. Methods modify config and wake the loop."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Callable

from avell_rgb.state import Config, EffectConfig, SolarConfig


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

    def SetEffect(self, name: str, color: str, speed: int) -> None:
        self._update(
            mode="effect",
            effect=EffectConfig(name=name, color=color, speed=speed),
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
        self._update(
            mode="fixed",
            color=preset.color,
            brightness=preset.brightness,
        )

    def GetState(self) -> tuple:
        return (
            self.config.mode,
            self.config.color,
            self.config.effect.name,
            self.config.brightness,
            self.config.solar.to_dict(),
        )

    def ListPresets(self) -> list[tuple[str, str, int]]:
        return [
            (name, p.color, p.brightness)
            for name, p in self.config.presets.items()
        ]
