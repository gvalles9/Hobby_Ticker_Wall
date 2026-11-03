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
    assert matrices_created[0]["options"] is options


def test_rgbmatrix_panel_rejects_non_divisible_display_width(monkeypatch):
    panel_class, options_created, matrices_created = _load_rgbmatrix_panel(monkeypatch)
    panel = panel_class()

    with pytest.raises(ValueError, match="must be divisible by panel count"):
        panel.init_matrix(width=191)

    assert options_created
    assert not matrices_created
