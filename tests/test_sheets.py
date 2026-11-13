from trackcod.sheets import (ApparenceCamo, ApparenceReading, apply_apparence, display_name, name_confirmed,
                             new_sheet, next_camo)


def _sheet():
    return new_sheet("ISO NIGHTSHADE", "Mitraillette")


def _get(sheet, key):
    return next(c for c in sheet.camos if c.key == key)


def _read(name, section="special", progress=None, reads=None, access_met=None, locked=False, counts=None,
          challenge=None, at=1.0):
    camo = ApparenceCamo(name, section, None, access_met, None, challenge, progress, locked, None,
                         name_reads=reads if reads is not None else [name])
    return ApparenceReading([camo], counts or {}, at=at)


def test_new_sheet_is_empty():
    s = _sheet()
    assert s.camos == [] and s.verified_at is None and s.category == "Mitraillette"


def test_slots_from_headers():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (8, 8), "special": (2, 3), "erudit": (0, 4)}, at=1.0))
    assert [c.key for c in s.camos if c.section == "special"] == ["special:1", "special:2", "special:3"]
    assert all(c.state == "done" for c in s.camos if c.section == "military") and len(s.camos) == 15
    assert display_name(_get(s, "military:3")) == "Militaire 3"
    assert display_name(_get(s, "special:2")) == "Spécial ?" and display_name(_get(s, "erudit:1")) == "Or"
    assert s.verified_at == 1.0


def test_one_read_is_not_confirmed_two_are():
    s = _sheet()
    apply_apparence(s, _read("ASPHA{3E-", progress=(46, 50), access_met=True, counts={"special": (0, 3)}))
    c = next(c for c in s.camos if c.progress == (46, 50))
    assert display_name(c) == "ASPHA 3E ?" and not name_confirmed(c)
    apply_apparence(s, _read("ASPHALTE", progress=(46, 50), reads=["ASPHALTE", "ASPHALTE"]))
    assert display_name(c) == "ASPHALTE" and name_confirmed(c)
    assert sum(1 for x in s.camos if x.section == "special" and x.name_votes) == 1


def test_state_kept_when_name_settles():
    s = _sheet()
    apply_apparence(s, _read("TOPO NOIR", progress=(10, 10), counts={"special": (1, 3)}))
    key = next(c.key for c in s.camos if c.state == "done")
    apply_apparence(s, _read("TOPO NOIR", reads=["TOPO NOIR", "TOPO NOIR"]))
    c = _get(s, key)
    assert c.state == "done" and name_confirmed(c)


def test_unknown_special_slots_inferred_done():
    s = _sheet()
    apply_apparence(s, _read("MARRON", progress=(9, 15), access_met=True, counts={"special": (2, 3)}))
    assert sorted(c.state for c in s.camos if c.section == "special") == ["available", "done", "done"]


def test_no_free_slot_ignores_read():
    s = _sheet()
    apply_apparence(s, _read("ASPHALTE", counts={"special": (0, 1)}))
    apply_apparence(s, _read("MARRON"))
    specials = [c for c in s.camos if c.section == "special"]
    assert len(specials) == 1 and list(specials[0].name_votes) == ["ASPHALTE"]


def test_untrusted_reading_skips_counts():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (8, 8)}, at=1.0), weapon_confirmed=False)
    assert s.camos == [] and s.verified_at is None


def test_military_read_by_number():
    s = _sheet()
    apply_apparence(s, _read("CAMOUFLAGE MILITAIRE 3", section="military", progress=(3, 10),
                             counts={"military": (2, 8)}))
    assert _get(s, "military:3").progress == (3, 10) and _get(s, "military:3").state == "available"


def test_locked_special():
    s = _sheet()
    apply_apparence(s, _read("OMBRE DE LA JUNGLE", access_met=False, locked=True, counts={"special": (0, 3)}))
    assert any(c.state == "locked" for c in s.camos)


def test_next_camo_priority():
    s = _sheet()
    apply_apparence(s, _read("MARRON", progress=(9, 15), access_met=True,
                             counts={"military": (8, 8), "special": (2, 3), "erudit": (0, 4)}))
    nxt = next_camo(s)
    assert nxt.progress == (9, 15)
    nxt.state = "done"
    assert next_camo(s).key == "erudit:1"


def test_full_count_overrides_stale_states():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (2, 8)}, at=1.0))
    _get(s, "military:3").state = "available"
    apply_apparence(s, ApparenceReading([], {"military": (8, 8)}, at=2.0))
    assert all(c.state == "done" for c in s.camos if c.section == "military")


