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
_HEADERS = {"JOUEUR", "SCORE", "ELIM.", "ASSIST.", "MORTS", "NIVEAU"}  # never the player's row
_ELIM_SHARE = (0.365 - 0.322) / (0.453 - 0.322)  # ÉLIM. between SCORE and MORTS (headers read on 13/11)


def _result_line(lines: list[OcrLine]) -> tuple[OcrLine, str] | None:
    for line in lines:
        text = re.sub(r"[^A-Z]", "", norm(line.text))  # 'DÉFAITE :' (a stroke next to the title, 14/11)
        if line.y < 0.2 and line.h > 0.04 and text in RESULTS:
            return line, RESULTS[text]
    return None


def is_scoreboard(lines: list[OcrLine]) -> bool:
    texts = {norm(l.text) for l in lines}
    return _result_line(lines) is not None and "JOUEUR" in texts and "MORTS" in texts


def _player_name(lines: list[OcrLine]) -> str | None:
    """The local player's name, shown in the summary panel left of 'ÉLIM./ASSIST.'."""
    # letters only: the console OCR reads 'ÉLIM. [ASSIST.'
    label = next((l for l in lines if re.sub(r"[^A-Z]", "", norm(l.text)).startswith("ELIMASSIST")), None)
    if label is None:
        return None
    left = [l for l in lines if abs(l.y - label.y) < 0.02 and l.x < label.x and sum(c.isalpha() for c in l.text) >= 3]
    return max(left, key=lambda l: l.x).text.strip() if left else None


def own_row_band(lines: list[OcrLine]) -> tuple[float, float, float, float] | None:
    """(x0, y0, x1, y1) of the player's row in their team table: the highlighted row the OCR reads worst."""
    name = _player_name(lines)
    if name is None:
        return None
    row = next((l for l in lines if 0.3 < l.y < 0.85 and norm(l.text) not in _HEADERS
                and fuzz.partial_ratio(norm(name), norm(l.text)) >= _NAME_MATCH
                and len(l.text) >= len(name) - 2), None)
    morts = _header(lines, "MORTS", row) if row is not None else None
    if row is None or morts is None:
        return None
    return max(0.0, row.x - 0.06), row.y - 0.018, min(1.0, morts.x + 0.04), row.y + row.h + 0.012


def replace_row(base: list[OcrLine], zoom: list[OcrLine], band: tuple[float, float, float, float]) -> list[OcrLine]:
    x0, y0, x1, y1 = band
    inside = lambda l: x0 <= l.x <= x1 and y0 <= l.y <= y1 and not any(c.isalpha() for c in l.text)
    return [l for l in base if not inside(l)] + zoom  # the numbers of the row are replaced, the name stays


def ocr_own_row(img, base: list[OcrLine]) -> list[OcrLine]:
    """Re-reads the player's highlighted row zoomed x2 (console: '28' read for 20, score missed) and puts it
    in place of the first read."""
    from trackcod.ocr.engine import ocr_image
    band = own_row_band(base)
    if band is None:
        return base
    x0, y0, x1, y1 = band
    W, H = img.size
    crop = img.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    zoom = [OcrLine(l.text, x0 + l.x * (x1 - x0), y0 + l.y * (y1 - y0), l.w * (x1 - x0), l.h * (y1 - y0))
            for l in ocr_image(crop, upscale=2.0)]
    return replace_row(base, zoom, band) if zoom else base


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
    # under the title, which is on the left for a win and on the right for a defeat
    below = [l for l in lines if result.y + result.h <= l.y < result.y + result.h + 0.06]
    starts = [l for l in below if result.x - 0.1 <= l.x <= result.x + result.w]
    if not starts:
        return None
    first = min(starts, key=lambda l: l.y)
    same_row = sorted((l for l in below if abs(l.y - first.y) < 0.01 and abs(l.x - first.x) < 0.3),
                      key=lambda l: l.x)
    return " ".join(l.text.strip() for l in same_row)


def read_scoreboard(lines: list[OcrLine], at: float, weapon: str | None) -> MatchStats | None:
    found = _result_line(lines)
    if found is None or not is_scoreboard(lines):
        return None
    result_line, result = found
    name = _player_name(lines)
    if name is None:
        return None
    rows = [l for l in lines if 0.3 < l.y < 0.85 and norm(l.text) not in _HEADERS
                and fuzz.partial_ratio(norm(name), norm(l.text)) >= _NAME_MATCH
            and len(l.text) >= len(name) - 2]
    if not rows:
        return None
    row = rows[0]
    score_h, morts_h = _header(lines, "SCORE", row), _header(lines, "MORTS", row)
    elim_h = _header(lines, "ELIM.", row)
    if elim_h is not None and score_h is not None and morts_h is not None and not score_h.x < elim_h.x < morts_h.x:
        elim_h = None  # the other team's 'ÉLIM.': ours was not read
    if elim_h is None and score_h is not None and morts_h is not None:
        # header not read: the columns never move, ÉLIM. sits at a fixed share of the SCORE -> MORTS gap
        elim_h = OcrLine("ELIM.", score_h.x + (morts_h.x - score_h.x) * _ELIM_SHARE, score_h.y, 0.0, score_h.h)
    score = _value(lines, score_h, row)  # optional: an unreadable score never drops the match
    kills = _value(lines, elim_h, row)
    deaths = _value(lines, morts_h, row)
    if kills is None or deaths is None:
        return None
    if score is not None and score < 50 * kills:
        score = None  # a digit lost ('260' for 2600): every kill is worth far more than 50 points
    mode = _mode(lines, result_line)
    return MatchStats(
        at=at, kills=kills, deaths=deaths, score=score, result=result, mode=mode, map=None, weapon=weapon,
        fingerprint=match_fingerprint(kills, deaths, score, mode, None, int(at // 600)),
    )
