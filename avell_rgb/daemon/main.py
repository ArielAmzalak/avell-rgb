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
