import json
from pathlib import Path

import pytest

from trackcod.engine import Engine
from trackcod.model import AppState
from trackcod.readers.common import OcrLine
from trackcod.store import load_state
from trackcod.weapons import WeaponRegistry

FIX = Path(__file__).parent / "fixtures" / "ocr"
OTHER = [OcrLine("FPS : 160", .15, .0, .02, .01)]


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path, registry):
    frames: list = []
    clock = Clock()

    def make(state=None, reg=None):
        def source():
            return frames.pop(0) if frames else None
        return Engine(reg if reg is not None else registry, state or AppState(), tmp_path / "state.json",
                      tmp_path / "matches.jsonl", source, clock)
    return make, frames, clock, tmp_path


def _run(e, clock, n, dt=1.0):
    for _ in range(n):
        e.step()
        clock.t += dt


def test_match_start_sets_weapon(env):
    make, frames, clock, _ = env
    e = make()
    frames.append(load("match_start_iso"))
    assert e.step() is True
    assert e.state.weapon == "ISO NIGHTSHADE" and e.state.phase == "in_match"
    assert e.state.sheets["ISO NIGHTSHADE"].category == "Mitraillette"


def test_full_frame_apparence_creates_slots(env):
    make, frames, clock, _ = env
    e = make()
    frames.extend([load("apparence_full_asphalte"), OTHER, OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 6)
    s = e.state.sheets["ISO NIGHTSHADE"]
    assert e.state.weapon == "ISO NIGHTSHADE" and s.verified_at is not None
    assert [c.state for c in s.camos if c.section == "military"] == ["done"] * 8
    assert len([c for c in s.camos if c.section == "special"]) == 3


def test_scoreboard_seen_twice_counts_once(env):
    make, frames, clock, tmp = env
    e = make()
    frames.extend([load("match_start_iso"), load("scoreboard_victoire"), load("scoreboard_victoire")])
    _run(e, clock, 3)
    g = e.state.global_stats
    assert (g.games, g.kills, g.deaths, g.wins) == (1, 13, 12, 1)
    assert e.state.last_match.map == "LITHIUM" and e.state.last_match.weapon == "ISO NIGHTSHADE"
    assert e.state.phase == "post_match"
    assert len((tmp / "matches.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert load_state(tmp / "state.json").global_stats.games == 1


def _with_mode(lines, text):
    out = []
    for l in lines:
        if l.text.startswith("MATCH À MORT"):
            l = OcrLine(text, l.x, l.y, l.w, l.h)
        elif l.text == "HARDCORE":
            continue
        out.append(l)
    return out


def test_scoreboard_mode_ocr_variation_counts_once(env):
    make, frames, clock, _ = env
    e = make()
    frames.extend([load("scoreboard_victoire"), _with_mode(load("scoreboard_victoire"), "MATCH A MORT PAR EQUIPE")])
    _run(e, clock, 2)
    assert e.state.global_stats.games == 1


def test_scoreboard_still_on_screen_long_after_counts_once(env):
    make, frames, clock, _ = env
    e = make()
    frames.extend([load("scoreboard_victoire")] * 4)
    _run(e, clock, 4, dt=250)
    assert e.state.global_stats.games == 1


def test_combat_record_calibrates(env):
    make, frames, clock, _ = env
    e = make()
    frames.append(load("combat_record_mp"))
    e.step()
    g = e.state.global_stats
    assert (g.kills, g.deaths, g.games) == (2079, 2330, 126) and g.calibrated_at == clock.t


def test_no_game_window_is_noop(env):
    make, *_ = env
    assert make().step() is False


def test_apparence_without_weapon_gives_notice(env):
    make, frames, clock, _ = env
    e = make()
    frames.extend([load("apparence_iso"), OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 5)
    assert any("Arme inconnue" in n for n in e.state.notices) and e.state.sheets == {}


def test_apparence_without_weapon_line_does_not_touch_other_sheet(env):
    make, frames, clock, _ = env
    e = make()
    e.state.weapon = "M4"
    frames.extend([[l for l in load("apparence_full_asphalte") if not l.text.upper().startswith("PROGRESSION")],
                   OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 5)
    m4 = e.state.sheets.get("M4")
    assert m4 is None or (m4.verified_at is None and all(c.read_at is None for c in m4.camos)
                          and not any(c.section == "military" for c in m4.camos))


def test_offline_first_launch_learns_weapon(env):
    make, frames, clock, tmp = env
    e = make(reg=WeaponRegistry([], []))
    frames.extend([load("match_start_iso"), load("match_start_iso")])
    _run(e, clock, 2)
    assert e.state.weapon == "ISO NIGHTSHADE"
    assert "ISO NIGHTSHADE" in load_state(tmp / "state.json").learned_weapons


# ----- final review fixes -----

def test_unknown_weapon_learned_in_one_apparence_visit(env):
    make, frames, clock, _ = env
    e = make(reg=WeaponRegistry([], []))
    frames.extend([load("apparence_full_asphalte"), load("apparence_full_asphalte"), OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 6)
    assert e.state.weapon == "ISO NIGHTSHADE" and "ISO NIGHTSHADE" in e.state.sheets


def test_unconfirmed_weapon_never_applied_to_previous_one(env):
    make, frames, clock, _ = env
    e = make(reg=WeaponRegistry([], []))
    e.state.weapon = "M4"
    frames.extend([load("apparence_full_asphalte"), OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 5)
    m4 = e.state.sheets.get("M4")
    assert (m4 is None or m4.camos == []) and "ISO NIGHTSHADE" not in e.state.sheets
    assert e.state.weapon == "M4"


def test_manual_weapon_is_learned(env):
    make, *_ = env
    e = make(reg=WeaponRegistry([], []))
    e.set_weapon("Nouvelle Arme")
    assert e.state.weapon == "NOUVELLE ARME" and "NOUVELLE ARME" in e.registry.learned


def test_sheet_category_filled_later(env, meta):
    make, *_ = env
    reg = WeaponRegistry([], [])
    e = make(reg=reg)
    e.set_weapon("ISO NIGHTSHADE")
    reg.update_site(meta)
    assert e.sheet("ISO NIGHTSHADE").category == "Mitraillette"


def test_no_pause_while_in_apparence(env):
    make, frames, clock, _ = env
    e = make()
    assert e.next_interval() == 1.0
    frames.append(load("apparence_full_asphalte"))
    e.step()
    assert e.next_interval() < 0.2


def test_known_specials_seeded_for_new_sheet(env):
    make, *_ = env
    e = make()
    e.set_weapon("REZI 12")
    names = [c.name_fr for c in e.state.sheets["REZI 12"].camos if c.section == "special"]
    assert names == ["Or noir", "Coup de pinceau", "Pin blanc"]


def test_apparence_visit_saves_thumbnails_for_the_confirmed_weapon(env, registry, tmp_path):
    from PIL import Image
    from trackcod.thumbs import thumb_path
    _, frames, clock, tmp = env
    tile = Image.new("RGB", (96, 96), (230, 120, 60))
    taken = []

    def tiles():
        taken.append(1)
        return {("special", 3): tile}

    e = Engine(registry, AppState(), tmp / "state.json", tmp / "matches.jsonl",
               lambda: frames.pop(0) if frames else None, clock, tile_source=tiles, thumbs_dir=tmp / "vignettes")
    frames.extend([load("apparence_full_asphalte"), OTHER, OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 6)
    assert thumb_path(tmp / "vignettes", "ISO NIGHTSHADE", "special", 3) is not None


def test_thumbnails_dropped_when_weapon_unconfirmed(env, registry):
    from PIL import Image
    _, frames, clock, tmp = env
    tile = Image.new("RGB", (96, 96))
    e = Engine(registry, AppState(), tmp / "state.json", tmp / "matches.jsonl",
               lambda: frames.pop(0) if frames else None, clock,
               tile_source=lambda: {("special", 1): tile}, thumbs_dir=tmp / "vignettes")
    frames.extend([load("apparence_iso"), OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 5)
    assert not (tmp / "vignettes").exists()


def test_weapon_switches_on_the_first_apparence_frame(env):
    make, frames, clock, _ = env
    e = make()
    frames.append(load("apparence_full_asphalte"))
    assert e.step() is True
    assert e.state.weapon == "ISO NIGHTSHADE"  # not 3 s after leaving Apparence


def test_new_weapon_closes_the_previous_visit(env):
    make, frames, clock, _ = env
    e = make()
    rezi = [OcrLine("PROGRESSION REZI 12", l.x, l.y, l.w, l.h) if l.text.startswith("PROGRESSION") else l
            for l in load("apparence_full_asphalte")]  # same screen, another weapon chosen meanwhile
    frames.extend([load("apparence_full_asphalte"), rezi, OTHER, OTHER, OTHER, OTHER])
    _run(e, clock, 6)
    assert e.state.sheets["ISO NIGHTSHADE"].verified_at is not None
    assert e.state.weapon == "REZI 12" and e.state.sheets["REZI 12"].verified_at is not None


def test_match_phase_has_a_time_and_apparence_means_menu(env):
    make, frames, clock, _ = env
    e = make()
    frames.append(load("match_start_iso"))
    e.step()
    assert e.state.phase == "in_match" and e.state.phase_at == clock.t
    clock.t += 5
    frames.extend([load("apparence_full_asphalte")])
    e.step()
    assert e.state.phase == "menu" and e.state.phase_at == clock.t


def test_scoreboard_time_stamps_post_match(env):
    make, frames, clock, _ = env
    e = make()
    frames.append(load("match_start_iso"))
    e.step()
    clock.t += 600
    frames.append(load("scoreboard_victoire"))
    e.step()
    assert e.state.phase == "post_match" and e.state.phase_at == clock.t
