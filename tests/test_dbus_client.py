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

    def SetDeviceColor(self, device, hex_color, brightness):
        self.calls.append(("SetDeviceColor", device, hex_color, brightness))

    def SetEffect(self, name, color, speed, brightness):
        self.calls.append(("SetEffect", name, color, speed, brightness))

    def SetSolar(self, lat, lon, day_color, night_color, day_bri, night_bri):
        self.calls.append(("SetSolar", lat, lon, day_color, night_color, day_bri, night_bri))

    def ApplyPreset(self, name):
        self.calls.append(("ApplyPreset", name))

    def SavePreset(self, name):
        self.calls.append(("SavePreset", name))

    def DeletePreset(self, name):
        self.calls.append(("DeletePreset", name))

    def GetState(self):
        return json.dumps({
            "mode": "fixed", "color": "#00FFFF", "brightness": 30,
            "independent_colors": False,
            "keyboard_color": "#00FFFF", "keyboard_brightness": 30,
            "lightbar_color": "#00FFFF", "lightbar_brightness": 80,
            "effect": {"name": "breathing", "color": "#00FFFF", "speed": 5, "brightness": 25},
            "solar": {
                "latitude": -23.55, "longitude": -46.63,
                "day_color": "#8FF0A4", "night_color": "#FF7800",
                "day_brightness": 50, "night_brightness": 20,
            },
        })

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


def test_client_set_device_color():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_device_color("lightbar", "#FF00FF", 66)
    assert proxy.calls[-1] == ("SetDeviceColor", "lightbar", "#FF00FF", 66)


def test_client_set_effect():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_effect("wave", "#00FF00", 8, 42)
    assert proxy.calls[-1] == ("SetEffect", "wave", "#00FF00", 8, 42)


def test_client_apply_preset():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.apply_preset("night")
    assert proxy.calls[-1] == ("ApplyPreset", "night")


def test_client_save_preset():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.save_preset("gamer")
    assert proxy.calls[-1] == ("SavePreset", "gamer")


def test_client_delete_preset():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.delete_preset("gamer")
    assert proxy.calls[-1] == ("DeletePreset", "gamer")


def test_client_get_state():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    state = client.get_state()
    assert state["mode"] == "fixed"
    assert state["color"] == "#00FFFF"
    assert state["brightness"] == 30
    assert state["independent_colors"] is False
    assert state["keyboard_color"] == "#00FFFF"
    assert state["lightbar_brightness"] == 80
    assert state["effect"]["name"] == "breathing"
    assert state["effect"]["brightness"] == 25


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


def test_client_set_solar():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    client.set_solar(-22.9, -43.2, "#FFFFFF", "#FF0000", 50, 10)
    assert proxy.calls[-1] == ("SetSolar", -22.9, -43.2, "#FFFFFF", "#FF0000", 50, 10)


def test_client_get_state_includes_solar():
    proxy = FakeProxy()
    client = DaemonClient(proxy=proxy)
    state = client.get_state()
    assert "solar" in state
    assert state["solar"]["latitude"] == -23.55
