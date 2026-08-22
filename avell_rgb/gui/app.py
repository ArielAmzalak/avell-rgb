"""AdwApplication: config window only (no tray — tray is separate process)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from avell_rgb.dbus_client import DaemonClient  # noqa: E402
from avell_rgb.gui.style import CSS  # noqa: E402
from avell_rgb.gui.window import AvellWindow  # noqa: E402


class AvellApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.avellrgb.Avell",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._window: AvellWindow | None = None
        self._client = DaemonClient()

    def do_activate(self):
        if self._window is None:
            style = Adw.StyleManager.get_default()
            style.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

            provider = Gtk.CssProvider()
            provider.load_from_data(CSS.encode())
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self._window = AvellWindow(application=self, client=self._client)
        self._window.present()
