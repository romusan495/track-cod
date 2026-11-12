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
    weapon: str
    section: str              # military / special / erudit
    number: int | None = None
    name: str | None = None

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


def read_banner(lines: list[OcrLine], registry: WeaponRegistry, known: KnownCamos) -> BannerRead | None:
    weapon = next((w for w in (registry.match(l.text) for l in lines if len(_plain(l.text)) >= 4) if w), None)
    if weapon is None:
        return None
    for line in lines:
        m = _MILITARY.search(_plain(line.text))
        if m:
            return BannerRead(weapon, "military", number=int(m.group(1)))
    texts = [_plain(l.text) for l in lines]
    for special in known.specials(weapon):
        target = _plain(special.name_fr)
        if any(fuzz.ratio(t, target) >= _NAME_MATCH for t in texts):
            return BannerRead(weapon, "special", name=special.name_fr)
    for key, label, _ in ERUDIT:
        if any((t == key) if len(key) <= 2 else fuzz.ratio(t, key) >= _NAME_MATCH for t in texts):
            return BannerRead(weapon, "erudit", name=label)
    return None
