"""Application state dataclasses."""

from dataclasses import dataclass, field
from typing import Literal

CamoState = Literal["locked", "available", "done", "unknown"]
Section = Literal["military", "special", "erudit"]
Phase = Literal["menu", "in_match", "post_match", "unknown"]


@dataclass
class Camo:
    key: str                      # stable slot id: 'military:3', 'special:2', 'erudit:1'
    name_fr: str | None
    section: Section
    order: int
    challenge_fr: str | None = None
    access_text: str | None = None
    access_met: bool | None = None
    access_progress: float | None = None
    items_left: int | None = None   # weapon items still to unlock before this special opens
    state: CamoState = "unknown"
    progress: tuple[int, int] | None = None
    read_at: float | None = None
    name_votes: dict[str, int] = field(default_factory=dict)   # normalized name -> OCR reads
    name_forms: dict[str, str] = field(default_factory=dict)   # normalized name -> most readable raw form


@dataclass
class WeaponSheet:
    weapon: str
    category: str
    camos: list[Camo]
    verified_at: float | None = None


@dataclass
class MatchStats:
    at: float
    kills: int
    deaths: int
    score: int | None
    result: Literal["win", "loss", "draw"] | None
    mode: str | None
    map: str | None
    weapon: str | None
    fingerprint: str

    @property
    def kd(self) -> float:
        return self.kills / max(self.deaths, 1)


@dataclass
class GlobalStats:
    kills: int = 0
    deaths: int = 0
    wins: int = 0
    losses: int = 0
    games: int = 0
    calibrated_at: float | None = None
    matches_since_calibration: int = 0

    @property
    def kd(self) -> float:
        return self.kills / max(self.deaths, 1)

    @property
    def win_rate(self) -> float | None:
        decided = self.wins + self.losses
        return self.wins / decided if decided else None


@dataclass
class AppState:
    weapon: str | None = None
    sheets: dict[str, WeaponSheet] = field(default_factory=dict)
    last_match: MatchStats | None = None
    global_stats: GlobalStats = field(default_factory=GlobalStats)
    seen_fingerprints: list[str] = field(default_factory=list)
    phase: Phase = "unknown"
    notices: list[str] = field(default_factory=list)
    window_geometry: tuple[int, int, int, int] | None = None
    always_on_top: bool = False
    meta_builds: dict[str, str] = field(default_factory=dict)  # weapon -> chosen meta build style
    learned_weapons: list[str] = field(default_factory=list)
    player_level: int | None = None
    prestige: int | None = None   # set by the player once (the emblem's digit can't be read)
    site_publish: bool = False    # 'Publier mes stats sur le site' (opt-in)
    site_pseudo: str | None = None
    site_id: str | None = None
    site_key: str | None = None   # secret given by the site at registration; stays on this PC
    site_show_camos: bool = False
    site_leagues: list[dict] = field(default_factory=list)  # [{"code": "QG7K2P", "name": "CoDQG France"}]
    reading_suspended: str | None = None  # remote switch off: message shown; None = screen reading allowed
    version: int = 3
