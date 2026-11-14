"""'DÉFI TERMINÉ' banner in the middle of the screen during a match, with the camo challenge just completed
('ÉLIMINEZ 20 JOUEUR(S) AU TIR AU JUGÉ.'), seen in a real session on 14/11/2026 (Cronen Osprey).

White text on the sky: the OCR reads only pieces of it ('R AU JUGÉ.', 'IMINEZ 29 JOU'). The frame source re-reads
the band zoomed (ocr_center_band), and the pieces are matched against the challenges of the held weapon: a piece
that fits a single camo's challenge decides, a piece common to several ('ÉLIMINEZ') does not.
"""

from __future__ import annotations

import re

from PIL import ImageOps
from rapidfuzz import fuzz

from trackcod.model import WeaponSheet
from trackcod.readers.common import OcrLine, norm

BAND = (0.33, 0.22, 0.67, 0.36)  # left, top, right, bottom (share of the frame)
_MIN_LETTERS = 8                 # a piece that decides alone
_MIN_SUPPORT = 6                 # a piece that backs up another frame ('AU JUGÉ')
_FIT = 90
_MAX_SHARED = 2                  # a backing piece fits at most this many challenges


def _in_band(line: OcrLine) -> bool:
    left, top, right, bottom = BAND
    return left <= line.x <= right and top <= line.y <= bottom


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z]", "", norm(text))


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", norm(text)))


def needs_band_pass(lines: list[OcrLine]) -> bool:
    return any(_in_band(l) and len(_letters(l.text)) >= 3 for l in lines)


def ocr_center_band(img, base: list[OcrLine]) -> list[OcrLine]:
    """Base lines plus two zoomed reads of the band (plain and inverted grey) when something was read there."""
    if not needs_band_pass(base):
        return base
    from trackcod.ocr.engine import ocr_image
    left, top, right, bottom = BAND
    W, H = img.size
    crop = img.crop((int(left * W), int(top * H), int(right * W), int(bottom * H)))
    sx, sy = right - left, bottom - top
    extra: list[OcrLine] = []
    for prepared in (crop, ImageOps.invert(ImageOps.grayscale(crop))):
        extra += [OcrLine(l.text, left + l.x * sx, top + l.y * sy, l.w * sx, l.h * sy)
                  for l in ocr_image(prepared, upscale=2.0)]
    return base + extra


def challenge_fits(lines: list[OcrLine], sheet: WeaponSheet) -> tuple[set[str], set[str]]:
    """(decisive, fitting) camo keys of `sheet` for the banner pieces of one frame: a decisive piece fits a single
    camo's challenge; a fitting one may be shared ('ÉLIMINEZ 29 JOUEUR(') and only backs up another frame."""
    candidates = [(c.key, _letters(c.challenge_fr), _numbers(c.challenge_fr)) for c in sheet.camos
                  if c.state != "done" and c.challenge_fr and len(_letters(c.challenge_fr)) >= _MIN_LETTERS]
    decisive: set[str] = set()
    fitting: set[str] = set()
    for line in lines:
        piece = _letters(line.text)
        if not _in_band(line) or len(piece) < _MIN_SUPPORT:
            continue
        numbers = _numbers(line.text)  # 'FAITES 5 ÉLIMINATIO' is not 'Faites 2 éliminations...': numbers must agree
        fits = {key for key, text, nums in candidates if numbers <= nums and fuzz.partial_ratio(piece, text) >= _FIT}
        if len(fits) <= _MAX_SHARED:  # 'JOUEUR' of the in-match scoreboard fits every challenge: no backing
            fitting |= fits
        if len(fits) == 1 and len(piece) >= _MIN_LETTERS:
            decisive |= fits
    return decisive, fitting
