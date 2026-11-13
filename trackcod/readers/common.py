import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class OcrLine:
    """One OCR text line; coordinates are proportions (0-1) of the source image."""
    text: str
    x: float
    y: float
    w: float
    h: float


_LOOK_ALIKE = re.compile(r"(?<=[A-Z])[01](?=[A-Z])|(?<![A-Z0-9])0(?=[A-Z]{2})|(?<=[A-Z]{2})0(?![A-Z0-9])")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = " ".join(s.upper().split())
    # OCR look-alikes inside words: VICT0IRE -> VICTOIRE, MILITA1RE -> MILITAIRE (PM-40, KG-7 stay as they are)
    return _LOOK_ALIKE.sub(lambda m: "O" if m.group(0) == "0" else "I", s)
