"""Reader for the end-of-match scoreboard ('VICTOIRE' / 'DÉFAITE' + team tables)."""

import re

from rapidfuzz import fuzz

from trackcod.model import MatchStats
from trackcod.readers.common import OcrLine, norm
from trackcod.stats import match_fingerprint

RESULTS = {"VICTOIRE": "win", "DEFAITE": "loss", "EGALITE": "draw"}
_NUMBER = re.compile(r"^\d{1,6}$")
_COLUMN_TOLERANCE = 0.015
_ROW_TOLERANCE = 0.012
_NAME_MATCH = 85
_ELIM_SHARE = (0.365 - 0.322) / (0.453 - 0.322)  # ÉLIM. between SCORE and MORTS (headers read on 13/11)


def _result_line(lines: list[OcrLine]) -> tuple[OcrLine, str] | None:
    for line in lines:
        text = norm(line.text)
        if line.y < 0.2 and line.h > 0.04 and text in RESULTS:
            return line, RESULTS[text]
    return None


def is_scoreboard(lines: list[OcrLine]) -> bool:
    texts = {norm(l.text) for l in lines}
    return _result_line(lines) is not None and "JOUEUR" in texts and "MORTS" in texts


def _player_name(lines: list[OcrLine]) -> str | None:
    """The local player's name, shown in the summary panel left of 'ÉLIM./ASSIST.'."""
    label = next((l for l in lines if norm(l.text).startswith("ELIM./ASSIST")), None)
    if label is None:
        return None
    left = [l for l in lines if abs(l.y - label.y) < 0.02 and l.x < label.x and sum(c.isalpha() for c in l.text) >= 3]
    return max(left, key=lambda l: l.x).text.strip() if left else None


def _header(lines: list[OcrLine], label: str, row: OcrLine) -> OcrLine | None:
    candidates = [l for l in lines if norm(l.text) == label and l.x > row.x and l.y < row.y]
    return min(candidates, key=lambda l: l.x - row.x) if candidates else None


def _value(lines: list[OcrLine], header: OcrLine | None, row: OcrLine) -> int | None:
    if header is None:
        return None
    for line in lines:
        text = line.text.strip()
        if (_NUMBER.match(text) and abs(line.y - row.y) < _ROW_TOLERANCE
                and abs(line.x - header.x) < _COLUMN_TOLERANCE):
            return int(text)
    return None


def _mode(lines: list[OcrLine], result: OcrLine) -> str | None:
    below = [l for l in lines if result.y + result.h <= l.y < result.y + result.h + 0.06 and l.x < 0.5]
    if not below:
        return None
    first = min(below, key=lambda l: l.y)
    same_row = sorted((l for l in below if abs(l.y - first.y) < 0.01), key=lambda l: l.x)
    return " ".join(l.text.strip() for l in same_row)


def read_scoreboard(lines: list[OcrLine], at: float, weapon: str | None) -> MatchStats | None:
    found = _result_line(lines)
    if found is None or not is_scoreboard(lines):
        return None
    result_line, result = found
    name = _player_name(lines)
    if name is None:
        return None
    rows = [l for l in lines if 0.3 < l.y < 0.85 and fuzz.partial_ratio(norm(name), norm(l.text)) >= _NAME_MATCH
            and len(l.text) >= len(name) - 2]
    if not rows:
        return None
    row = rows[0]
    score_h, morts_h = _header(lines, "SCORE", row), _header(lines, "MORTS", row)
    elim_h = _header(lines, "ELIM.", row)
    if elim_h is None and score_h is not None and morts_h is not None:
        # header not read: the columns never move, ÉLIM. sits at a fixed share of the SCORE -> MORTS gap
        elim_h = OcrLine("ELIM.", score_h.x + (morts_h.x - score_h.x) * _ELIM_SHARE, score_h.y, 0.0, score_h.h)
    score = _value(lines, score_h, row)  # optional: an unreadable score never drops the match
    kills = _value(lines, elim_h, row)
    deaths = _value(lines, morts_h, row)
    if kills is None or deaths is None:
        return None
    mode = _mode(lines, result_line)
    return MatchStats(
        at=at, kills=kills, deaths=deaths, score=score, result=result, mode=mode, map=None, weapon=weapon,
        fingerprint=match_fingerprint(kills, deaths, score, mode, None, int(at // 600)),
    )
