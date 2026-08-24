"""Config window v2: live preview, per-device control, presets, solar.

Layout: laptop preview on top, mode pills, a per-mode panel (fixed with
sync/split device cards, effect grid, solar day/night cards, off), then
presets and preferences. Changes apply live (debounced) via D-Bus.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from avell_rgb.backends.keyboard import _EFFECT_CAPS
from avell_rgb.dbus_client import DaemonClient
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.gui.preview import LaptopPreview
from avell_rgb.gui.style import SWATCHES
from avell_rgb.state import VALID_EFFECTS

log = logging.getLogger("avell_rgb.gui.window")

EFFECT_LABELS = {
    "breathing": "Respiração",
    "wave": "Onda",
    "random": "Aleatório",
    "rainbow": "Arco-íris",
    "ripple": "Ondulação",
    "marquee": "Letreiro",
    "raindrop": "Chuva",
    "aurora": "Aurora",
    "fireworks": "Fogos",
}

_DEBOUNCE_MS = 130


def _swatch_provider(css: str) -> Gtk.CssProvider:
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    return provider


def _paint(widget: Gtk.Widget, css: str) -> None:
    """Attach a one-off CSS background to a single widget."""
    widget.get_style_context().add_provider(
        _swatch_provider(css), Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def _card(title: str | None = None, css_class: str = "glass-card") -> tuple[Gtk.Box, Gtk.Box]:
    """Return (outer_card, content_box)."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    outer.add_css_class(css_class)
    if title:
        lbl = Gtk.Label(label=title, xalign=0)
        lbl.add_css_class("card-title")
        outer.append(lbl)
    return outer, outer


def _slider(lo: int, hi: int) -> Gtk.Scale:
    s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
    s.set_hexpand(True)
    s.set_draw_value(True)
    s.set_value_pos(Gtk.PositionType.RIGHT)
    return s


class _ColorControls:
    """Swatch row + color dialog button + brightness slider for one target."""

    def __init__(self, bri_max: int, on_change) -> None:
        self._on_change = on_change
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        flow = Gtk.FlowBox()
        flow.add_css_class("swatch-flow")
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_min_children_per_line(4)
        flow.set_max_children_per_line(9)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        flow.set_hexpand(True)
        flow.set_valign(Gtk.Align.CENTER)
        for hexc in SWATCHES:
            b = Gtk.Button()
            b.add_css_class("swatch")
            b.set_size_request(28, 28)
            b.set_valign(Gtk.Align.CENTER)
            b.set_halign(Gtk.Align.CENTER)
            _paint(b, f"button.swatch {{ background: {hexc}; }}")
            b.set_tooltip_text(hexc)
            b.connect("clicked", self._on_swatch, hexc)
            flow.append(b)
        row.append(flow)

        self.color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self.color_btn.set_dialog(dlg)
        self.color_btn.set_valign(Gtk.Align.CENTER)
        self.color_btn.connect("notify::rgba", lambda *_: self._on_change())
        row.append(self.color_btn)
        self.box.append(row)

        bri_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("display-brightness-symbolic")
        icon.add_css_class("dim-label")
        bri_box.append(icon)
        self.brightness = _slider(0, bri_max)
        self.brightness.connect("value-changed", lambda *_: self._on_change())
        bri_box.append(self.brightness)
        self.box.append(bri_box)

    def _on_swatch(self, _btn, hexc: str) -> None:
        self.color_btn.set_rgba(hex_to_rgba(hexc))
        # notify::rgba fires and triggers on_change

    @property
    def hex(self) -> str:
        return rgba_to_hex(self.color_btn.get_rgba())

    @property
    def bri(self) -> int:
        return int(self.brightness.get_value())

    def set(self, hexc: str, bri: int) -> None:
        self.color_btn.set_rgba(hex_to_rgba(hexc))
        self.brightness.set_value(bri)


