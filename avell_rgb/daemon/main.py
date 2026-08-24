"""Daemon: computes desired state and applies via backends."""

import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.typing import Int, Str

from avell_rgb import lightbar_fx
from avell_rgb.config import load_config, save_config
from avell_rgb.solar import hex_to_rgb, interpolate_solar
from avell_rgb.state import Config, kb_to_lb_brightness

# Software animation rate for the lightbar (sysfs writes; keep gentle).
ANIM_TICK_SECONDS = 0.05

log = logging.getLogger("avell_rgb.daemon")


class KeyboardProto(Protocol):
    def available(self) -> bool: ...
    def apply_solid(self, rgb: tuple[int, int, int], brightness: int) -> None: ...
    def apply_effect(
        self, effect: str, color: str, speed: int, brightness: int,
    ) -> None: ...
    def off(self) -> None: ...


class LightbarProto(Protocol):
    def available(self) -> bool: ...
    def apply(self, rgb: tuple[int, int, int], brightness: int) -> None: ...
    def off(self) -> None: ...


class DaemonCore:
    """Pure decision engine. No I/O except injected backends and clock."""

    def __init__(
        self,
        config: Config,
        keyboard: KeyboardProto,
        lightbar: LightbarProto,
        # Aware UTC: astral treats naive datetimes as UTC, which shifts the
        # day/night transition by the local UTC offset.
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        mono: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self.keyboard = keyboard
        self.lightbar = lightbar
        self.clock = clock
        self.mono = mono
        self._anim_start: Optional[float] = None
        self._last_frame: Optional[tuple] = None
        self._kb_available: Optional[bool] = None
        self._lb_available: Optional[bool] = None

    def apply_current(self) -> None:
        mode = self.config.mode
        self._anim_start = None
        self._last_frame = None
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
            lambda: self.keyboard.apply_solid(hex_to_rgb(kb_color), kb_bri)
        )
        self._safe_lb(
            lambda: self.lightbar.apply(hex_to_rgb(lb_color), lb_bri)
        )

    def _apply_effect(self) -> None:
        eff = self.config.effect
        self._safe_kb(
            lambda: self.keyboard.apply_effect(
                effect=eff.name, color=eff.color,
                speed=eff.speed, brightness=eff.brightness,
            )
        )
        self._anim_start = self.mono()
        self.animate_step()

    def animating(self) -> bool:
        return self.config.mode == "effect" and self._anim_start is not None

    def tick_seconds(self) -> Optional[float]:
        return ANIM_TICK_SECONDS if self.animating() else None

    def animate_step(self) -> None:
        """Write the current lightbar animation frame (dedup identical frames)."""
        if not self.animating():
            return
        eff = self.config.effect
        t = self.mono() - self._anim_start
        try:
            rgb, bri = lightbar_fx.frame(
                eff.name, hex_to_rgb(eff.color), eff.speed,
                kb_to_lb_brightness(eff.brightness), t,
            )
        except Exception:
            log.exception("animation frame failed; disabling animation")
            self._anim_start = None
            return
        new_frame = (rgb, bri)
        if new_frame == self._last_frame:
            return
        self._last_frame = new_frame
        self._safe_lb(lambda: self.lightbar.apply(rgb, bri))

    def _apply_solar(self) -> None:
        color, kb_bri, lb_bri = interpolate_solar(self.config.solar, self.clock())
        self._safe_kb(
            lambda: self.keyboard.apply_solid(hex_to_rgb(color), kb_bri)
        )
        self._safe_lb(
            lambda: self.lightbar.apply(hex_to_rgb(color), lb_bri)
        )

    def sleep_seconds(self) -> float:
        if self.config.mode == "solar":
            return 60.0
        return math.inf

    def _safe_kb(self, fn) -> None:
        avail = self.keyboard.available()
        prev = self._kb_available
        self._kb_available = avail
        if not avail:
            if prev is not False:
                log.warning("keyboard backend unavailable")
            return
        if prev is False:
            log.info("keyboard backend available again")
        try:
            fn()
        except Exception:
            log.exception("keyboard backend error")

    def _safe_lb(self, fn) -> None:
        avail = self.lightbar.available()
        prev = self._lb_available
        self._lb_available = avail
        if not avail:
            if prev is not False:
                log.warning("lightbar backend unavailable")
            return
        if prev is False:
            log.info("lightbar backend available again")
        try:
            fn()
        except Exception:
            log.exception("lightbar backend error")


@dbus_interface("io.github.avellrgb.Daemon")
class DBusAdapter(object):
    """Exports the daemon API on D-Bus; delegates to a DaemonDBusAPI."""

    def __init__(self, api):
        self._api = api

    @dbus_signal
    def StateChanged(self, mode: Str, color: Str, brightness: Int):
        """Notification that state changed; receivers should call GetState."""

    def SetMode(self, mode: str):
        self._api.SetMode(mode)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def SetColor(self, hex_color: str, brightness: int):
        self._api.SetColor(hex_color, brightness)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def SetDeviceColor(self, device: str, hex_color: str, brightness: int):
        self._api.SetDeviceColor(device, hex_color, brightness)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def SetEffect(self, name: str, color: str, speed: int, brightness: int):
        self._api.SetEffect(name, color, speed, brightness)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def SetSolar(self, lat: float, lon: float, day_color: str, night_color: str, day_bri: int, night_bri: int):
        self._api.SetSolar(lat, lon, day_color, night_color, day_bri, night_bri)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def ApplyPreset(self, name: str):
        self._api.ApplyPreset(name)
        c = self._api.config
        self.StateChanged.emit(c.mode, c.color, c.brightness)

    def SavePreset(self, name: str):
        self._api.SavePreset(name)

    def DeletePreset(self, name: str):
        self._api.DeletePreset(name)

    def GetState(self) -> str:
        return json.dumps(self._api.GetState())

    def ListPresets(self) -> str:
        return json.dumps(self._api.ListPresets())


def main() -> int:
    """Entry point. Wires real backends, D-Bus, and asyncio loop."""
    import asyncio
    import signal as sig

    from avell_rgb.backends.keyboard import KeyboardBackend
    from avell_rgb.backends.lightbar import LightbarBackend
    from avell_rgb.daemon.dbus_api import DaemonDBusAPI

    from dasbus.connection import SessionMessageBus

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    config = load_config()
    wakeup = asyncio.Event()

    def persist(cfg: Config) -> None:
        save_config(cfg)

    api = DaemonDBusAPI(config, persist, wakeup)

    bus = SessionMessageBus()
    adapter = DBusAdapter(api)

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
            try:
                core.apply_current()
            except Exception:
                log.exception("apply_current failed")
            else:
                log.info("applied mode=%s color=%s bri=%d",
                         core.config.mode, core.config.color, core.config.brightness)

            delay = core.sleep_seconds()
            wakeup.clear()
            aloop = asyncio.get_event_loop()
            deadline = None if math.isinf(delay) else aloop.time() + delay

            while not wakeup.is_set():
                if deadline is not None and aloop.time() >= deadline:
                    break
                pump_glib()
                core.animate_step()
                interval = core.tick_seconds() or 0.1
                if deadline is not None:
                    interval = min(interval, max(0.01, deadline - aloop.time()))
                await asyncio.sleep(interval)

    try:
        asyncio.run(run())
    except SystemExit:
        pass
    finally:
        bus.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
