"""Keyboard backend: wraps the ite8291r3-ctl CLI."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

BINARY = "ite8291r3-ctl"


class KeyboardBackend:
    def available(self) -> bool:
        return shutil.which(BINARY) is not None

    def apply_solid(self, rgb: tuple[int, int, int], brightness: int) -> None:
        rgb_str = "{},{},{}".format(*rgb)
        cmd = [BINARY, "monocolor", "--rgb", rgb_str, "-b", str(brightness)]
        self._run(cmd)

    def apply_effect(
        self,
        effect: str,
        color: str,
        speed: int,
        direction: Optional[str],
        brightness: int,
    ) -> None:
        cmd = [
            BINARY,
            "effect",
            effect,
            "-c",
            color,
            "-s",
            str(speed),
            "-b",
            str(brightness),
        ]
        if direction is not None:
            cmd.extend(["-d", direction])
        self._run(cmd)

    def off(self) -> None:
        self._run([BINARY, "off"])

    def _run(self, cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            log.warning("ite8291r3-ctl not found; keyboard command skipped")
        except subprocess.CalledProcessError as e:
            log.warning("ite8291r3-ctl exited %d: %s", e.returncode, e.stderr or "")
