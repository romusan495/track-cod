"""'DÉFI TERMINÉ' in the middle of the screen during a match (real session 14/11/2026, Cronen Osprey: 'Dans
l'herbe', 'Éliminez 20 joueur(s) au tir au jugé.' over a bright sky)."""

import json
from pathlib import Path

from trackcod.engine import Engine
from trackcod.model import AppState
from trackcod.readers.challenge_done import challenge_fits
from trackcod.readers.common import OcrLine
from trackcod.known_camos import KnownCamos
from trackcod.sheets import new_sheet, seed_specials

FIX = Path(__file__).parent / "fixtures" / "ocr"
OSPREY = "CRONEN OSPREY"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def osprey_sheet():
    sheet = new_sheet(OSPREY, "Fusil d'assaut")
    seed_specials(sheet, KnownCamos.load().specials(OSPREY))
    return sheet


def test_the_full_piece_points_to_one_camo():
    decisive, fitting = challenge_fits(load("defi_termine_centre_a"), osprey_sheet())
    sheet = osprey_sheet()
    herbe = next(c for c in sheet.camos if c.challenge_fr and "jugé" in c.challenge_fr)
    assert decisive == {herbe.key} and herbe.key in fitting


def test_broken_pieces_only_back_up():
    sheet = osprey_sheet()
    herbe = next(c for c in sheet.camos if c.challenge_fr and "jugé" in c.challenge_fr)
    decisive, fitting = challenge_fits(load("defi_termine_centre_b"), sheet)
    assert decisive == set() and herbe.key in fitting


def test_a_done_camo_is_not_a_candidate():
    sheet = osprey_sheet()
    for c in sheet.camos:
        c.state = "done"
    assert challenge_fits(load("defi_termine_centre_a"), sheet) == (set(), set())


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def _engine(tmp_path, registry, frames):
    state = AppState()
    state.weapon, state.phase = OSPREY, "in_match"
    state.sheets[OSPREY] = osprey_sheet()
    clock = Clock()
    clock.t = 1_000_000.0
    state.phase_at = clock.t
    e = Engine(registry, state, tmp_path / "state.json", tmp_path / "matches.jsonl",
               lambda: frames.pop(0) if frames else None, clock)
    return e, clock


def _herbe(e):
    return next(c for c in e.state.sheets[OSPREY].camos if c.challenge_fr and "jugé" in c.challenge_fr)


def test_banner_read_on_two_frames_marks_the_camo_done(tmp_path, registry):
    e, clock = _engine(tmp_path, registry, [load("defi_termine_centre_a"), load("defi_termine_centre_b")])
    e.step()
    clock.t += 1
    e.step()
    assert _herbe(e).state == "done"
    assert any("Dans les herbes" in n for n in e.state.notices)


def test_one_frame_alone_is_not_enough(tmp_path, registry):
    e, clock = _engine(tmp_path, registry, [load("defi_termine_centre_a")])
    e.step()
    assert _herbe(e).state != "done"


def test_not_in_a_match_nothing_happens(tmp_path, registry):
    e, clock = _engine(tmp_path, registry, [load("defi_termine_centre_a"), load("defi_termine_centre_b")])
    e.state.phase = "menu"
    e.step()
    clock.t += 1
    e.step()
    assert _herbe(e).state != "done"


def test_another_challenge_with_another_number_is_not_taken():
    """09:18 the same session: 'DÉFI TERMINÉ — FAITES 5 ÉLIMINATIONS PEU APRÈS AVOIR SPRINTÉ.' must not finish
    'Faites 2 éliminations de joueurs sans recharger, 25 fois' (Enchaîné)."""
    lines = [OcrLine("FAITES 5 ÉLIMINATIO", 0.39, 0.30, 0.1, 0.02), OcrLine("APRÈ", 0.53, 0.30, 0.02, 0.02),
             OcrLine("É PEUAPRÈS AVOIR SPRINTÉ.", 0.51, 0.30, 0.1, 0.02)]
    assert challenge_fits(lines, osprey_sheet()) == (set(), set())


def test_scoreboard_words_in_the_band_back_up_nothing():
    """The in-match scoreboard ('I JOUEUR', 'ASSIST.') sits in the same band: words found in every challenge."""
    lines = [OcrLine("I JOUEUR", 0.56, 0.29, 0.03, 0.02), OcrLine("ASSIST.", 0.41, 0.30, 0.03, 0.02)]
    assert challenge_fits(lines, osprey_sheet()) == (set(), set())
