"""Page 'Agora' — direct preview controls that write manual_state."""

from __future__ import annotations

import subprocess
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardEffect,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    VALID_EFFECTS,
)


def _reload_daemon() -> None:
    """Send SIGHUP to the daemon via systemctl --user."""
    try:
        subprocess.run(
            ["systemctl", "--user", "kill", "-s", "HUP", "avell-rgb-daemon.service"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass  # systemctl missing in test env


class NowPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config: Config = load_config()
        self._suspend_events = False

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        # Keyboard group
        kb_group = Adw.PreferencesGroup(title="Teclado")
        outer.append(kb_group)
        self._build_keyboard_rows(kb_group)

        # Lightbar group
        bar_group = Adw.PreferencesGroup(title="Barra inferior")
        outer.append(bar_group)
        self._build_lightbar_rows(bar_group)

        # Apply current state into the widgets on load
        self._load_from_config()

    # ---------- build ----------

    def _build_keyboard_rows(self, group: Adw.PreferencesGroup) -> None:
        mode_row = Adw.ComboRow(title="Modo")
        self.kb_mode_model = Gtk.StringList.new(["Cor sólida", "Efeito", "Desligado"])
        mode_row.set_model(self.kb_mode_model)
        mode_row.connect("notify::selected", self._on_kb_mode_changed)
        group.add(mode_row)
        self.kb_mode_row = mode_row

        color_row = Adw.ActionRow(title="Cor")
        self.kb_color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self.kb_color_btn.set_dialog(dlg)
        self.kb_color_btn.set_valign(Gtk.Align.CENTER)
        self.kb_color_btn.connect("notify::rgba", self._on_kb_color_changed)
        color_row.add_suffix(self.kb_color_btn)
        group.add(color_row)
        self.kb_color_row = color_row

        eff_row = Adw.ComboRow(title="Efeito")
        self.kb_effect_model = Gtk.StringList.new(list(VALID_EFFECTS))
        eff_row.set_model(self.kb_effect_model)
        eff_row.connect("notify::selected", self._on_kb_settings_changed)
        group.add(eff_row)
        self.kb_effect_row = eff_row

        speed_row = Adw.ActionRow(title="Velocidade")
        self.kb_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 10, 1)
        self.kb_speed.set_value(5)
        self.kb_speed.set_size_request(200, -1)
        self.kb_speed.set_valign(Gtk.Align.CENTER)
        self.kb_speed.connect("value-changed", self._on_kb_settings_changed)
        speed_row.add_suffix(self.kb_speed)
        group.add(speed_row)
        self.kb_speed_row = speed_row

        bright_row = Adw.ActionRow(title="Brilho")
        self.kb_brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 50, 1
        )
        self.kb_brightness.set_value(30)
        self.kb_brightness.set_size_request(200, -1)
        self.kb_brightness.set_valign(Gtk.Align.CENTER)
        self.kb_brightness.connect("value-changed", self._on_kb_settings_changed)
        bright_row.add_suffix(self.kb_brightness)
        group.add(bright_row)

    def _build_lightbar_rows(self, group: Adw.PreferencesGroup) -> None:
        color_row = Adw.ActionRow(title="Cor")
        self.bar_color_btn = Gtk.ColorDialogButton()
        dlg = Gtk.ColorDialog()
        dlg.set_with_alpha(False)
        self.bar_color_btn.set_dialog(dlg)
        self.bar_color_btn.set_valign(Gtk.Align.CENTER)
        self.bar_color_btn.connect("notify::rgba", self._on_bar_changed)
        color_row.add_suffix(self.bar_color_btn)
        group.add(color_row)

        bright_row = Adw.ActionRow(title="Brilho")
        self.bar_brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.bar_brightness.set_value(80)
        self.bar_brightness.set_size_request(200, -1)
        self.bar_brightness.set_valign(Gtk.Align.CENTER)
        self.bar_brightness.connect("value-changed", self._on_bar_changed)
        bright_row.add_suffix(self.bar_brightness)
        group.add(bright_row)

    # ---------- load / save ----------

    def _load_from_config(self) -> None:
        self._suspend_events = True
        state = self.config.manual_state
        if state is None:
            # Use first preset as a starting point
            if self.config.presets:
                state = next(iter(self.config.presets.values()))
        if state is not None:
            kb = state.keyboard
            bar = state.lightbar
            if isinstance(kb, KeyboardSolid):
                self.kb_mode_row.set_selected(0)
                self.kb_color_btn.set_rgba(hex_to_rgba(kb.color))
                self.kb_brightness.set_value(kb.brightness)
            elif isinstance(kb, KeyboardEffect):
                self.kb_mode_row.set_selected(1)
                for i, name in enumerate(VALID_EFFECTS):
                    if name == kb.effect:
                        self.kb_effect_row.set_selected(i)
                        break
                self.kb_speed.set_value(kb.speed)
                self.kb_brightness.set_value(kb.brightness)
            else:
                self.kb_mode_row.set_selected(2)
            self.bar_color_btn.set_rgba(hex_to_rgba(bar.color))
            self.bar_brightness.set_value(bar.brightness)
        self._update_row_visibility()
        self._suspend_events = False

    def _current_device_state(self) -> DeviceState:
        idx = self.kb_mode_row.get_selected()
        if idx == 0:
            kb = KeyboardSolid(
                color=rgba_to_hex(self.kb_color_btn.get_rgba()),
                brightness=int(self.kb_brightness.get_value()),
            )
        elif idx == 1:
            effect_idx = self.kb_effect_row.get_selected()
            kb = KeyboardEffect(
                effect=VALID_EFFECTS[effect_idx],
                color=rgba_to_hex(self.kb_color_btn.get_rgba()),
                speed=int(self.kb_speed.get_value()),
                direction=None,
                brightness=int(self.kb_brightness.get_value()),
            )
        else:
            kb = KeyboardOff()
        bar = LightbarState(
            color=rgba_to_hex(self.bar_color_btn.get_rgba()),
            brightness=int(self.bar_brightness.get_value()),
        )
        return DeviceState(keyboard=kb, lightbar=bar)

    def _write_and_reload(self) -> None:
        if self._suspend_events:
            return
        state = self._current_device_state()
        self.config = load_config()  # pick up anything else changed externally
        from dataclasses import replace

        self.config = replace(self.config, manual_state=state)
        save_config(self.config)
        _reload_daemon()

    # ---------- signals ----------

    def _on_kb_mode_changed(self, *args) -> None:
        self._update_row_visibility()
        self._write_and_reload()

    def _on_kb_color_changed(self, *args) -> None:
        self._write_and_reload()

    def _on_kb_settings_changed(self, *args) -> None:
        self._write_and_reload()

    def _on_bar_changed(self, *args) -> None:
        self._write_and_reload()

    def _update_row_visibility(self) -> None:
        idx = self.kb_mode_row.get_selected()
        is_solid = idx == 0
        is_effect = idx == 1
        self.kb_color_row.set_visible(is_solid or is_effect)
        self.kb_effect_row.set_visible(is_effect)
        self.kb_speed_row.set_visible(is_effect)
