import json
from pathlib import Path

import pytest
from PIL import Image

from trackcod.readers.apparence import SECTION_MARK, HoverTracker, ocr_apparence, read_apparence
from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine, norm
from trackcod.sheets import ApparenceCamo, ApparenceReading

FIX = Path(__file__).parent / "fixtures" / "ocr"
CAPTURES = Path(__file__).parents[1] / "docs" / "captures"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def test_classify_apparence():
    assert classify(load("apparence_iso")) == "apparence"
    assert classify(load("apparence_vel46")) == "apparence"
    assert classify([OcrLine("SCORE", .5, .5, .1, .05)]) == "other"


def test_read_iso_special():
    r = read_apparence(load("apparence_iso"), at=1.0)
    c = r.camos[0]
    assert norm(c.name_fr).startswith("ASPHA") and c.section == "special"
    assert c.progress == (46, 50) and c.access_met is True and c.locked is False
    assert c.challenge_fr.startswith("Faites 50 éliminations") and "viseu" in c.challenge_fr
    assert r.section_counts.get("erudit") == (0, 4)


def test_read_vel46_locked():
    c = read_apparence(load("apparence_vel46"), at=1.0).camos[0]
    assert norm(c.name_fr).startswith("OMBRE") and c.access_met is False and c.locked is True
    assert "8" in c.access_text and c.progress is None


def test_counter_ocr_fixes():
    lines = [OcrLine("Faites 50 éliminations de joueurs.", .5, .7, .3, .03),
             OcrLine("4G/5O", .88, .75, .04, .03), OcrLine("ASPHALTE", .55, .45, .2, .06),
             OcrLine("§SECTION:special", 0, 0, 0, 0)]
    assert read_apparence(lines, 1.0) is None or read_apparence(lines, 1.0).camos[0].progress in (None, (46, 50))
    lines[1] = OcrLine("46/5O", .88, .75, .04, .03)
    assert read_apparence(lines, 1.0).camos[0].progress == (46, 50)


def test_hover_order():
    t = HoverTracker()
    for n in ["ASPHALTE", "ASPHALTE", "TOPO NOIR", "MARRON"]:
        t.feed(ApparenceReading([ApparenceCamo(n, "special", None, None, None, None, None, False, None)], {}, 1.0))
    assert [(c.name_fr, c.position) for c in t.finish().camos] == [("ASPHALTE", 1), ("TOPO NOIR", 2), ("MARRON", 3)]
    assert t.finish() is None


def test_hover_keeps_best_reading():
    t = HoverTracker()
    t.feed(ApparenceReading([ApparenceCamo("ASPHALTE", "special", None, None, None, None, None, False, None)],
                            {"special": (0, 3)}, 1.0))
    t.feed(ApparenceReading([ApparenceCamo("ASPHALTE", "special", None, True, None, "Faites", (46, 50), False, None)],
                            {}, 2.0))
    r = t.finish()
    assert r.camos[0].progress == (46, 50) and r.section_counts == {"special": (0, 3)} and r.at == 2.0


def test_other_screen():
    assert read_apparence([OcrLine("SCORE", .5, .5, .1, .05)], 1.0) is None


@pytest.mark.windows
@pytest.mark.parametrize("src,expect", [("apparence-iso-special1-46sur50", "ASPHA"),
                                        ("apparence-vel46-special1-verrouille", "OMBRE")])
def test_ocr_apparence_end_to_end(src, expect):
    lines = ocr_apparence(Image.open(CAPTURES / f"{src}.webp").convert("RGB"))
    r = read_apparence(lines, 1.0)
    assert r is not None and norm(r.camos[0].name_fr).startswith(expect)


# ----- real full-frame captures (collection session 2026-11-12) -----

def test_full_frame_asphalte_done_section_counts():
    r = read_apparence(load("apparence_full_asphalte"), at=1.0)
    assert norm(r.camos[0].name_fr) == "ASPHALTE"
    assert r.section_counts["military"] == (8, 8) and r.section_counts["special"] == (1, 3)
    assert r.section_counts["erudit"] == (0, 4)
    assert r.weapon is not None and norm(r.weapon) == "ISO NIGHTSHADE"


def test_full_frame_military_name():
    r = read_apparence(load("apparence_full_militaire1"), at=1.0)
    c = r.camos[0]
    assert "MILITAIRE 1" in norm(c.name_fr) and c.section == "military"


def test_reading_without_challenge_keeps_unknowns():
    lines = [OcrLine("SPÉCIAL [1/3]", .18, .39, .06, .02), OcrLine("ÉRUDIT [0/4]", .18, .56, .06, .02),
             OcrLine("ASPHALTE", .39, .63, .1, .035), OcrLine("234", .40, .61, .01, .008),
             OcrLine("§SECTION:special", 0, 0, 0, 0)]
    c = read_apparence(lines, 1.0).camos[0]
    assert c.name_fr == "ASPHALTE" and c.challenge_fr is None and c.progress is None and c.access_met is None
    assert c.locked is False


