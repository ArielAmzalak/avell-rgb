"""Color conversion helpers shared by GUI pages."""

from __future__ import annotations

from gi.repository import Gdk


def hex_to_rgba(hex_str: str) -> Gdk.RGBA:
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    rgba = Gdk.RGBA()
    rgba.red = r / 255
    rgba.green = g / 255
    rgba.blue = b / 255
    rgba.alpha = 1.0
    return rgba


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    r = round(rgba.red * 255)
    g = round(rgba.green * 255)
    b = round(rgba.blue * 255)
    return "#{:02X}{:02X}{:02X}".format(r, g, b)