def test_challenge_and_progress_copied():
    s = _sheet()
    apply_apparence(s, _read("ASPHALTE", progress=(46, 50), access_met=True, counts={"special": (0, 3)},
                             challenge="Faites 50 éliminations"))
    c = next(c for c in s.camos if c.progress)
    assert c.challenge_fr == "Faites 50 éliminations" and c.read_at == 1.0 and c.state == "available"


def test_display_name_is_cleaned():
    s = _sheet()
    apply_apparence(s, _read("TOPO+NOIR-", reads=["TOPO+NOIR-"] * 2, counts={"special": (0, 3)}))
    assert display_name(next(c for c in s.camos if c.name_votes)) == "TOPO NOIR"


def test_full_count_ignored_when_a_camo_is_seen_in_progress():
    s = _sheet()
    apply_apparence(s, _read("MARRON", progress=(9, 15), access_met=True, counts={"special": (3, 3)}))
    assert next(c for c in s.camos if c.progress == (9, 15)).state == "available"


# ----- Érudit : ordre et noms fixes du jeu -----

def test_erudit_slots_named_in_game_order():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"erudit": (0, 4)}, at=1.0))
    er = sorted((c for c in s.camos if c.section == "erudit"), key=lambda c: c.order)
    assert [display_name(c) for c in er] == ["Or", "Platine", "Rupture harmonique", "Divergence"]
    assert "33" in er[3].access_text


def test_erudit_read_lands_on_its_named_slot():
    s = _sheet()
    apply_apparence(s, _read("PLATINE", section="erudit", progress=(3, 25), access_met=True,
                             counts={"erudit": (0, 4)}))
    apply_apparence(s, _read("RUPTURE+ARMONIQUE-", section="erudit", access_met=False, locked=True))
    er = sorted((c for c in s.camos if c.section == "erudit"), key=lambda c: c.order)
    assert er[1].progress == (3, 25) and er[2].state == "locked" and er[0].state == "unknown"


def test_existing_sheet_erudit_reordered():
    s = _sheet()
    from trackcod.model import Camo
    s.camos = [Camo("erudit:1", "PLATINE", "erudit", 201, name_votes={"PLATINE": 2}),
               Camo("erudit:2", None, "erudit", 202), Camo("erudit:3", None, "erudit", 203),
               Camo("erudit:4", None, "erudit", 204)]
    apply_apparence(s, ApparenceReading([], {"erudit": (0, 4)}, at=1.0))
    er = sorted((c for c in s.camos if c.section == "erudit"), key=lambda c: c.order)
    assert [display_name(c) for c in er] == ["Or", "Platine", "Rupture harmonique", "Divergence"]


def test_display_uses_most_frequent_read():
    s = _sheet()
    apply_apparence(s, _read("OR NOIR", reads=["OR NOIRI", "OR NOIR", "OR NOIR", "OR NOIR"],
                             counts={"special": (0, 3)}))
    assert display_name(next(c for c in s.camos if c.name_votes)) == "OR NOIR"


def test_special_slot_holding_an_erudit_name_is_cleared():
    from trackcod.model import Camo
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"special": (0, 3), "erudit": (0, 4)}, at=1.0))
    bad = _get(s, "special:2")
    bad.name_votes, bad.state = {"RUPTURE4RMONIQUE": 2}, "available"
    apply_apparence(s, ApparenceReading([], {"special": (0, 3)}, at=2.0))
    assert bad.name_votes == {} and bad.state == "unknown" and display_name(bad) == "Spécial ?"


# ----- un camo reconnu par sa condition / son défi -----

ACCESS27 = "Obtenez 27 armets) supplémentaire[s en utilisant : Rezi 12"


def _read_access(name, access, challenge=None, counts=None):
    camo = ApparenceCamo(name, "special", access, False, None, challenge, None, True, None, name_reads=[name])
    return ApparenceReading([camo], counts or {}, at=1.0)


def test_garbled_names_with_same_condition_share_one_slot():
    s = _sheet()
    apply_apparence(s, _read_access("Pl NBI", ACCESS27, counts={"special": (0, 3)}))
    apply_apparence(s, _read_access("PIN", ACCESS27))
    apply_apparence(s, _read_access("PIN LANC", "Obtenez 27 armes supplémentaires en utilisant : Rezi 12"))
    named = [c for c in s.camos if c.section == "special" and c.name_votes]
    assert len(named) == 1 and sum(named[0].name_votes.values()) == 3


