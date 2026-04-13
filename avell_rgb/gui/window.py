"""Single-page config window: mode selector, color, presets, solar, effect, preferences."""

from __future__ import annotations

import logging
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from avell_rgb.dbus_client import DaemonClient
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import VALID_EFFECTS

log = logging.getLogger("avell_rgb.gui.window")


class AvellWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, client: DaemonClient):
        super().__init__(application=application)
        self._client = client
        self._suppress = False

        self.set_default_size(500, 700)
        self.set_title("Avell RGB")

        toolbar = Adw.ToolbarView()
        self.set_content(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        toolbar.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=600)
        scroll.set_child(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        self._build_mode_section(outer)
        self._build_color_section(outer)
        self._build_effect_section(outer)
        self._build_presets_section(outer)
        self._build_solar_section(outer)
        self._build_prefs_section(outer)

        self._load_state()

    def _build_mode_section(self, parent: Gtk.Box) -> None:
        group = Adw.PreferencesGroup(title="Modo")
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, homogeneous=True)
        mode_box.set_margin_top(6)
        mode_box.set_margin_bottom(6)
        self._mode_buttons = {}
        first = None
        for label, mode in [("Fixo", "fixed"), ("Solar", "solar"), ("Efeito", "effect"), ("Off", "off")]:
            btn = Gtk.ToggleButton(label=label)
            if first is not None:
                btn.set_group(first)
            else:
                first = btn
            btn.connect("toggled", self._on_mode_toggled, mode)
            mode_box.append(btn)
            self._mode_buttons[mode] = btn
        group.add(mode_box)
        parent.append(group)

    def _build_color_section(self, parent: Gtk.Box) -> None:
        self._color_group = Adw.PreferencesGroup(title="Cor & Brilho")

        color_row = Adw.ActionRow(title="Cor")
        self._color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self._color_btn.set_dialog(dlg)
        self._color_btn.set_valign(Gtk.Align.CENTER)
        self._color_btn.connect("notify::rgba", self._on_color_changed)
        color_row.add_suffix(self._color_btn)
        self._color_group.add(color_row)

        bri_row = Adw.ActionRow(title="Brilho")
        self._brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 50, 1)
        self._brightness.set_size_request(200, -1)
        self._brightness.set_valign(Gtk.Align.CENTER)
        self._brightness.set_draw_value(True)
        self._brightness.connect("value-changed", self._on_color_changed)
        bri_row.add_suffix(self._brightness)
        self._color_group.add(bri_row)

        parent.append(self._color_group)

    def _build_effect_section(self, parent: Gtk.Box) -> None:
        self._effect_group = Adw.PreferencesGroup(title="Efeito")

        eff_row = Adw.ComboRow(title="Tipo")
        eff_row.set_model(Gtk.StringList.new(list(VALID_EFFECTS)))
        eff_row.connect("notify::selected", self._on_effect_changed)
        self._effect_group.add(eff_row)
        self._effect_combo = eff_row

        eff_color_row = Adw.ActionRow(title="Cor")
        self._effect_color = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self._effect_color.set_dialog(dlg)
        self._effect_color.set_valign(Gtk.Align.CENTER)
        self._effect_color.connect("notify::rgba", self._on_effect_changed)
        eff_color_row.add_suffix(self._effect_color)
        self._effect_group.add(eff_color_row)

        speed_row = Adw.ActionRow(title="Velocidade")
        self._effect_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 10, 1)
        self._effect_speed.set_size_request(200, -1)
        self._effect_speed.set_valign(Gtk.Align.CENTER)
        self._effect_speed.set_draw_value(True)
        self._effect_speed.connect("value-changed", self._on_effect_changed)
        speed_row.add_suffix(self._effect_speed)
        self._effect_group.add(speed_row)

        parent.append(self._effect_group)

    def _build_presets_section(self, parent: Gtk.Box) -> None:
        self._presets_group = Adw.PreferencesGroup(title="Presets")
        self._presets_outer = parent
        parent.append(self._presets_group)

    def _refresh_presets(self) -> None:
        parent = self._presets_outer
        idx = _child_index(parent, self._presets_group)
        parent.remove(self._presets_group)

        self._presets_group = Adw.PreferencesGroup(title="Presets")

        try:
            presets = self._client.list_presets()
        except Exception:
            presets = []

        for preset in presets:
            name = preset["name"]
            color = preset["color"]
            brightness = preset["brightness"]
            row = Adw.ActionRow(title=name, subtitle=f"{color} · brilho {brightness}")

            swatch = Gtk.Frame()
            swatch.set_size_request(24, 24)
            swatch.set_valign(Gtk.Align.CENTER)
            css = Gtk.CssProvider()
            css.load_from_data(f"frame {{ background: {color}; border-radius: 4px; }}".encode())
            swatch.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            row.add_prefix(swatch)

            apply_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            apply_btn.set_valign(Gtk.Align.CENTER)
            apply_btn.set_tooltip_text("Aplicar")
            apply_btn.connect("clicked", self._on_preset_apply, name)
            row.add_suffix(apply_btn)

            self._presets_group.add(row)

        _insert_child_at(parent, self._presets_group, idx)

    def _build_solar_section(self, parent: Gtk.Box) -> None:
        self._solar_group = Adw.PreferencesGroup(title="Configuração Solar")

        lat_row = Adw.EntryRow(title="Latitude")
        self._solar_lat = lat_row
        self._solar_group.add(lat_row)

        lon_row = Adw.EntryRow(title="Longitude")
        self._solar_lon = lon_row
        self._solar_group.add(lon_row)

        day_row = Adw.ActionRow(title="Cor de dia")
        self._solar_day_color = Gtk.ColorDialogButton()
        self._solar_day_color.set_dialog(Gtk.ColorDialog())
        self._solar_day_color.set_valign(Gtk.Align.CENTER)
        day_row.add_suffix(self._solar_day_color)
        self._solar_group.add(day_row)

        night_row = Adw.ActionRow(title="Cor de noite")
        self._solar_night_color = Gtk.ColorDialogButton()
        self._solar_night_color.set_dialog(Gtk.ColorDialog())
        self._solar_night_color.set_valign(Gtk.Align.CENTER)
        night_row.add_suffix(self._solar_night_color)
        self._solar_group.add(night_row)

        parent.append(self._solar_group)

    def _build_prefs_section(self, parent: Gtk.Box) -> None:
        group = Adw.PreferencesGroup(title="Preferências")

        autostart_row = Adw.SwitchRow(
            title="Iniciar no login",
            subtitle="Daemon systemd de usuário",
        )
        autostart_row.set_active(self._is_daemon_enabled())
        autostart_row.connect("notify::active", self._on_autostart_toggled)
        group.add(autostart_row)

        parent.append(group)

    # ---------- load / sync ----------

    def _load_state(self) -> None:
        self._suppress = True
        try:
            state = self._client.get_state()
            mode = state["mode"]
            color = state["color"]
            effect_name = state["effect"]
            brightness = state["brightness"]
        except Exception:
            mode, color, effect_name, brightness = "fixed", "#808080", "breathing", 30

        for m, btn in self._mode_buttons.items():
            btn.set_active(m == mode)
        self._color_btn.set_rgba(hex_to_rgba(color))
        self._brightness.set_value(brightness)

        for i, name in enumerate(VALID_EFFECTS):
            if name == effect_name:
                self._effect_combo.set_selected(i)
                break

        self._update_section_visibility(mode)
        self._refresh_presets()
        self._suppress = False

    def on_state_changed(self, mode: str, color: str, brightness: int) -> None:
        """Called externally when daemon emits StateChanged."""
        self._suppress = True
        for m, btn in self._mode_buttons.items():
            btn.set_active(m == mode)
        self._color_btn.set_rgba(hex_to_rgba(color))
        self._brightness.set_value(brightness)
        self._update_section_visibility(mode)
        self._suppress = False

    def _update_section_visibility(self, mode: str) -> None:
        self._color_group.set_visible(mode == "fixed")
        self._effect_group.set_visible(mode == "effect")
        self._solar_group.set_visible(mode == "solar")

    # ---------- signals ----------

    def _on_mode_toggled(self, btn, mode: str) -> None:
        if self._suppress or not btn.get_active():
            return
        self._update_section_visibility(mode)
        try:
            self._client.set_mode(mode)
        except Exception:
            log.exception("failed to set mode")

    def _on_color_changed(self, *_args) -> None:
        if self._suppress:
            return
        color = rgba_to_hex(self._color_btn.get_rgba())
        brightness = int(self._brightness.get_value())
        try:
            self._client.set_color(color, brightness)
        except Exception:
            log.exception("failed to set color")

    def _on_effect_changed(self, *_args) -> None:
        if self._suppress:
            return
        idx = self._effect_combo.get_selected()
        name = VALID_EFFECTS[idx]
        color = rgba_to_hex(self._effect_color.get_rgba())
        speed = int(self._effect_speed.get_value())
        try:
            self._client.set_effect(name, color, speed)
        except Exception:
            log.exception("failed to set effect")

    def _on_preset_apply(self, _btn, name: str) -> None:
        try:
            self._client.apply_preset(name)
        except Exception:
            log.exception("failed to apply preset")

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


def _child_index(box: Gtk.Box, target: Gtk.Widget) -> int:
    """Find the index of target among box's children."""
    child = box.get_first_child()
    i = 0
    while child is not None:
        if child is target:
            return i
        child = child.get_next_sibling()
        i += 1
    return -1


def _insert_child_at(box: Gtk.Box, widget: Gtk.Widget, index: int) -> None:
    """Insert widget at a given index in a Gtk.Box."""
    if index <= 0:
        box.prepend(widget)
        return
    child = box.get_first_child()
    i = 0
    while child is not None:
        if i == index - 1:
            box.insert_child_after(widget, child)
            return
        child = child.get_next_sibling()
        i += 1
    box.append(widget)
