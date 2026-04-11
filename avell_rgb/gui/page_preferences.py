"""Preferences page: simple toggles + about info."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from avell_rgb import __version__
from avell_rgb.config import CONFIG_PATH, load_config, save_config


class PreferencesPage(Gtk.Box):
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

        group = Adw.PreferencesGroup(title="Comportamento")

        autostart_row = Adw.SwitchRow(
            title="Iniciar daemon no login",
            subtitle="Habilita o serviço systemd de usuário",
        )
        autostart_row.set_active(self._is_daemon_enabled())
        autostart_row.connect("notify::active", self._on_autostart_toggled)
        group.add(autostart_row)

        pause_row = Adw.SwitchRow(
            title="Manter estado manual ao fechar",
            subtitle="Quando ligado, fechar a janela não limpa o preview ao vivo",
        )
        pause_row.set_active(self.config.manual_paused)
        pause_row.connect("notify::active", self._on_pause_toggled)
        group.add(pause_row)

        open_row = Adw.ActionRow(title="Abrir config.json no editor")
        open_btn = Gtk.Button(label="Abrir")
        open_btn.set_valign(Gtk.Align.CENTER)
        open_btn.connect("clicked", self._on_open_config)
        open_row.add_suffix(open_btn)
        group.add(open_row)

        outer.append(group)

        about = Adw.PreferencesGroup(title="Sobre")
        version_row = Adw.ActionRow(title="Versão", subtitle=__version__)
        about.add(version_row)
        license_row = Adw.ActionRow(title="Licença", subtitle="MIT")
        about.add(license_row)
        outer.append(about)

    def _is_daemon_enabled(self) -> bool:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-enabled", "avell-rgb-daemon.service"],
                capture_output=True,
                text=True,
            )
            return r.stdout.strip() == "enabled"
        except FileNotFoundError:
            return False

    def _on_autostart_toggled(self, row, _pspec) -> None:
        action = "enable" if row.get_active() else "disable"
        try:
            subprocess.run(
                ["systemctl", "--user", action, "--now", "avell-rgb-daemon.service"],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass

    def _on_pause_toggled(self, row, _pspec) -> None:
        self.config = load_config()
        self.config = replace(self.config, manual_paused=row.get_active())
        save_config(self.config)

    def _on_open_config(self, _btn) -> None:
        try:
            subprocess.Popen(["xdg-open", str(CONFIG_PATH)])
        except FileNotFoundError:
            pass
