"""GUI entry point."""

from __future__ import annotations

import sys

from avell_rgb.gui.app import AvellApp


def main() -> int:
    app = AvellApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
