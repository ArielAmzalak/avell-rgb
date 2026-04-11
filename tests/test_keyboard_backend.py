from unittest.mock import patch

import pytest

from avell_rgb.backends.keyboard import KeyboardBackend


@pytest.fixture
def backend():
    return KeyboardBackend()


def test_available_true_when_binary_present(backend, monkeypatch):
    monkeypatch.setattr(
        "avell_rgb.backends.keyboard.shutil.which",
        lambda name: "/usr/bin/" + name,
    )
    assert backend.available() is True


def test_available_false_when_binary_missing(backend, monkeypatch):
    monkeypatch.setattr(
        "avell_rgb.backends.keyboard.shutil.which", lambda name: None
    )
    assert backend.available() is False


def test_apply_solid_calls_monocolor(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_solid((0, 255, 255), 30)
        args = run.call_args.args[0]
        assert args[0].endswith("ite8291r3-ctl")
        assert "monocolor" in args
        assert "--rgb" in args
        assert "0,255,255" in args
        assert "-b" in args
        assert "30" in args


def test_apply_effect_calls_effect(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="breathing",
            color="random",
            speed=5,
            direction="right",
            brightness=40,
        )
        args = run.call_args.args[0]
        assert "effect" in args
        assert "breathing" in args
        assert "-c" in args
        assert "random" in args
        assert "-s" in args
        assert "5" in args
        assert "-d" in args
        assert "right" in args
        assert "-b" in args
        assert "40" in args


def test_apply_effect_without_direction_omits_flag(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="breathing",
            color="purple",
            speed=3,
            direction=None,
            brightness=25,
        )
        args = run.call_args.args[0]
        assert "-d" not in args


@pytest.mark.parametrize(
    "hex_color,expected_palette",
    [
        ("#FF0000", "red"),
        ("#FF8000", "orange"),
        ("#FFFF00", "yellow"),
        ("#00FF00", "green"),
        ("#0000FF", "blue"),
        ("#00FFFF", "teal"),
        ("#800080", "purple"),
        ("#FF00FF", "purple"),  # magenta → nearest is purple
        ("#010203", "blue"),    # near-black → nearest hue is blue
    ],
)
def test_apply_effect_hex_color_maps_to_palette(backend, hex_color, expected_palette):
    """ite8291r3-ctl effect -c only accepts palette names, not hex.
    Backend must translate hex to the nearest supported palette."""
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="breathing",  # effect that accepts -c
            color=hex_color,
            speed=5,
            direction=None,
            brightness=30,
        )
        args = run.call_args.args[0]
        c_idx = args.index("-c")
        assert args[c_idx + 1] == expected_palette


def test_apply_effect_passthrough_palette_name(backend):
    """Palette names already valid should pass through unchanged."""
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="breathing",
            color="teal",
            speed=5,
            direction=None,
            brightness=30,
        )
        args = run.call_args.args[0]
        c_idx = args.index("-c")
        assert args[c_idx + 1] == "teal"


def test_apply_effect_wave_omits_color(backend):
    """wave rejects -c per ite8291r3-ctl ('color attr is not needed by effect')."""
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="wave",
            color="#FF0000",
            speed=5,
            direction="right",
            brightness=30,
        )
        args = run.call_args.args[0]
        assert "-c" not in args
        assert "-s" in args
        assert "-b" in args


def test_apply_effect_marquee_omits_color(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="marquee",
            color="#00FF00",
            speed=3,
            direction=None,
            brightness=20,
        )
        args = run.call_args.args[0]
        assert "-c" not in args


def test_apply_effect_rainbow_omits_color_and_speed(backend):
    """rainbow rejects both -c and -s per ite8291r3-ctl."""
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.apply_effect(
            effect="rainbow",
            color="#FF0000",
            speed=5,
            direction=None,
            brightness=40,
        )
        args = run.call_args.args[0]
        assert "-c" not in args
        assert "-s" not in args
        assert "-b" in args
        assert "40" in args


def test_off_calls_off_subcommand(backend):
    with patch("avell_rgb.backends.keyboard.subprocess.run") as run:
        backend.off()
        args = run.call_args.args[0]
        assert args[-1] == "off"


def test_nonzero_exit_does_not_raise(backend, caplog):
    import subprocess

    with patch(
        "avell_rgb.backends.keyboard.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "ite8291r3-ctl"),
    ):
        backend.off()  # must not raise
