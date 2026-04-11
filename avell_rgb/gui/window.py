"""Main application window. Sidebar + content stack with 4 pages."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402


def _stub_page(title: str) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_top(48)
    box.set_margin_bottom(48)
    box.set_margin_start(48)
    box.set_margin_end(48)
    label = Gtk.Label(label=title)
    label.add_css_class("title-1")
    box.append(label)
    box.append(Gtk.Label(label="(em construção)"))
    return box


class AvellWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(application=application)
        self.set_default_size(900, 620)
        self.set_title("Avell RGB")

        split = Adw.NavigationSplitView()
        self.set_content(split)

        # Sidebar
        sidebar = Adw.NavigationPage()
        sidebar.set_title("Avell RGB")
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_header = Adw.HeaderBar()
        sidebar_header.add_css_class("flat")
        sidebar_box.append(sidebar_header)

        self.stack = Adw.ViewStack()
        from avell_rgb.gui.page_now import NowPage

        self.stack.add_titled(NowPage(), "now", "Agora")
        from avell_rgb.gui.page_presets import PresetsPage

        self.stack.add_titled(PresetsPage(), "presets", "Presets")
        from avell_rgb.gui.page_schedule import SchedulePage

        self.stack.add_titled(SchedulePage(), "schedule", "Agenda")
        from avell_rgb.gui.page_preferences import PreferencesPage

        self.stack.add_titled(PreferencesPage(), "preferences", "Preferências")

        sidebar_list = Adw.ViewSwitcher()
        sidebar_list.set_stack(self.stack)
        sidebar_list.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        sidebar_box.append(sidebar_list)
        sidebar.set_child(sidebar_box)
        split.set_sidebar(sidebar)

        # Content
        content = Adw.NavigationPage()
        content.set_title("Avell RGB")
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_header = Adw.HeaderBar()
        content_box.append(content_header)
        content_box.append(self.stack)
        content.set_child(content_box)
        split.set_content(content)

        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, *_args) -> bool:
        """On window close, clear manual_state unless user opted into 'keep'."""
        from dataclasses import replace

        from avell_rgb.config import load_config, save_config
        from avell_rgb.gui.page_now import _reload_daemon

        cfg = load_config()
        if not cfg.manual_paused and cfg.manual_state is not None:
            cfg = replace(cfg, manual_state=None)
            save_config(cfg)
            _reload_daemon()
        return False  # allow close
