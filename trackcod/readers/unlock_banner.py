"""In-match camo unlock banner: '<ARME>' + 'CAMOUFLAGE MILITAIRE 8' (or a camo name), then 'DÉBLOQUÉ'.

Built from real French OCR reads of the banner. A banner alone is not enough (other HUD messages mention
camos): the engine waits for the 'DÉBLOQUÉ' word within a few seconds before marking the camo done.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from trackcod.known_camos import KnownCamos
from trackcod.readers.common import OcrLine, norm
from trackcod.sheets import ERUDIT
from trackcod.weapons import WeaponRegistry

_MILITARY = re.compile(r"MILITAIRE\s*(\d)\b")
_NAME_MATCH = 85


@dataclass(frozen=True)
class BannerRead:
    weapon: str | None        # None: a corner notification whose weapon line was not read (16/11)
    section: str              # military / special / erudit
    number: int | None = None
    name: str | None = None
    corner: bool = False      # top-right notification: the game's own unlock message, no 'DEBLOQUE' word

    @property
    def label(self) -> str:
        return f"Camouflage militaire {self.number}" if self.section == "military" else (self.name or "?")


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text)).split())


def has_unlocked_word(lines: list[OcrLine]) -> bool:
    """'DÉBLOQUÉ' on its own (not 'Nouvelle arme débloquée', which is another HUD message)."""
    for line in lines:
        text = _plain(line.text)
        if text and len(text.split()) <= 2 and fuzz.ratio(text.split()[0], "DEBLOQUE") >= 85:
            return True
    return False


def _in_corner(line: OcrLine) -> bool:
    return line.x > 0.7 and line.y < 0.4


def _weapon_above(line: OcrLine, lines: list[OcrLine], registry: WeaponRegistry) -> str | None:
    """The banner's weapon is the line right above its camo line ('VEL 46' over 'CAMOUFLAGE MILITAIRE 2')."""
    above = [l for l in lines if 0 < line.y - l.y < 0.06 and abs(l.x - line.x) < 0.05]
    return next((w for w in (registry.match(l.text) for l in sorted(above, key=lambda l: line.y - l.y)) if w), None)


def read_banner(lines: list[OcrLine], registry: WeaponRegistry, known: KnownCamos) -> BannerRead | None:
    # anywhere on screen, HUD text can look like a weapon ('LATENCE : 12 MS' ~ REZI 12): prefer the line above
    anywhere = next((w for w in (registry.match(l.text) for l in lines if len(_plain(l.text)) >= 4) if w), None)
    for line in lines:
        m = _MILITARY.search(_plain(line.text))
        if m:
            corner = _in_corner(line)
            # in the corner, a weapon read elsewhere on screen is HUD text, not the notification's weapon
            weapon = _weapon_above(line, lines, registry) or (None if corner else anywhere)
            if weapon is None and not corner:
                return None
            return BannerRead(weapon, "military", number=int(m.group(1)), corner=corner)
    weapon = anywhere
    if weapon is None:
        return None
    texts = [_plain(l.text) for l in lines]
    for special in known.specials(weapon):
        target = _plain(special.name_fr)
        hit = next((l for l, t in zip(lines, texts) if fuzz.ratio(t, target) >= _NAME_MATCH), None)
        if hit is not None:
            return BannerRead(weapon, "special", name=special.name_fr, corner=_in_corner(hit))
    for key, label, _ in ERUDIT:
        if any((t == key) if len(key) <= 2 else fuzz.ratio(t, key) >= _NAME_MATCH for t in texts):
            return BannerRead(weapon, "erudit", name=label)
    return None
