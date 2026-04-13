"""D-Bus client for communicating with the daemon."""

from __future__ import annotations

import json


class DaemonClient:
    """Wraps the D-Bus proxy to the daemon. Accepts injected proxy for testing."""

    def __init__(self, proxy=None):
        if proxy is None:
            from dasbus.connection import SessionMessageBus
            bus = SessionMessageBus()
            proxy = bus.get_proxy(
                "io.github.avellrgb.Daemon",
                "/io/github/avellrgb/Daemon",
            )
        self._proxy = proxy

    def set_mode(self, mode: str) -> None:
        self._proxy.SetMode(mode)

    def set_color(self, hex_color: str, brightness: int) -> None:
        self._proxy.SetColor(hex_color, brightness)

    def set_effect(self, name: str, color: str, speed: int) -> None:
        self._proxy.SetEffect(name, color, speed)

    def apply_preset(self, name: str) -> None:
        self._proxy.ApplyPreset(name)

    def get_state(self) -> dict:
        result = self._proxy.GetState()
        return json.loads(result)

    def list_presets(self) -> list[dict]:
        result = self._proxy.ListPresets()
        return json.loads(result)

    def is_available(self) -> bool:
        try:
            self._proxy.GetState()
            return True
        except Exception:
            return False
