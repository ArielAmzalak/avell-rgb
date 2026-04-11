"""Shared test fixtures. Fake backends for daemon-loop tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FakeKeyboardBackend:
    """Records every call; used by daemon-loop tests."""

    available_returns: bool = True
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def available(self) -> bool:
        return self.available_returns

    def apply_solid(self, rgb, brightness):
        self.calls.append(("apply_solid", (rgb, brightness)))

    def apply_effect(self, effect, color, speed, direction, brightness):
        self.calls.append(("apply_effect", (effect, color, speed, direction, brightness)))

    def off(self):
        self.calls.append(("off", ()))


@dataclass
class FakeLightbarBackend:
    available_returns: bool = True
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def available(self) -> bool:
        return self.available_returns

    def apply(self, rgb, brightness):
        self.calls.append(("apply", (rgb, brightness)))

    def off(self):
        self.calls.append(("off", ()))
