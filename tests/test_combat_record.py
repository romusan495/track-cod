import json
from pathlib import Path

from trackcod.readers.classify import classify
from trackcod.readers.combat_record import parse_int, read_combat_record
from trackcod.readers.common import OcrLine

FIX = Path(__file__).parent / "fixtures" / "ocr"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def test_classify():
    assert classify(load("combat_record_mp")) == "combat_record"
    assert classify(load("combat_record_recent")) == "other"
    assert classify(load("combat_record_carriere")) == "other"


def test_read_real_career():
    g = read_combat_record(load("combat_record_mp"))
    assert (g.kills, g.deaths, g.wins, g.losses, g.games) == (2079, 2330, 69, 57, 126)
    assert round(g.kd, 2) == 0.89


def test_other_views_give_none():
    assert read_combat_record(load("combat_record_recent")) is None
    assert read_combat_record(load("combat_record_carriere")) is None


def test_missing_value_gives_none():
    lines = [l for l in load("combat_record_mp") if l.text.strip() != "2330"]
    assert read_combat_record(lines) is None


def test_parse_int():
    assert parse_int("8 420") == 8420 and parse_int("8.420") == 8420 and parse_int("2079") == 2079
    assert parse_int("16H 29M") is None and parse_int("0.89") is None
