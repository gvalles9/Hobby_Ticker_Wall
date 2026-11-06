import importlib.util
import types
from pathlib import Path

import pytest


def _load_rgbmatrix_panel(monkeypatch):
    options_created = []
    matrices_created = []

    class FakeOptions:
        def __init__(self):
            options_created.append(self)

    def fake_matrix(**kwargs):
        matrices_created.append(kwargs)
        return types.SimpleNamespace()

    fake_rgbmatrix = types.ModuleType("rgbmatrix")
    fake_rgbmatrix.RGBMatrix = fake_matrix
    fake_rgbmatrix.RGBMatrixOptions = FakeOptions
    fake_rgbmatrix.graphics = types.SimpleNamespace()
    monkeypatch.setitem(__import__("sys").modules, "rgbmatrix", fake_rgbmatrix)

    path = Path(__file__).parents[1] / "display" / "rgbpanel_rgbmatrix.py"
    spec = importlib.util.spec_from_file_location("rgbpanel_rgbmatrix_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RGBMatrixPanel, options_created, matrices_created


def test_rgbmatrix_panel_configures_three_panel_chain(monkeypatch):
    from setup import screen

    panel_class, options_created, matrices_created = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    panel.init_matrix(width=screen.WIDTH, height=screen.HEIGHT)

    options = options_created[0]
    assert options.cols == screen.PANEL_WIDTH
    assert options.rows == screen.PANEL_HEIGHT
    assert options.chain_length == 3
    assert options.hardware_mapping == "adafruit-hat-pwm"
    assert matrices_created[0]["options"] is options


@pytest.mark.parametrize(
    "hat_pwm, expected_mapping",
    [(True, "adafruit-hat-pwm"), (False, "adafruit-hat")],
)
def test_single_bonnet_uses_adafruit_mapping(monkeypatch, hat_pwm, expected_mapping):
    panel_class, options_created, _ = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    panel.init_matrix(hat_pwm=hat_pwm)

    assert options_created[0].hardware_mapping == expected_mapping


@pytest.mark.parametrize("hat_pwm", [True, False])
def test_triple_bonnet_uses_regular_mapping(monkeypatch, hat_pwm):
    from setup import screen

    panel_class, options_created, _ = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    panel.init_matrix(
        width=screen.WIDTH,
        height=screen.HEIGHT,
        hat_pwm=hat_pwm,
        bonnet_type="triple",
    )

    options = options_created[0]
    assert options.hardware_mapping == "regular"
    # Daisy-chained from port 1: three panels on one chain, no parallel rows.
    assert options.chain_length == 3
    assert options.parallel == 1


def test_invalid_bonnet_type_raises(monkeypatch):
    panel_class, options_created, matrices_created = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    with pytest.raises(ValueError, match="Invalid bonnet type"):
        panel.init_matrix(bonnet_type="quad")

    assert options_created
    assert not matrices_created


def test_rgbmatrix_panel_rejects_non_divisible_display_width(monkeypatch):
    panel_class, options_created, matrices_created = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    with pytest.raises(ValueError, match="must be divisible by panel count"):
        panel.init_matrix(width=191)

    assert options_created
    assert not matrices_created
