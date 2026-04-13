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
    """Entry point. Wires real backends, D-Bus, and asyncio loop."""
    import asyncio
    import signal as sig

    from avell_rgb.backends.keyboard import KeyboardBackend
    from avell_rgb.backends.lightbar import LightbarBackend
    from avell_rgb.daemon.dbus_api import DaemonDBusAPI

    from dasbus.connection import SessionMessageBus
    from dasbus.server.interface import dbus_interface
    from dasbus.typing import Str, Int32
    from dasbus.signal import Signal

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    config = load_config()
    wakeup = asyncio.Event()

    def persist(cfg: Config) -> None:
        save_config(cfg)

    api = DaemonDBusAPI(config, persist, wakeup)

    @dbus_interface("io.github.avellrgb.Daemon")
    class DBusAdapter(object):
        def __init__(self):
            self.StateChanged = Signal()

        def SetMode(self, mode: Str):
            api.SetMode(mode)
            c = api.config
            self.StateChanged.emit(c.mode, c.color, c.brightness)

        def SetColor(self, hex_color: Str, brightness: Int32):
            api.SetColor(hex_color, brightness)
            c = api.config
            self.StateChanged.emit(c.mode, c.color, c.brightness)

        def SetEffect(self, name: Str, color: Str, speed: Int32):
            api.SetEffect(name, color, speed)
            c = api.config
            self.StateChanged.emit(c.mode, c.color, c.brightness)

        def ApplyPreset(self, name: Str):
            api.ApplyPreset(name)
            c = api.config
            self.StateChanged.emit(c.mode, c.color, c.brightness)

        def GetState(self) -> Str:
            import json
            m, c, e, b = api.GetState()
            return json.dumps({"mode": m, "color": c, "effect": e, "brightness": b})

        def ListPresets(self) -> Str:
            import json
            return json.dumps([
                {"name": n, "color": c, "brightness": b}
                for n, c, b in api.ListPresets()
            ])

    bus = SessionMessageBus()
    adapter = DBusAdapter()

    bus.publish_object("/io/github/avellrgb/Daemon", adapter)
    bus.register_service("io.github.avellrgb.Daemon")
    log.info("D-Bus service registered: io.github.avellrgb.Daemon")

    core = DaemonCore(
        config=config,
        keyboard=KeyboardBackend(),
        lightbar=LightbarBackend(),
    )

    async def run():
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(sig.SIGTERM, lambda: sys.exit(0))
        loop.add_signal_handler(sig.SIGINT, lambda: sys.exit(0))

        from gi.repository import GLib
        glib_ctx = GLib.MainContext.default()

        def pump_glib():
            while glib_ctx.pending():
                glib_ctx.iteration(False)

        while True:
            core.config = api.config
            core.apply_current()
            log.info("applied mode=%s color=%s bri=%d",
                     core.config.mode, core.config.color, core.config.brightness)

            delay = core.sleep_seconds()
            wakeup.clear()

            if math.isinf(delay):
                while not wakeup.is_set():
                    pump_glib()
                    await asyncio.sleep(0.1)
            else:
                deadline = asyncio.get_event_loop().time() + delay
                while not wakeup.is_set():
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    pump_glib()
                    await asyncio.sleep(min(0.1, remaining))

    try:
        asyncio.run(run())
    except SystemExit:
        pass
    finally:
        bus.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
