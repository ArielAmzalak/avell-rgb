"""AdwApplication subclass."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from avell_rgb.gui.window import AvellWindow


class AvellApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.avellrgb.Avell")
        self.window: AvellWindow | None = None

    def do_activate(self):
        if self.window is None:
            self.window = AvellWindow(application=self)
        self.window.present()
