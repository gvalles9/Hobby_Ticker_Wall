import contextlib
import importlib.util
import types
from pathlib import Path

from setup import screen

MODULE_PATH = Path(__file__).resolve().parents[1] / "flight-tracker.py"
SPEC = importlib.util.spec_from_file_location("flight_tracker_module", MODULE_PATH)
flight_tracker_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(flight_tracker_module)


class _SplashImage:
    width = screen.PANEL_WIDTH
    height = screen.PANEL_HEIGHT

    def convert(self, mode):
        return self

    def tobytes(self):
        return bytes(self.width * self.height * 3)


class _SplashPanel:
    def __init__(self):
        self.pixels = []
        self.text = []

    def set_pixel(self, canvas, x, y, r, g, b):
        self.pixels.append((x, y))

    def draw_text(self, canvas, font, x, y, colour, text):
        self.text.append((x, y, text))

    def swap(self, canvas):
        pass


def _fake_qrcode(matrix):
    class FakeQRCode:
        def __init__(self, **kwargs):
            pass

        def add_data(self, url):
            pass

        def make(self, fit):
            pass

        def get_matrix(self):
            return matrix

    return types.SimpleNamespace(QRCode=FakeQRCode)


def test_splash_logo_and_qr_use_separate_panels(monkeypatch):
    panel = _SplashPanel()

    class FakeImageModule:
        @staticmethod
        def open(path):
            return _SplashImage()

    flight_tracker_module.render_splash(
        panel,
        "canvas",
        FakeImageModule,
        "font",
        url="http://example.test",
        qrcode=_fake_qrcode([[True, False, True], [False, True, False]]),
        ERROR_CORRECT_L=1,
    )

    splash_pixels = [(x, y) for x, y in panel.pixels if x < screen.PANEL_WIDTH]
    qr_pixels = [(x, y) for x, y in panel.pixels if x >= screen.PANEL_WIDTH]
    assert splash_pixels
    assert qr_pixels
    assert min(x for x, _ in qr_pixels) >= screen.WIDTH - screen.PANEL_WIDTH


def test_splash_loading_text_uses_middle_panel(monkeypatch):
    panel = _SplashPanel()

    class FakeImageModule:
        @staticmethod
        def open(path):
            return _SplashImage()

    flight_tracker_module.render_splash(panel, "canvas", FakeImageModule, "font")

    assert (8, 12, "HOBBY TICKER") in panel.text
    assert (screen.PANEL_WIDTH + 1, 20, "Loading") in panel.text
    assert (screen.PANEL_WIDTH + 1, 28, "v1.1.0") in panel.text


def test_splash_wifi_setup_qr_contains_wifi_credentials_and_portal_hint():
    panel = _SplashPanel()
    qr_data = []

    class FakeImageModule:
        @staticmethod
        def open(path):
            return _SplashImage()

    class FakeQRCode:
        def __init__(self, **kwargs):
            pass

        def add_data(self, data):
            qr_data.append(data)

        def make(self, fit):
            pass

        def get_matrix(self):
            return [[True, False], [False, True]]

    flight_tracker_module.render_splash(
        panel,
        "canvas",
        FakeImageModule,
        "font",
        url="http://192.168.4.1:8584/wifi-setup",
        qrcode=types.SimpleNamespace(QRCode=FakeQRCode),
        ERROR_CORRECT_L=1,
        wifi_setup={"ssid": "F1234", "password": "Ab12Cd34X"},
    )

    assert qr_data == ["WIFI:T:WPA;S:F1234;P:Ab12Cd34X;;"]
    assert any("192.168.4.1:8584" in text for _, _, text in panel.text)


def test_pygame_close_resets_simulator_config(monkeypatch):
    saved = []
    cfg = types.SimpleNamespace(
        data_store={"web_password_hash": "custom"},
        save=lambda: saved.append(True),
    )
    monkeypatch.setattr(flight_tracker_module.Config, "instance", lambda: cfg)
    monkeypatch.setattr(flight_tracker_module, "DEFAULTS", {"web_password_hash": ""})
    migrated = []
    monkeypatch.setattr(
        flight_tracker_module,
        "_migrate_provider_lists",
        lambda data, loaded: migrated.append((data, loaded)),
    )
    monkeypatch.setattr(
        flight_tracker_module.panel, "is_simulator", True, raising=False
    )

    class ClosedDisplay:
        def run(self):
            raise SystemExit(0)

    try:
        flight_tracker_module._run_display(ClosedDisplay())
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("Closing the simulator should exit the app")

    assert cfg.data_store == {"web_password_hash": ""}
    assert migrated == [(cfg.data_store, {})]
    assert saved == [True]


def test_non_simulator_exit_does_not_reset_config(monkeypatch):
    reset = []
    monkeypatch.setattr(
        flight_tracker_module,
        "_reset_simulator_config",
        lambda: reset.append(True),
    )
    monkeypatch.setattr(
        flight_tracker_module.panel, "is_simulator", False, raising=False
    )

    class ClosedDisplay:
        def run(self):
            raise SystemExit(0)

    with contextlib.suppress(SystemExit):
        flight_tracker_module._run_display(ClosedDisplay())

    assert reset == []


def test_check_data_source(monkeypatch):
    import utilities.lookups.flights as flights_service

    monkeypatch.setattr(flights_service, "startup_check", lambda: True)
    assert flight_tracker_module._check_data_source(None) is True


def test_check_data_source_handles_failure(monkeypatch):
    import utilities.lookups.flights as flights_service

    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(flights_service, "startup_check", boom)
    assert flight_tracker_module._check_data_source(None) is False


def test_check_routing_reachable(monkeypatch):
    import utilities.lookups.routes as routes_service

    monkeypatch.setattr(routes_service, "check_routing", lambda: True)

    assert flight_tracker_module._check_routing_reachable(None) is True


def test_check_routing_reachable_handles_failure(monkeypatch):
    import utilities.lookups.routes as routes_service

    monkeypatch.setattr(routes_service, "check_routing", lambda: False)
    assert flight_tracker_module._check_routing_reachable(None) is False
