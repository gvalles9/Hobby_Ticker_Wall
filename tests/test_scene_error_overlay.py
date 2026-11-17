"""Tests for the on-panel scene failure message."""

from display import draw_scene_error


class _FakeFont:
    def __init__(self, width):
        self.width = width

    def CharacterWidth(self, codepoint):
        return self.width


class _FakePanel:
    def __init__(self):
        self.cleared = False
        self.texts = []

    def clear(self, canvas):
        self.cleared = True

    def draw_text(self, canvas, font, x, y, colour, text):
        self.texts.append({"font": font, "x": x, "y": y, "text": text})
        return len(text) * font.width


def _draw(label, *, width=192, height=32, title_width=7, body_width=5):
    panel = _FakePanel()
    title_font = _FakeFont(title_width)
    body_font = _FakeFont(body_width)
    draw_scene_error(
        panel,
        object(),
        label,
        width=width,
        height=height,
        title_font=title_font,
        body_font=body_font,
    )
    return panel, title_font, body_font


def test_draws_the_scene_name_and_the_log_hint():
    panel, _, _ = _draw("flight")

    assert panel.cleared
    assert [item["text"] for item in panel.texts] == [
        "FLIGHT FAILED",
        "SEE LOG VIEWER",
    ]


def test_the_title_is_centred_on_the_panel():
    panel, _, _ = _draw("flight")

    title = panel.texts[0]
    assert title["x"] == (192 - len("FLIGHT FAILED") * 7) // 2


def test_both_lines_sit_inside_a_32_pixel_panel():
    panel, _, _ = _draw("flight")

    assert [item["y"] for item in panel.texts] == [14, 27]
    assert all(0 <= item["y"] < 32 for item in panel.texts)


def test_a_long_scene_name_drops_to_the_smaller_font():
    panel, _, body_font = _draw("satellite", title_width=20)

    assert panel.texts[0]["font"] is body_font
    assert panel.texts[0]["text"] == "SATELLITE FAILED"


def test_a_very_long_scene_name_is_truncated_but_keeps_failed():
    panel, _, _ = _draw("x" * 100)

    title = panel.texts[0]
    assert title["text"].endswith("FAILED")
    assert title["x"] + len(title["text"]) * 5 <= 192


def test_the_message_is_ascii():
    panel, _, _ = _draw("indy top3")

    assert all(item["text"].isascii() for item in panel.texts)
