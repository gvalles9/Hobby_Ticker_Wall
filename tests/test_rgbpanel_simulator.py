from display.rgbpanel_simulator import _fit_dimensions


def test_fit_dimensions_preserves_matrix_aspect_ratio():
    assert _fit_dimensions((1920, 320), (800, 600)) == (800, 133)


def test_fit_dimensions_uses_full_height_when_window_is_wide():
    assert _fit_dimensions((1920, 320), (2400, 600)) == (2400, 400)


def test_fit_dimensions_handles_small_window():
    assert _fit_dimensions((1920, 320), (1, 1)) == (1, 1)
