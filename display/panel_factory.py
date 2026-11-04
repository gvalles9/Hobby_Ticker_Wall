"""
Panel factory - selects the appropriate RGBPanel driver at runtime.

Tries to import the piomatter (Pi 5) driver on Raspberry Pi 5 hardware, or
the rgbmatrix (Pi 3/4) driver on earlier boards. The selected panel is cached
as a singleton.

On desktop machines where neither hardware driver is available, the pygame
simulator is used as a final fallback so the app always runs.
"""

import importlib

_panel = None


def is_pi5():
    """Detect if running on a Raspberry Pi 5."""
    try:
        with open("/proc/device-tree/model", "r") as f:
            return "Raspberry Pi 5" in f.read()
    except Exception:
        return False


def get_panel():
    """Return the singleton RGBPanel instance, creating it if needed."""
    global _panel
    if _panel is not None:
        return _panel

    # Check for Raspberry Pi 5 first
    if is_pi5():
        try:
            mod = importlib.import_module("display.rgbpanel_piomatter")
            _panel = mod.PiomatterPanel()
            return _panel
        except (ImportError, Exception):
            pass

    # Try Pi 3/4 rgbmatrix driver
    try:
        mod = importlib.import_module("display.rgbpanel_rgbmatrix")
        _panel = mod.RGBMatrixPanel()
        return _panel
    except (ImportError, Exception):
        pass

    # Fallback attempt for piomatter if not previously attempted
    if not is_pi5():
        try:
            mod = importlib.import_module("display.rgbpanel_piomatter")
            _panel = mod.PiomatterPanel()
            return _panel
        except (ImportError, Exception):
            pass

    # Final fallback: desktop pygame simulator
    try:
        mod = importlib.import_module("display.rgbpanel_simulator")
        _panel = mod.SimulatorPanel()
        return _panel
    except ImportError:
        pass

    raise ImportError(
        "No RGB panel driver available. "
        "Install adafruit-blinka-raspberry-pi5-piomatter (Pi 5), "
        "rgbmatrix (Pi 3/4), or pygame (desktop simulator). "
        "See platforms/ for platform-specific requirements files."
    )


def reset_panel():
    """Clear the cached panel (used for testing)."""
    global _panel
    _panel = None
