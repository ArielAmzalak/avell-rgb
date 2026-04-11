from datetime import datetime, timezone

import pytest

from avell_rgb.solar import (
    hex_to_rgb,
    interpolate_solar,
    rgb_to_hex,
    solar_t_from_elevation,
)
from avell_rgb.state import DeviceState, SolarConfig


def test_hex_to_rgb_parses_six_chars():
    assert hex_to_rgb("#FF0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("#000000") == (0, 0, 0)
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)


def test_rgb_to_hex_uppercase():
    assert rgb_to_hex((255, 0, 0)) == "#FF0000"
    assert rgb_to_hex((0, 128, 255)) == "#0080FF"


def test_solar_t_nadir_is_zero():
    assert solar_t_from_elevation(-90) == 0.0


def test_solar_t_zenith_is_one():
    assert solar_t_from_elevation(90) == 1.0


def test_solar_t_horizon_is_half():
    # at elevation 0 (horizon), t should be 0.5
    assert solar_t_from_elevation(0) == pytest.approx(0.5, abs=0.05)


def test_solar_t_clamps_below_minus_six():
    assert solar_t_from_elevation(-30) == 0.0


def test_solar_t_clamps_above_six():
    assert solar_t_from_elevation(45) == 1.0


def _solar_cfg() -> SolarConfig:
    return SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",  # 255,255,255
        night_color="#000000",  # 0,0,0
        day_brightness=100,
        night_brightness=0,
        apply_to=("keyboard", "lightbar"),
    )


def test_interpolate_at_noon_sp_gives_day_color():
    cfg = _solar_cfg()
    # Apr 10, noon São Paulo (-03:00). Using tz-aware datetime.
    from datetime import timedelta

    noon_sp = datetime(2026, 4, 10, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, noon_sp)
    # At noon, sun elevation in SP is ~70°+, so t should be 1.0
    # keyboard solid, color close to #FFFFFF
    from avell_rgb.state import KeyboardSolid
    assert isinstance(state.keyboard, KeyboardSolid)
    assert state.keyboard.color == "#FFFFFF"
    assert state.lightbar.color == "#FFFFFF"
    assert state.keyboard.brightness >= 40  # scale applied (keyboard uses 0-50)
    assert state.lightbar.brightness == 100


def test_interpolate_at_midnight_sp_gives_night_color():
    cfg = _solar_cfg()
    from datetime import timedelta

    midnight_sp = datetime(2026, 4, 10, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, midnight_sp)
    from avell_rgb.state import KeyboardSolid
    assert isinstance(state.keyboard, KeyboardSolid)
    assert state.keyboard.color == "#000000"
    assert state.lightbar.color == "#000000"
    assert state.lightbar.brightness == 0


def test_interpolate_respects_apply_to_keyboard_only():
    cfg = SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",
        night_color="#000000",
        day_brightness=100,
        night_brightness=0,
        apply_to=("keyboard",),  # lightbar excluded
    )
    from datetime import timedelta

    noon_sp = datetime(2026, 4, 10, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
    state = interpolate_solar(cfg, noon_sp)
    # keyboard interpolated; lightbar gets off (brightness=0)
    assert state.lightbar.brightness == 0
