"""Specials open after N more weapon items: read N in Apparence, count 'NOUVEL ÉLÉMENT DÉBLOQUÉ' in match."""

from trackcod.known_camos import KnownCamos
from trackcod.model import AppState
from trackcod.readers.common import OcrLine
from trackcod.readers.item_unlock import read_item_unlock
from trackcod.sheets import (ApparenceCamo, ApparenceReading, apply_apparence, count_item_unlock, items_left,
                             new_sheet, seed_specials)
from trackcod.ui.viewmodel import build_view


def _lines(*items):
    return [OcrLine(t, x, y, 0.2, 0.03) for t, x, y in items]


BANNER = _lines(("NOUVEL ÉLÉMENT", 0.05, 0.38), ("SILEN", 0.9, 0.7))  # real OCR of the in-game banner
# level-up screen as shown in game: 'NIVEAU SUPÉRIEUR' + weapon, and the card 'DÉBLOQUÉ' + item name
BANNER_STOCK = _lines(("NIVEAU SUPÉRIEUR", 0.12, 0.58), ("M4", 0.33, 0.70), ("DÉBLOQUÉ", 0.69, 0.62),
                      ("CROSSE DEMO HVR2", 0.68, 0.71))
BANNER_CAMO = _lines(("NIVEAU SUPÉRIEUR", 0.12, 0.58), ("DÉBLOQUÉ", 0.69, 0.62),
                     ("CAMOUFLAGE MILITAIRE 3", 0.68, 0.71))


def test_items_left_from_real_access_reads():
    assert items_left("Obtenez 10 armets) supplémentaire[sj én utilisant : Rezi 12") == 10
    assert items_left("Obtenez 27 arme(s) supplémentaire(s)") == 27
    assert items_left("Obtenez tous les camouflages militaires") is None and items_left(None) is None


def test_read_item_unlock():
    assert read_item_unlock(BANNER).item == "SILEN" and not read_item_unlock(BANNER).is_camo
    assert read_item_unlock(BANNER_CAMO).is_camo
    assert read_item_unlock(BANNER_STOCK).item == "CROSSE DEMO HVR2" and not read_item_unlock(BANNER_STOCK).is_camo
    assert read_item_unlock(_lines(("Nouvelle arme débloquée", 0.4, 0.3))) is None
    assert read_item_unlock(_lines(("63 /63 ÉLÉMENTS DÉBLOQUÉS", 0.1, 0.1))) is None  # armory menu


def _rezi():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    reads = [ApparenceCamo("OR NOIR", "special", "Obtenez 2 arme(s) supplémentaire(s)", False, None, None, None,
                           True, None),
             ApparenceCamo("PIN BLANC", "special", "Obtenez 5 arme(s) supplémentaire(s)", False, None, None, None,
                           True, None)]
    for r in reads:
        apply_apparence(s, ApparenceReading([r], {"special": (0, 3)}, at=1.0))
    return s


def _special(s, name):
    return next(c for c in s.camos if c.name_fr == name)


def test_apparence_stores_items_left():
    s = _rezi()
    assert _special(s, "Or noir").items_left == 2 and _special(s, "Pin blanc").items_left == 5


def test_count_opens_special_when_zero():
    s = _rezi()
    assert count_item_unlock(s) == []
    opened = count_item_unlock(s)
    assert [c.name_fr for c in opened] == ["Or noir"] and _special(s, "Or noir").state == "available"
    assert _special(s, "Pin blanc").items_left == 3 and _special(s, "Pin blanc").state == "locked"


def test_row_shows_items_left():
    s = _rezi()
    v = build_view(AppState(weapon="REZI 12", sheets={"REZI 12": s}), 2.0)
    or_noir = next(r for r in v.specials if r.name == "Or noir")
    assert "2" in or_noir.detail and "débloquer" in or_noir.detail


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def _engine(tmp_path, registry, frames):
    from trackcod.engine import Engine
    st = AppState(weapon="REZI 12", sheets={"REZI 12": _rezi()})
    clock = Clock()
    e = Engine(registry, st, tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, clock)
    return e, clock


def _run(e, clock, n):
    for _ in range(n):
        e.step()
        clock.t += 1.0


