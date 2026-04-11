from datetime import datetime
from math import isinf

import pytest

from avell_rgb.config import DEFAULT_CONFIG
from avell_rgb.daemon.main import DaemonCore
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)
from tests.conftest import FakeKeyboardBackend, FakeLightbarBackend


def _simple_config(
    mode: str = "schedule",
    manual_state=None,
    schedule=None,
    presets=None,
) -> Config:
    return Config(
        version=1,
        mode=mode,
        manual_paused=False,
        manual_state=manual_state,
        presets=presets
        or {
            "work": DeviceState(
                keyboard=KeyboardSolid(color="#00FFFF", brightness=30),
                lightbar=LightbarState(color="#00FFFF", brightness=80),
            ),
            "off": DeviceState(
                keyboard=KeyboardOff(),
                lightbar=LightbarState(color="#000000", brightness=0),
            ),
        },
        schedule=schedule
        or [
            ScheduleBand(start="07:00", end="18:00", preset="work"),
            ScheduleBand(start="18:00", end="07:00", preset="off"),
        ],
        solar=SolarConfig(
            latitude=0.0,
            longitude=0.0,
            day_color="#FFFFFF",
            night_color="#000000",
            day_brightness=50,
            night_brightness=10,
            apply_to=("keyboard", "lightbar"),
        ),
    )


def test_manual_state_overrides_schedule():
    manual = DeviceState(
        keyboard=KeyboardSolid(color="#FF00FF", brightness=40),
        lightbar=LightbarState(color="#FF00FF", brightness=90),
    )
    cfg = _simple_config(manual_state=manual)
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    state = core.compute_desired_state()
    assert state == manual


def test_schedule_applied_at_noon():
    cfg = _simple_config()
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls[-1][0] == "apply_solid"
    assert kb.calls[-1][1] == ((0, 255, 255), 30)
    assert bar.calls[-1][0] == "apply"
    assert bar.calls[-1][1] == ((0, 255, 255), 80)


def test_schedule_applied_at_night_keyboard_off_lightbar_off():
    cfg = _simple_config()
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 22, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls[-1][0] == "off"
    assert bar.calls[-1][0] == "off"


def test_seconds_until_next_change_manual_is_infinity():
    manual = DeviceState(
        keyboard=KeyboardOff(),
        lightbar=LightbarState(color="#000000", brightness=0),
    )
    cfg = _simple_config(manual_state=manual)
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    assert isinf(core.seconds_until_next_change())


def test_seconds_until_next_change_solar_is_300():
    cfg = _simple_config(mode="solar")
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    assert core.seconds_until_next_change() == 300.0


def test_seconds_until_next_change_schedule_is_boundary():
    cfg = _simple_config()
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    # nearest boundary from 12:00 is 18:00 (6h)
    assert core.seconds_until_next_change() == 6 * 3600


def test_unavailable_keyboard_does_not_crash():
    cfg = _simple_config()
    kb = FakeKeyboardBackend(available_returns=False)
    bar = FakeLightbarBackend()
    core = DaemonCore(
        config=cfg,
        keyboard=kb,
        lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    core.apply(core.compute_desired_state())
    assert kb.calls == []
    assert bar.calls[-1][0] == "apply"  # lightbar still applied


def test_solar_mode_produces_some_state():
    cfg = _simple_config(mode="solar")
    core = DaemonCore(
        config=cfg,
        keyboard=FakeKeyboardBackend(),
        lightbar=FakeLightbarBackend(),
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    state = core.compute_desired_state()
    assert state is not None
    assert state.lightbar.color.startswith("#")
