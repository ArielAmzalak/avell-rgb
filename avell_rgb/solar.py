"""Solar gradient interpolation. Uses astral for sun elevation."""

from __future__ import annotations

from datetime import datetime

from astral import LocationInfo, sun

from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    SolarConfig,
)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def solar_t_from_elevation(elevation_deg: float) -> float:
    """Map sun elevation in degrees to a normalized blend factor t in [0, 1].
    - elevation <= -6° (past civil twilight): t = 0 (full night)
    - elevation >=  6°: t = 1 (full day)
    - between: linear interpolation"""
    if elevation_deg <= -6:
        return 0.0
    if elevation_deg >= 6:
        return 1.0
    return (elevation_deg + 6) / 12


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _lerp_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


def interpolate_solar(cfg: SolarConfig, now: datetime) -> DeviceState:
    """Compute the DeviceState for the given moment, blending between day
    and night colors using the real sun elevation at (lat, lon, now)."""
    loc = LocationInfo(latitude=cfg.latitude, longitude=cfg.longitude)
    elevation = sun.elevation(loc.observer, now)
    t = solar_t_from_elevation(elevation)

    night_rgb = hex_to_rgb(cfg.night_color)
    day_rgb = hex_to_rgb(cfg.day_color)
    blended_rgb = _lerp_rgb(night_rgb, day_rgb, t)
    blended_hex = rgb_to_hex(blended_rgb)

    kb_brightness = round(cfg.night_brightness + (cfg.day_brightness - cfg.night_brightness) * t)
    bar_brightness = kb_brightness  # same scale intent; 0-100

    # Keyboard brightness in ite8291r3-ctl is 0-50. Scale from the 0-100 user input.
    kb_brightness_scaled = min(50, round(kb_brightness * 50 / 100))

    if "keyboard" in cfg.apply_to:
        kb_state = KeyboardSolid(color=blended_hex, brightness=kb_brightness_scaled)
    else:
        kb_state = KeyboardOff()

    if "lightbar" in cfg.apply_to:
        bar_state = LightbarState(color=blended_hex, brightness=bar_brightness)
    else:
        bar_state = LightbarState(color="#000000", brightness=0)

    return DeviceState(keyboard=kb_state, lightbar=bar_state)
