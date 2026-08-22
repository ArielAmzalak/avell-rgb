"""Tests for the single-zone lightbar effect frames."""
import pytest

from avell_rgb.lightbar_fx import frame
from avell_rgb.state import VALID_EFFECTS

BASE = (255, 0, 0)


@pytest.mark.parametrize("name", VALID_EFFECTS)
@pytest.mark.parametrize("t", [0.0, 0.31, 1.7, 12.9])
def test_frame_in_range(name, t):
    rgb, bri = frame(name, BASE, 5, 100, t)
    assert all(isinstance(c, int) and 0 <= c <= 255 for c in rgb)
    assert isinstance(bri, int)
    assert 0 <= bri <= 100


def test_breathing_pulses_brightness_keeps_color():
    samples = [frame("breathing", BASE, 5, 100, t) for t in
               [i * 0.1 for i in range(60)]]
    bris = [b for _, b in samples]
    assert all(rgb == BASE for rgb, _ in samples)
    assert max(bris) > 90
    assert min(bris) < 30


def test_wave_cycles_hue_at_full_brightness():
    (rgb1, bri1) = frame("wave", BASE, 5, 80, 0.0)
    (rgb2, bri2) = frame("wave", BASE, 5, 80, 1.5)
    assert bri1 == bri2 == 80
    assert rgb1 != rgb2


def test_hue_cycle_effects_ignore_base_color():
    for name in ("wave", "rainbow", "marquee"):
        a = frame(name, (255, 0, 0), 5, 100, 0.7)
        b = frame(name, (0, 0, 255), 5, 100, 0.7)
        assert a == b, name


def test_random_stable_within_step_changes_between_steps():
    # speed 5 → spd 1.0, step length 1/1.1 s
    a1 = frame("random", BASE, 5, 100, 0.10)
    a2 = frame("random", BASE, 5, 100, 0.50)
    b = frame("random", BASE, 5, 100, 2.5)
    assert a1 == a2
    assert a1 != b


def test_speed_zero_still_animates():
    (_, bri1) = frame("breathing", BASE, 0, 100, 0.0)
    (_, bri2) = frame("breathing", BASE, 0, 100, 4.0)
    assert bri1 != bri2


def test_unknown_effect_falls_back_to_static():
    rgb, bri = frame("nope", BASE, 5, 70, 3.3)
    assert rgb == BASE
    assert bri == 70
