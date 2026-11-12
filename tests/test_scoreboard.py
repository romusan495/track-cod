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
    lines = [l for l in load("scoreboard_victoire") if "1595" not in l.text]
    assert read_scoreboard(lines, at=1.0, weapon=None) is None


def test_midmatch_gives_none():
    assert read_scoreboard(load("scoreboard_midmatch"), at=1.0, weapon=None) is None
