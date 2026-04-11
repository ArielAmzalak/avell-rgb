"""Presets page: list, add, edit, remove named DeviceStates."""

from __future__ import annotations

from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import (
    DeviceState,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
)


class PresetsPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config = load_config()

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_hexpand(True)
        title = Gtk.Label(label="Presets")
        title.add_css_class("title-2")
        title.set_xalign(0)
        title.set_hexpand(True)
        header.append(title)

        add_btn = Gtk.Button(label="+ Novo preset")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_clicked)
        header.append(add_btn)
        outer.append(header)

        self.group = Adw.PreferencesGroup()
        outer.append(self.group)

        self._refresh_list()

    def _refresh_list(self) -> None:
        # Remove existing rows
        child = self.group.get_first_child()
        # Adw.PreferencesGroup children accessible via internal list; rebuild by clearing:
        # Simpler: recreate the whole group
        parent = self.group.get_parent()
        parent.remove(self.group)
        self.group = Adw.PreferencesGroup()
        parent.append(self.group)

        self.config = load_config()
        for name, state in self.config.presets.items():
            row = self._make_row(name, state)
            self.group.add(row)

    def _make_row(self, name: str, state: DeviceState) -> Adw.ActionRow:
        row = Adw.ActionRow(title=name)
        # Color swatches
        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        kb_swatch = self._swatch_for_keyboard(state)
        bar_swatch = Gtk.Frame()
        bar_swatch.set_size_request(24, 24)
        bar_swatch.set_valign(Gtk.Align.CENTER)
        bar_swatch.set_tooltip_text(f"Barra: {state.lightbar.color}")
        css = Gtk.CssProvider()
        css.load_from_data(
            f"frame {{ background: {state.lightbar.color}; }}".encode()
        )
        bar_swatch.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        swatches.append(kb_swatch)
        swatches.append(bar_swatch)
        row.add_suffix(swatches)

        menu_btn = Gtk.MenuButton(icon_name="view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)

        popover = Gtk.Popover()
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_top(6)
        menu_box.set_margin_bottom(6)
        menu_box.set_margin_start(6)
        menu_box.set_margin_end(6)
        edit = Gtk.Button(label="Editar")
        edit.set_has_frame(False)
        edit.connect("clicked", lambda _b, n=name: self._on_edit(n))
        menu_box.append(edit)
        dup = Gtk.Button(label="Duplicar")
        dup.set_has_frame(False)
        dup.connect("clicked", lambda _b, n=name: self._on_duplicate(n))
        menu_box.append(dup)
        rem = Gtk.Button(label="Remover")
        rem.set_has_frame(False)
        rem.connect("clicked", lambda _b, n=name: self._on_remove(n))
        menu_box.append(rem)
        popover.set_child(menu_box)
        menu_btn.set_popover(popover)

        row.add_suffix(menu_btn)
        return row

    def _swatch_for_keyboard(self, state: DeviceState) -> Gtk.Widget:
        frame = Gtk.Frame()
        frame.set_size_request(24, 24)
        frame.set_valign(Gtk.Align.CENTER)
        kb = state.keyboard
        if isinstance(kb, KeyboardSolid):
            color = kb.color
            tip = f"Teclado: {color}"
        elif isinstance(kb, KeyboardOff):
            color = "#222222"
            tip = "Teclado: desligado"
        else:
            color = "#666666"
            tip = f"Teclado: efeito {getattr(kb, 'effect', '?')}"
        frame.set_tooltip_text(tip)
        css = Gtk.CssProvider()
        css.load_from_data(f"frame {{ background: {color}; }}".encode())
        frame.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        return frame

    # ---------- actions ----------

    def _on_add_clicked(self, _btn) -> None:
        self._open_editor(name=None)

    def _on_edit(self, name: str) -> None:
        self._open_editor(name=name)

    def _on_duplicate(self, name: str) -> None:
        self.config = load_config()
        src = self.config.presets[name]
        new_name = name + "_copy"
        i = 2
        while new_name in self.config.presets:
            new_name = f"{name}_copy{i}"
            i += 1
        new_presets = dict(self.config.presets)
        new_presets[new_name] = src
        self.config = replace(self.config, presets=new_presets)
        save_config(self.config)
        self._refresh_list()

    def _on_remove(self, name: str) -> None:
        self.config = load_config()
        new_presets = {k: v for k, v in self.config.presets.items() if k != name}
        self.config = replace(self.config, presets=new_presets)
        save_config(self.config)
        self._refresh_list()

    def _open_editor(self, name: str | None) -> None:
        self.config = load_config()
        dialog = Adw.Window()
        dialog.set_modal(True)
        dialog.set_transient_for(self.get_root())
        dialog.set_default_size(480, 420)
        dialog.set_title("Editar preset" if name else "Novo preset")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Nome do preset")
        if name is not None:
            name_entry.set_text(name)
            name_entry.set_editable(False)
        box.append(name_entry)

        kb_color_btn = Gtk.ColorDialogButton()
        kb_color_btn.set_dialog(Gtk.ColorDialog())
        box.append(Gtk.Label(label="Cor do teclado", xalign=0))
        box.append(kb_color_btn)

        kb_bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 50, 1)
        box.append(Gtk.Label(label="Brilho do teclado", xalign=0))
        box.append(kb_bri)

        bar_color_btn = Gtk.ColorDialogButton()
        bar_color_btn.set_dialog(Gtk.ColorDialog())
        box.append(Gtk.Label(label="Cor da barra", xalign=0))
        box.append(bar_color_btn)

        bar_bri = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        box.append(Gtk.Label(label="Brilho da barra", xalign=0))
        box.append(bar_bri)

        if name is not None:
            state = self.config.presets[name]
            if isinstance(state.keyboard, KeyboardSolid):
                kb_color_btn.set_rgba(hex_to_rgba(state.keyboard.color))
                kb_bri.set_value(state.keyboard.brightness)
            bar_color_btn.set_rgba(hex_to_rgba(state.lightbar.color))
            bar_bri.set_value(state.lightbar.brightness)
        else:
            kb_color_btn.set_rgba(hex_to_rgba("#FFFFFF"))
            kb_bri.set_value(30)
            bar_color_btn.set_rgba(hex_to_rgba("#FFFFFF"))
            bar_bri.set_value(80)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dialog.close())
        btns.append(cancel)
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")

        def on_save(_b):
            self.config = load_config()
            new_name = name_entry.get_text().strip() or "novo"
            new_state = DeviceState(
                keyboard=KeyboardSolid(
                    color=rgba_to_hex(kb_color_btn.get_rgba()),
                    brightness=int(kb_bri.get_value()),
                ),
                lightbar=LightbarState(
                    color=rgba_to_hex(bar_color_btn.get_rgba()),
                    brightness=int(bar_bri.get_value()),
                ),
            )
            new_presets = dict(self.config.presets)
            new_presets[new_name] = new_state
            self.config = replace(self.config, presets=new_presets)
            save_config(self.config)
            self._refresh_list()
            dialog.close()

        save.connect("clicked", on_save)
        btns.append(save)
        box.append(btns)

        dialog.set_content(box)
        dialog.present()
