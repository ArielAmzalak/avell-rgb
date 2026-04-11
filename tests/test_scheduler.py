from datetime import datetime, time

import pytest

from avell_rgb.scheduler import (
    resolve_schedule,
    seconds_until_next_schedule_boundary,
)
from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
)


def _p(name: str, color: str = "#FFFFFF") -> DeviceState:
    return DeviceState(
        keyboard=KeyboardSolid(color=color, brightness=20),
        lightbar=LightbarState(color=color, brightness=50),
    )


def test_resolve_inside_single_band():
    presets = {"work": _p("work", "#00FFFF")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 12, 0)
    assert resolve_schedule(schedule, presets, now) == presets["work"]


def test_resolve_at_start_boundary_is_inside():
    presets = {"work": _p("work")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 7, 0)
    assert resolve_schedule(schedule, presets, now) == presets["work"]


def test_resolve_at_end_boundary_is_outside():
    presets = {"work": _p("work"), "off": _p("off", "#000000")}
    schedule = [
        ScheduleBand(start="07:00", end="18:00", preset="work"),
        ScheduleBand(start="18:00", end="07:00", preset="off"),
    ]
    now = datetime(2026, 4, 10, 18, 0)
    assert resolve_schedule(schedule, presets, now) == presets["off"]


def test_resolve_outside_all_bands_returns_none():
    presets = {"work": _p("work")}
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 20, 0)
    assert resolve_schedule(schedule, presets, now) is None


def test_resolve_midnight_crossing_band_morning():
    presets = {"night": _p("night")}
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 3, 0)
    assert resolve_schedule(schedule, presets, now) == presets["night"]


def test_resolve_midnight_crossing_band_evening():
    presets = {"night": _p("night")}
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 23, 30)
    assert resolve_schedule(schedule, presets, now) == presets["night"]


def test_resolve_first_band_wins_on_overlap():
    presets = {"a": _p("a", "#FF0000"), "b": _p("b", "#00FF00")}
    schedule = [
        ScheduleBand(start="07:00", end="18:00", preset="a"),
        ScheduleBand(start="10:00", end="12:00", preset="b"),
    ]
    now = datetime(2026, 4, 10, 11, 0)
    assert resolve_schedule(schedule, presets, now) == presets["a"]


def test_resolve_unknown_preset_in_band_raises():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="missing")]
    now = datetime(2026, 4, 10, 12, 0)
    with pytest.raises(KeyError):
        resolve_schedule(schedule, {}, now)


def test_next_boundary_from_inside_band():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 12, 0)
    # 18:00 - 12:00 = 6h
    assert seconds_until_next_schedule_boundary(schedule, now) == 6 * 3600


def test_next_boundary_from_outside_all_bands():
    schedule = [ScheduleBand(start="07:00", end="18:00", preset="work")]
    now = datetime(2026, 4, 10, 20, 0)
    # next boundary = tomorrow 07:00 = 11h later
    assert seconds_until_next_schedule_boundary(schedule, now) == 11 * 3600


def test_next_boundary_midnight_crossing_band():
    schedule = [ScheduleBand(start="23:00", end="07:00", preset="night")]
    now = datetime(2026, 4, 10, 2, 0)
    # end = today 07:00, 5h away
    assert seconds_until_next_schedule_boundary(schedule, now) == 5 * 3600


def test_next_boundary_empty_schedule_returns_infinity():
    from math import isinf

    assert isinf(seconds_until_next_schedule_boundary([], datetime(2026, 4, 10, 12, 0)))
