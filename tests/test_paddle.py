"""Fine OCR (PaddleOCR models through onnxruntime) on real crops of the 16/11/2026 session."""

from pathlib import Path

import pytest
from PIL import Image

import trackcod.ocr.paddle as paddle
from trackcod.readers.daily import read_daily

IMG = Path(__file__).parent / "fixtures" / "img"
WHOLE = (0.0, 0.0, 1.0, 1.0)

needs_models = pytest.mark.skipif(not paddle.available(), reason="onnxruntime or the OCR models are missing")


@needs_models
def test_reads_the_daily_counters_the_windows_ocr_missed():
    lines = paddle.ocr_zone(Image.open(IMG / "fin_defis_du_jour.webp"), WHOLE)
    texts = [l.text for l in lines]
    assert texts.count("0/2") == 3 and texts.count("0/3") == 2
    assert "Remportez 2 partie[s] Multijoueur." in texts or "Remportez 2 partie(s) Multijoueur." in texts
    assert all(ord(c) < 0x2000 for t in texts for c in t)  # Latin only: no Chinese answer from the multilingual model


@needs_models
def test_daily_panel_read_by_the_fine_ocr_gives_every_counter():
    board = read_daily(paddle.ocr_zone(Image.open(IMG / "fin_defis_du_jour.webp"), WHOLE))
    assert [(c.progress, c.total) for c in board.challenges] == [(0, 3), (0, 2), (0, 2), (0, 2)]
    assert board.bonus == (0, 3)


@needs_models
def test_reads_the_item_banner_whole():
    texts = [l.text for l in paddle.ocr_zone(Image.open(IMG / "fin_bandeau_element.webp"), WHOLE)]
    assert "NOUVEL ÉLÉMENT DÉBLOQUÉ" in texts and "SANG 9MM" in texts and "LASER DCR-80" in texts


@needs_models
def test_lines_are_placed_on_the_whole_frame():
    img = Image.open(IMG / "fin_bandeau_element.webp")
    canvas = Image.new("RGB", (img.width * 2, img.height * 2))
    canvas.paste(img, (img.width, img.height))  # the crop in the bottom-right quarter
    lines = paddle.ocr_zone(canvas, (0.5, 0.5, 1.0, 1.0))
    banner = next(l for l in lines if l.text == "NOUVEL ÉLÉMENT DÉBLOQUÉ")
    assert 0.5 < banner.x < 0.75 and 0.5 < banner.y < 0.75 and banner.w < 0.5


def test_missing_models_leave_the_windows_ocr_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(paddle, "MODELS", tmp_path)
    monkeypatch.setattr(paddle, "_engine", None)
    monkeypatch.setattr(paddle, "_failed", False)
    assert paddle.ocr_zone(Image.new("RGB", (200, 100)), WHOLE) is None
    assert not paddle.available()


def test_connected_regions():
    import numpy as np
    mask = np.zeros((6, 10), dtype=bool)
    mask[1:3, 1:4] = True   # a block
    mask[3, 4] = True       # touching it by a corner: same region
    mask[1:2, 7:9] = True   # another one
    assert sorted(paddle._components(mask)) == [(1, 1, 5, 4), (7, 1, 9, 2)]
