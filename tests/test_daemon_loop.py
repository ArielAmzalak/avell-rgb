from datetime import datetime
from math import isinf

import pytest

from avell_rgb.daemon.main import DaemonCore
from avell_rgb.state import Config, EffectConfig, Preset, SolarConfig
from tests.conftest import FakeKeyboardBackend, FakeLightbarBackend


def _cfg(
    mode: str = "fixed",
    color: str = "#00FFFF",
    brightness: int = 30,
    independent_colors: bool = False,
    keyboard_color: str = "#00FFFF",
    keyboard_brightness: int = 30,
    lightbar_color: str = "#00FFFF",
    lightbar_brightness: int = 80,
    effect_name: str = "breathing",
    effect_color: str = "#00FFFF",
    effect_speed: int = 5,
    presets: dict | None = None,
) -> Config:
    return Config(
        version=2,
        mode=mode,
        color=color,
        brightness=brightness,
        independent_colors=independent_colors,
        keyboard_color=keyboard_color,
        keyboard_brightness=keyboard_brightness,
        lightbar_color=lightbar_color,
        lightbar_brightness=lightbar_brightness,
        effect=EffectConfig(name=effect_name, color=effect_color, speed=effect_speed),
        solar=SolarConfig(0, 0, "#FFFFFF", "#000000", 50, 10),
        presets=presets or {"work": Preset(color="#00FFFF", brightness=30)},
    )


def test_fixed_mode_applies_unified_color():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(config=_cfg(), keyboard=kb, lightbar=bar)
    core.apply_current()
    assert kb.calls[-1] == ("apply_solid", ((0, 255, 255), 30))
    assert bar.calls[-1] == ("apply", ((0, 255, 255), 60))  # 30*2


def test_fixed_mode_independent_colors():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(
            independent_colors=True,
            keyboard_color="#FF0000", keyboard_brightness=20,
            lightbar_color="#00FF00", lightbar_brightness=70,
        ),
        keyboard=kb, lightbar=bar,
    )
    core.apply_current()
    assert kb.calls[-1] == ("apply_solid", ((255, 0, 0), 20))
    assert bar.calls[-1] == ("apply", ((0, 255, 0), 70))


def test_effect_mode_applies_effect_and_lightbar():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(mode="effect", effect_name="breathing", effect_color="#FF0000", effect_speed=7),
        keyboard=kb, lightbar=bar,
    )
    core.apply_current()
    assert kb.calls[-1][0] == "apply_effect"
    assert kb.calls[-1][1][0] == "breathing"
    assert bar.calls[-1][0] == "apply"


def test_off_mode_turns_everything_off():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(config=_cfg(mode="off"), keyboard=kb, lightbar=bar)
    core.apply_current()
    assert kb.calls[-1] == ("off", ())
    assert bar.calls[-1] == ("off", ())


def test_solar_mode_applies_interpolated():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(mode="solar"),
        keyboard=kb, lightbar=bar,
        clock=lambda: datetime(2026, 4, 10, 12, 0),
    )
    core.apply_current()
    assert kb.calls[-1][0] == "apply_solid"
    assert bar.calls[-1][0] == "apply"


def test_sleep_seconds_fixed_is_infinite():
    core = DaemonCore(
        config=_cfg(mode="fixed"),
        keyboard=FakeKeyboardBackend(), lightbar=FakeLightbarBackend(),
    )
    assert isinf(core.sleep_seconds())


def test_sleep_seconds_solar_is_60():
    core = DaemonCore(
        config=_cfg(mode="solar"),
        keyboard=FakeKeyboardBackend(), lightbar=FakeLightbarBackend(),
    )
    assert core.sleep_seconds() == 60.0


def test_sleep_seconds_off_is_infinite():
    core = DaemonCore(
        config=_cfg(mode="off"),
        keyboard=FakeKeyboardBackend(), lightbar=FakeLightbarBackend(),
    )
    assert isinf(core.sleep_seconds())


def test_unavailable_keyboard_does_not_crash():
    kb = FakeKeyboardBackend(available_returns=False)
    bar = FakeLightbarBackend()
    core = DaemonCore(config=_cfg(), keyboard=kb, lightbar=bar)
    core.apply_current()
    assert kb.calls == []
    assert bar.calls[-1][0] == "apply"


def test_apply_catches_backend_exception():
    class ExplodingKb(FakeKeyboardBackend):
        def apply_solid(self, rgb, brightness):
            raise RuntimeError("USB gone")

    kb = ExplodingKb()
    bar = FakeLightbarBackend()
    core = DaemonCore(config=_cfg(), keyboard=kb, lightbar=bar)
    core.apply_current()  # should not raise
    assert bar.calls[-1][0] == "apply"


def test_effect_mode_animates_lightbar():
    now = [100.0]
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(mode="effect", effect_name="breathing", effect_color="#FF0000"),
        keyboard=kb, lightbar=bar, mono=lambda: now[0],
    )
    core.apply_current()
    assert core.animating()
    assert core.tick_seconds() is not None
    frames_before = len(bar.calls)
    now[0] += 0.4
    core.animate_step()
    assert len(bar.calls) == frames_before + 1
    assert bar.calls[-1][0] == "apply"


def test_animate_step_dedups_identical_frames():
    now = [100.0]
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(
        config=_cfg(mode="effect", effect_name="breathing", effect_color="#FF0000"),
        keyboard=kb, lightbar=bar, mono=lambda: now[0],
    )
    core.apply_current()
    frames = len(bar.calls)
    core.animate_step()  # same t → same frame → no write
    assert len(bar.calls) == frames


def test_animate_step_noop_outside_effect_mode():
    kb, bar = FakeKeyboardBackend(), FakeLightbarBackend()
    core = DaemonCore(config=_cfg(mode="fixed"), keyboard=kb, lightbar=bar)
    core.apply_current()
    frames = len(bar.calls)
    core.animate_step()
    assert len(bar.calls) == frames
    assert core.tick_seconds() is None
