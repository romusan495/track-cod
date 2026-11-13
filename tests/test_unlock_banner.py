"""In-game unlock banner, built from real OCR text of the game (French client)."""

import pytest

from trackcod.engine import Engine
from trackcod.known_camos import KnownCamos
from trackcod.model import AppState
from trackcod.readers.common import OcrLine
from trackcod.readers.unlock_banner import has_unlocked_word, read_banner


def _lines(*texts):
    return [OcrLine(t, 0.40, 0.30 + 0.03 * i, 0.2, 0.025) for i, t in enumerate(texts)]


# real OCR reads of the banner (military camo 7 then 8 on the ISO Nightshade)
CAMO7 = _lines("ISO NIGHTSHADE", "CAMOUFLAGE MILITAIRE 7", "NIGHTSHADE")
CAMO8 = _lines("Faites IO élimin tion", "arme qui possède m", "uso NIGHTSHADE", "MOUFLAGE MILITAIRE 8",
               "5 accessoires.", "8/19")
UNLOCKED = _lines("DÉBLOQUÉ", "elGHTSHADE")
NOT_AN_UNLOCK = _lines("RécupeO>n téléphone d'opératio", "dynamique dans le village de", "TYPE 73",
                       "CAMOUFLAGE MILITAIRE 4")


def test_read_military_banner(registry):
    b = read_banner(CAMO7, registry, KnownCamos.load())
    assert (b.weapon, b.section, b.number) == ("ISO NIGHTSHADE", "military", 7)
    b = read_banner(CAMO8, registry, KnownCamos.load())
    assert (b.weapon, b.number) == ("ISO NIGHTSHADE", 8)


def test_read_special_banner(registry):
    b = read_banner(_lines("REZI 12", "PIN BLANC"), registry, KnownCamos.load())
    assert (b.weapon, b.section, b.name) == ("REZI 12", "special", "Pin blanc")


def test_unlocked_word():
    assert has_unlocked_word(UNLOCKED) and has_unlocked_word(_lines("DEBLOQUE"))
    assert not has_unlocked_word(CAMO7) and not has_unlocked_word(_lines("Nouvelle arme débloquée"))


def test_no_banner_without_weapon(registry):
    assert read_banner(_lines("CAMOUFLAGE MILITAIRE 7"), registry, KnownCamos.load()) is None


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def engine(tmp_path, registry):
    frames, clock = [], Clock()
    e = Engine(registry, AppState(), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, clock)
    return e, frames, clock


def _run(e, clock, n):
    for _ in range(n):
        e.step()
        clock.t += 1.5


def _military(e, weapon):
    sheet = e.state.sheets[weapon]
    return [c.state for c in sorted((c for c in sheet.camos if c.section == "military"), key=lambda c: c.order)]


def test_unlock_applied_when_debloque_follows(engine):
    e, frames, clock = engine
    frames.extend([CAMO7, UNLOCKED, UNLOCKED])
    _run(e, clock, 3)
    assert _military(e, "ISO NIGHTSHADE") == ["done"] * 7 + ["available"]
    assert any("CAMOUFLAGE MILITAIRE 7" in n.upper() for n in e.state.notices)


def test_banner_without_debloque_is_ignored(engine):
    e, frames, clock = engine
    frames.extend([NOT_AN_UNLOCK, _lines("FPS"), _lines("FPS"), _lines("FPS"), _lines("FPS"), _lines("FPS"),
                   _lines("FPS"), UNLOCKED])
    _run(e, clock, 8)
    assert "TYPE 73" not in e.state.sheets or all(c.state != "done" for c in e.state.sheets["TYPE 73"].camos)


def test_same_unlock_applied_once(engine):
    e, frames, clock = engine
    frames.extend([CAMO7, UNLOCKED, CAMO7, UNLOCKED])
    _run(e, clock, 4)
    assert sum("MILITAIRE 7" in n.upper() for n in e.state.notices) == 1


def test_special_unlock_marks_known_camo(engine):
    e, frames, clock = engine
    frames.extend([_lines("REZI 12", "PIN BLANC"), UNLOCKED])
    _run(e, clock, 2)
    pin = next(c for c in e.state.sheets["REZI 12"].camos if c.name_fr == "Pin blanc")
    assert pin.state == "done"


def test_corner_banner_takes_the_weapon_just_above_the_camo(registry):
    """Real session 13/11: 'LATENCE : 12 MS' in the HUD looked like REZI 12; the weapon is the line above the camo."""
    import json
    from pathlib import Path
    from trackcod.readers.common import OcrLine
    fix = Path(__file__).parent / "fixtures" / "ocr" / "banniere_coin_vel46.json"
    lines = [OcrLine(**d) for d in json.loads(fix.read_text(encoding="utf-8"))]
    b = read_banner(lines, registry, KnownCamos.load())
    assert b is not None and (b.weapon, b.section, b.number, b.corner) == ("VEL 46", "military", 2, True)
