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


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.upper().split())