def test_different_conditions_stay_separate():
    s = _sheet()
    apply_apparence(s, _read_access("OR NOIR", "Obtenez 10 armes supplémentaires en utilisant : Rezi 12",
                                    counts={"special": (0, 3)}))
    apply_apparence(s, _read_access("PIN BLANC", ACCESS27))
    assert len([c for c in s.camos if c.section == "special" and c.name_votes]) == 2


def test_recorded_duplicates_are_merged():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"special": (0, 3)}, at=1.0))
    for key, name in (("special:1", "PL NBI"), ("special:2", "PIN"), ("special:3", "PIN LANC")):
        c = _get(s, key)
        c.name_votes, c.name_forms, c.access_text, c.state = {name: 1}, {name: name}, ACCESS27, "locked"
    apply_apparence(s, ApparenceReading([], {"special": (0, 3)}, at=2.0))
    named = [c for c in s.camos if c.section == "special" and c.name_votes]
    assert len(named) == 1 and sum(named[0].name_votes.values()) == 3 and named[0].state == "locked"
    assert sum(1 for c in s.camos if c.section == "special" and display_name(c) == "Spécial ?") == 2


# ----- militaires débloqués dans l'ordre -----

def test_military_partial_count_is_sequential():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (5, 8)}, at=1.0))
    states = [c.state for c in sorted((c for c in s.camos if c.section == "military"), key=lambda c: c.order)]
    assert states == ["done"] * 5 + ["available"] + ["locked"] * 2


def test_military_zero_count():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (0, 8)}, at=1.0))
    states = [c.state for c in sorted((c for c in s.camos if c.section == "military"), key=lambda c: c.order)]
    assert states == ["available"] + ["locked"] * 7


# ----- Érudit et spéciaux aussi dans l'ordre (HAN 86 : 'ÉRUDIT [1/4]' avec Or obtenu) -----

def _states(s, section):
    return [c.state for c in sorted((c for c in s.camos if c.section == section), key=lambda c: c.order)]


def test_erudit_partial_count_marks_first_ones_done():
    # Platine stays as read: it needs every weapon of the category in Or
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"erudit": (1, 4)}, at=1.0))
    assert _states(s, "erudit")[0] == "done" and "done" not in _states(s, "erudit")[1:]


def test_special_partial_count_does_not_open_the_next_one():
    from trackcod.known_camos import KnownCamos
    from trackcod.sheets import seed_specials
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))  # game order known: Or noir, Coup de pinceau, Pin blanc
    apply_apparence(s, ApparenceReading([], {"special": (1, 3)}, at=1.0))
    assert _states(s, "special") == ["done", "unknown", "unknown"]  # the next one may still need attachments


def test_count_never_undoes_a_done_camo():
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"military": (5, 8)}, at=1.0))
    apply_apparence(s, ApparenceReading([], {"military": (3, 8)}, at=2.0))  # misread digit
    assert _states(s, "military")[:5] == ["done"] * 5


def test_unreadable_count_digit_is_ignored():
    from trackcod.readers.apparence import _section_counts
    from trackcod.readers.common import OcrLine
    counts = _section_counts([OcrLine("ÉRUDIT [�/4]", 0.18, 0.56, 0.05, 0.02)])
    s = _sheet()
    apply_apparence(s, ApparenceReading([], {"erudit": (1, 4)}, at=1.0))
    apply_apparence(s, ApparenceReading([], counts, at=2.0))
    assert _states(s, "erudit")[0] == "done" and len(_states(s, "erudit")) == 4


# ----- 'ÉRUDIT [Ø/4]': the slashed zero is read '9', 'a', '3'... (CRONEN OSPREY got Or/Platine/Rupture done) -----

def test_conflicting_count_reads_are_ignored():
    from trackcod.readers.apparence import _section_counts
    from trackcod.readers.common import OcrLine
    lines = [OcrLine("ÉRUDIT [3/4]", 0.18, 0.56, 0.05, 0.02), OcrLine("ÉRUDIT [9/4]", 0.18, 0.56, 0.05, 0.02),
             OcrLine("SPÉCIAL [1/3]", 0.18, 0.4, 0.05, 0.02), OcrLine("SPÉCIAL [1/3]", 0.18, 0.4, 0.05, 0.02)]
    counts = _section_counts(lines)
    assert counts["erudit"] == (-1, 4) and counts["special"] == (1, 3)


