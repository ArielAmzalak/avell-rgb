from datetime import datetime

from avell_rgb.solar import interpolate_solar, solar_t_from_elevation
from avell_rgb.state import SolarConfig


def test_solar_t_full_night():
    assert solar_t_from_elevation(-10) == 0.0


def test_solar_t_full_day():
    assert solar_t_from_elevation(10) == 1.0


def test_solar_t_midpoint():
    assert solar_t_from_elevation(0) == 0.5


def test_interpolate_solar_returns_tuple():
    cfg = SolarConfig(
        latitude=-23.55, longitude=-46.63,
        day_color="#FFFFFF", night_color="#000000",
        day_brightness=50, night_brightness=10,
    )
    result = interpolate_solar(cfg, datetime(2026, 4, 10, 12, 0))
    assert isinstance(result, tuple)
    assert len(result) == 3  # (color_hex, kb_brightness, lb_brightness)


def test_interpolate_solar_returns_color_and_brightness():
    cfg = SolarConfig(
        latitude=-23.55, longitude=-46.63,
        day_color="#FFFFFF", night_color="#000000",
        day_brightness=50, night_brightness=10,
    )
    color, kb_bri, lb_bri = interpolate_solar(cfg, datetime(2026, 4, 10, 12, 0))
    assert color.startswith("#")
    assert 0 <= kb_bri <= 50
    assert 0 <= lb_bri <= 100


def test_interpolate_solar_clamps_negative_brightness():
    cfg = SolarConfig(
        latitude=-23.55, longitude=-46.63,
        day_color="#FFFFFF", night_color="#000000",
        day_brightness=-5, night_brightness=-10,
    )
    _, kb_bri, lb_bri = interpolate_solar(cfg, datetime(2026, 4, 10, 12, 0))
    assert kb_bri == 0
    assert lb_bri == 0
