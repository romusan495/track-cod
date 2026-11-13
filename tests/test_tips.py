import csv
from pathlib import Path

from trackcod.sheets import ERUDIT_CHALLENGES
from trackcod.tips import tip

CSV = Path(__file__).resolve().parents[1] / "trackcod" / "data" / "camos_speciaux_mw4.csv"


def test_tip_by_challenge_kind():
    assert "grande carte" in tip("Faites 20 éliminations de joueurs à longue distance")
    assert "petite carte" in tip("Faites 20 éliminations de joueurs à bout portant")
    assert "silencieux" in tip("Faites 30 éliminations de joueurs avec un silencieux")
    assert tip("Tuer 50 joueurs au tir au jugé") == tip("Faites 20 éliminations de joueurs au tir au jugé")
    assert tip("") is None and tip(None) is None and tip("défi inconnu") is None


def test_every_known_challenge_has_a_tip():
    with CSV.open(encoding="utf-8-sig") as f:
        rows = [r[4] for r in csv.reader(f, delimiter=";")][1:]
    challenges = {c for c in rows if c and "Miri" not in c}
    challenges |= {c for t in ERUDIT_CHALLENGES.values() for c in t}
    missing = sorted(c for c in challenges if tip(c) is None)
    assert missing == []
