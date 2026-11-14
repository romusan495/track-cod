import json
from pathlib import Path

from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine
from trackcod.readers.scoreboard import read_scoreboard

FIX = Path(__file__).parent / "fixtures" / "ocr"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def test_classify():
    assert classify(load("scoreboard_victoire")) == "scoreboard"
    assert classify(load("scoreboard_midmatch")) == "other"


def test_read_real_end_of_match():
    m = read_scoreboard(load("scoreboard_victoire"), at=1000.0, weapon="ISO Nightshade")
    assert (m.kills, m.deaths, m.score, m.result) == (13, 12, 1595, "win")
    assert m.mode == "MATCH À MORT PAR ÉQUIPE HARDCORE" and m.weapon == "ISO Nightshade"
    assert round(m.kd, 2) == 1.08 and m.fingerprint


def test_same_screen_same_fingerprint():
    a = read_scoreboard(load("scoreboard_victoire"), at=1000.0, weapon=None)
    b = read_scoreboard(load("scoreboard_victoire"), at=1003.0, weapon=None)
    assert a.fingerprint == b.fingerprint


def test_player_row_unreadable_gives_none():
    # the score alone may be unreadable (see below); without the kills value there is no match to record
    m = read_scoreboard(load("scoreboard_victoire"), at=1.0, weapon=None)
    lines = [l for l in load("scoreboard_victoire") if not (l.text.strip() == str(m.kills) and abs(l.y - 0.742) < 0.1)]
    assert read_scoreboard(lines, at=1.0, weapon=None) is None


def test_midmatch_gives_none():
    assert read_scoreboard(load("scoreboard_midmatch"), at=1.0, weapon=None) is None


def test_unreadable_score_still_records_the_match():
    """Real session 13/11: the score cell was read '8��'; kills and deaths are still there."""
    m = read_scoreboard(load("scoreboard_defaite_score_illisible"), at=1000.0, weapon="VEL 46")
    assert m is not None and (m.kills, m.deaths, m.score, m.result) == (6, 8, None, "loss")


def test_missing_elim_header_is_placed_between_score_and_morts():
    """Real session 13/11: the 'ÉLIM.' header was not read; the columns never move."""
    m = read_scoreboard(load("scoreboard_victoire_sans_entete_elim"), at=1000.0, weapon="VEL 46")
    assert m is not None and (m.kills, m.deaths, m.score, m.result) == (19, 19, 2410, "win")


def test_console_summary_label_read_with_a_bracket():
    """Console capture (Twitch, 13/11): the summary label reads 'ÉLIM. [ASSIST.'; the player is still found."""
    from trackcod.readers.scoreboard import _player_name
    assert _player_name(load("console_scoreboard_victoire")) == "Joueur1"


def test_console_scoreboards_after_the_zoomed_row_pass():
    """Real console end screens, as the live pipeline sees them (own highlighted row re-read zoomed x2)."""
    win = read_scoreboard(load("console_scoreboard_victoire_zoom"), at=1.0, weapon=None)
    assert (win.kills, win.deaths, win.score, win.result) == (20, 12, None, "win")  # "260" for 2600: dropped
    loss = read_scoreboard(load("console_scoreboard_defaite_zoom"), at=1.0, weapon=None)
    assert (loss.kills, loss.deaths, loss.score, loss.result) == (15, 14, 1915, "loss")


def test_zoomed_row_replaces_the_first_read_of_that_row():
    from trackcod.readers.scoreboard import replace_row
    base = [OcrLine("Joueur1", 0.14, 0.664, 0.05, 0.02), OcrLine("28", 0.322, 0.664, 0.01, 0.02),
            OcrLine("27", 0.322, 0.60, 0.01, 0.02), OcrLine("Autre", 0.6, 0.664, 0.05, 0.02)]
    zoom = [OcrLine("20", 0.321, 0.665, 0.01, 0.02)]
    out = replace_row(base, zoom, (0.08, 0.645, 0.47, 0.686))
    texts = {l.text for l in out}
    assert "28" not in texts and {"20", "27", "Autre", "Joueur1"} <= texts


def test_defeat_title_on_the_right_with_a_mark():
    """Real session 14/11: on a defeat the title sits on the right and reads 'DÉFAITE :' (a stroke next to it).
    Every defeat of the session was dropped."""
    m = read_scoreboard(load("scoreboard_defaite_titre_a_droite"), at=1.0, weapon="CRONEN OSPREY")
    assert m is not None
    assert (m.kills, m.deaths, m.score, m.result) == (29, 17, 3915, "loss")
    assert m.mode == "MATCH À MORT PAR EQUIPE HARDCORE" or "MORT PAR EQUIPE HARDCORE" in m.mode
