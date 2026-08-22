"""AppIndicator tray icon with mode/preset/effect menus."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator3
from gi.repository import Gtk as Gtk3

from avell_rgb.dbus_client import DaemonClient
from avell_rgb.state import VALID_EFFECTS

log = logging.getLogger("avell_rgb.gui.tray")

_ICON_TEMPLATE = '''\
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22">
  <circle cx="11" cy="11" r="9" fill="{color}" stroke="#333" stroke-width="1"/>
</svg>'''


class TrayIcon:
    def __init__(
        self,
        client: DaemonClient,
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._client = client
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit
        self._icon_dir = tempfile.mkdtemp(prefix="avell-rgb-icon-")
        self._current_color = "#808080"
        self._suppress_signals = False

        self._write_icon("#808080")
        self._indicator = AppIndicator3.Indicator.new(
            "avell-rgb",
            os.path.join(self._icon_dir, "icon"),
            AppIndicator3.IndicatorCategory.HARDWARE,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._build_menu()

    def _write_icon(self, color: str) -> str:
        path = os.path.join(self._icon_dir, "icon.svg")
        with open(path, "w") as f:
            f.write(_ICON_TEMPLATE.format(color=color))
        return path

    def update_state(self, mode: str, color: str, brightness: int) -> None:
        self._current_color = color
        self._write_icon(color)
        self._indicator.set_icon_full(
            os.path.join(self._icon_dir, "icon"), f"Avell RGB: {mode}"
        )
        self._suppress_signals = True
        for item, item_mode in self._mode_items:
            item.set_active(item_mode == mode)
        self._suppress_signals = False

    def _build_menu(self) -> None:
        menu = Gtk3.Menu()

        self._mode_items = []
        group = []
        for label, mode in [("Fixo", "fixed"), ("Solar", "solar")]:
            item = Gtk3.RadioMenuItem.new_with_label(group, label)
            group = item.get_group()
            item.connect("toggled", self._on_mode_toggled, mode)
            menu.append(item)
            self._mode_items.append((item, mode))

        effect_item = Gtk3.RadioMenuItem.new_with_label(group, "Efeito")
        group = effect_item.get_group()
        effect_sub = Gtk3.Menu()
        for eff_name in VALID_EFFECTS:
            eff_item = Gtk3.MenuItem.new_with_label(eff_name)
            eff_item.connect("activate", self._on_effect_selected, eff_name)
            effect_sub.append(eff_item)
        effect_sub.append(Gtk3.SeparatorMenuItem())
        customize = Gtk3.MenuItem.new_with_label("Personalizar...")
        customize.connect("activate", lambda _: self._on_open_settings())
        effect_sub.append(customize)
        effect_item.set_submenu(effect_sub)
        effect_item.connect("toggled", self._on_mode_toggled, "effect")
        menu.append(effect_item)
        self._mode_items.append((effect_item, "effect"))

        off_item = Gtk3.RadioMenuItem.new_with_label(group, "Desligado")
        off_item.connect("toggled", self._on_mode_toggled, "off")
        menu.append(off_item)
        self._mode_items.append((off_item, "off"))

        menu.append(Gtk3.SeparatorMenuItem())

        presets_item = Gtk3.MenuItem.new_with_label("Presets")
        self._presets_sub = Gtk3.Menu()
        presets_item.set_submenu(self._presets_sub)
        menu.append(presets_item)
        self._rebuild_presets_menu()

        menu.append(Gtk3.SeparatorMenuItem())

        settings_item = Gtk3.MenuItem.new_with_label("Configurações...")
        settings_item.connect("activate", lambda _: self._on_open_settings())
        menu.append(settings_item)

        quit_item = Gtk3.MenuItem.new_with_label("Sair")
        quit_item.connect("activate", lambda _: self._on_quit())
        menu.append(quit_item)

        menu.show_all()
        self._indicator.set_menu(menu)

    def _rebuild_presets_menu(self) -> None:
        for child in self._presets_sub.get_children():
            self._presets_sub.remove(child)
        try:
            presets = self._client.list_presets()
        except Exception:
            presets = []
        for preset in presets:
            name = preset["name"]
            color = preset["color"]
            item = Gtk3.MenuItem.new_with_label(f"{name}  ({color})")
            item.connect("activate", self._on_preset_selected, name)
            self._presets_sub.append(item)
        self._presets_sub.show_all()

    def _on_mode_toggled(self, item, mode: str) -> None:
        if self._suppress_signals or not item.get_active():
            return
        try:
            self._client.set_mode(mode)
        except Exception:
            log.exception("failed to set mode %s", mode)

    def _on_effect_selected(self, _item, effect_name: str) -> None:
        try:
            state = self._client.get_state()
            eff = state.get("effect", {})
            if not isinstance(eff, dict):
                eff = {}
            self._client.set_effect(
                effect_name,
                eff.get("color", state["color"]),
                eff.get("speed", 5),
                eff.get("brightness", 25),
            )
        except Exception:
            log.exception("failed to set effect %s", effect_name)

    def _on_preset_selected(self, _item, name: str) -> None:
        try:
            self._client.apply_preset(name)
        except Exception:
            log.exception("failed to apply preset %s", name)
