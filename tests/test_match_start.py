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


def _with_map(text):
    lines = load("match_start_iso")
    return [OcrLine(text, l.x, l.y, l.w, l.h) if l.text == "LITHIUM" else l for l in lines]


def test_map_is_never_a_piece_of_the_mode():
    """Real sessions 14-15/11: 'HARDCORE' wrapped under the mode was taken for the map ('OCORE', 'AROCORE',
    'HARDCOR', 'MATCH'), so were the lobby message and stray marks ('.BACKSTAB')."""
    for junk in ("OCORE", "AROCORE", "A OCORE", "HARDCOR", "MATCH", "MATCH MORT",
                 "Vous attendez de pouvoir rejoindre le salon.", "Fusil tactique - Multi"):
        assert read_match_info(_with_map(junk))[1] is None, junk
    assert read_match_info(_with_map(".BACKSTAB"))[1] == "BACKSTAB"
    assert read_match_info(_with_map("-CANYON"))[1] == "CANYON"
    assert read_match_info(_with_map("REACTOR 092"))[1] == "REACTOR 092"


def test_game_modes_are_told_from_class_menus():
    from trackcod.readers.match_start import is_game_mode
    for mode in ("MATCH À MORT PAR ÉQUIPE HARDCORE", "PAR ÉQUIPE HARDCORÉ", "H À ÉQUIPE HARDCORÉ", "DOMINATION",
                 "RECHERCHE ET DESTRUCTION", "MÊLÉE GÉNÉRALE", "POINT STRATÉGIQUE"):
        assert is_game_mode(mode), mode
    for menu in ("VERSION CRÉÉE", "RÉCOMPENSES BONUS", "JETONS DISPONIBLES", None):
        assert not is_game_mode(menu), menu


def test_map_read_with_a_stray_letter_or_digit_in_front():
    """Real session 16/11: '3CANYON' and 'E JOUEURS' (the lobby's player count) were kept as maps."""
    assert read_match_info(_with_map("3CANYON"))[1] == "CANYON"
    assert read_match_info(_with_map("I LOTUS"))[1] == "LOTUS"
    assert read_match_info(_with_map("E JOUEURS"))[1] is None
    assert read_match_info(_with_map("12 JOUEURS"))[1] is None
    assert read_match_info(_with_map("OUEURS"))[1] is None
