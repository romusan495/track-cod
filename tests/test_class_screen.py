"""Weapon read from the class screens ('CRÉER UNE CLASSE / MODIFIER CLASSE PERSONNALISÉE', 'CHOISIR LA CLASSE')."""

import json
from pathlib import Path

from trackcod.engine import Engine
from trackcod.model import AppState
from trackcod.readers.class_screen import read_class_weapon
from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine

FIX = Path(__file__).parent / "fixtures" / "ocr"


def _load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


# the player's screenshot: selected card with the category and the name in big letters
PATRIOT = [OcrLine("< MODIFIER CLASSE PERSONNALISÉE", 0.17, 0.05, 0.19, 0.03),
           OcrLine("OPÉRATEUR", 0.245, 0.144, 0.03, 0.015), OcrLine("OH-JI", 0.245, 0.169, 0.02, 0.015),
           OcrLine("PRINCIPAL(E)", 0.245, 0.214, 0.037, 0.016), OcrLine("Fusil d'assaut", 0.246, 0.283, 0.044, 0.012),
           OcrLine("PATRIOT XMR", 0.245, 0.306, 0.04, 0.015), OcrLine("71 /71", 0.377, 0.306, 0.017, 0.015),
           OcrLine("SECONDAIRE", 0.245, 0.353, 0.031, 0.012), OcrLine("Pistolet", 0.246, 0.42, 0.025, 0.012),
           OcrLine("SANG 9MM", 0.245, 0.443, 0.034, 0.013)]


def test_class_screen_weapon_big_name(registry):
    assert read_class_weapon(PATRIOT, registry) == "PATRIOT XMR"


def test_class_screen_weapon_partly_hidden_by_the_gun(registry):
    # real OCR: 'Mitraillette -' 'ISO' 'Nigh' on one row, 'MULTI' below; the pistol must not be taken
    assert read_class_weapon(_load("classe_iso"), registry) == "ISO NIGHTSHADE"


def test_not_a_class_screen(registry):
    assert read_class_weapon(_load("apparence_full_asphalte"), registry) is None
    assert classify(PATRIOT) == "class"


def test_engine_switches_weapon_from_class_screen(tmp_path, registry):
    frames = [PATRIOT]
    e = Engine(registry, AppState(weapon="REZI 12"), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, lambda: 1_000_000.0)
    assert e.step() is True and e.state.weapon == "PATRIOT XMR"


# weapon screen (ARMURERIE / APPARENCE / PROGRESSION tabs): the name in big letters under the path
WEAPON_SCREEN = [OcrLine("CRÉER UNE CLASSE / MODIFIER CLASSE PERSONNALISÉE /", 0.184, 0.023, 0.17, 0.02),
                 OcrLine("< PATRIOT XMR", 0.169, 0.05, 0.09, 0.033), OcrLine("Fusil d'assaut", 0.184, 0.095, 0.05, 0.015),
                 OcrLine("71 /71 ÉLÉMENTS DÉBLOQUÉS", 0.19, 0.122, 0.08, 0.015),
                 OcrLine("ARMURERIE", 0.43, 0.058, 0.03, 0.015), OcrLine("APPARENCE", 0.48, 0.058, 0.03, 0.015),
                 OcrLine("PROGRESSION", 0.53, 0.058, 0.04, 0.015)]


def test_weapon_screen_title(registry):
    from trackcod.readers.match_start import read_weapon_title
    assert read_weapon_title(WEAPON_SCREEN, registry) == "PATRIOT XMR"
    assert read_weapon_title(PATRIOT, registry) is None  # 'MODIFIER CLASSE PERSONNALISÉE' is not a weapon


def test_engine_switches_weapon_from_weapon_screen(tmp_path, registry):
    frames = [WEAPON_SCREEN]
    e = Engine(registry, AppState(weapon="REZI 12"), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, lambda: 1_000_000.0)
    assert e.step() is True and e.state.weapon == "PATRIOT XMR"


# real OCR of the weapon screen with a blueprint: the big title is the blueprint's name
BLUEPRINT = [OcrLine("CRÉER UNE CLASSE / MODIFIER CLASSE PERSONNALISÉE /", 0.1835, 0.0227, 0.165, 0.0203),
             OcrLine("< VEILLE DU DÉMON", 0.169, 0.0442, 0.1185, 0.0382),
             OcrLine("Fusil d' assaut Patriot XMR", 0.184, 0.0956, 0.1005, 0.0155),
             OcrLine("71 171 ÉLÉMENTS DÉBLOQUÉS", 0.192, 0.1219, 0.0845, 0.0179),
             OcrLine("ARMURERIE", 0.427, 0.0585, 0.0325, 0.0131), OcrLine("APPARENCE", 0.481, 0.0585, 0.0305, 0.0119)]


def test_weapon_screen_with_blueprint(registry):
    from trackcod.readers.match_start import read_weapon_title
    assert read_weapon_title(BLUEPRINT, registry) == "PATRIOT XMR"


def test_combat_record_best_weapons_is_not_a_weapon_screen(registry):
    # real OCR of the combat record: 'CRÉER UNE CLASSE : MEILLEURES ARMES' lists the most played weapons
    from trackcod.readers.match_start import read_weapon_title
    record = [OcrLine("CARRIÈRE/", 0.18, 0.023, 0.03, 0.02), OcrLine("< RAPPORT COMBAT", 0.17, 0.05, 0.1, 0.03),
              OcrLine("CRÉER UNE CLASSE : MEILLEURES", 0.1916, 0.209, 0.13, 0.027),
              OcrLine("2. PATRIOT XMR", 0.321, 0.276, 0.05, 0.015), OcrLine("FUSIL D' ASSAUT", 0.196, 0.299, 0.05, 0.015)]
    assert read_weapon_title(record, registry) is None
