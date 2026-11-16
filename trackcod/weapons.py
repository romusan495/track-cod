"""Known MW4 weapons: the player's meta site first, then weapons learned from the game screen."""

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from trackcod.meta import MetaData
from trackcod.readers.common import norm

MATCH_THRESHOLD = 85   # WRatio, same as v1 Catalog.match_weapon
SAME_READ = 80         # ratio for two reads of an unknown name to count as the same
MIN_LETTERS = 4
NEAR_SITE = 60       # a read this close to a site weapon is a garbled read of it, never a new weapon


@dataclass(frozen=True)
class WeaponInfo:
    name: str
    category: str


def _digits(s: str) -> list[str]:
    return [c for c in s if c.isdigit()]


class WeaponRegistry:
    def __init__(self, site: list[WeaponInfo], learned: list[str]):
        self._site = list(site)
        self.learned: list[str] = list(learned)
        self._pending: dict[str, tuple[int, str]] = {}  # normalized read -> (count, most readable form)

    @classmethod
    def from_meta(cls, meta: MetaData | None, learned: list[str]) -> "WeaponRegistry":
        site = [WeaponInfo(w.name, w.category) for w in meta.weapons] if meta else []
        return cls(site, learned)

    def update_site(self, meta: MetaData | None) -> None:
        if meta is not None:
            self._site = [WeaponInfo(w.name, w.category) for w in meta.weapons]
            site = [norm(w.name) for w in self._site]
            self.learned = [n for n in self.learned
                            if not (process.extractOne(norm(n), site, scorer=fuzz.WRatio) or (None, 0))[1] >= MATCH_THRESHOLD]

    def add(self, text: str) -> str | None:
        """Name typed by the player in the window: accepted as is (cleaned)."""
        known = self.match(text)
        if known is not None:
            return known
        cleaned = " ".join(norm(text or "").split())
        if not cleaned:
            return None
        self.learned.append(cleaned)
        return cleaned

    def _names(self) -> list[str]:
        known = [w.name for w in self._site]
        return known + [n for n in self.learned if n not in known]

    def weapons(self) -> list[WeaponInfo]:
        site_names = {w.name for w in self._site}
        extra = [WeaponInfo(n, "") for n in self.learned if n not in site_names]
        return sorted(self._site + extra, key=lambda w: w.name)

    def category(self, name: str) -> str:
        return next((w.category for w in self._site if w.name == name), "")

    def match(self, text: str) -> str | None:
        query = norm(text or "")
        if not query:
            return None
        names = self._names()
        best = process.extractOne(query, [norm(n) for n in names], scorer=fuzz.WRatio)
        if best is None or best[1] < MATCH_THRESHOLD or not _letters_read(names[best[2]], query):
            return None
        return names[best[2]]

    def observe(self, text: str) -> str | None:
        """Known weapon, or a new name accepted after two concordant reads (spec §4.1, §4.3)."""
        known = self.match(text)
        if known is not None:
            return known
        cleaned = " ".join(norm(text or "").split())
        if sum(c.isalpha() for c in cleaned) < MIN_LETTERS:
            return None
        site = [norm(w.name) for w in self._site]
        if site and (process.extractOne(cleaned, site, scorer=fuzz.WRatio) or (None, 0))[1] >= NEAR_SITE:
            return None
        letters = lambda t: sum(c.isalpha() for c in t)  # noqa: E731
        for seen, (count, form) in list(self._pending.items()):
            digits_ok = not (_digits(seen) and _digits(cleaned)) or _digits(seen) == _digits(cleaned)
            if fuzz.ratio(seen, cleaned) >= SAME_READ and digits_ok:
                best = cleaned if letters(cleaned) > letters(form) else form
                if count + 1 >= 2:
                    del self._pending[seen]
                    self.learned.append(best)
                    return best
                self._pending[seen] = (count + 1, best)
                return None
        self._pending[cleaned] = (1, cleaned)
        return None


def _letters_read(name: str, query: str) -> bool:
    """A weapon is named by its letters: '46 /59 ÉLÉMENTS DÉBLOQUÉS' is not the VEL 46 (16/11). A word of 3
    letters or more of the name is in the read, give or take an OCR slip ('STRICA' for 'STRIGA')."""
    words = [w for w in "".join(c if c.isalpha() else " " for c in norm(name)).split() if len(w) >= 3]
    return not words or any(fuzz.partial_ratio(w, query) >= 80 for w in words)
