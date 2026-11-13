from trackcod.model import AppState, Camo, GlobalStats, MatchStats, WeaponSheet
from trackcod.store import append_match, load_state, save_state


def _state():
    s = AppState(weapon="ISO Nightshade", window_geometry=(10, 20, 340, 900))
    s.sheets["ISO Nightshade"] = WeaponSheet(
        "ISO Nightshade", "Mitraillette",
        [Camo("special:1", "ASPHALTE", "special", 101, progress=(46, 50), state="available",
              name_votes={"ASPHALTE": 2}, name_forms={"ASPHALTE": "ASPHALTE"})],
    )
    s.last_match = MatchStats(1.0, 24, 17, 2475, "win", "Domination", "Cheongun", "ISO Nightshade", "fp")
    s.global_stats = GlobalStats(kills=10, deaths=5, games=1, calibrated_at=3.0)
    return s


def test_roundtrip(tmp_path):
    s = _state()
    save_state(s, tmp_path / "state.json")
    t = load_state(tmp_path / "state.json")
    assert t == s and t.sheets["ISO Nightshade"].camos[0].progress == (46, 50)


def test_missing_file_gives_default(tmp_path):
    assert load_state(tmp_path / "nope.json") == AppState()


def test_corrupt_file_gives_default(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{oops", encoding="utf-8")
    assert load_state(p) == AppState() and (tmp_path / "state.json.bak").exists()


def test_fingerprints_bounded(tmp_path):
    s = AppState(seen_fingerprints=[str(i) for i in range(250)])
    save_state(s, tmp_path / "s.json")
    assert load_state(tmp_path / "s.json").seen_fingerprints == [str(i) for i in range(50, 250)]


def test_append_match(tmp_path):
    p = tmp_path / "m.jsonl"
    m = MatchStats(1.0, 24, 17, None, None, None, None, None, "a")
    append_match(m, p)
    append_match(m, p)
    assert len(p.read_text(encoding="utf-8").splitlines()) == 2


def test_kd_no_deaths():
    assert MatchStats(0, 5, 0, None, None, None, None, None, "x").kd == 5.0


def test_global_ratios():
    g = GlobalStats(kills=30, deaths=20, wins=3, losses=1, games=4)
    assert g.kd == 1.5 and g.win_rate == 0.75
    assert GlobalStats().win_rate is None


def test_list_root_gives_default(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("[1, 2]", encoding="utf-8")
    assert load_state(p) == AppState()


def test_meta_builds_roundtrip(tmp_path):
    s = AppState(meta_builds={"ISO Nightshade": "LOW_LEVEL"})
    save_state(s, tmp_path / "s.json")
    assert load_state(tmp_path / "s.json").meta_builds == {"ISO Nightshade": "LOW_LEVEL"}


def test_v1_state_migrated(tmp_path):
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"weapon": "ISO Nightshade", 
                             "sheets": {"ISO Nightshade": {"weapon": "ISO Nightshade", "category": "SMG", "camos": [
                                 {"key": "asphalt", "name_en": "Asphalt", "name_fr": "Asphalte", "section": "special",
                                  "order": 9, "challenge_en": "x"}], "applied_feed_ids": ["3@1"]}},
                             "global_stats": {"kills": 2079, "deaths": 2330, "games": 126},
                             "window_geometry": [1, 2, 3, 4], "meta_builds": {"ISO Nightshade": "LOW_LEVEL"}}),
                 encoding="utf-8")
    s = load_state(p)
    assert s.version == 3 and s.sheets == {} and s.global_stats.kills == 2079
    assert s.window_geometry == (1, 2, 3, 4) and s.meta_builds == {"ISO Nightshade": "LOW_LEVEL"}
    assert (tmp_path / "state-v1.json").exists()


def test_learned_weapons_roundtrip(tmp_path):
    save_state(AppState(learned_weapons=["NOUVELLE ARME"]), tmp_path / "s.json")
    assert load_state(tmp_path / "s.json").learned_weapons == ["NOUVELLE ARME"]


def test_migration_saves_v2_state_immediately(tmp_path):
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"global_stats": {"kills": 5}}), encoding="utf-8")
    load_state(p)
    assert json.loads(p.read_text(encoding="utf-8"))["version"] == 3
    assert (tmp_path / "state-v1.json").exists()


def test_v2_sheets_specials_relearned_once(tmp_path):
    import dataclasses
    import json
    s = AppState(version=2)
    s.sheets["REZI 12"] = WeaponSheet("REZI 12", "Fusil à pompe", [
        Camo("military:1", "Militaire 1", "military", 1, state="done"),
        Camo("special:1", "FLI", "special", 101, state="locked", name_votes={"FLI": 2}, name_forms={"FLI": "FLI"}),
        Camo("erudit:1", "Or", "erudit", 201, state="done", name_votes={"OR": 2})])
    p = tmp_path / "state.json"
    data = dataclasses.asdict(s)
    p.write_text(json.dumps(data, default=list), encoding="utf-8")
    t = load_state(p)
    sh = t.sheets["REZI 12"]
    sp = next(c for c in sh.camos if c.key == "special:1")
    assert t.version == 3 and sp.name_votes == {} and sp.state == "unknown"
    assert next(c for c in sh.camos if c.key == "military:1").state == "done"
    assert next(c for c in sh.camos if c.key == "erudit:1").state == "done"   # érudit names are fixed now


def test_raw_site_category_translated_on_load(tmp_path):
    from trackcod.model import AppState, WeaponSheet
    from trackcod.store import load_state, save_state
    st = AppState(sheets={"PILA": WeaponSheet("PILA", "LAUNCHER", [])})  # saved before 'Lanceur' existed
    save_state(st, tmp_path / "s.json")
    assert load_state(tmp_path / "s.json").sheets["PILA"].category == "Lanceur"


def test_compact_mode_and_phase_time_are_saved(tmp_path):
    s = AppState(phase="in_match", phase_at=123.0, compact=True, compact_geometry=(10, 20, 300, 110))
    save_state(s, tmp_path / "state.json")
    t = load_state(tmp_path / "state.json")
    assert (t.phase_at, t.compact, t.compact_geometry) == (123.0, True, (10, 20, 300, 110))
