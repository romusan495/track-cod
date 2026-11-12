"""Weapon of the class on screen ('MODIFIER CLASSE PERSONNALISÉE', 'CHOISIR LA CLASSE'): the PRINCIPAL(E) card.

Two layouts seen in game: category + name in big letters ('Fusil d'assaut' / 'PATRIOT XMR'), or one small row
'Mitraillette - ISO Nightshade' partly hidden by the gun picture, with the mode ('MULTI') below.
"""

import re

from rapidfuzz import fuzz

from trackcod.meta import CATEGORY_FR
from trackcod.readers.common import OcrLine, norm
from trackcod.weapons import WeaponRegistry

_CATEGORIES = [norm(c) for c in CATEGORY_FR.values()]
_ROW = 0.006


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 \-]+", " ", norm(text)).split())


def _find(lines: list[OcrLine], word: str) -> OcrLine | None:
    return next((l for l in lines if any(fuzz.ratio(w, word) >= 80 for w in _plain(l.text).replace("-", " ").split()
                                         if len(w) >= 6)), None)


def is_class_screen(lines: list[OcrLine]) -> bool:
    p, s = _find(lines, "PRINCIPAL"), _find(lines, "SECONDAIRE")
    return p is not None and s is not None and s.y > p.y


def _candidates(card: list[OcrLine]) -> list[str]:
    rows: list[list[OcrLine]] = []
    for line in sorted(card, key=lambda l: l.y):
        if rows and abs(rows[-1][0].y - line.y) <= _ROW:
            rows[-1].append(line)
        else:
            rows.append([line])
    out = []
    for row in rows:
        text = _plain(" ".join(l.text for l in sorted(row, key=lambda l: l.x)))
        parts = [p.strip() for p in text.split("-")]
        for part in ([parts[-1]] if len(parts) > 1 else []) + [text]:
            if sum(c.isalpha() for c in part) >= 3 and max(fuzz.ratio(part, c) for c in _CATEGORIES) < 85:
                out.append(part)
    return out


def read_class_weapon(lines: list[OcrLine], registry: WeaponRegistry) -> str | None:
    if not is_class_screen(lines):
        return None
    p, s = _find(lines, "PRINCIPAL"), _find(lines, "SECONDAIRE")
    card = [l for l in lines if p.y < l.y < s.y - 0.005 and p.x - 0.01 <= l.x <= p.x + 0.12]
    for text in _candidates(card):
        weapon = registry.match(text)
        if weapon:
            return weapon
    return None
