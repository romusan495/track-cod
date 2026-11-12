import pytest
from PIL import Image, ImageDraw, ImageFont

from trackcod.ocr.engine import ocr_available, ocr_image
from trackcod.readers.common import norm

pytestmark = pytest.mark.windows


def test_norm():
    assert norm("  Spécial  [0/3] ") == "SPECIAL [0/3]"


def test_ocr_available():
    assert ocr_available() is True


def test_ocr_reads_text():
    img = Image.new("RGB", (800, 200), "black")
    ImageDraw.Draw(img).text((20, 60), "CAMOUFLAGE MILITAIRE 8", fill="white",
                             font=ImageFont.truetype("arial.ttf", 48))
    lines = ocr_image(img)
    hit = [l for l in lines if "MILITAIRE" in norm(l.text)]
    assert hit and 0 <= hit[0].x <= 1 and 0 <= hit[0].y <= 1 and 0 < hit[0].h < 1
