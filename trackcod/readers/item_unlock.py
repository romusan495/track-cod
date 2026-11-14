"""In-match 'NOUVEL ÉLÉMENT DÉBLOQUÉ' banner (a weapon item reached by levelling: stock, silencer, barrel...).

Built from the real OCR read of the banner ('NOUVEL ÉLÉMENT' + the item card on the right, e.g. 'SILEN').
A military camo can show up in the same card: it does not count toward the specials' item condition.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from trackcod.readers.common import OcrLine, norm


@dataclass(frozen=True)
class ItemUnlock:
    item: str        # text of the item card (may be partial or empty)
    is_camo: bool
    weapon: str | None = None  # weapon line under the banner title ('CRONEN OSPREY'), when read


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text)).split())


def _is_banner(text: str) -> bool:
    words = _plain(text).split()
    return (len(words) >= 2 and fuzz.ratio(words[0], "NOUVEL") >= 80 and fuzz.ratio(words[1], "ELEMENT") >= 80
            and len(words) <= 3)


_MIDDLE = (0.3, 0.2, 0.62, 0.32)  # left, top, right, bottom: where the banner title sits on a full frame


def _is_middle_title(line: OcrLine) -> bool:
    """The banner title in the middle of the screen, white over the sky and read in pieces ('IJYEL ÉLÉMENT D -',
    'NOUVEL ÉLÉ?', 'L ÉLÉM'): any piece of 'NOUVEL ÉLÉMENT' is enough there; a lone 'DÉBLOQUÉ' is not."""
    left, top, right, bottom = _MIDDLE
    plain = _plain(line.text)
    return (left <= line.x <= right and top <= line.y <= bottom and len(plain.replace(" ", "")) >= 5
            and "ELE" in plain.replace(" ", "") and fuzz.partial_ratio(plain, "NOUVEL ELEMENT") >= 75)


def _is_level_up(text: str) -> bool:
    words = _plain(text).split()
    return len(words) >= 2 and fuzz.ratio(words[0], "NIVEAU") >= 80 and fuzz.ratio(words[1], "SUPERIEUR") >= 75


def _is_card_title(text: str) -> bool:
    words = _plain(text).split()
    return 0 < len(words) <= 1 and fuzz.ratio(words[0], "DEBLOQUE") >= 80


def read_item_unlock(lines: list[OcrLine]) -> ItemUnlock | None:
    """Level-up card: 'DÉBLOQUÉ' with the item name just below ('CROSSE DEMO HVR2'), next to 'NIVEAU
    SUPÉRIEUR'; or the 'NOUVEL ÉLÉMENT' banner with the item card on its right."""
    title = next((l for l in lines if _is_card_title(l.text)), None)
    banner = next((l for l in lines if _is_banner(l.text)), None) or next(
        (l for l in lines if _is_middle_title(l)), None)
    if banner is None and not any(_is_level_up(l.text) for l in lines):
        return None  # a lone 'DÉBLOQUÉ' also labels items in the class menus
    if title is None and banner is None:
        return None
    if title is not None:
        below = [l for l in lines if l is not title and title.y < l.y <= title.y + 4 * max(title.h, 0.01)
                 and abs(l.x - title.x) < 0.1 and _plain(l.text)]
        item = _plain(min(below, key=lambda l: l.y).text) if below else ""
    else:
        item = " ".join(_plain(l.text) for l in lines
                        if l.x > banner.x + banner.w and _plain(l.text) and "DEBLO" not in _plain(l.text)
                        and not _plain(l.text).isdigit())
    texts = [_plain(l.text) for l in lines]
    is_camo = any("CAMOUF" in t or "MILITAIRE" in t for t in texts + [item])
    weapon = None
    if banner is not None:
        under = [l for l in lines if 0.02 < l.y - banner.y < 0.08 and abs(l.x - banner.x) < 0.12
                 and not _is_middle_title(l) and sum(c.isalpha() for c in l.text) >= 3]
        weapon = min(under, key=lambda l: l.y).text.strip() if under else None
        if weapon:
            item = " ".join(w for w in item.split() if w not in _plain(weapon).split()).strip()
    return ItemUnlock(item, is_camo, weapon)