class _SolarBar(Gtk.DrawingArea):
    """Night→day gradient with a marker at the current solar position."""

    def __init__(self):
        super().__init__()
        self.set_content_height(22)
        self.set_hexpand(True)
        self._night = "#FF7800"
        self._day = "#8FF0A4"
        self._t = 0.5
        self.set_draw_func(self._draw)

    def update(self, night_hex: str, day_hex: str, t: float) -> None:
        self._night = night_hex
        self._day = day_hex
        self._t = max(0.0, min(1.0, t))
        self.queue_draw()

    def _draw(self, _a, cr, w: int, h: int) -> None:
        import cairo

        def rgbf(hx):
            hx = hx.lstrip("#")
            return tuple(int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4))

        grad = cairo.LinearGradient(0, 0, w, 0)
        grad.add_color_stop_rgb(0, *rgbf(self._night))
        grad.add_color_stop_rgb(1, *rgbf(self._day))
        y = h / 2 - 3
        cr.set_source(grad)
        cr.rectangle(0, y, w, 6)
        cr.fill()

        x = self._t * w
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.arc(x, h / 2, 6, 0, 2 * 3.14159)
        cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.5)
        cr.set_line_width(1.5)
        cr.arc(x, h / 2, 6, 0, 2 * 3.14159)
        cr.stroke()


class AvellWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, client: DaemonClient):
        super().__init__(application=application)
        self._client = client
        self._suppress = False
        self._pending: dict[str, int] = {}

        self.set_default_size(660, 940)
        self.set_title("Avell RGB")
        self.add_css_class("avell-bg")

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        header.add_css_class("flat")
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t1 = Gtk.Label(label="AVELL RGB")
        t1.add_css_class("avell-title")
        t2 = Gtk.Label(label="TECLADO · BARRA LED")
        t2.add_css_class("avell-subtitle")
        title_box.append(t1)
        title_box.append(t2)
        header.set_title_widget(title_box)
        toolbar.add_top_bar(header)

        self._banner = Adw.Banner(title="Daemon não conectado")
        self._banner.set_button_label("Iniciar")
        self._banner.connect("button-clicked", self._on_start_daemon)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self._scroll = scroll

        content_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_wrap.append(self._banner)
        content_wrap.append(scroll)
        toolbar.set_content(content_wrap)

        clamp = Adw.Clamp(maximum_size=620)
        scroll.set_child(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        outer.set_margin_top(4)
        outer.set_margin_bottom(24)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        self._preview = LaptopPreview()
        outer.append(self._preview)

        outer.append(self._build_status_row())
        outer.append(self._build_mode_pills())

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(160)
        self._stack.add_named(self._build_fixed_panel(), "fixed")
        self._stack.add_named(self._build_effect_panel(), "effect")
        self._stack.add_named(self._build_solar_panel(), "solar")
        self._stack.add_named(self._build_off_panel(), "off")
        outer.append(self._stack)

        outer.append(self._build_presets_section())
        outer.append(self._build_prefs_section())

        self._load_state()

        def scroll_top():
            self.set_focus(None)
            self._scroll.get_vadjustment().set_value(0)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(scroll_top)

    # ---------- construction ----------

    def _build_status_row(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        row.set_halign(Gtk.Align.CENTER)
        self._status_labels: dict[str, Gtk.Label] = {}
        for key, name in (("daemon", "Daemon"), ("keyboard", "Teclado"), ("lightbar", "Barra LED")):
            lbl = Gtk.Label(label=f"● {name}")
            lbl.add_css_class("status-dot")
            row.append(lbl)
            self._status_labels[key] = lbl
        return row

    def _build_mode_pills(self) -> Gtk.Widget:
        wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wrap.set_halign(Gtk.Align.CENTER)
        pills = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        pills.add_css_class("mode-pills")
        self._mode_buttons: dict[str, Gtk.ToggleButton] = {}
        first: Gtk.ToggleButton | None = None
        for label, mode in (("Fixo", "fixed"), ("Efeito", "effect"), ("Solar", "solar"), ("Off", "off")):
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("mode-pill")
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.connect("toggled", self._on_mode_toggled, mode)
            pills.append(btn)
            self._mode_buttons[mode] = btn
        wrap.append(pills)
        return wrap

    def _build_fixed_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        sync_card, _ = _card()
        sync_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sync_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        st1 = Gtk.Label(label="Sincronizar dispositivos", xalign=0)
        st1.add_css_class("card-title")
        st2 = Gtk.Label(label="Teclado e barra LED com a mesma cor", xalign=0)
        st2.add_css_class("dim-label")
        sync_text.append(st1)
        sync_text.append(st2)
        sync_row.append(sync_text)
        sync_row.append(Gtk.Box(hexpand=True))
        self._sync_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._sync_switch.connect("notify::active", self._on_sync_toggled)
        sync_row.append(self._sync_switch)
        sync_card.append(sync_row)
        panel.append(sync_card)

        self._fixed_stack = Gtk.Stack()
        self._fixed_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._fixed_stack.set_transition_duration(140)

        synced_card, _ = _card()
        self._synced_ctl = _ColorControls(50, self._on_synced_changed)
        synced_card.append(self._synced_ctl.box)
        self._fixed_stack.add_named(synced_card, "synced")

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        kb_card, _ = _card("⌨  Teclado", "device-card")
        self._kb_ctl = _ColorControls(50, self._on_kb_changed)
        kb_card.append(self._kb_ctl.box)
        split.append(kb_card)

        lb_card, _ = _card("▬  Barra LED", "device-card")
        self._lb_ctl = _ColorControls(100, self._on_lb_changed)
        lb_card.append(self._lb_ctl.box)
        split.append(lb_card)
        self._fixed_stack.add_named(split, "split")

        panel.append(self._fixed_stack)
        return panel

    def _build_effect_panel(self) -> Gtk.Widget:
        panel, _ = _card()

        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_min_children_per_line(3)
        grid.set_max_children_per_line(5)
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        self._effect_buttons: dict[str, Gtk.ToggleButton] = {}
        first: Gtk.ToggleButton | None = None
        for name in VALID_EFFECTS:
            btn = Gtk.ToggleButton(label=EFFECT_LABELS.get(name, name))
            btn.add_css_class("mode-pill")
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.connect("toggled", self._on_effect_chip, name)
            self._effect_buttons[name] = btn
            grid.append(btn)
        panel.append(grid)

        self._effect_ctl = _ColorControls(50, self._on_effect_changed)
        panel.append(self._effect_ctl.box)

        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sp_icon = Gtk.Image.new_from_icon_name("media-seek-forward-symbolic")
        sp_icon.add_css_class("dim-label")
        speed_box.append(sp_icon)
        self._effect_speed = _slider(0, 10)
        self._effect_speed.connect("value-changed", lambda *_: self._on_effect_changed())
        speed_box.append(self._effect_speed)
        self._effect_speed_box = speed_box
        panel.append(speed_box)

        self._effect_hint = Gtk.Label(xalign=0)
        self._effect_hint.add_css_class("dim-label")
        panel.append(self._effect_hint)

        return panel

    def _build_solar_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        cards = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        day_card, _ = _card("☀  Dia", "solar-day-card")
        self._solar_day = _ColorControls(50, self._on_solar_preview)
        day_card.append(self._solar_day.box)
        cards.append(day_card)

        night_card, _ = _card("☾  Noite", "solar-night-card")
        self._solar_night = _ColorControls(50, self._on_solar_preview)
        night_card.append(self._solar_night.box)
        cards.append(night_card)
        panel.append(cards)

        geo_card, _ = _card()
        geo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        geo_lbl = Gtk.Label(label="Localização")
        geo_lbl.add_css_class("card-title")
        geo_row.append(geo_lbl)
        geo_row.append(Gtk.Box(hexpand=True))
        self._solar_lat = Gtk.Entry(placeholder_text="Latitude", width_chars=9)
        self._solar_lat.add_css_class("entry-slim")
        self._solar_lon = Gtk.Entry(placeholder_text="Longitude", width_chars=9)
        self._solar_lon.add_css_class("entry-slim")
        geo_row.append(self._solar_lat)
        geo_row.append(self._solar_lon)
        geo_card.append(geo_row)

        self._solar_bar = _SolarBar()
        geo_card.append(self._solar_bar)
        self._solar_now = Gtk.Label(xalign=0)
        self._solar_now.add_css_class("dim-label")
        geo_card.append(self._solar_now)

        apply_btn = Gtk.Button(label="Aplicar")
        apply_btn.add_css_class("accent-apply")
        apply_btn.set_halign(Gtk.Align.END)
        apply_btn.connect("clicked", self._on_apply_solar)
        geo_card.append(apply_btn)
        panel.append(geo_card)

        return panel

    def _build_off_panel(self) -> Gtk.Widget:
        panel, _ = _card()
        hint = Gtk.Label(
            label="Iluminação desligada. Escolha outro modo para acender.",
            xalign=0,
        )
        hint.add_css_class("off-hint")
        hint.set_wrap(True)
        panel.append(hint)
        return panel

    def _build_presets_section(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label="PRESETS", xalign=0)
        lbl.add_css_class("section-label")
        head.append(lbl)
        head.append(Gtk.Box(hexpand=True))
        save_btn = Gtk.Button(label="＋ Salvar atual")
        save_btn.add_css_class("pill-button")
        save_btn.connect("clicked", self._on_save_preset)
        head.append(save_btn)
        box.append(head)

        self._presets_flow = Gtk.FlowBox()
        self._presets_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._presets_flow.set_min_children_per_line(2)
        self._presets_flow.set_max_children_per_line(4)
        self._presets_flow.set_row_spacing(6)
        self._presets_flow.set_column_spacing(6)
        box.append(self._presets_flow)
        return box

    def _build_prefs_section(self) -> Gtk.Widget:
        card, _ = _card()
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t1 = Gtk.Label(label="Iniciar no login", xalign=0)
        t1.add_css_class("card-title")
        t2 = Gtk.Label(label="Daemon systemd de usuário", xalign=0)
        t2.add_css_class("dim-label")
        text.append(t1)
        text.append(t2)
        row.append(text)
        row.append(Gtk.Box(hexpand=True))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        switch.set_active(self._is_daemon_enabled())
        switch.connect("notify::active", self._on_autostart_toggled)
        row.append(switch)
        card.append(row)
        return card

    # ---------- state loading ----------

    def _load_state(self) -> None:
        self._suppress = True
        state: dict = {}
        try:
            state = self._client.get_state()
            self._banner.set_revealed(False)
        except Exception:
            log.warning("daemon unavailable; using defaults")
            self._banner.set_revealed(True)

        mode = state.get("mode", "fixed")
        color = state.get("color", "#00FFFF")
        brightness = state.get("brightness", 30)
        independent = bool(state.get("independent_colors", False))

        effect = state.get("effect", {})
        if not isinstance(effect, dict):
            effect = {"name": str(effect), "color": color, "speed": 5, "brightness": 25}

        for m, btn in self._mode_buttons.items():
            btn.set_active(m == mode)

        self._synced_ctl.set(color, brightness)
        self._kb_ctl.set(state.get("keyboard_color", color),
                         state.get("keyboard_brightness", brightness))
        self._lb_ctl.set(state.get("lightbar_color", color),
                         state.get("lightbar_brightness", min(100, brightness * 2)))
        self._sync_switch.set_active(not independent)
        self._fixed_stack.set_visible_child_name("split" if independent else "synced")

        eff_name = effect.get("name", "breathing")
        for name, btn in self._effect_buttons.items():
            btn.set_active(name == eff_name)
        self._effect_ctl.set(effect.get("color", color), effect.get("brightness", 25))
        self._effect_speed.set_value(effect.get("speed", 5))
        self._update_effect_caps(eff_name)

        solar = state.get("solar", {})
        if solar:
            self._solar_lat.set_text(str(solar.get("latitude", "")))
            self._solar_lon.set_text(str(solar.get("longitude", "")))
            self._solar_day.set(solar.get("day_color", "#8FF0A4"),
                                solar.get("day_brightness", 50))
            self._solar_night.set(solar.get("night_color", "#FF7800"),
                                  solar.get("night_brightness", 20))

        self._stack.set_visible_child_name(mode)
        self._refresh_presets()
        self._refresh_status()
        self._suppress = False
        self._sync_preview()

    def _refresh_status(self) -> None:
        import shutil
        from pathlib import Path

        daemon_ok = False
        try:
            daemon_ok = self._client.is_available()
        except Exception:
            pass
        kb_ok = shutil.which("ite8291r3-ctl") is not None
        lb = Path("/sys/class/leds/rgb:lightbar")
        lb_ok = (lb / "brightness").exists()

        for key, ok in (("daemon", daemon_ok), ("keyboard", kb_ok), ("lightbar", lb_ok)):
            lbl = self._status_labels[key]
            name = {"daemon": "Daemon", "keyboard": "Teclado", "lightbar": "Barra LED"}[key]
            lbl.set_label(f"● {name}")
            _paint(lbl, "label { color: %s; }" % ("#2EC27E" if ok else "#FF6B6B"))

    # ---------- preview ----------

    def _sync_preview(self) -> None:
        mode = self._current_mode()
        if mode == "off":
            self._preview.set_off()
        elif mode == "effect":
            name = self._current_effect()
            caps = _EFFECT_CAPS.get(name, frozenset())
            color = self._effect_ctl.hex if "color" in caps else "#FFFFFF"
            self._preview.set_effect(
                name, color,
                int(self._effect_speed.get_value()),
                self._effect_ctl.bri / 50,
            )
        elif mode == "solar":
            self._update_solar_now()
        else:  # fixed
            if self._sync_switch.get_active():
                c, b = self._synced_ctl.hex, self._synced_ctl.bri
                self._preview.set_static(c, b / 50, c, min(100, b * 2) / 100)
            else:
                self._preview.set_static(
                    self._kb_ctl.hex, self._kb_ctl.bri / 50,
                    self._lb_ctl.hex, self._lb_ctl.bri / 100,
                )

    def _update_solar_now(self) -> None:
        """Compute current solar interpolation for preview + gradient bar."""
        try:
            from astral import LocationInfo, sun

            from avell_rgb.solar import interpolate_solar, solar_t_from_elevation
            from avell_rgb.state import SolarConfig

            cfg = SolarConfig(
                latitude=float(self._solar_lat.get_text() or -23.55),
                longitude=float(self._solar_lon.get_text() or -46.63),
                day_color=self._solar_day.hex,
                night_color=self._solar_night.hex,
                day_brightness=self._solar_day.bri,
                night_brightness=self._solar_night.bri,
            )
            now = datetime.now(timezone.utc)
            color, kb_bri, lb_bri = interpolate_solar(cfg, now)
            loc = LocationInfo(latitude=cfg.latitude, longitude=cfg.longitude)
            t = solar_t_from_elevation(sun.elevation(loc.observer, now))
            self._solar_bar.update(cfg.night_color, cfg.day_color, t)
            pct = round(t * 100)
            self._solar_now.set_label(f"Agora: {color} · {pct}% dia · brilho {kb_bri}")
            self._preview.set_static(color, kb_bri / 50, color, lb_bri / 100)
        except Exception:
            log.exception("solar preview failed")

    # ---------- debounce ----------

    def _debounce(self, key: str, fn) -> None:
        old = self._pending.pop(key, None)
        if old is not None:
            GLib.source_remove(old)

        def run():
            self._pending.pop(key, None)
            try:
                fn()
            except Exception:
                log.exception("daemon call failed (%s)", key)
            return GLib.SOURCE_REMOVE

        self._pending[key] = GLib.timeout_add(_DEBOUNCE_MS, run)

    # ---------- handlers ----------

    def _current_mode(self) -> str:
        for mode, btn in self._mode_buttons.items():
            if btn.get_active():
                return mode
        return "fixed"

    def _current_effect(self) -> str:
        for name, btn in self._effect_buttons.items():
            if btn.get_active():
                return name
        return "breathing"

    def _on_mode_toggled(self, btn: Gtk.ToggleButton, mode: str) -> None:
        if self._suppress or not btn.get_active():
            return
        self._stack.set_visible_child_name(mode)
        self._sync_preview()
        self._debounce("mode", lambda: self._client.set_mode(mode))

    def _on_sync_toggled(self, switch: Gtk.Switch, _pspec) -> None:
        if self._suppress:
            return
        if switch.get_active():
            self._fixed_stack.set_visible_child_name("synced")
            self._sync_preview()
            self._debounce("color", lambda: self._client.set_color(
                self._synced_ctl.hex, self._synced_ctl.bri))
        else:
            # Restore the preserved per-device values from the daemon instead
            # of overwriting them with a copy of the synced color.
            c, b = self._synced_ctl.hex, self._synced_ctl.bri
            kb_c, kb_b = c, b
            lb_c, lb_b = c, min(100, b * 2)
            try:
                state = self._client.get_state()
                if state.get("keyboard_color"):
                    kb_c = state["keyboard_color"]
                    kb_b = int(state.get("keyboard_brightness", kb_b))
                if state.get("lightbar_color"):
                    lb_c = state["lightbar_color"]
                    lb_b = int(state.get("lightbar_brightness", lb_b))
            except Exception:
                log.warning("daemon unavailable; splitting from synced values")
            self._suppress = True
            self._kb_ctl.set(kb_c, kb_b)
            self._lb_ctl.set(lb_c, lb_b)
            self._suppress = False
            self._fixed_stack.set_visible_child_name("split")
            self._sync_preview()

            def unsync():
                self._client.set_device_color("keyboard", self._kb_ctl.hex, self._kb_ctl.bri)
                self._client.set_device_color("lightbar", self._lb_ctl.hex, self._lb_ctl.bri)

            self._debounce("color", unsync)

    def _on_synced_changed(self) -> None:
        if self._suppress:
            return
        self._sync_preview()
        self._debounce("color", lambda: self._client.set_color(
            self._synced_ctl.hex, self._synced_ctl.bri))

    def _on_kb_changed(self) -> None:
        if self._suppress:
            return
        self._sync_preview()
        self._debounce("kb", lambda: self._client.set_device_color(
            "keyboard", self._kb_ctl.hex, self._kb_ctl.bri))

    def _on_lb_changed(self) -> None:
        if self._suppress:
            return
        self._sync_preview()
        self._debounce("lb", lambda: self._client.set_device_color(
            "lightbar", self._lb_ctl.hex, self._lb_ctl.bri))

    def _on_effect_chip(self, btn: Gtk.ToggleButton, name: str) -> None:
        if self._suppress or not btn.get_active():
            return
        self._update_effect_caps(name)
        self._on_effect_changed()

    def _update_effect_caps(self, name: str) -> None:
        caps = _EFFECT_CAPS.get(name, frozenset({"color", "speed", "brightness"}))
        self._effect_ctl.box.get_first_child().set_visible("color" in caps)
        self._effect_speed_box.set_visible("speed" in caps)
        hints = []
        if "color" not in caps:
            hints.append("cor automática")
        if "speed" not in caps:
            hints.append("velocidade fixa")
        self._effect_hint.set_label(" · ".join(hints))
        self._effect_hint.set_visible(bool(hints))

    def _on_effect_changed(self) -> None:
        if self._suppress:
            return
        self._sync_preview()
        name = self._current_effect()
        color = self._effect_ctl.hex
        speed = int(self._effect_speed.get_value())
        bri = self._effect_ctl.bri
        self._debounce("effect", lambda: self._client.set_effect(name, color, speed, bri))

    def _on_solar_preview(self) -> None:
        if self._suppress:
            return
        if self._current_mode() == "solar":
            self._update_solar_now()

    def _on_apply_solar(self, _btn) -> None:
        try:
            lat = float(self._solar_lat.get_text())
            lon = float(self._solar_lon.get_text())
        except ValueError:
            log.warning("invalid latitude/longitude values")
            return
        try:
            self._client.set_solar(
                lat, lon,
                self._solar_day.hex, self._solar_night.hex,
                self._solar_day.bri, self._solar_night.bri,
            )
        except Exception:
            log.exception("failed to apply solar config")
        self._update_solar_now()

    # ---------- presets ----------

    def _refresh_presets(self) -> None:
        child = self._presets_flow.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._presets_flow.remove(child)
            child = nxt

        try:
            presets = self._client.list_presets()
        except Exception:
            presets = []

        for preset in presets:
            name = preset["name"]
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            chip.add_css_class("preset-chip")

            dot = Gtk.Box()
            dot.set_size_request(16, 16)
            dot.set_valign(Gtk.Align.CENTER)
            if preset.get("independent"):
                kb = preset.get("keyboard_color", preset["color"])
                lb = preset.get("lightbar_color", preset["color"])
                _paint(dot, "box { background: linear-gradient(90deg, %s 50%%, %s 50%%);"
                            " border-radius: 999px; }" % (kb, lb))
            else:
                _paint(dot, "box { background: %s; border-radius: 999px; }" % preset["color"])
            chip.append(dot)

            lbl = Gtk.Label(label=name)
            chip.append(lbl)

            delete = Gtk.Button(label="✕")
            delete.add_css_class("preset-delete")
            delete.set_valign(Gtk.Align.CENTER)
            delete.set_tooltip_text("Apagar preset")
            delete.connect("clicked", self._on_delete_preset, name)
            chip.append(delete)

            click = Gtk.GestureClick()
            click.connect("released", self._on_preset_clicked, name)
            chip.add_controller(click)

            self._presets_flow.append(chip)

    def _on_preset_clicked(self, _g, _n, _x, _y, name: str) -> None:
        try:
            self._client.apply_preset(name)
        except Exception:
            log.exception("failed to apply preset")
            return
        self._load_state()

    def _on_save_preset(self, _btn) -> None:
        dialog = Adw.AlertDialog(
            heading="Salvar preset",
            body="Guarda as cores e brilhos atuais do modo fixo.",
        )
        entry = Gtk.Entry(placeholder_text="Nome do preset")
        entry.set_margin_top(6)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("save", "Salvar")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(_d, response):
            if response != "save":
                return
            name = entry.get_text().strip()
            if not name:
                return
            try:
                self._client.save_preset(name)
            except Exception:
                log.exception("failed to save preset")
                return
            self._refresh_presets()

        dialog.connect("response", on_response)
        entry.connect("activate", lambda *_: dialog.close())
        dialog.present(self)

    def _on_delete_preset(self, _btn, name: str) -> None:
        dialog = Adw.AlertDialog(
            heading="Apagar preset?",
            body=f"“{name}” será removido.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Apagar")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_d, response):
            if response != "delete":
                return
            try:
                self._client.delete_preset(name)
            except Exception:
                log.exception("failed to delete preset")
                return
            self._refresh_presets()

        dialog.connect("response", on_response)
        dialog.present(self)

    # ---------- autostart ----------

    def _is_daemon_enabled(self) -> bool:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-enabled", "avell-rgb-daemon.service"],
                capture_output=True, text=True,
            )
            return r.stdout.strip() == "enabled"
        except FileNotFoundError:
            return False

    def _on_autostart_toggled(self, row, _pspec) -> None:
        action = "enable" if row.get_active() else "disable"
        try:
            subprocess.run(
                ["systemctl", "--user", action, "--now", "avell-rgb-daemon.service"],
                check=False, capture_output=True,
            )
        except FileNotFoundError:
            pass

    def _on_start_daemon(self, _banner) -> None:
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "avell-rgb-daemon.service"],
                check=False, capture_output=True,
            )
        except FileNotFoundError:
            return
        GLib.timeout_add(800, lambda: (self._load_state(), GLib.SOURCE_REMOVE)[1])
