"""Which game screen is shown, from OCR lines."""

import re
from typing import Literal

from rapidfuzz import fuzz

from trackcod.readers.common import OcrLine, norm

ScreenKind = Literal["apparence", "match_start", "scoreboard", "combat_record", "class", "daily", "other"]

SECTION_HEADERS = {"SPECIAL": "special", "ERUDIT": "erudit", "PRESTIGE": "prestige", "MILITAIRE": "military"}
_HEADER_THRESHOLD = 75


def header_section(line: OcrLine) -> str | None:
    """Section name if the line is an Apparence section header ('SPÉCIAL [0/3]')."""
    text = norm(line.text)
    first = re.split(r"[\s\[(|]", text, maxsplit=1)[0]
    if not first or len(text) > 24:
        return None
    for word, section in SECTION_HEADERS.items():
        if fuzz.ratio(first, word) >= _HEADER_THRESHOLD:
            return section
    return None


def classify(lines: list[OcrLine]) -> ScreenKind:
    headers = {s for s in (header_section(l) for l in lines) if s}
    if len(headers) >= 2:
        return "apparence"
    from trackcod.readers.match_start import is_match_start

    if is_match_start(lines):
        return "match_start"
    from trackcod.readers.scoreboard import is_scoreboard

    if is_scoreboard(lines):
        return "scoreboard"
    from trackcod.readers.combat_record import is_combat_record

    if is_combat_record(lines):
        return "combat_record"
    from trackcod.readers.class_screen import is_class_screen

    if is_class_screen(lines):
        return "class"
    from trackcod.readers.daily import is_daily

    if is_daily(lines):
        return "daily"
    return "other"
