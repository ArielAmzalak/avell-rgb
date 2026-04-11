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
            effect="wave",
            color="rainbow",
            speed=5,
            direction="right",
            brightness=40,
        )
        args = run.call_args.args[0]
        assert "effect" in args
        assert "wave" in args
        assert "-c" in args
        assert "rainbow" in args
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
