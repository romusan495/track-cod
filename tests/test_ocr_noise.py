"""Screen reading must survive the usual Windows OCR slips: lost accents, boxes a few pixels off, case changes,
letter/digit look-alikes in words, and stray lines (HUD, chat, FPS counter)."""

import json
import random
import unicodedata
from pathlib import Path

import pytest

from trackcod.known_camos import KnownCamos
from trackcod.readers.apparence import read_apparence
from trackcod.readers.class_screen import read_class_weapon
from trackcod.readers.classify import classify
from trackcod.readers.combat_record import read_combat_record
from trackcod.readers.common import OcrLine, norm
from trackcod.readers.match_start import read_match_info, read_match_start
from trackcod.readers.scoreboard import read_scoreboard

FIX = Path(__file__).parent / "fixtures" / "ocr"
FIXTURES = sorted(p.stem for p in FIX.glob("*.json"))


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def _words(text, fn):
    """Apply fn to alphabetic words only, so numbers (stats, counters) stay as read. '§' lines are fixture markers."""
    if text.startswith("§"):
        return text
    return " ".join(fn(w) if any(c.isalpha() for c in w) and not any(c.isdigit() for c in w) else w
                    for w in text.split(" "))


def no_accents(lines, rng):
    strip = lambda s: "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return [OcrLine(strip(l.text), l.x, l.y, l.w, l.h) for l in lines]


def jitter(lines, rng):
    j = lambda v: min(max(v + rng.uniform(-0.003, 0.003), 0.0), 1.0)
    return [OcrLine(l.text, j(l.x), j(l.y), l.w, l.h) for l in lines]


def lower_case(lines, rng):
    """One letter of a word read in the wrong case (ASPHALtE): whole words never change case on these fonts."""
    def slip(w):
        if len(w) < 4 or rng.random() > 0.2:
            return w
        i = rng.randrange(1, len(w))
        return w[:i] + w[i].swapcase() + w[i + 1:]
    return [OcrLine(_words(l.text, slip), l.x, l.y, l.w, l.h) for l in lines]


def look_alikes(lines, rng):
    def swap(w):
        if len(w) < 5 or rng.random() > 0.15:
            return w
        return w.replace("O", "0", 1) if "O" in w else w.replace("l", "I", 1)
    return [OcrLine(_words(l.text, swap), l.x, l.y, l.w, l.h) for l in lines]


def stray_lines(lines, rng):
    extra = [OcrLine(t, rng.uniform(0.0, 0.95), rng.uniform(0.0, 0.98), 0.05, 0.015)
             for t in ("FPS : 144", "Ping 32 ms", "[GG] salut", "|", "··")]
    return lines + extra


NOISES = [no_accents, jitter, lower_case, look_alikes, stray_lines]


def reading(name, lines, registry):
    kind = classify(lines)
    if kind == "apparence":
        r = read_apparence(lines, 1.0)
        return kind, r and (norm(r.weapon or ""), [(c.section, c.progress, c.locked) for c in r.camos], r.section_counts)
    if kind == "match_start":
        return kind, read_match_start(lines, registry)
    if kind == "scoreboard":
        m = read_scoreboard(lines, 1.0, None)
        return kind, m and (m.kills, m.deaths, m.score, m.result)
    if kind == "combat_record":
        return kind, read_combat_record(lines)
    if kind == "class":
        return kind, read_class_weapon(lines, registry)
    return kind, None


@pytest.mark.parametrize("noise", NOISES, ids=lambda f: f.__name__)
@pytest.mark.parametrize("name", FIXTURES)
def test_reading_survives_ocr_noise(name, noise, registry):
    clean = reading(name, load(name), registry)
    for seed in range(5):
        noisy = reading(name, noise(load(name), random.Random(seed)), registry)
        assert noisy == clean, f"{name} + {noise.__name__} (seed {seed})"
