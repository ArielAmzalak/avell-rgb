import os
from pathlib import Path

import pytest

from avell_rgb.backends.lightbar import LightbarBackend


@pytest.fixture
def fake_sysfs(tmp_path: Path) -> Path:
    sysfs = tmp_path / "rgb_lightbar"
    sysfs.mkdir()
    (sysfs / "brightness").write_text("0\n")
    (sysfs / "multi_intensity").write_text("255 255 255\n")
    return sysfs


def test_available_false_when_sysfs_missing(tmp_path):
    bad = tmp_path / "nope"
    b = LightbarBackend(sysfs=bad)
    assert b.available() is False


def test_available_true_with_writable_sysfs(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    assert b.available() is True


def test_apply_writes_color_and_brightness(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    b.apply((0, 255, 255), 80)
    assert (fake_sysfs / "multi_intensity").read_text().strip() == "0 255 255"
    assert (fake_sysfs / "brightness").read_text().strip() == "80"


def test_off_sets_brightness_zero(fake_sysfs):
    b = LightbarBackend(sysfs=fake_sysfs)
    b.off()
    assert (fake_sysfs / "brightness").read_text().strip() == "0"


def test_apply_handles_permission_denied_gracefully(fake_sysfs, monkeypatch):
    b = LightbarBackend(sysfs=fake_sysfs)

    def deny(*args, **kwargs):
        raise PermissionError("no write")

    monkeypatch.setattr(Path, "write_text", deny)
    # Must not raise
    b.apply((255, 0, 0), 50)
