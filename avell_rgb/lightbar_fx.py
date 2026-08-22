"""Software effect frames for the single-zone lightbar.

The keyboard runs effects in firmware, but the lightbar is a plain sysfs
LED — so the daemon animates it by computing one (color, brightness)
frame per tick. Each keyboard effect maps to a single-zone equivalent:
pulses for the positional ones, hue cycles for the multicolor ones.

Pure functions only; the daemon and the GUI preview share this module.
"""

from __future__ import annotations

import colorsys
import math

# Effects whose firmware rendering is inherently multicolor (the keyboard
# ignores/lacks a color attr) — the bar cycles hues instead of using the
# stored effect color, which the user cannot see for these.
HUE_CYCLE_EFFECTS = frozenset({"wave", "rainbow", "marquee"})


def _hash01(a: float, b: float) -> float:
    """Deterministic pseudo-random in [0,1) from two floats."""
    return (math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1.0


def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def frame(
    name: str,
    base: tuple[int, int, int],
    speed: int,
    max_bri: int,
    t: float,
) -> tuple[tuple[int, int, int], int]:
    """Return ((r, g, b), brightness) for effect `name` at elapsed time `t`.

    `base` is the effect color (0-255 each), `speed` the 0-10 effect speed,
    `max_bri` the brightness ceiling (lightbar scale, 0-100).
    """
    spd = max(0.2, speed / 5.0)

    if name == "breathing":
        pulse = 0.5 + 0.5 * math.sin(t * spd * 2.2)
        return (base, round(max_bri * (0.10 + 0.90 * pulse)))

    if name == "wave":
        return (_hsv(t * spd * 0.25), max_bri)

    if name == "rainbow":
        return (_hsv(t * 0.08), max_bri)

    if name == "marquee":
        p = (t * spd * 0.8) % 1.0
        tri = 1.0 - abs(2.0 * p - 1.0)
        return (_hsv(t * spd * 0.15), round(max_bri * (0.15 + 0.85 * tri * tri)))

    if name == "random":
        step = math.floor(t * spd * 1.1)
        return (_hsv(_hash01(step, 0.37), 0.95), max_bri)

    if name == "ripple":
        p = (t * spd * 0.9) % 1.0
        return (base, round(max_bri * (0.08 + 0.92 * (1.0 - p) ** 3)))

    if name == "raindrop":
        p = (t * spd / 1.4) % 1.0
        flash = max(0.0, 1.0 - p * 3.0) ** 2
        return (base, round(max_bri * (0.10 + 0.90 * flash)))

    if name == "aurora":
        h0, s0, _ = colorsys.rgb_to_hsv(base[0] / 255, base[1] / 255, base[2] / 255)
        hue = h0 + 0.12 * math.sin(t * spd * 0.5)
        breathe = 0.75 + 0.25 * math.sin(t * spd * 0.8)
        return (_hsv(hue, max(s0, 0.7)), round(max_bri * breathe))

    if name == "fireworks":
        step = math.floor(t * spd * 1.1)
        p = (t * spd * 1.1) % 1.0
        decay = max(0.06, (1.0 - p) ** 2)
        return (_hsv(_hash01(step, 0.61), 0.9), round(max_bri * decay))

    return (base, max_bri)