OTHER = _lines(("FPS : 160", 0.15, 0.0))


def test_banner_held_on_screen_counts_once(tmp_path, registry):
    frames = [BANNER, BANNER, BANNER, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 4)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 1


def test_two_items_in_a_row_count_twice_and_open_the_special(tmp_path, registry):
    frames = [BANNER, BANNER_STOCK, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 3)
    s = e.state.sheets["REZI 12"]
    assert _special(s, "Or noir").state == "available"
    assert any("Or noir" in n for n in e.state.notices)


def test_military_camo_in_the_card_does_not_count(tmp_path, registry):
    frames = [BANNER_CAMO, OTHER, OTHER, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 4)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 2


def test_unreadable_card_again_after_a_gap_counts_again(tmp_path, registry):
    card = _lines(("NIVEAU SUPÉRIEUR", 0.12, 0.58), ("DÉBLOQUÉ", 0.69, 0.62))  # item name not read
    frames = [card, card, OTHER, OTHER, OTHER, card]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 6)
    assert _special(e.state.sheets["REZI 12"], "Or noir").state == "available"


def test_same_item_card_on_consecutive_frames_counts_once(tmp_path, registry):
    frames = [BANNER_STOCK, BANNER_STOCK, BANNER_STOCK, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 4)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 1



def test_number_shown_is_what_is_left():
    # Rezi 12 'Or noir': the game shows 'Obtenez 10 arme(s) supplémentaire(s)' with 10 attachments still to get
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    r = ApparenceCamo("OR NOIR", "special", "Obtenez 10 arme(s) supplémentaire(s) en utilisant : Rezi 12", False,
                      None, None, None, True, None)
    apply_apparence(s, ApparenceReading([r], {"special": (0, 3)}, at=1.0))
    assert _special(s, "Or noir").items_left == 10


def _state_like_player():
    # the player's REZI 12 sheet: Or noir locked (10 left), Pin blanc read before the counter existed
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    on, pin = _special(s, "Or noir"), _special(s, "Pin blanc")
    on.state, on.items_left = "locked", 10
    pin.state, pin.access_text = "locked", "Obtenez 27 armets) supplémentaire[s en utilisant : Rezi 12"
    return AppState(weapon="REZI 12", sheets={"REZI 12": s})


def test_special_after_a_locked_one_shows_as_locked():
    v = build_view(_state_like_player(), 2.0)
    coup = next(r for r in v.specials if r.name == "Coup de pinceau")
    assert coup.icon == "🔒" and "Or noir" in coup.detail


def test_old_condition_text_shows_the_counter():
    v = build_view(_state_like_player(), 2.0)
    pin = next(r for r in v.specials if r.name == "Pin blanc")
    assert pin.detail == "encore 27 accessoires à débloquer"


def test_old_condition_text_is_counted_in_match():
    st = _state_like_player()
    count_item_unlock(st.sheets["REZI 12"])
    assert _special(st.sheets["REZI 12"], "Pin blanc").items_left == 26


def test_menu_debloque_label_is_not_a_level_up():
    # real log, class menu: a lone 'DÉBLOQUÉ' above the weapon description was counted as an attachment
    menu = _lines(("DÉBLOQUÉ", 0.69, 0.62), ("FUSIL A POMPE SEMI AUTOMATIQUE DE CALIBRE 12 A CADENCE RAPIDE", 0.68, 0.66))
    assert read_item_unlock(menu) is None


def test_level_up_without_card_is_not_an_item():
    assert read_item_unlock(_lines(("NIVEAU SUPÉRIEUR", 0.12, 0.58), ("M4", 0.33, 0.70))) is None


def test_locked_special_never_hovered_says_how_to_get_the_count():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    _special(s, "Or noir").state = "locked"  # padlock seen on the tile, condition never read
    v = build_view(AppState(weapon="REZI 12", sheets={"REZI 12": s}), 2.0)
    row = next(r for r in v.specials if r.name == "Or noir")
    assert "survole" in row.detail and "Apparence" in row.detail


