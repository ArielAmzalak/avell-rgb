"""Test the D-Bus adapter: exported signal, emitted payloads, resilience."""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from avell_rgb.daemon.dbus_api import DaemonDBusAPI
from avell_rgb.daemon.main import DaemonCore, DBusAdapter
from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig
from tests.conftest import FakeKeyboardBackend, FakeLightbarBackend


def _cfg(**overrides) -> Config:
    # keyboard_* deliberately differs from color/brightness so a payload
    # built from the wrong fields cannot pass by coincidence.
    defaults = dict(
        version=2, mode="fixed", color="#00FFFF", brightness=30,
        independent_colors=False,
        keyboard_color="#112233", keyboard_brightness=7,
        lightbar_color="#00FFFF", lightbar_brightness=80,
        effect=EffectConfig(name="breathing", color="#00FFFF", speed=5),
        solar=SolarConfig(-23.55, -46.63, "#8FF0A4", "#FF7800", 50, 20),
        presets={"work": Preset(color="#123456", brightness=11)},
    )
    defaults.update(overrides)
    return Config(**defaults)


def _adapter(cfg=None):
    api = DaemonDBusAPI(cfg or _cfg(), lambda c: None, asyncio.Event())
    adapter = DBusAdapter(api)
    events: list[tuple] = []
    adapter.StateChanged.connect(
        lambda mode, color, brightness: events.append((mode, color, brightness))
    )
    return adapter, api, events


def test_dbus_xml_declares_state_changed_signal():
    xml = DBusAdapter.__dbus_xml__
    assert '<signal name="StateChanged">' in xml
    node = ET.fromstring(xml)
    signal = node.find(
        './interface[@name="io.github.avellrgb.Daemon"]/signal[@name="StateChanged"]'
    )
    assert signal is not None
    args = [
        (a.get("name"), a.get("type"), a.get("direction"))
        for a in signal.findall("arg")
    ]
    assert args == [
        ("mode", "s", "out"),
        ("color", "s", "out"),
        ("brightness", "i", "out"),
    ]


def test_set_mode_emits_state():
    adapter, api, events = _adapter()
    adapter.SetMode("off")
    assert events == [("off", "#00FFFF", 30)]


def test_set_color_emits_state():
    adapter, api, events = _adapter()
    adapter.SetColor("#FF0000", 25)
    assert events == [("fixed", "#FF0000", 25)]


def test_set_device_color_keyboard_emits_global_state():
    adapter, api, events = _adapter()
    adapter.SetDeviceColor("keyboard", "#FF0000", 40)
    c = api.config
    assert events == [(c.mode, c.color, c.brightness)]
    assert events == [("fixed", "#00FFFF", 30)]


def test_set_device_color_lightbar_emits_global_state():
    adapter, api, events = _adapter()
    adapter.SetDeviceColor("lightbar", "#00FF00", 90)
    c = api.config
    assert events == [(c.mode, c.color, c.brightness)]
    assert events == [("fixed", "#00FFFF", 30)]


def test_set_effect_emits_state():
    adapter, api, events = _adapter()
    adapter.SetEffect("wave", "#00FF00", 8, 42)
    assert events == [("effect", "#00FFFF", 30)]


def test_set_solar_emits_state():
    adapter, api, events = _adapter()
    adapter.SetSolar(-22.9, -43.2, "#FFFFFF", "#FF0000", 50, 10)
    assert events == [("solar", "#00FFFF", 30)]


def test_apply_preset_emits_state():
    adapter, api, events = _adapter()
    adapter.ApplyPreset("work")
    assert events == [("fixed", "#123456", 11)]


def test_save_and_delete_preset_do_not_emit():
    adapter, api, events = _adapter()
    adapter.SavePreset("tmp")
    adapter.DeletePreset("tmp")
    assert events == []


def test_get_state_and_list_presets_json_roundtrip():
    adapter, api, events = _adapter()
    state = json.loads(adapter.GetState())
    assert state["mode"] == "fixed"
    assert state["color"] == "#00FFFF"
    presets = json.loads(adapter.ListPresets())
    assert presets[0]["name"] == "work"


def test_animate_step_invalid_color_disables_animation(caplog):
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(
            mode="effect",
            effect=EffectConfig(name="breathing", color="not-a-color", speed=5),
        ),
        keyboard=kb, lightbar=bar,
    )
    with caplog.at_level(logging.ERROR, logger="avell_rgb.daemon"):
        core.apply_current()  # must not raise
        assert core.animating() is False
        core.animate_step()  # disabled: no further logs, no writes
        core.animate_step()
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert bar.calls == []
    # next apply with a good config re-enables the animation
    core.config = _cfg(mode="effect")
    core.apply_current()
    assert core.animating() is True


_HAVE_DBUS_TOOLS = bool(shutil.which("dbus-run-session")) and bool(shutil.which("busctl"))

_EPHEMERAL_DAEMON = """\
import asyncio

from avell_rgb.daemon.dbus_api import DaemonDBusAPI
from avell_rgb.daemon.main import DBusAdapter
from avell_rgb.state import Config, EffectConfig, SolarConfig
from dasbus.connection import SessionMessageBus
from gi.repository import GLib

cfg = Config(
    version=2, mode="fixed", color="#00FFFF", brightness=30,
    independent_colors=False,
    keyboard_color="#00FFFF", keyboard_brightness=30,
    lightbar_color="#00FFFF", lightbar_brightness=80,
    effect=EffectConfig(name="breathing", color="#00FFFF", speed=5),
    solar=SolarConfig(-23.55, -46.63, "#8FF0A4", "#FF7800", 50, 20),
    presets={},
)
api = DaemonDBusAPI(cfg, lambda c: None, asyncio.Event())
bus = SessionMessageBus()
bus.publish_object("/io/github/avellrgb/Daemon", DBusAdapter(api))
bus.register_service("io.github.avellrgb.Daemon")
GLib.MainLoop().run()
"""


@pytest.mark.skipif(not _HAVE_DBUS_TOOLS, reason="dbus-run-session/busctl not available")
def test_state_changed_signal_exported_on_real_bus(tmp_path):
    script = tmp_path / "ephemeral_daemon.py"
    script.write_text(_EPHEMERAL_DAEMON)
    out_file = tmp_path / "introspect.out"
    shell = (
        f'"{sys.executable}" "{script}" & pid=$!; ok=1; '
        f"for i in $(seq 1 50); do "
        f"if busctl --user introspect io.github.avellrgb.Daemon "
        f'/io/github/avellrgb/Daemon > "{out_file}" 2>/dev/null; '
        f"then ok=0; break; fi; sleep 0.2; done; "
        f"kill $pid 2>/dev/null; exit $ok"
    )
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    result = subprocess.run(
        ["dbus-run-session", "--", "bash", "-c", shell],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    line = next(
        l for l in out_file.read_text().splitlines() if ".StateChanged" in l
    )
    assert "signal" in line
    assert "ssi" in line
