"""Keyboard backend: wraps the ite8291r3-ctl CLI."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

BINARY = "ite8291r3-ctl"

# ite8291r3-ctl effect -c only accepts these palette names, not hex colors.
# Canonical RGB anchors used to map an arbitrary hex color to the nearest
# palette name by Euclidean distance in RGB space.
_EFFECT_PALETTE: dict[str, tuple[int, int, int]] = {
    "red": (255, 0, 0),
    "orange": (255, 128, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "teal": (0, 255, 255),
    "purple": (255, 0, 255),
}
_EFFECT_PALETTE_PASSTHROUGH = set(_EFFECT_PALETTE) | {"none", "random"}

# Each ite8291r3-ctl effect accepts a different subset of flags. Passing a
# rejected flag makes the CLI fail with "<attr> attr is not needed by effect".
# Probed empirically against firmware 34.3.0.0.
_EFFECT_CAPS: dict[str, frozenset[str]] = {
    "breathing": frozenset({"color", "speed", "brightness"}),
    "wave": frozenset({"speed", "brightness"}),
    "random": frozenset({"color", "speed", "brightness"}),
    "rainbow": frozenset({"brightness"}),
    "ripple": frozenset({"color", "speed", "brightness"}),
    "marquee": frozenset({"speed", "brightness"}),
    "raindrop": frozenset({"color", "speed", "brightness"}),
    "aurora": frozenset({"color", "speed", "brightness"}),
    "fireworks": frozenset({"color", "speed", "brightness"}),
}


def _resolve_effect_color(color: str) -> str:
    """Accept a palette name verbatim or map #RRGGBB to the nearest palette."""
    if color in _EFFECT_PALETTE_PASSTHROUGH:
        return color
    if color.startswith("#") and len(color) == 7:
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except ValueError:
            return "random"
        best_name = "random"
        best_dist = float("inf")
        for name, (pr, pg, pb) in _EFFECT_PALETTE.items():
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_dist:
                best_dist = d
                best_name = name
        return best_name
    return "random"


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
        caps = _EFFECT_CAPS.get(effect, frozenset({"color", "speed", "brightness"}))
        cmd = [BINARY, "effect", effect]
        if "color" in caps:
            cmd.extend(["-c", _resolve_effect_color(color)])
        if "speed" in caps:
            cmd.extend(["-s", str(speed)])
        if "brightness" in caps:
            cmd.extend(["-b", str(brightness)])
        if direction is not None and "speed" in caps:
            cmd.extend(["-d", direction])
        self._run(cmd)

    def off(self) -> None:
        self._run([BINARY, "off"])

    def _run(self, cmd: list[str]) -> None:
        log.info("apply: %s", " ".join(cmd[1:]))
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError:
            log.warning("ite8291r3-ctl not found; keyboard command skipped")
        except subprocess.CalledProcessError as e:
            log.warning("ite8291r3-ctl exited %d: %s", e.returncode, e.stderr or "")
