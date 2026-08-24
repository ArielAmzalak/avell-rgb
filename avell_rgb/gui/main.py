"""GUI entry point. Routes to tray (Gtk3) or window (Gtk4) mode."""

from __future__ import annotations

import sys


def main() -> int:
    if "--tray" in sys.argv:
        return _run_tray()
    return _run_window()


def _run_tray() -> int:
    """Tray mode: Gtk3-based AppIndicator. No Gtk4 imports."""
    import subprocess

    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib
    from gi.repository import Gtk as Gtk3

    from avell_rgb.dbus_client import DaemonClient
    from avell_rgb.gui.tray import TrayIcon

    client = DaemonClient()

    def open_settings():
        subprocess.Popen(
            [sys.executable, "-m", "avell_rgb.gui.main"],
            start_new_session=True,
        )

    tray = TrayIcon(
        client=client,
        on_open_settings=open_settings,
        on_quit=Gtk3.main_quit,
    )

    def on_state_changed(mode, color, brightness):
        def apply_state():
            tray.update_state(mode, color, brightness)
            tray._rebuild_presets_menu()
            return False

        GLib.idle_add(apply_state)

    signal_connected = False

    def connect_signal():
        nonlocal signal_connected
        if signal_connected:
            return
        try:
            client.connect_state_changed(on_state_changed)
            signal_connected = True
        except Exception:
            pass

    connect_signal()

    attempts = 0

    def poll_initial_state():
        nonlocal attempts
        attempts += 1
        try:
            state = client.get_state()
        except Exception:
            return attempts < 15
        tray.update_state(state["mode"], state["color"], state["brightness"])
        connect_signal()
        return False

    if poll_initial_state():
        GLib.timeout_add(1000, poll_initial_state)

    Gtk3.main()
    return 0


def _run_window() -> int:
    """Window mode: Gtk4/libadwaita config window."""
    from avell_rgb.gui.app import AvellApp

    app = AvellApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
