"""Last-match and global multiplayer stats."""

import hashlib


from trackcod.model import AppState, GlobalStats, MatchStats
from trackcod.store import MAX_FINGERPRINTS


def match_fingerprint(kills: int, deaths: int, score: int | None, mode: str | None,
                      map: str | None, minute: int) -> str:
    raw = f"{kills}|{deaths}|{score}|{(mode or '').upper()}|{(map or '').upper()}|{minute}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def record_match(state: AppState, m: MatchStats) -> bool:
    if m.fingerprint in state.seen_fingerprints:
        return False
    state.seen_fingerprints.append(m.fingerprint)
    del state.seen_fingerprints[:-MAX_FINGERPRINTS]
    state.last_match = m
    g = state.global_stats
    g.games += 1
    g.kills += m.kills
    g.deaths += m.deaths
    if m.result == "win":
        g.wins += 1
    elif m.result == "loss":
        g.losses += 1
    g.matches_since_calibration += 1
    return True


def calibrate(state: AppState, g: GlobalStats, at: float) -> None:
    state.global_stats = GlobalStats(
        kills=g.kills, deaths=g.deaths, wins=g.wins, losses=g.losses, games=g.games,
        calibrated_at=at, matches_since_calibration=0,
    )
