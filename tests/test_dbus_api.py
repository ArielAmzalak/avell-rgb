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


def test_set_mode():
    cfg = _cfg()
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    api.SetMode("solar")
    assert api.config.mode == "solar"
    assert writer.saved is not None
    assert writer.saved.mode == "solar"
    assert event.is_set()


def test_set_color():
    cfg = _cfg(independent_colors=True)
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    api.SetColor("#FF0000", 25)
    assert api.config.color == "#FF0000"
    assert api.config.brightness == 25
    assert api.config.mode == "fixed"
    assert api.config.independent_colors is False


def test_set_effect():
    cfg = _cfg()
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    api.SetEffect("wave", "#00FF00", 8)
    assert api.config.mode == "effect"
    assert api.config.effect.name == "wave"
    assert api.config.effect.color == "#00FF00"
    assert api.config.effect.speed == 8


def test_apply_preset():
    cfg = _cfg(presets={"night": Preset(color="#FF3300", brightness=10)})
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    api.ApplyPreset("night")
    assert api.config.mode == "fixed"
    assert api.config.color == "#FF3300"
    assert api.config.brightness == 10


def test_apply_preset_unknown_raises():
    cfg = _cfg()
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    with pytest.raises(KeyError):
        api.ApplyPreset("nonexistent")


def test_get_state():
    cfg = _cfg(mode="effect", effect=EffectConfig("wave", "#FF0000", 3))
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    mode, color, effect_name, brightness, solar = api.GetState()
    assert mode == "effect"
    assert color == "#00FFFF"
    assert effect_name == "wave"
    assert brightness == 30


def test_list_presets():
    cfg = _cfg(presets={
        "work": Preset(color="#00FFFF", brightness=30),
        "night": Preset(color="#FF3300", brightness=10),
    })
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    result = api.ListPresets()
    names = [r[0] for r in result]
    assert "work" in names
    assert "night" in names


def test_set_solar():
    cfg = _cfg()
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
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


def test_get_state_includes_solar():
    solar = SolarConfig(-23.55, -46.63, "#8FF0A4", "#FF7800", 50, 20)
    cfg = _cfg(solar=solar)
    writer = FakeConfigWriter()
    event = asyncio.Event()
    api = DaemonDBusAPI(cfg, writer, event)
    result = api.GetState()
    assert len(result) == 5
    mode, color, effect_name, brightness, solar_dict = result
    assert solar_dict["latitude"] == -23.55
    assert solar_dict["day_color"] == "#8FF0A4"
