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
    matches_unread: int = 0    # matches played with this camo as target since its counter was last read
    matches_stalled: int = 0   # matches after which a fresh read showed the very same counter


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
class DailyChallenge:
    """One 'DÉFI DU JOUR' as read in the menus (text as shown in game, total from the text)."""
    text: str
    total: int | None
    progress: int | None = None
    done: bool = False


@dataclass
class AppState:
    weapon: str | None = None
    sheets: dict[str, WeaponSheet] = field(default_factory=dict)
    last_match: MatchStats | None = None
    global_stats: GlobalStats = field(default_factory=GlobalStats)
    seen_fingerprints: list[str] = field(default_factory=list)
    phase: Phase = "unknown"
    phase_at: float | None = None  # when the phase was last set (a match left without a scoreboard ends)
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
    compact: bool = False         # small always-on-top window instead of the full one (hidden during a match)
    compact_geometry: tuple[int, int, int, int] | None = None
    daily: list[DailyChallenge] = field(default_factory=list)  # 'DÉFIS DU JOUR'
    daily_bonus: tuple[int, int] | None = None                 # 'Terminez 3 défi(s) du jour' n/3
    daily_at: float | None = None                              # last read of the list
    daily_resets_at: float | None = None                       # from the 'xxH yyM' timer, when read
    reading_suspended: str | None = None  # remote switch off: message shown; None = screen reading allowed
    version: int = 3