@pytest.mark.windows
def test_ocr_full_frame_end_to_end():
    img = Image.open(FIX.parent / "img" / "apparence_full_asphalte.webp").convert("RGB")
    r = read_apparence(ocr_apparence(img), 1.0)
    assert norm(r.camos[0].name_fr) == "ASPHALTE" and r.section_counts["special"] == (1, 3)


def test_hover_military_numbers_not_merged():
    t = HoverTracker()
    t.feed(ApparenceReading([ApparenceCamo("CAMOUFLAGE MILITAIRE 3", "military", None, None, None, None, None,
                                           False, None)], {}, 1.0))
    t.feed(ApparenceReading([ApparenceCamo("CAMOUFLAGE MILITAIRE 4", "military", None, True, None, None, (3, 10),
                                           False, None)], {}, 2.0))
    camos = t.finish().camos
    assert [c.name_fr for c in camos] == ["CAMOUFLAGE MILITAIRE 3", "CAMOUFLAGE MILITAIRE 4"]
    assert camos[0].progress is None and camos[1].progress == (3, 10)


def test_hover_collects_name_reads():
    t = HoverTracker()
    for n in ["ASPHALTE", "ASPHALTE", "ASPHALTF"]:
        t.feed(ApparenceReading([ApparenceCamo(n, "special", None, None, None, None, None, False, None)], {}, 1.0))
    assert t.finish().camos[0].name_reads == ["ASPHALTE", "ASPHALTE", "ASPHALTF"]


def test_name_prefers_most_complete_read_of_same_row():
    lines = [OcrLine("SPÉCIAL [1/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("-I AS", .364, .625, .03, .039), OcrLine("HA TE", .429, .626, .03, .035),
             OcrLine("ASPHALTE", .386, .626, .09, .035), OcrLine("§SECTION:special", 0, 0, 0, 0)]         + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    assert read_apparence(lines, 1.0).camos[0].name_fr == "ASPHALTE"


# ----- essai en jeu v2 -----

def test_two_letter_camo_name_is_read():
    lines = [OcrLine("SPÉCIAL [3/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("OR", .386, .626, .03, .035)] + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    assert read_apparence(lines, 1.0).camos[0].name_fr == "OR"


@pytest.mark.windows
def test_full_frame_fast_path_reads_name_and_counts():
    import time
    img = Image.open(FIX.parent / "img" / "apparence_full_asphalte.webp").convert("RGB")
    from trackcod.ocr.engine import ocr_image
    raw = ocr_image(img)
    t = time.perf_counter()
    r = read_apparence(ocr_apparence(img, raw=raw), 1.0)
    elapsed = time.perf_counter() - t
    assert norm(r.camos[0].name_fr) == "ASPHALTE" and r.section_counts["special"] == (1, 3)
    assert elapsed < 0.8


# ----- section du camo survolé -----

@pytest.mark.windows
@pytest.mark.parametrize("fixture,section", [("apparence_full_asphalte", "special"),
                                             ("apparence_full_militaire1", "military")])
def test_selected_section_detected_on_full_frames(fixture, section):
    img = Image.open(FIX.parent / "img" / f"{fixture}.webp").convert("RGB")
    assert read_apparence(ocr_apparence(img), 1.0).camos[0].section == section


def test_selected_section_marker_used():
    lines = [OcrLine("SPÉCIAL [1/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("TOPO NOIR", .386, .626, .09, .035), OcrLine(f"{SECTION_MARK}erudit", 0, 0, 0, 0)] \
        + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    assert read_apparence(lines, 1.0).camos[0].section == "erudit"


def test_erudit_name_wins_over_unknown_section():
    lines = [OcrLine("SPÉCIAL [1/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("RUPTURE+ARMONIQUE-", .386, .626, .12, .035)] + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    assert read_apparence(lines, 1.0).camos[0].section == "erudit"


def test_unknown_section_read_is_ignored():
    lines = [OcrLine("SPÉCIAL [1/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("TOPO NOIR", .386, .626, .09, .035)] + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    r = read_apparence(lines, 1.0)
    assert r.camos == [] and r.section_counts["special"] == (1, 3)


def test_running_text_is_not_a_name():
    lines = [OcrLine("SPÉCIAL [0/3]", .184, .392, .06, .020), OcrLine("ÉRUDIT [0/4]", .184, .566, .06, .021),
             OcrLine("OR NOIR", .40, .44, .12, .035),
             OcrLine("btenez 27 armets supplémentaireff frllisant R'zi 12", .40, .52, .30, .045),
             OcrLine(f"{SECTION_MARK}special", 0, 0, 0, 0)] + [OcrLine("PIVOTER", .728, .952, .03, .013)] * 4
    assert read_apparence(lines, 1.0).camos[0].name_fr == "OR NOIR"