def test_same_card_read_with_different_junk_counts_once(tmp_path, registry):
    """Real session 13/11: one 'NOUVEL ÉLÉMENT DÉBLOQUÉ' card read twice, one second apart, with other OCR junk."""
    a = _lines(("NOUVEL ÉLÉMENT DÉBLOQ", 0.39, 0.27), ("MUNITIONS PERFORANTES X 30 MM PART SRY LAUSER81", 0.6, 0.32))
    b = _lines(("NOUVEL ÉLÉMENT DÉBLOQ", 0.39, 0.27), ("ADMINISTRATIF MUNITIONS PERFORANTES X INJ", 0.6, 0.32))
    frames = [a, b, OTHER, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 4)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 1


def test_corner_camo_notification_of_the_held_weapon_unlocks_without_the_word(tmp_path, registry):
    """Real session 13/11: top-right 'VEL 46' + 'CAMOUFLAGE MILITAIRE 2', on one frame, no 'DÉBLOQUÉ' word."""
    toast = [OcrLine("REZI 12", 0.833, 0.252, 0.03, 0.015), OcrLine("CAMOUFLAGE MILITAIRE 2", 0.834, 0.272, 0.08, 0.026)]
    frames = [toast, OTHER, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 3)
    mil = {c.key: c.state for c in e.state.sheets["REZI 12"].camos if c.section == "military"}
    assert mil["military:1"] == "done" and mil["military:2"] == "done" and mil["military:3"] == "available"


def test_enemy_kill_card_with_a_camo_never_unlocks(tmp_path, registry):
    """The card of the enemy who killed you (centre of the screen) lists their weapon: never ours to unlock."""
    card = [OcrLine("REZI 12", 0.48, 0.652, 0.04, 0.017), OcrLine("CAMOUFLAGE MILITAIRE 2", 0.49, 0.669, 0.1, 0.021)]
    frames = [card, OTHER, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 3)
    assert all(c.state != "done" for c in e.state.sheets["REZI 12"].camos if c.section == "military")


def test_same_card_rule():
    from trackcod.engine import same_card
    assert same_card("MUNITIONS PERFORANTES X 30 MM PART SRY LAUSER81", "ADMINISTRATIF MUNITIONS PERFORANTES X INJ")
    assert not same_card("CHARGEUR 30 CARTOUCHES", "CHARGEUR 45 CARTOUCHES")
    assert not same_card("SILENCIEUX MONOLITHIQUE", "CROSSE DEMO HVR2")


