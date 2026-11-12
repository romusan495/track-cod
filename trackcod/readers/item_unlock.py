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


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text)).split())


def _is_banner(text: str) -> bool:
    words = _plain(text).split()
    return (len(words) >= 2 and fuzz.ratio(words[0], "NOUVEL") >= 80 and fuzz.ratio(words[1], "ELEMENT") >= 80
            and len(words) <= 3)


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
    banner = next((l for l in lines if _is_banner(l.text)), None)
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
    return ItemUnlock(item, is_camo)
