"""Special camos known in advance for each MW4 weapon (French names + challenges), shipped with the app.

Source: trackcod/data/camos_speciaux_mw4.csv, reviewed by the player and refreshed with `python -m tools.veille`.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from trackcod.readers.common import norm

CSV_PATH = Path(__file__).resolve().parent / "data" / "camos_speciaux_mw4.csv"


@dataclass(frozen=True)
class KnownSpecial:
    name_fr: str
    challenge_fr: str


class KnownCamos:
    def __init__(self, by_weapon: dict[str, list[KnownSpecial]]):
        self._by_weapon = by_weapon

    @classmethod
    def load(cls, path: Path = CSV_PATH) -> "KnownCamos":
        by_weapon: dict[str, list[KnownSpecial]] = {}
        try:
            with Path(path).open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)
                for row in reader:
                    if len(row) < 5 or row[1] == "TBD" or not row[2].strip():
                        continue
                    by_weapon.setdefault(norm(row[0]), []).append(KnownSpecial(row[2].strip(), row[4].strip()))
        except OSError:
            pass
        return cls(by_weapon)

    def specials(self, weapon: str) -> list[KnownSpecial]:
        return list(self._by_weapon.get(norm(weapon or ""), []))
