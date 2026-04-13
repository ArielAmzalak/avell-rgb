from avell_rgb.state import (
    Config,
    EffectConfig,
    Preset,
    SolarConfig,
    VALID_EFFECTS,
    VALID_MODES,
)


def test_valid_modes():
    assert VALID_MODES == ("fixed", "solar", "effect", "off")


def test_valid_effects_includes_breathing():
    assert "breathing" in VALID_EFFECTS


def test_preset_round_trip():
    p = Preset(color="#00FFFF", brightness=30)
    d = p.to_dict()
    assert d == {"color": "#00FFFF", "brightness": 30}
    assert Preset.from_dict(d) == p


def test_effect_config_round_trip():
    e = EffectConfig(name="breathing", color="#00FFFF", speed=5)
    d = e.to_dict()
    assert d == {"name": "breathing", "color": "#00FFFF", "speed": 5}
    assert EffectConfig.from_dict(d) == e


def test_solar_config_round_trip():
    s = SolarConfig(
        latitude=-23.55,
        longitude=-46.63,
        day_color="#8FF0A4",
        night_color="#FF7800",
        day_brightness=50,
        night_brightness=20,
    )
    back = SolarConfig.from_dict(s.to_dict())
    assert back == s


def test_solar_config_no_apply_to():
    s = SolarConfig(
        latitude=0, longitude=0,
        day_color="#FFF", night_color="#000",
        day_brightness=50, night_brightness=10,
    )
    d = s.to_dict()
    assert "apply_to" not in d


def test_config_round_trip():
    cfg = Config(
        version=2,
        mode="fixed",
        color="#00FFFF",
        brightness=30,
        independent_colors=False,
        keyboard_color="#00FFFF",
        keyboard_brightness=30,
        lightbar_color="#00FFFF",
        lightbar_brightness=80,
        effect=EffectConfig(name="breathing", color="#00FFFF", speed=5),
        solar=SolarConfig(
            latitude=-23.55, longitude=-46.63,
            day_color="#8FF0A4", night_color="#FF7800",
            day_brightness=50, night_brightness=20,
        ),
        presets={"trabalho": Preset(color="#00FFFF", brightness=30)},
    )
    back = Config.from_dict(cfg.to_dict())
    assert back == cfg


def test_config_mode_must_be_valid():
    import pytest
    with pytest.raises(ValueError, match="invalid mode"):
        Config.from_dict({
            "version": 2, "mode": "bogus", "color": "#FFF", "brightness": 30,
            "independent_colors": False,
            "keyboard_color": "#FFF", "keyboard_brightness": 30,
            "lightbar_color": "#FFF", "lightbar_brightness": 80,
            "effect": {"name": "breathing", "color": "#FFF", "speed": 5},
            "solar": {
                "latitude": 0, "longitude": 0,
                "day_color": "#FFF", "night_color": "#000",
                "day_brightness": 50, "night_brightness": 10,
            },
            "presets": {},
        })


def test_config_resolved_colors_unified():
    cfg = Config(
        version=2, mode="fixed", color="#FF0000", brightness=25,
        independent_colors=False,
        keyboard_color="#IGNORED", keyboard_brightness=99,
        lightbar_color="#IGNORED", lightbar_brightness=99,
        effect=EffectConfig(name="breathing", color="#FF0000", speed=5),
        solar=SolarConfig(0, 0, "#FFF", "#000", 50, 10),
        presets={},
    )
    kb_color, kb_bri, lb_color, lb_bri = cfg.resolved_colors()
    assert kb_color == "#FF0000"
    assert kb_bri == 25
    assert lb_color == "#FF0000"
    assert lb_bri == 50  # 25 * 2


def test_config_resolved_colors_independent():
    cfg = Config(
        version=2, mode="fixed", color="#IGNORED", brightness=99,
        independent_colors=True,
        keyboard_color="#00FF00", keyboard_brightness=20,
        lightbar_color="#0000FF", lightbar_brightness=60,
        effect=EffectConfig(name="breathing", color="#FFF", speed=5),
        solar=SolarConfig(0, 0, "#FFF", "#000", 50, 10),
        presets={},
    )
    kb_color, kb_bri, lb_color, lb_bri = cfg.resolved_colors()
    assert kb_color == "#00FF00"
    assert kb_bri == 20
    assert lb_color == "#0000FF"
    assert lb_bri == 60
