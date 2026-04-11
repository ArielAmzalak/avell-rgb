"""Schedule page: time-band editor + solar mode."""

from __future__ import annotations

import subprocess
from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from avell_rgb.config import load_config, save_config
from avell_rgb.gui.color_helpers import hex_to_rgba, rgba_to_hex
from avell_rgb.state import ScheduleBand, SolarConfig


def _reload_daemon() -> None:
    # See page_now._reload_daemon for why --kill-whom=main is required.
    try:
        subprocess.run(
            [
                "systemctl",
                "--user",
                "kill",
                "--kill-whom=main",
                "-s",
                "HUP",
                "avell-rgb-daemon.service",
            ],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


class SchedulePage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.config = load_config()

        clamp = Adw.Clamp(maximum_size=700)
        self.append(clamp)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)
        clamp.set_child(outer)

        mode_group = Adw.PreferencesGroup(title="Modo automático")
        self.mode_row = Adw.ComboRow(title="Modo")
        self.mode_row.set_model(
            Gtk.StringList.new(["Por faixa horária", "Seguir o sol"])
        )
        self.mode_row.set_selected(0 if self.config.mode == "schedule" else 1)
        self.mode_row.connect("notify::selected", self._on_mode_changed)
        mode_group.add(self.mode_row)
        outer.append(mode_group)

        # Schedule bands
        self.bands_group = Adw.PreferencesGroup(title="Faixas horárias")
        outer.append(self.bands_group)
        add_row = Adw.ActionRow()
        add_btn = Gtk.Button(label="+ Adicionar faixa")
        add_btn.set_valign(Gtk.Align.CENTER)
        add_btn.connect("clicked", self._on_add_band)
        add_row.add_suffix(add_btn)
        self.bands_group.add(add_row)
        self._refresh_bands()

        # Solar config
        self.solar_group = Adw.PreferencesGroup(title="Configuração solar")
        outer.append(self.solar_group)
        self._build_solar_rows()

        self._update_sections_visibility()

    # ---------- bands ----------

    def _refresh_bands(self) -> None:
        self.config = load_config()
        parent = self.bands_group.get_parent()
        parent.remove(self.bands_group)
        self.bands_group = Adw.PreferencesGroup(title="Faixas horárias")
        parent.prepend(self.bands_group)  # keep above solar
        # Re-add button
        add_row = Adw.ActionRow()
        add_btn = Gtk.Button(label="+ Adicionar faixa")
        add_btn.set_valign(Gtk.Align.CENTER)
        add_btn.connect("clicked", self._on_add_band)
        add_row.add_suffix(add_btn)
        self.bands_group.add(add_row)
        for i, band in enumerate(self.config.schedule):
            row = self._make_band_row(i, band)
            self.bands_group.add(row)

    def _make_band_row(self, idx: int, band: ScheduleBand) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=f"{band.start} – {band.end}",
            subtitle=f"Preset: {band.preset}",
        )
        rm = Gtk.Button(icon_name="edit-delete-symbolic")
        rm.set_valign(Gtk.Align.CENTER)
        rm.set_has_frame(False)
        rm.connect("clicked", lambda _b, i=idx: self._on_remove_band(i))
        row.add_suffix(rm)
        return row

    def _on_add_band(self, _btn) -> None:
        self._open_band_editor(None)

    def _on_remove_band(self, idx: int) -> None:
        self.config = load_config()
        new_sched = list(self.config.schedule)
        del new_sched[idx]
        self.config = replace(self.config, schedule=new_sched)
        save_config(self.config)
        _reload_daemon()
        self._refresh_bands()

    def _open_band_editor(self, idx: int | None) -> None:
        self.config = load_config()
        dialog = Adw.Window()
        dialog.set_modal(True)
        dialog.set_transient_for(self.get_root())
        dialog.set_default_size(400, 300)
        dialog.set_title("Nova faixa" if idx is None else "Editar faixa")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        start_entry = Gtk.Entry(placeholder_text="HH:MM início (ex: 07:00)")
        end_entry = Gtk.Entry(placeholder_text="HH:MM fim (ex: 18:00)")
        preset_row = Adw.ComboRow(title="Preset")
        preset_names = list(self.config.presets.keys()) or ["(sem presets)"]
        preset_row.set_model(Gtk.StringList.new(preset_names))

        box.append(start_entry)
        box.append(end_entry)
        box.append(preset_row)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dialog.close())
        btns.append(cancel)
        save_btn = Gtk.Button(label="Salvar")
        save_btn.add_css_class("suggested-action")

        def on_save(_b):
            try:
                start = start_entry.get_text().strip()
                end = end_entry.get_text().strip()
                p_idx = preset_row.get_selected()
                preset = preset_names[p_idx]
                new_band = ScheduleBand(start=start, end=end, preset=preset)
            except Exception:
                return
            self.config = load_config()
            new_sched = list(self.config.schedule)
            new_sched.append(new_band)
            self.config = replace(self.config, schedule=new_sched)
            save_config(self.config)
            _reload_daemon()
            self._refresh_bands()
            dialog.close()

        save_btn.connect("clicked", on_save)
        btns.append(save_btn)
        box.append(btns)

        dialog.set_content(box)
        dialog.present()

    # ---------- solar ----------

    def _build_solar_rows(self) -> None:
        solar = self.config.solar
        lat_row = Adw.ActionRow(title="Latitude")
        self.lat_entry = Gtk.Entry()
        self.lat_entry.set_text(str(solar.latitude))
        self.lat_entry.set_valign(Gtk.Align.CENTER)
        self.lat_entry.connect("changed", self._on_solar_changed)
        lat_row.add_suffix(self.lat_entry)
        self.solar_group.add(lat_row)

        lon_row = Adw.ActionRow(title="Longitude")
        self.lon_entry = Gtk.Entry()
        self.lon_entry.set_text(str(solar.longitude))
        self.lon_entry.set_valign(Gtk.Align.CENTER)
        self.lon_entry.connect("changed", self._on_solar_changed)
        lon_row.add_suffix(self.lon_entry)
        self.solar_group.add(lon_row)

        day_row = Adw.ActionRow(title="Cor de dia")
        self.day_color = Gtk.ColorDialogButton()
        self.day_color.set_dialog(Gtk.ColorDialog())
        self.day_color.set_rgba(hex_to_rgba(solar.day_color))
        self.day_color.set_valign(Gtk.Align.CENTER)
        self.day_color.connect("notify::rgba", self._on_solar_changed)
        day_row.add_suffix(self.day_color)
        self.solar_group.add(day_row)

        night_row = Adw.ActionRow(title="Cor de noite")
        self.night_color = Gtk.ColorDialogButton()
        self.night_color.set_dialog(Gtk.ColorDialog())
        self.night_color.set_rgba(hex_to_rgba(solar.night_color))
        self.night_color.set_valign(Gtk.Align.CENTER)
        self.night_color.connect("notify::rgba", self._on_solar_changed)
        night_row.add_suffix(self.night_color)
        self.solar_group.add(night_row)

    def _on_solar_changed(self, *_a) -> None:
        try:
            lat = float(self.lat_entry.get_text())
            lon = float(self.lon_entry.get_text())
        except ValueError:
            return
        self.config = load_config()
        new_solar = SolarConfig(
            latitude=lat,
            longitude=lon,
            day_color=rgba_to_hex(self.day_color.get_rgba()),
            night_color=rgba_to_hex(self.night_color.get_rgba()),
            day_brightness=self.config.solar.day_brightness,
            night_brightness=self.config.solar.night_brightness,
            apply_to=self.config.solar.apply_to,
        )
        self.config = replace(self.config, solar=new_solar)
        save_config(self.config)
        _reload_daemon()

    # ---------- mode ----------

    def _on_mode_changed(self, *_a) -> None:
        idx = self.mode_row.get_selected()
        new_mode = "schedule" if idx == 0 else "solar"
        self.config = load_config()
        self.config = replace(self.config, mode=new_mode)
        save_config(self.config)
        _reload_daemon()
        self._update_sections_visibility()

    def _update_sections_visibility(self) -> None:
        is_schedule = self.mode_row.get_selected() == 0
        self.bands_group.set_visible(is_schedule)
        self.solar_group.set_visible(not is_schedule)
