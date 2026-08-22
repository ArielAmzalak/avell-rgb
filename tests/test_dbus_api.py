"""Test the D-Bus interface logic without a real bus."""
from dataclasses import replace
import asyncio

import pytest

from avell_rgb.daemon.dbus_api import DaemonDBusAPI
from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig


def _cfg(**overrides) -> Config:
    defaults = dict(
        version=2, mode="fixed", color="#00FFFF", brightness=30,
        independent_colors=False,
        keyboard_color="#00FFFF", keyboard_brightness=30,
        lightbar_color="#00FFFF", lightbar_brightness=80,
        effect=EffectConfig(name="breathing", color="#00FFFF", speed=5),
        solar=SolarConfig(-23.55, -46.63, "#8FF0A4", "#FF7800", 50, 20),
        presets={"work": Preset(color="#00FFFF", brightness=30)},
    )
    defaults.update(overrides)
    return Config(**defaults)


class FakeConfigWriter:
    def __init__(self):
        self.saved: Config | None = None

    def __call__(self, cfg):
        self.saved = cfg


def _api(cfg=None):
    cfg = cfg or _cfg()
    writer = FakeConfigWriter()
    event = asyncio.Event()
    return DaemonDBusAPI(cfg, writer, event), writer, event


def test_set_mode():
    api, writer, event = _api()
    api.SetMode("solar")
    assert api.config.mode == "solar"
    assert writer.saved is not None
    assert writer.saved.mode == "solar"
    assert event.is_set()


def test_set_color():
    api, writer, event = _api(_cfg(independent_colors=True))
    api.SetColor("#FF0000", 25)
    assert api.config.color == "#FF0000"
    assert api.config.brightness == 25
    assert api.config.mode == "fixed"
    assert api.config.independent_colors is False


def test_set_device_color_keyboard():
    api, writer, event = _api()
    api.SetDeviceColor("keyboard", "#FF0000", 40)
    assert api.config.independent_colors is True
    assert api.config.mode == "fixed"
    assert api.config.keyboard_color == "#FF0000"
    assert api.config.keyboard_brightness == 40
    assert api.config.lightbar_color == "#00FFFF"
    assert writer.saved is not None
    assert event.is_set()


def test_set_device_color_lightbar():
    api, _, _ = _api()
    api.SetDeviceColor("lightbar", "#00FF00", 90)
    assert api.config.independent_colors is True
    assert api.config.lightbar_color == "#00FF00"
    assert api.config.lightbar_brightness == 90
    assert api.config.keyboard_color == "#00FFFF"


def test_set_device_color_invalid_device():
    api, _, _ = _api()
    with pytest.raises(ValueError):
        api.SetDeviceColor("mouse", "#FF0000", 30)


def test_set_effect():
    api, _, _ = _api()
    api.SetEffect("wave", "#00FF00", 8, 42)
    assert api.config.mode == "effect"
    assert api.config.effect.name == "wave"
    assert api.config.effect.color == "#00FF00"
    assert api.config.effect.speed == 8
    assert api.config.effect.brightness == 42


def test_apply_preset():
    api, _, _ = _api(_cfg(presets={"night": Preset(color="#FF3300", brightness=10)}))
    api.ApplyPreset("night")
    assert api.config.mode == "fixed"
    assert api.config.color == "#FF3300"
    assert api.config.brightness == 10
    assert api.config.independent_colors is False


def test_apply_preset_independent():
    preset = Preset(
        color="#FF0000", brightness=30, independent=True,
        keyboard_color="#FF0000", keyboard_brightness=30,
        lightbar_color="#0000FF", lightbar_brightness=70,
    )
    api, _, _ = _api(_cfg(presets={"duo": preset}))
    api.ApplyPreset("duo")
    assert api.config.mode == "fixed"
    assert api.config.independent_colors is True
    assert api.config.keyboard_color == "#FF0000"
    assert api.config.keyboard_brightness == 30
    assert api.config.lightbar_color == "#0000FF"
    assert api.config.lightbar_brightness == 70


def test_apply_preset_unknown_raises():
    api, _, _ = _api()
    with pytest.raises(KeyError):
        api.ApplyPreset("nonexistent")


def test_save_preset_synced():
    api, writer, _ = _api(_cfg(color="#123456", brightness=22))
    api.SavePreset("meu")
    p = api.config.presets["meu"]
    assert p.color == "#123456"
    assert p.brightness == 22
    assert p.independent is False
    assert writer.saved is not None


def test_save_preset_independent():
    cfg = _cfg(
        independent_colors=True,
        keyboard_color="#111111", keyboard_brightness=11,
        lightbar_color="#222222", lightbar_brightness=44,
    )
    api, _, _ = _api(cfg)
    api.SavePreset("duo")
    p = api.config.presets["duo"]
    assert p.independent is True
    assert p.keyboard_color == "#111111"
    assert p.keyboard_brightness == 11
    assert p.lightbar_color == "#222222"
    assert p.lightbar_brightness == 44


def test_save_preset_empty_name_raises():
    api, _, _ = _api()
    with pytest.raises(ValueError):
        api.SavePreset("   ")


def test_delete_preset():
    api, writer, _ = _api()
    api.DeletePreset("work")
    assert "work" not in api.config.presets
    assert writer.saved is not None


def test_delete_preset_missing_is_noop():
    api, writer, _ = _api()
    api.DeletePreset("nonexistent")
    assert writer.saved is None


def test_get_state():
    api, _, _ = _api(_cfg(mode="effect", effect=EffectConfig("wave", "#FF0000", 3, 25)))
    state = api.GetState()
    assert state["mode"] == "effect"
    assert state["color"] == "#00FFFF"
    assert state["brightness"] == 30
    assert state["effect"]["name"] == "wave"
    assert state["effect"]["color"] == "#FF0000"
    assert state["effect"]["speed"] == 3
    assert state["effect"]["brightness"] == 25
    assert state["independent_colors"] is False
    assert state["keyboard_color"] == "#00FFFF"
    assert state["lightbar_brightness"] == 80


def test_get_state_includes_solar():
    solar = SolarConfig(-23.55, -46.63, "#8FF0A4", "#FF7800", 50, 20)
    api, _, _ = _api(_cfg(solar=solar))
    state = api.GetState()
    assert state["solar"]["latitude"] == -23.55
    assert state["solar"]["day_color"] == "#8FF0A4"


def test_list_presets():
    api, _, _ = _api(_cfg(presets={
        "work": Preset(color="#00FFFF", brightness=30),
        "night": Preset(color="#FF3300", brightness=10),
    }))
    result = api.ListPresets()
    names = [r["name"] for r in result]
    assert "work" in names
    assert "night" in names
    assert result[0]["color"] == "#00FFFF"


def test_set_solar():
    api, writer, event = _api()
    api.SetSolar(-22.9, -43.2, "#FFFFFF", "#FF0000", 50, 10)
    assert api.config.mode == "solar"
    assert api.config.solar.latitude == -22.9
    assert api.config.solar.longitude == -43.2
    assert api.config.solar.day_color == "#FFFFFF"
    assert api.config.solar.night_color == "#FF0000"
    assert api.config.solar.day_brightness == 50
    assert api.config.solar.night_brightness == 10
    assert writer.saved is not None
    assert event.is_set()
