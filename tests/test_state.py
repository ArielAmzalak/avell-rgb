from avell_rgb.state import (
    Config,
    DeviceState,
    KeyboardEffect,
    KeyboardOff,
    KeyboardSolid,
    LightbarState,
    ScheduleBand,
    SolarConfig,
)


def test_keyboard_solid_round_trip():
    k = KeyboardSolid(color="#00FFFF", brightness=30)
    d = k.to_dict()
    assert d == {"type": "solid", "color": "#00FFFF", "brightness": 30}
    assert KeyboardSolid.from_dict(d) == k


def test_keyboard_effect_round_trip():
    k = KeyboardEffect(
        effect="wave", color="rainbow", speed=5, direction="right", brightness=50
    )
    d = k.to_dict()
    assert d["type"] == "effect"
    from_back = KeyboardEffect.from_dict(d)
    assert from_back == k


def test_keyboard_off_round_trip():
    k = KeyboardOff()
    assert k.to_dict() == {"type": "off"}
    assert KeyboardOff.from_dict({"type": "off"}) == k


def test_device_state_with_solid_kb():
    state = DeviceState(
        keyboard=KeyboardSolid(color="#FF0000", brightness=20),
        lightbar=LightbarState(color="#00FF00", brightness=50),
    )
    d = state.to_dict()
    assert d["keyboard"]["type"] == "solid"
    assert d["lightbar"]["color"] == "#00FF00"
    back = DeviceState.from_dict(d)
    assert back == state


def test_device_state_with_effect_kb():
    state = DeviceState(
        keyboard=KeyboardEffect(
            effect="breathing", color="purple", speed=3, direction=None, brightness=40
        ),
        lightbar=LightbarState(color="#FFFFFF", brightness=100),
    )
    back = DeviceState.from_dict(state.to_dict())
    assert back == state


def test_schedule_band_round_trip():
    b = ScheduleBand(start="07:00", end="18:00", preset="trabalho")
    assert b.to_dict() == {"start": "07:00", "end": "18:00", "preset": "trabalho"}
    assert ScheduleBand.from_dict(b.to_dict()) == b


def test_solar_config_round_trip():
    s = SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#FFFFFF",
        night_color="#FF6600",
        day_brightness=50,
        night_brightness=20,
        apply_to=("keyboard", "lightbar"),
    )
    back = SolarConfig.from_dict(s.to_dict())
    assert back == s


def test_config_round_trip():
    cfg = Config(
        version=1,
        mode="schedule",
        manual_paused=False,
        manual_state=None,
        presets={
            "trabalho": DeviceState(
                keyboard=KeyboardSolid(color="#00FFFF", brightness=30),
                lightbar=LightbarState(color="#00FFFF", brightness=80),
            ),
            "off": DeviceState(
                keyboard=KeyboardOff(),
                lightbar=LightbarState(color="#000000", brightness=0),
            ),
        },
        schedule=[ScheduleBand(start="07:00", end="18:00", preset="trabalho")],
        solar=SolarConfig(
            latitude=0.0,
            longitude=0.0,
            day_color="#FFFFFF",
            night_color="#000000",
            day_brightness=50,
            night_brightness=10,
            apply_to=("keyboard", "lightbar"),
        ),
    )
    back = Config.from_dict(cfg.to_dict())
    assert back == cfg


def test_config_mode_must_be_valid():
    import pytest
    with pytest.raises(ValueError):
        Config.from_dict(
            {
                "version": 1,
                "mode": "bogus",
                "manual_paused": False,
                "manual_state": None,
                "presets": {},
                "schedule": [],
                "solar": SolarConfig(
                    latitude=0.0,
                    longitude=0.0,
                    day_color="#000000",
                    night_color="#000000",
                    day_brightness=0,
                    night_brightness=0,
                    apply_to=(),
                ).to_dict(),
            }
        )
