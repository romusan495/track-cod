"""Meta loadouts from the player's own site (L'antre de Romusan, page MW4), refreshed once a day.

The page embeds its data as `JSON.parse('[{"id":...}]')` plus the update date `"YYYY-MM-DD"`.
"""

import dataclasses
import json
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from trackcod.readers.common import norm

META_URL = "https://romusan495.github.io/antre-de-romusan/mw4/"
MAX_AGE_S = 86400
RETRY_AFTER_FAILURE_S = 3600
_DATA = re.compile(r"JSON\.parse\('(\[\{\"id\":.*?\])'\)", re.S)
_DATE = re.compile(r'="(\d{4}-\d{2}-\d{2})"')
_JS_ESCAPE = re.compile(r"\\(['\\])")

SLOT_LABELS = {"optic": "Lunette", "muzzle": "Bouche", "barrel": "Canon", "underbarrel": "Accessoire canon",
               "magazine": "Chargeur", "ammunition": "Munitions", "rearGrip": "Poignée arrière", "stock": "Crosse",
               "laser": "Laser"}
CATEGORY_FR = {"ASSAULT_RIFLE": "Fusil d'assaut", "SMG": "Mitraillette", "LMG": "Mitrailleuse",
               "MARKSMAN_RIFLE": "Fusil tactique", "SNIPER_RIFLE": "Fusil de précision", "SHOTGUN": "Fusil à pompe",
               "PISTOL": "Pistolet", "LAUNCHER": "Lanceur"}
STYLE_LABELS = {"VERSATILE": "Polyvalent", "LOW_LEVEL": "Faible niveau", "APEX": "Apex", "ADS_SPEED": "Visée rapide",
                "LONG_RANGE": "Longue portée", "SHORT_RANGE": "Courte portée", "SNIPER": "Précision",
                "SNIPER_SUPPORT": "Soutien précision"}


@dataclass
class MetaAttachment:
    slot: str
    slot_label: str
    name: str
    level: int | None


@dataclass
class MetaBuild:
    style: str
    label: str
    attachments: list[MetaAttachment]


@dataclass
class MetaWeapon:
    name: str
    tier: str
    builds: list[MetaBuild]
    category: str = ""


@dataclass
class MetaData:
    updated: str | None
    weapons: list[MetaWeapon]
    fetched_at: float = 0.0
    stale: bool = False


def _label(style: str) -> str:
    return STYLE_LABELS.get(style) or style.replace("_", " ").capitalize()


def _weapons(raw: list[dict]) -> list[MetaWeapon]:
    return [
        MetaWeapon(
            name=w["nom"], tier=w.get("tier") or "",
            category=CATEGORY_FR.get(w.get("cat") or "", w.get("cat") or ""),
            builds=[MetaBuild(b["style"], _label(b["style"]),
                              [MetaAttachment(a["slot"], SLOT_LABELS.get(a["slot"], a["slot"]), a["nom"], a.get("niv"))
                               for a in b.get("acc", [])])
                    for b in w.get("builds", [])])
        for w in raw
    ]


def parse_meta_page(html: str) -> MetaData | None:
    m = _DATA.search(html)
    if not m:
        return None
    try:
        raw = json.loads(_JS_ESCAPE.sub(r"\1", m.group(1)))
        weapons = _weapons(raw)
    except (ValueError, KeyError, TypeError):
        return None
    date = _DATE.search(html)
    return MetaData(updated=date.group(1) if date else None, weapons=weapons) if weapons else None


def find_weapon(meta: MetaData, weapon: str) -> MetaWeapon | None:
    return next((w for w in meta.weapons if norm(w.name) == norm(weapon)), None)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "TrackCOD/0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def _load_cache(path: Path) -> MetaData | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if any("category" not in w for w in d["weapons"]):
            return None  # cache written by an older version: refetch to get the categories
        weapons = [MetaWeapon(w["name"], w["tier"],
                              [MetaBuild(b["style"], b["label"], [MetaAttachment(**a) for a in b["attachments"]])
                               for b in w["builds"]], w.get("category", "")) for w in d["weapons"]]
        return MetaData(d.get("updated"), weapons, float(d.get("fetched_at", 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return None


class MetaSource:
    def __init__(self, url: str, cache_path: Path, fetch: Callable[[str], str] = _http_get,
                 clock: Callable[[], float] = time.time):
        self.url = url
        self.cache_path = Path(cache_path)
        self.fetch = fetch
        self.clock = clock
        self._meta: MetaData | None = None
        self._retry_at = 0.0

    def cached(self) -> MetaData | None:
        """Last saved data, without any network access (used at startup)."""
        if self._meta is None:
            self._meta = _load_cache(self.cache_path)
        return self._meta

    def get(self) -> MetaData | None:
        """Fresh data (< 1 day) if possible; otherwise the last known data marked stale; None if never fetched."""
        now = self.clock()
        if self._meta is None:
            self._meta = _load_cache(self.cache_path)
        if self._meta is not None and now - self._meta.fetched_at < MAX_AGE_S:
            return self._meta
        if now < self._retry_at:
            return self._meta
        try:
            fresh = parse_meta_page(self.fetch(self.url))
        except Exception:  # OSError, HTTPException (IncompleteRead...), decode errors: keep the cache
            fresh = None
        if fresh is None:
            self._retry_at = now + RETRY_AFTER_FAILURE_S
            if self._meta is not None:
                self._meta.stale = True
            return self._meta
        fresh.fetched_at = now
        self._meta = fresh
        try:
            tmp = self.cache_path.with_name(self.cache_path.name + ".tmp")
            tmp.write_text(json.dumps(dataclasses.asdict(fresh), ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.cache_path)
        except OSError:
            pass  # in-memory data still used; the next refresh retries the write
        return fresh
