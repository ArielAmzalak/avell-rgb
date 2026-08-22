"""Live laptop preview: Cairo-drawn keyboard deck + lightbar with glow.

Renders the currently selected colors/effect so the user sees the result
before it even hits the hardware. Effect animations approximate the
firmware behavior (hue sweeps, pulses, twinkles) — they are previews,
not exact reproductions.
"""

from __future__ import annotations

import colorsys
import math

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

from avell_rgb import lightbar_fx

# Simplified ANSI-ish key layout: rows of relative key widths.
_ROWS: tuple[tuple[float, ...], ...] = (
    tuple([1.0] * 14),
    tuple([1.0] * 13 + [2.0]),
    tuple([1.5] + [1.0] * 12 + [1.5]),
    tuple([1.8] + [1.0] * 11 + [2.2]),
    tuple([2.3] + [1.0] * 10 + [2.7]),
    (1.3, 1.3, 1.3, 6.2, 1.3, 1.3, 1.3, 1.3),
)

_TICK_MS = 40  # 25 fps


def _hex_to_rgbf(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def _hash01(a: float, b: float) -> float:
    """Deterministic pseudo-random in [0,1) from two floats."""
    return (math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1.0


def _rounded_rect(cr, x: float, y: float, w: float, h: float, r: float) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class LaptopPreview(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_content_height(252)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

        self._kb_rgb = (0.0, 1.0, 1.0)
        self._kb_level = 0.6
        self._lb_rgb = (0.0, 1.0, 1.0)
        self._lb_level = 0.8
        self._effect: str | None = None
        self._speed = 5
        self._t = 0.0
        self._tick_id: int | None = None

    # ---------- public API ----------

    def set_static(self, kb_hex: str, kb_level: float, lb_hex: str, lb_level: float) -> None:
        self._kb_rgb = _hex_to_rgbf(kb_hex)
        self._kb_level = max(0.0, min(1.0, kb_level))
        self._lb_rgb = _hex_to_rgbf(lb_hex)
        self._lb_level = max(0.0, min(1.0, lb_level))
        self._effect = None
        self._stop_tick()
        self.queue_draw()

    def set_effect(self, name: str, color_hex: str, speed: int, level: float) -> None:
        self._kb_rgb = _hex_to_rgbf(color_hex)
        self._kb_level = max(0.0, min(1.0, level))
        self._lb_rgb = self._kb_rgb
        self._lb_level = max(0.0, min(1.0, level))
        self._effect = name
        self._speed = max(1, speed)
        self._lb_base255 = tuple(round(c * 255) for c in self._kb_rgb)
        self._lb_max_bri = round(max(0.0, min(1.0, level)) * 100)
        self._start_tick()
        self.queue_draw()

    def set_off(self) -> None:
        self._effect = None
        self._kb_level = 0.0
        self._lb_level = 0.0
        self._stop_tick()
        self.queue_draw()

    # ---------- animation ----------

    def _start_tick(self) -> None:
        if self._tick_id is None:
            self._tick_id = GLib.timeout_add(_TICK_MS, self._on_tick)

    def _stop_tick(self) -> None:
        if self._tick_id is not None:
            GLib.source_remove(self._tick_id)
            self._tick_id = None

    def _on_tick(self) -> bool:
        self._t += _TICK_MS / 1000.0
        if self._effect is not None:
            rgb, bri = lightbar_fx.frame(
                self._effect, self._lb_base255, self._speed,
                self._lb_max_bri, self._t,
            )
            self._lb_rgb = (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
            self._lb_level = bri / 100
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    # ---------- per-key effect color ----------

    def _key_color(self, cx: float, ry: float) -> tuple[float, float, float, float]:
        """Return (r, g, b, intensity 0..1) for a key at col-frac cx, row-frac ry."""
        base = self._kb_rgb
        lvl = self._kb_level
        eff = self._effect
        t = self._t
        spd = self._speed / 5.0  # 1.0 at speed 5

        if eff is None:
            return (*base, lvl)

        if eff == "breathing":
            pulse = 0.5 + 0.5 * math.sin(t * spd * 2.2)
            return (*base, lvl * (0.15 + 0.85 * pulse))

        if eff in ("wave", "rainbow"):
            drift = t * spd * 0.25 if eff == "wave" else t * 0.05
            hue = (cx * 1.1 + ry * 0.18 - drift) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            return (r, g, b, lvl)

        if eff == "marquee":
            band = math.cos((cx * 2.0 - t * spd * 0.4) * 2 * math.pi)
            inten = 0.18 + 0.82 * max(0.0, band) ** 3
            return (*base, lvl * inten)

        if eff == "random":
            cell = math.floor(t * spd * 1.4)
            hue = _hash01(round(cx * 14), round(ry * 5) * 31 + cell)
            r, g, b = colorsys.hsv_to_rgb(hue, 0.95, 1.0)
            return (r, g, b, lvl * (0.35 + 0.65 * _hash01(cell, cx * 7 + ry * 3)))

        if eff == "raindrop":
            phase = _hash01(round(cx * 14), 1.7)
            pos = (t * spd * 0.35 + phase * 1.3) % 1.3
            d = abs(ry - pos)
            inten = max(0.0, 1.0 - d * 4.0) ** 2
            return (*base, lvl * (0.08 + 0.92 * inten))

        if eff == "ripple":
            d = math.hypot(cx - 0.5, (ry - 0.5) * 0.45)
            ring = math.cos((d * 6.0 - t * spd * 1.2) * math.pi)
            inten = max(0.0, ring) ** 3
            return (*base, lvl * (0.10 + 0.90 * inten))

        if eff == "aurora":
            h0, s0, v0 = colorsys.rgb_to_hsv(*base)
            hue = (h0 + 0.12 * math.sin(cx * 3.0 + t * spd * 0.5)
                   + 0.08 * math.sin(ry * 2.0 - t * spd * 0.3)) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, max(s0, 0.7), 1.0)
            breathe = 0.75 + 0.25 * math.sin(t * spd * 0.8 + cx * 2)
            return (r, g, b, lvl * breathe)

        if eff == "fireworks":
            cell = math.floor(t * spd * 1.1)
            spark = _hash01(round(cx * 14) * 13 + round(ry * 5), cell)
            frac = (t * spd * 1.1) % 1.0
            if spark > 0.88:
                hue = _hash01(cell, spark)
                r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
                return (r, g, b, lvl * max(0.0, 1.0 - frac) ** 1.5)
            return (*base, lvl * 0.06)

        return (*base, lvl)

    # ---------- drawing ----------

    def _draw(self, _area, cr, width: int, height: int) -> None:
        deck_w = min(width - 48, 560)
        if deck_w < 200:
            return
        deck_x = (width - deck_w) / 2
        deck_y = 16.0
        deck_h = height - 66.0

        # Deck body
        _rounded_rect(cr, deck_x, deck_y, deck_w, deck_h, 18)
        grad = self._linear(cr, deck_x, deck_y, deck_x, deck_y + deck_h,
                            (0.086, 0.101, 0.141, 1.0), (0.051, 0.063, 0.090, 1.0))
        cr.set_source(grad)
        cr.fill()
        _rounded_rect(cr, deck_x, deck_y, deck_w, deck_h, 18)
        cr.set_source_rgba(1, 1, 1, 0.06)
        cr.set_line_width(1.0)
        cr.stroke()

        # Keyboard well
        kb_margin = 22.0
        kb_x = deck_x + kb_margin
        kb_y = deck_y + 16.0
        kb_w = deck_w - kb_margin * 2
        kb_h = deck_h - 46.0

        _rounded_rect(cr, kb_x - 7, kb_y - 7, kb_w + 14, kb_h + 14, 10)
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.fill()

        # Ambient glow behind keys (average of key color at low alpha)
        if self._kb_level > 0.01:
            gr, gg, gb, ga = self._avg_key_color()
            for grow, alpha in ((26, 0.05), (14, 0.08), (5, 0.10)):
                _rounded_rect(cr, kb_x - grow, kb_y - grow,
                              kb_w + grow * 2, kb_h + grow * 2, 16)
                cr.set_source_rgba(gr, gg, gb, ga * alpha * 10)
                cr.fill()

        # Keys
        gap = 3.0
        n_rows = len(_ROWS)
        row_h = (kb_h - gap * (n_rows - 1)) / n_rows
        for ri, row in enumerate(_ROWS):
            total = sum(row)
            x = kb_x
            ry = ri / (n_rows - 1)
            y = kb_y + ri * (row_h + gap)
            for wi, rel in enumerate(row):
                kw = (kb_w - gap * (len(row) - 1)) * (rel / total)
                cx = (x - kb_x + kw / 2) / kb_w
                r, g, b, inten = self._key_color(cx, ry)
                _rounded_rect(cr, x, y, kw, row_h, 3.5)
                cr.set_source_rgba(0.10, 0.11, 0.14, 1.0)
                cr.fill()
                if inten > 0.01:
                    _rounded_rect(cr, x, y, kw, row_h, 3.5)
                    cr.set_source_rgba(r, g, b, 0.14 + 0.86 * inten)
                    cr.fill()
                x += kw + gap

        # Lightbar on the front edge
        lb_h = 7.0
        lb_x = deck_x + 26
        lb_w = deck_w - 52
        lb_y = deck_y + deck_h - lb_h - 9

        _rounded_rect(cr, lb_x, lb_y, lb_w, lb_h, 4)
        cr.set_source_rgba(0.08, 0.09, 0.12, 1.0)
        cr.fill()

        if self._lb_level > 0.01:
            lr, lg, lb_ = self._lb_rgb
            la = 0.25 + 0.75 * self._lb_level
            _rounded_rect(cr, lb_x, lb_y, lb_w, lb_h, 4)
            cr.set_source_rgba(lr, lg, lb_, la)
            cr.fill()

            # Light pooling below the deck
            pool_y = deck_y + deck_h
            pool_h = height - pool_y - 2
            if pool_h > 4:
                grad = self._linear(
                    cr, 0, pool_y, 0, pool_y + pool_h,
                    (lr, lg, lb_, 0.34 * self._lb_level),
                    (lr, lg, lb_, 0.0),
                )
                cr.set_source(grad)
                cr.rectangle(lb_x - 14, pool_y, lb_w + 28, pool_h)
                cr.fill()

    def _avg_key_color(self) -> tuple[float, float, float, float]:
        """Sample a few keys to estimate the ambient glow color."""
        rs = gs = bs = as_ = 0.0
        samples = ((0.2, 0.3), (0.5, 0.5), (0.8, 0.7))
        for cx, ry in samples:
            r, g, b, a = self._key_color(cx, ry)
            rs += r
            gs += g
            bs += b
            as_ += a
        n = len(samples)
        return (rs / n, gs / n, bs / n, as_ / n)

    @staticmethod
    def _linear(cr, x0, y0, x1, y1, c0, c1):
        import cairo
        grad = cairo.LinearGradient(x0, y0, x1, y1)
        grad.add_color_stop_rgba(0, *c0)
        grad.add_color_stop_rgba(1, *c1)
        return grad