def test_erudit_cannot_be_done_while_a_special_is_not():
    from trackcod.known_camos import KnownCamos
    from trackcod.sheets import seed_specials
    s = new_sheet("CRONEN OSPREY", "Fusil d'assaut")
    seed_specials(s, KnownCamos.load().specials("CRONEN OSPREY"))
    apply_apparence(s, ApparenceReading([], {"special": (0, 3), "erudit": (3, 4)}, at=1.0))
    assert "done" not in _states(s, "erudit")


def test_padlock_seen_undoes_a_wrong_done():
    from trackcod.sheets import apply_tile_locks, ensure_slots
    s = _sheet()
    ensure_slots(s, "erudit", 4)
    er = sorted((c for c in s.camos if c.section == "erudit"), key=lambda c: c.order)
    er[2].state = "done"
    apply_tile_locks(s, {("erudit", 3): True})
    assert er[2].state == "locked"


def test_visit_frames_disagreeing_on_a_count_cancel_it():
    from trackcod.readers.apparence import HoverTracker
    h = HoverTracker()
    h.feed(ApparenceReading([], {"erudit": (3, 4)}, at=1.0))
    h.feed(ApparenceReading([], {"erudit": (0, 4)}, at=2.0))
    assert h.finish().section_counts["erudit"] == (-1, 4)


def test_saved_sheet_repaired_when_loaded(tmp_path, registry):
    from trackcod.engine import Engine
    from trackcod.model import AppState
    s = _sheet()
    from trackcod.sheets import ensure_slots
    ensure_slots(s, "special", 3)
    ensure_slots(s, "erudit", 4)
    for c in s.camos:
        c.state = {"special": "locked", "erudit": "done"}.get(c.section, c.state)
    st = AppState(weapon=s.weapon, sheets={s.weapon: s})
    e = Engine(registry, st, tmp_path / "s.json", tmp_path / "m.jsonl", lambda: None, lambda: 1.0)
    assert "done" not in _states(e.sheet(s.weapon), "erudit")


def test_erudit_locked_while_specials_are_locked():
    # CRONEN OSPREY: 3 specials locked, Or / Platine read as unknown -> they can't be started either
    from trackcod.known_camos import KnownCamos
    from trackcod.model import AppState
    from trackcod.sheets import ensure_slots, next_camo, seed_specials
    from trackcod.ui.viewmodel import build_view
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    ensure_slots(s, "erudit", 4)
    ensure_slots(s, "military", 8)
    for c in s.camos:
        c.state = {"special": "locked", "military": "done"}.get(c.section, "unknown")
    apply_apparence(s, ApparenceReading([], {}, at=1.0))
    assert next_camo(s) is None
    rows = build_view(AppState(weapon="REZI 12", sheets={"REZI 12": s}), 2.0).erudit
    assert all(r.icon == "🔒" for r in rows)
    assert "spéciaux" in rows[0].detail and "Or" in rows[1].detail
    for c in s.camos:  # the last special done: Or is within reach again
        if c.section == "special":
            c.state = "done"
    assert next_camo(s).key == "erudit:1"


def _target(s):
    apply_apparence(s, _read("ASPHALTE", progress=(10, 50), counts={"military": (0, 0), "special": (0, 3)}))
    return next_camo(s)


def test_counter_that_does_not_move_after_matches_is_stalled():
    from trackcod.sheets import count_match
    s = _sheet()
    c = _target(s)
    assert c.name_fr == "ASPHALTE" and c.matches_stalled == 0
    for _ in range(3):
        count_match(s)
    assert c.matches_unread == 3 and c.matches_stalled == 0        # not read again yet: nothing known
    apply_apparence(s, _read("ASPHALTE", progress=(10, 50), at=2.0))
    assert c.matches_unread == 0 and c.matches_stalled == 3
    count_match(s)
    apply_apparence(s, _read("ASPHALTE", progress=(12, 50), at=3.0))   # it moved: all good again
    assert c.matches_stalled == 0 and c.matches_unread == 0


def test_erudit_challenges_for_pistols_and_launchers():
    from trackcod.sheets import ERUDIT_CHALLENGES
    assert ERUDIT_CHALLENGES["Pistolet"][1] == "Tuer 20 joueurs par derrière"
    assert ERUDIT_CHALLENGES["Lanceur"][2] == "Éliminer 7 fois 10 joueurs dans une même partie"
