"""Lightbar backend: writes to the kernel sysfs LED interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_SYSFS = Path("/sys/class/leds/rgb:lightbar")


class LightbarBackend:
    def __init__(self, sysfs: Path = DEFAULT_SYSFS):
        self.sysfs = sysfs

    def available(self) -> bool:
        brightness = self.sysfs / "brightness"
        multi = self.sysfs / "multi_intensity"
        if not (brightness.exists() and multi.exists()):
            return False
        return os.access(brightness, os.W_OK) and os.access(multi, os.W_OK)

    def apply(self, rgb: tuple[int, int, int], brightness: int) -> None:
        r, g, b = rgb
        try:
            (self.sysfs / "multi_intensity").write_text(f"{r} {g} {b}\n")
            (self.sysfs / "brightness").write_text(f"{int(brightness)}\n")
        except (PermissionError, FileNotFoundError, OSError) as e:
            log.warning("lightbar write failed: %s", e)

    def off(self) -> None:
        try:
            (self.sysfs / "brightness").write_text("0\n")
        except (PermissionError, FileNotFoundError, OSError) as e:
            log.warning("lightbar off failed: %s", e)
