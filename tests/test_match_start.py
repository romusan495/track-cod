import json
from pathlib import Path

import pytest
from PIL import Image

from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine
from trackcod.readers.match_start import ocr_match_start, read_breadcrumb, read_match_info, read_match_start
from trackcod.weapons import WeaponRegistry

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / "ocr" / f"{name}.json").read_text(encoding="utf-8"))]


def test_classify_match_start():
    assert classify(load("match_start_iso")) == "match_start"
    assert classify(load("apparence_full_asphalte")) == "apparence"


def test_read_weapon(registry):
    assert read_match_start(load("match_start_iso"), registry) == "ISO NIGHTSHADE"


def test_read_weapon_unknown_to_site_learned_after_two():
    r = WeaponRegistry([], [])
    assert read_match_start(load("match_start_iso"), r) is None
    assert read_match_start(load("match_start_iso"), r) == "ISO NIGHTSHADE"


def test_breadcrumb():
    lines = [OcrLine("CRÉER UNE CLASSE / MODIFIER CLASSE PERSONNALISÉE /", .18, .02, .3, .02),
             OcrLine("MITRAILLETTE - ISO NIGHTSHADE", .2, .05, .2, .02)]
    assert read_breadcrumb(lines) == "ISO NIGHTSHADE"
    assert read_breadcrumb([OcrLine("MITRAILLETTE - ISO NIGHTSHADE", .2, .05, .2, .02)]) is None


def test_category_alone_is_not_a_weapon(registry):
    lines = [OcrLine("< CHOISIR LA CLASSE", .17, .05, .13, .03), OcrLine("PRINCIPAL(E)", .30, .215, .04, .015),
             OcrLine("Mitraillette", .30, .283, .04, .012)]
    assert read_match_start(lines, registry) is None


def test_other_screens_give_none(registry):
    assert read_match_start(load("apparence_iso"), registry) is None


def test_match_info():
    assert read_match_info(load("match_start_iso")) == ("MATCH À MORT PAR ÉQUIPE HARDCORE", "LITHIUM")


@pytest.mark.windows
def test_ocr_match_start_end_to_end(registry):
    img = Image.open(FIX / "img" / "match_start_iso.webp").convert("RGB")
    from trackcod.ocr.engine import ocr_image
    base = ocr_image(img)
    assert read_match_start(base + ocr_match_start(img, base), registry) == "ISO NIGHTSHADE"
