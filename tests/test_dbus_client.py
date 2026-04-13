"""Test the D-Bus client wrapper with a mock proxy."""
import json
from unittest.mock import MagicMock

import pytest

from avell_rgb.dbus_client import DaemonClient


class FakeProxy:
    def __init__(self):
        self.calls = []

    def SetMode(self, mode):
        self.calls.append(("SetMode", mode))

    def SetColor(self, hex_color, brightness):
        self.calls.append(("SetColor", hex_color, brightness))

    def SetEffect(self, name, color, speed):
        self.calls.append(("SetEffect", name, color, speed))

    def ApplyPreset(self, name):
        self.calls.append(("ApplyPreset", name))

    def GetState(self):
        return json.dumps({"mode": "fixed", "color": "#00FFFF", "effect": "breathing", "brightness": 30})

    def ListPresets(self):
        return json.dumps([
            {"name": "work", "color": "#00FFFF", "brightness": 30},
            {"name": "night", "color": "#FF3300", "brightness": 10},
        ])


def test_client_set_mode():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_mode("solar")
    assert proxy.calls[-1] == ("SetMode", "solar")


def test_client_set_color():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_color("#FF0000", 25)
    assert proxy.calls[-1] == ("SetColor", "#FF0000", 25)


def test_client_set_effect():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_effect("wave", "#00FF00", 8)
    assert proxy.calls[-1] == ("SetEffect", "wave", "#00FF00", 8)


def test_client_apply_preset():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.apply_preset("night")
    assert proxy.calls[-1] == ("ApplyPreset", "night")


def test_client_get_state():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    state = client.get_state()
    assert state["mode"] == "fixed"
    assert state["color"] == "#00FFFF"
    assert state["effect"] == "breathing"
    assert state["brightness"] == 30


def test_client_list_presets():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    presets = client.list_presets()
    assert len(presets) == 2
    assert presets[0]["name"] == "work"
    assert presets[1]["name"] == "night"


def test_client_is_available():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    assert client.is_available() is True


def test_client_is_available_when_daemon_down():
    proxy = MagicMock()
    proxy.GetState.side_effect = Exception("daemon not running")
    client = DaemonClient(proxy=proxy)
    assert client.is_available() is False
