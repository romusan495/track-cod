from trackcod.known_camos import KnownCamos
from trackcod.sheets import (ApparenceCamo, ApparenceReading, apply_apparence, display_name, new_sheet,
                             seed_specials)


def _known():
    return KnownCamos.load()


def _specials(sheet):
    return [c for c in sheet.camos if c.section == "special"]


def test_shipped_list_has_rezi(registry):
    names = [k.name_fr for k in _known().specials("REZI 12")]
    assert names == ["Or noir", "Coup de pinceau", "Pin blanc"]
    assert _known().specials("ISO NIGHTSHADE") and _known().specials("Inconnue") == []


def test_seed_names_and_challenges():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, _known().specials("REZI 12"))
    assert [display_name(c) for c in _specials(s)] == ["Or noir", "Coup de pinceau", "Pin blanc"]
    assert _specials(s)[2].challenge_fr == "Faites 40 éliminations de joueurs en sautant"
    seed_specials(s, _known().specials("REZI 12"))
    assert len(_specials(s)) == 3


def _read(name, challenge=None, access=None):
    return ApparenceReading([ApparenceCamo(name, "special", access, None, None, challenge, None, False, None)],
                            {"special": (0, 3)}, at=1.0)


def test_garbled_reads_snap_to_known_names():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, _known().specials("REZI 12"))
    apply_apparence(s, _read("PIN LANC"))
    apply_apparence(s, _read("Pl NBI", challenge="Faites 40 éliminations de joueurs en sautant."))
    pin = next(c for c in _specials(s) if display_name(c) == "Pin blanc")
    assert pin.read_at == 1.0 and len(_specials(s)) == 3
    assert all(display_name(c) in ("Or noir", "Coup de pinceau", "Pin blanc") for c in _specials(s))


def test_unrecognised_read_is_ignored_when_list_known():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, _known().specials("REZI 12"))
    apply_apparence(s, _read("XQZW"))
    assert all(c.read_at is None for c in _specials(s))


def test_existing_junk_slots_replaced_by_known_names():
    s = new_sheet("REZI 12", "Fusil à pompe")
    apply_apparence(s, _read("OR NOIRI"))
    apply_apparence(s, _read("btenez 27 armes"))
    or_noir = next(c for c in _specials(s) if c.name_votes and "NOIR" in next(iter(c.name_votes)))
    or_noir.state = "locked"
    seed_specials(s, _known().specials("REZI 12"))
    named = {display_name(c): c.state for c in _specials(s)}
    assert named == {"Or noir": "locked", "Coup de pinceau": "unknown", "Pin blanc": "unknown"}


def test_specials_follow_shipped_order_even_if_read_out_of_order():
    # REZI 12 in game, left to right: Or noir, Coup de pinceau, Pin blanc. Pin blanc was read first.
    s = new_sheet("REZI 12", "Fusil à pompe")
    apply_apparence(s, _read("PIN BLANC"))
    apply_apparence(s, _read("OR NOIR"))
    seed_specials(s, _known().specials("REZI 12"))
    ordered = sorted(_specials(s), key=lambda c: c.order)
    assert [display_name(c) for c in ordered] == ["Or noir", "Coup de pinceau", "Pin blanc"]


def test_next_camo_does_not_skip_a_locked_special():
    from trackcod.sheets import next_camo
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, _known().specials("REZI 12"))
    or_noir = next(c for c in _specials(s) if display_name(c) == "Or noir")
    or_noir.state = "locked"
    nxt = next_camo(s)
    assert nxt is None or nxt.section != "special"