def _fixture(name):
    import json
    from pathlib import Path
    path = Path(__file__).parent / "fixtures" / "ocr" / f"{name}.json"
    return [OcrLine(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


import pytest


@pytest.mark.parametrize("frame", [2243, 2888, 3344, 4290, 4594])
def test_half_read_banner_in_the_middle_is_an_item(frame):
    """Real session 14/11 (Cronen Osprey): 'NOUVEL ÉLÉMENT DÉBLOQUÉ' in white over the sky, read 'IJYEL ÉLÉMENT
    D -', 'NOUVEL ÉLÉ?', 'L ÉLÉMENT DÉB', 'L ÉLÉM'...: 9 banners of 13 were missed."""
    unlock = read_item_unlock(_fixture(f"element_debloque_{frame}"))
    assert unlock is not None and not unlock.is_camo


def test_banner_weapon_is_read_under_the_title():
    unlock = read_item_unlock(_fixture("element_debloque_3344"))
    assert unlock.weapon == "CRONEN OSPREY"


def test_item_name_read_on_the_next_frame_is_the_same_banner(tmp_path, registry):
    """The card name ('XR-9 TACTIQUE V2') shows up a frame after the title: still one item."""
    title = [OcrLine("L ÉLÉMENT DÉB", 0.44, 0.27, 0.1, 0.02)]
    named = title + [OcrLine("XR-9 TACTIQUE V2", 0.60, 0.32, 0.08, 0.015)]
    frames = [title, named, named, OTHER]
    e, clock = _engine(tmp_path, registry, frames)
    _run(e, clock, 4)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 1


def test_menu_label_alone_in_the_middle_is_not_a_banner():
    assert read_item_unlock(_lines(("DÉBLOQUÉ", 0.45, 0.27))) is None


def test_item_counts_for_the_weapon_named_on_the_banner(tmp_path, registry):
    """The banner names its weapon ('CRONEN OSPREY' under the title): another weapon's specials stay as they are."""
    banner = [OcrLine("L ÉLÉMENT DÉB", 0.44, 0.27, 0.1, 0.02), OcrLine("CRONEN OSPREY", 0.47, 0.32, 0.06, 0.015)]
    e, clock = _engine(tmp_path, registry, [banner, OTHER])
    _run(e, clock, 2)
    assert _special(e.state.sheets["REZI 12"], "Or noir").items_left == 2


def test_garbled_condition_never_replaces_a_readable_one():
    """Real session 15/11 (MAR-9): 'Obtenez 8 arme(s) supplémentaire(s)...' read well, then 'Obtenez batifiüs) supp e'
    on a later frame of the same visit: the tracker showed the garbled text instead of 'encore 8 accessoires'."""
    from trackcod.readers.apparence import HoverTracker
    good = ApparenceCamo("MANGROVE", "special", "Obtenez 8 armets) supplémentaire[s) en utilisant : MAR-9", False,
                         None, None, None, True, None)
    bad = ApparenceCamo("MANGROVE", "special", "Obtenez batifiüs) supp e", False, None, None, None, True, None)
    hover = HoverTracker()
    for camo in (good, bad):
        hover.feed(ApparenceReading([camo], {}, at=1.0, weapon="MAR-9"))
    read = hover.finish().camos[0]
    assert items_left(read.access_text) == 8


def test_garbled_condition_on_a_later_visit_keeps_the_count():
    s = _rezi()
    good = ApparenceCamo("OR NOIR", "special", "Obtenez 8 armets) supplémentaire[s) en utilisant : REZI 12", False,
                         None, None, None, True, None)
    bad = ApparenceCamo("OR NOIR", "special", "Obtenez u ârhéts Slipp", False, None, None, None, True, None)
    for camo in (good, bad):
        apply_apparence(s, ApparenceReading([camo], {}, at=1.0, weapon="REZI 12"))
    c = _special(s, "Or noir")
    assert c.items_left == 8 and items_left(c.access_text) == 8


# ----- real session 15/11 (VEL 46 levelling): each banner was counted twice -----

def _vel(tmp_path, registry, names):
    import json
    from pathlib import Path
    from trackcod.engine import Engine
    fix = Path(__file__).parent / "fixtures" / "ocr"
    frames = [OTHER if n is None else
              [OcrLine(**d) for d in json.loads((fix / f"element_bandeau_{n}.json").read_text(encoding="utf-8"))]
              for n in names]
    s = new_sheet("VEL 46", "Mitraillette")
    seed_specials(s, KnownCamos.load().specials("VEL 46"))
    gris = next(c for c in s.camos if c.name_fr == "Gris acier")
    gris.state, gris.items_left = "locked", 9
    clock = Clock()
    e = Engine(registry, AppState(weapon="VEL 46", sheets={"VEL 46": s}), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, clock)
    _run(e, clock, len(names) + 3)
    return 9 - gris.items_left


def test_banner_whose_name_shows_after_a_piece_of_debloque_counts_once(tmp_path, registry):
    """'OQUÉ' (the end of 'DÉBLOQUÉ') read where the name goes, then 'CROSSE EXP U-TURN' a frame later."""
    assert _vel(tmp_path, registry, ["1534", "1535"]) == 1


def test_banner_read_with_hud_text_on_the_next_frame_counts_once(tmp_path, registry):
    """'CANON RV-B V2', then 'CANON RV-B' with the perks on the right ('NINJA', 'SANG-FROID')."""
    assert _vel(tmp_path, registry, ["1800", "1801"]) == 1


def test_banner_with_a_shorter_name_on_the_next_frame_counts_once(tmp_path, registry):
    """'V46 VERT-TAC', then 'VERT-TAC'."""
    assert _vel(tmp_path, registry, ["2051", "2052"]) == 1


def test_banners_of_one_session_each_count(tmp_path, registry):
    """Banners 50, 53, 54 and 55 of the session: four items."""
    gap = [None] * 3  # minutes apart in the session
    assert _vel(tmp_path, registry, ["1534", "1535", *gap, "1800", "1801", *gap, "1997", *gap, "2051", "2052"]) == 4
