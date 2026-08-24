"""Solar gradient interpolation. Uses astral for sun elevation."""

from __future__ import annotations

from datetime import datetime

from astral import LocationInfo, sun

from avell_rgb.state import SolarConfig, kb_to_lb_brightness


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def solar_t_from_elevation(elevation_deg: float) -> float:
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


def interpolate_solar(cfg: SolarConfig, now: datetime) -> tuple[str, int, int]:
    """Return (color_hex, kb_brightness, lb_brightness) for the given moment."""
    loc = LocationInfo(latitude=cfg.latitude, longitude=cfg.longitude)
    elevation = sun.elevation(loc.observer, now)
    t = solar_t_from_elevation(elevation)

    night_rgb = hex_to_rgb(cfg.night_color)
    day_rgb = hex_to_rgb(cfg.day_color)
    blended_hex = rgb_to_hex(_lerp_rgb(night_rgb, day_rgb, t))

    raw_brightness = round(
        cfg.night_brightness + (cfg.day_brightness - cfg.night_brightness) * t
    )
    kb_brightness = max(0, min(50, raw_brightness))
    lb_brightness = max(0, kb_to_lb_brightness(raw_brightness))

    return (blended_hex, kb_brightness, lb_brightness)
