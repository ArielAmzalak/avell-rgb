"""Daemon: computes desired state and applies via backends."""

from __future__ import annotations

import logging
import math
import sys
from datetime import datetime
from typing import Callable, Optional, Protocol

from avell_rgb.config import load_config, save_config
from avell_rgb.solar import interpolate_solar
from avell_rgb.state import Config

log = logging.getLogger("avell_rgb.daemon")


class KeyboardProto(Protocol):
    def available(self) -> bool: ...
    def apply_solid(self, rgb: tuple[int, int, int], brightness: int) -> None: ...
    def apply_effect(
        self, effect: str, color: str, speed: int,
        direction: Optional[str], brightness: int,
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
    """Pure decision engine. No I/O except injected backends and clock."""

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

    def apply_current(self) -> None:
        mode = self.config.mode
        if mode == "off":
            self._safe_kb(lambda: self.keyboard.off())
            self._safe_lb(lambda: self.lightbar.off())
        elif mode == "solar":
            self._apply_solar()
        elif mode == "effect":
            self._apply_effect()
        else:  # fixed
            self._apply_fixed()

    def _apply_fixed(self) -> None:
        kb_color, kb_bri, lb_color, lb_bri = self.config.resolved_colors()
        self._safe_kb(
            lambda: self.keyboard.apply_solid(_hex_to_rgb(kb_color), kb_bri)
        )
        self._safe_lb(
            lambda: self.lightbar.apply(_hex_to_rgb(lb_color), lb_bri)
        )

    def _apply_effect(self) -> None:
        eff = self.config.effect
        self._safe_kb(
            lambda: self.keyboard.apply_effect(
                effect=eff.name, color=eff.color,
                speed=eff.speed, direction=None, brightness=self.config.brightness,
            )
        )
        self._safe_lb(
            lambda: self.lightbar.apply(
                _hex_to_rgb(eff.color), min(100, self.config.brightness * 2)
            )
        )

    def _apply_solar(self) -> None:
        color, kb_bri, lb_bri = interpolate_solar(self.config.solar, self.clock())
        self._safe_kb(
            lambda: self.keyboard.apply_solid(_hex_to_rgb(color), kb_bri)
        )
        self._safe_lb(
            lambda: self.lightbar.apply(_hex_to_rgb(color), lb_bri)
        )

    def sleep_seconds(self) -> float:
        if self.config.mode == "solar":
            return 60.0
        return math.inf

    def _safe_kb(self, fn) -> None:
        if not self.keyboard.available():
            log.debug("keyboard backend unavailable")
            return
        try:
            fn()
        except Exception:
            log.exception("keyboard backend error")

    def _safe_lb(self, fn) -> None:
        if not self.lightbar.available():
            log.debug("lightbar backend unavailable")
            return
        try:
            fn()
        except Exception:
            log.exception("lightbar backend error")


def main() -> int:
    """Entry point — will be rewritten with D-Bus in Task 6."""
    log.error("daemon v2 D-Bus loop not yet implemented")
    return 1


if __name__ == "__main__":
    sys.exit(main())
