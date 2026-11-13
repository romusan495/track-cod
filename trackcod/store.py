"""JSON persistence of AppState (atomic writes)."""

import dataclasses
import json
import os
from pathlib import Path

from trackcod.meta import CATEGORY_FR
from trackcod.model import AppState, Camo, GlobalStats, MatchStats, WeaponSheet

MAX_FINGERPRINTS = 200


def _to_json(obj):
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(type(obj))


def _camo(d: dict) -> Camo:
    d = dict(d)
    if d.get("progress") is not None:
        d["progress"] = tuple(d["progress"])
    return Camo(**d)


def _sheet(d: dict) -> WeaponSheet:
    return WeaponSheet(
        weapon=d["weapon"],
        category=CATEGORY_FR.get(d["category"], d["category"]),  # raw site key saved by older versions
        camos=[_camo(c) for c in d["camos"]],
        verified_at=d.get("verified_at"),
    )


def _from_dict(d: dict) -> AppState:
    geometry = d.get("window_geometry")
    return AppState(
        weapon=d.get("weapon"),
        sheets={k: _sheet(v) for k, v in d.get("sheets", {}).items()},
        last_match=MatchStats(**d["last_match"]) if d.get("last_match") else None,
        global_stats=GlobalStats(**d.get("global_stats", {})),
        seen_fingerprints=list(d.get("seen_fingerprints", []))[-MAX_FINGERPRINTS:],
        phase=d.get("phase", "unknown"),
        notices=list(d.get("notices", [])),
        window_geometry=tuple(geometry) if geometry else None,
        always_on_top=d.get("always_on_top", False),
        meta_builds=dict(d.get("meta_builds", {})),
        learned_weapons=list(d.get("learned_weapons", [])),
        player_level=d.get("player_level"),
        prestige=d.get("prestige"),
        site_publish=bool(d.get("site_publish", False)),
        site_pseudo=d.get("site_pseudo"),
        site_id=d.get("site_id"),
        site_key=d.get("site_key"),
        site_show_camos=bool(d.get("site_show_camos", False)),
        reading_suspended=d.get("reading_suspended"),
    )


def _relearn_specials(state: AppState) -> None:
    """v2.0 test builds could file érudit names or sentences as specials: forget specials once, keep the rest."""
    for sheet in state.sheets.values():
        for c in sheet.camos:
            if c.section == "special":
                c.name_votes, c.name_forms, c.name_fr = {}, {}, None
                c.state, c.progress, c.challenge_fr = "unknown", None, None
                c.access_text, c.access_met, c.read_at = None, None, None
    state.version = 3


def _migrate_v1(data: dict, path: Path) -> AppState:
    """v1 sheets came from an external catalog: keep stats and window prefs, relearn sheets from the game (spec v2 §5)."""
    kept = {k: data[k] for k in ("last_match", "global_stats", "seen_fingerprints", "window_geometry",
                                 "always_on_top", "meta_builds") if k in data}
    state = _from_dict(kept)  # may raise: then the caller moves the file to .bak, nothing renamed yet
    os.replace(path, path.with_name("state-v1.json"))
    save_state(state, path)   # a crash before the first save must not lose the migrated stats
    return state


def load_state(path: Path) -> AppState:
    path = Path(path)
    if not path.exists():
        return AppState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("version", 1) < 2:
            return _migrate_v1(data, path)
        state = _from_dict(data)
        if data.get("version") == 2:
            _relearn_specials(state)
        return state
    except (ValueError, TypeError, KeyError, AttributeError):
        os.replace(path, path.with_name(path.name + ".bak"))
        return AppState()


def save_state(state: AppState, path: Path) -> None:
    path = Path(path)
    data = dataclasses.asdict(state)
    data["seen_fingerprints"] = data["seen_fingerprints"][-MAX_FINGERPRINTS:]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, default=_to_json, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_matches(path: Path, n: int) -> list[MatchStats]:
    """The n most recent matches of matches.jsonl, newest first (unreadable lines skipped)."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[MatchStats] = []
    for line in reversed(lines):
        try:
            out.append(MatchStats(**json.loads(line)))
        except (ValueError, TypeError):
            continue
        if len(out) >= n:
            break
    return out


def append_match(m: MatchStats, path: Path) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(dataclasses.asdict(m), ensure_ascii=False) + "\n")
