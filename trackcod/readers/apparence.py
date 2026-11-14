"""Reader for the Apparence (weapon camos) screen.

The game uses stylised fonts on textured backgrounds, so OCR runs in several
passes (different thresholds/scales); the challenge line ('Faites ...') is the
most reliable anchor and the other fields are located relative to it.
"""

import re

from PIL import Image, ImageChops, ImageFilter, ImageOps
from rapidfuzz import fuzz

from trackcod.readers.classify import header_section
from trackcod.readers.common import OcrLine, norm
from trackcod.sheets import ERUDIT, ApparenceCamo, ApparenceReading

_COUNTER = re.compile(r"(?<![\[\d])(\d{1,4})\s*/\s*(\d{1,4})(?![\]\d])")
_SECTION_COUNT = re.compile(r"[\[(|lI]?\s*([0-9AEOUQD])\s*/\s*(\d)")
_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1"})
_CATEGORY_WORDS = {"SPECIAL": "special", "ERUDIT": "erudit", "PRESTIGE": "prestige", "MILITAIRE": "military"}
_CHECK_MARKS = {"✓", "✔", "V", "v", "J"}
_SAME_NAME = 80
SECTION_MARK = "§SECTION:"   # synthetic OCR line carrying the section framed by the game (see _selected_section)
_HIGHLIGHT_LEAD = 0.15
_BRIGHT = 150
_ERUDIT_NAME = 75


# ---------- OCR passes ----------

def _threshold(img: Image.Image, cutoff: int, scale: float, median: bool = False) -> Image.Image:
    g = ImageOps.grayscale(img)
    if scale != 1.0:
        g = g.resize((max(1, int(g.width * scale)), max(1, int(g.height * scale))), Image.LANCZOS)
    if median:
        g = g.filter(ImageFilter.MedianFilter(3))
    return g.point(lambda p: 0 if p > cutoff else 255)


def _strip_icons(text: str) -> str:
    """Drops leading 1-char tokens (lock / check icons read as 'ô', '-', 'v'...)."""
    parts = text.strip().split()
    while len(parts) > 1 and len(parts[0]) <= 2 and sum(c.isalpha() for c in parts[0]) <= 1:
        parts.pop(0)
    return " ".join(parts)


_CHALLENGE_VERBS = ("FAITES", "ELIMINEZ")  # the game writes both: 'Faites 50 éliminations...', 'Éliminez 20 joueur(s)...'


def _is_challenge(line: OcrLine) -> bool:
    return norm(_strip_icons(line.text)).startswith(_CHALLENGE_VERBS)


def _merge(groups: list[list[OcrLine]]) -> list[OcrLine]:
    out: list[OcrLine] = []
    for group in groups:
        for line in group:
            if not any(norm(o.text) == norm(line.text) and abs(o.y - line.y) < 0.02 for o in out):
                out.append(line)
    return out


def _crop_ocr(img: Image.Image, box: tuple[float, float, float, float], prep) -> list[OcrLine]:
    """OCR of a proportional crop (left, top, right, bottom), coordinates mapped back to the full image."""
    from trackcod.ocr.engine import ocr_image

    left, top, right, bottom = (min(1.0, max(0.0, v)) for v in box)
    if right <= left or bottom <= top:
        return []
    W, H = img.size
    crop = img.crop((int(left * W), int(top * H), int(right * W), int(bottom * H)))
    sx, sy = right - left, bottom - top
    return [OcrLine(l.text, left + l.x * sx, top + l.y * sy, l.w * sx, l.h * sy) for l in ocr_image(prep(crop))]


def _selected_section(img: Image.Image, lines: list[OcrLine]) -> str | None:
    """The game frames the hovered section with a bright line around its header: the header whose band holds
    the longest bright line wins, if clearly ahead of the others."""
    W, H = img.size
    scores: dict[str, float] = {}
    for line in lines:
        section = header_section(line)
        if not section or section in scores:
            continue
        box = (int(line.x * W), max(0, int((line.y - 0.03) * H)),
               min(W, int((line.x + 0.17) * W)), min(H, int((line.y + line.h + 0.03) * H)))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        r, g, b = img.crop(box).convert("RGB").split()
        avg = ImageChops.add(ImageChops.add(r.point(lambda v: v // 3), g.point(lambda v: v // 3)),
                             b.point(lambda v: v // 3))
        bright = avg.point(lambda v: 255 if v > _BRIGHT else 0)
        not_warm = ImageChops.subtract(r, g).point(lambda v: 0 if v > 0 else 255)  # G >= R: skips gold tiles
        mask = ImageChops.multiply(bright, not_warm)
        rows = mask.resize((1, mask.height), Image.BOX)  # mean of each row = share of bright pixels
        scores[section] = max(rows.tobytes()) / 255
    if len(scores) < 2:
        return None
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[0][0] if ranked[0][1] - ranked[1][1] >= _HIGHLIGHT_LEAD else None


def ocr_apparence(img: Image.Image, raw: list[OcrLine] | None = None) -> list[OcrLine]:
    lines = _ocr_apparence(img, raw)
    section = _selected_section(img, lines)
    return lines + ([OcrLine(SECTION_MARK + section, 0, 0, 0, 0)] if section else [])


def _ocr_apparence(img: Image.Image, raw: list[OcrLine] | None = None) -> list[OcrLine]:
    from trackcod.ocr.engine import ocr_image

    if raw is None:
        raw = ocr_image(img)
    name = _name_line(raw)
    if name is not None and any(header_section(l) for l in raw):
        # Full game frame (fast path, ~0.4 s): headers re-read on the left panel only, details below the name.
        box = (name.x - 0.03, name.y + name.h, name.x + 0.4, name.y + name.h + 0.2)
        title = (name.x - 0.02, name.y - 0.015, name.x + 0.5, name.y + name.h + 0.015)
        return _merge([
            raw,
            _crop_ocr(img, title, lambda c: _threshold(c, 230, 1.0)),  # title glyphs (digits, 'OR NOIR'...)
            _crop_ocr(img, (0.0, 0.0, 0.32, 1.0), lambda c: _threshold(c, 170, 2.0)),
            _crop_ocr(img, box, lambda c: _threshold(c, 240, 2.0)),
            _crop_ocr(img, box, lambda c: _threshold(c, 200, 2.0)),
            _crop_ocr(img, box, lambda c: c.resize((c.width * 2, c.height * 2), Image.LANCZOS)),
        ])
    base = ocr_image(_threshold(img, 170, 2.0))
    groups = [base, ocr_image(_threshold(img, 225, 1.0)), raw]

    # Cropped screenshots: anchor on the challenge line, the big name sits above it.
    anchor = next((l for l in sorted(base, key=lambda l: l.y) if _is_challenge(l)), None)
    if anchor is not None:
        h = anchor.h
        groups.append(_crop_ocr(img, (anchor.x - 0.1, anchor.y - 10 * h, 1.0, anchor.y - 3.5 * h),
                                lambda c: _threshold(c, 230, 0.5, median=True)))

    # Full frames: the big name is read directly; details (access, challenge, counter) sit below it.
    name = _name_line(raw + base)
    if name is not None:
        box = (name.x - 0.03, name.y + name.h, name.x + 0.4, name.y + name.h + 0.2)
        groups.append(_crop_ocr(img, box, lambda c: _threshold(c, 240, 2.0)))
        groups.append(_crop_ocr(img, box, lambda c: _threshold(c, 200, 2.0)))
        groups.append(_crop_ocr(img, box, lambda c: c.resize((c.width * 2, c.height * 2), Image.LANCZOS)))
    return _merge(groups)


# ---------- parsing ----------

def _counter(text: str) -> tuple[int, int] | None:
    m = _COUNTER.search(text.translate(_DIGIT_FIXES))
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return (a, b) if 0 <= a <= b and b > 0 else None


def _section_counts(lines: list[OcrLine]) -> dict[str, tuple[int, int]]:
    """'[done/total]' per section. The game's slashed zero 'Ø' is read '0', 'O', '9', 'a', '3'...: a done count
    is kept only when every read of the header agrees (an impossible value like 9/4 is a disagreement)."""
    reads: dict[str, list[tuple[int, int]]] = {}
    for line in lines:
        section = header_section(line)
        if not section:
            continue
        m = _SECTION_COUNT.search(norm(line.text))
        if not m:
            continue
        raw = m.group(1)
        done = int(raw) if raw.isdigit() else (0 if raw in "OQDU" else -1)
        reads.setdefault(section, []).append((done, int(m.group(2))))
    counts: dict[str, tuple[int, int]] = {}
    for section, rs in reads.items():
        total = rs[0][1]
        values = {d for d, t in rs if t == total}
        valid = {d for d in values if 0 <= d <= total}
        counts[section] = (valid.pop() if len(valid) == 1 and values == valid else -1, total)
    return counts


_NOT_NAMES = ("ID", "OBTENEZ", *_CHALLENGE_VERBS, "PROGRESSION")


def _looks_like_title(text: str) -> bool:
    """Camo names are short upper-case titles; the access/challenge lines are long mixed-case sentences."""
    letters = [c for c in text if c.isalpha()]
    if not letters or len(text.split()) > 5:
        return False
    upper = sum(1 for c in letters if c.isupper()) / len(letters)
    plain = norm(text)
    return upper >= 0.7 and not any(w in plain for w in ("BTENEZ", "SUPPLEMENTAIRE", "ELIMINATION"))


def _name_line(lines: list[OcrLine]) -> OcrLine | None:
    """The camo name: the tallest text line of the right-hand panel."""
    candidates = [
        l for l in lines
        if l.x > 0.3 and sum(c.isalpha() for c in l.text) >= 2 and header_section(l) is None
        and not norm(_strip_icons(l.text)).startswith(_NOT_NAMES) and _looks_like_title(l.text)
    ]
    if not candidates:
        return None
    tallest = max(candidates, key=lambda l: l.h)
    heights = sorted(l.h for l in lines)
    median = heights[len(heights) // 2]
    if len(lines) >= 3 and tallest.h < 1.3 * median:
        return None
    # Several passes read the same big title ('-I AS', 'HA TE', 'ASPHALTE'): keep the most complete one.
    same_row = [l for l in candidates if l.h >= 0.75 * tallest.h and abs(l.y - tallest.y) < tallest.h]
    # Digits weigh double: 'CAMOUFLAGE MILITAIRE 1' must beat the misread 'CAMOUFLAGE MILITAIREA'.
    return max(same_row, key=lambda l: sum(2 if c.isdigit() else c.isalpha() for c in _strip_icons(l.text)))


def _is_erudit_name(text: str) -> bool:
    plain = " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text)).split())
    return any(fuzz.ratio(plain, key) >= _ERUDIT_NAME for key, _, _ in ERUDIT)


def _category(lines: list[OcrLine], name: OcrLine, below: float) -> str | None:
    """Section of the hovered camo, or None when unknown (the read is then not learned)."""
    if "MILITAIRE" in norm(name.text):
        return "military"
    if _is_erudit_name(name.text):
        return "erudit"
    mark = next((l.text[len(SECTION_MARK):] for l in lines if l.text.startswith(SECTION_MARK)), None)
    if mark:
        return mark
    for line in lines:
        if name.y < line.y < below and line.x >= name.x - 0.05:
            first = norm(line.text).split(" ")[0] if line.text.strip() else ""
            for word, section in _CATEGORY_WORDS.items():
                if first and fuzz.ratio(first, word) >= 80:
                    return section
    return None


def _weapon(lines: list[OcrLine]) -> str | None:
    for line in lines:
        text = norm(line.text)
        if text.startswith("PROGRESSION "):
            return line.text.strip()[len("PROGRESSION "):].strip() or None
    return None


def read_apparence(lines: list[OcrLine], at: float) -> ApparenceReading | None:
    if not any(header_section(l) for l in lines) and not any(_is_challenge(l) for l in lines):
        return None
    name = _name_line(lines)
    if name is None:
        return None
    challenges = sorted((l for l in lines if _is_challenge(l) and l.y > name.y), key=lambda l: l.y)
    ch = challenges[0] if challenges else None
    zone_bottom = ch.y if ch else name.y + name.h + 0.2

    text = None
    progress = None
    if ch is not None:
        h = ch.h
        text = _strip_icons(ch.text)
        last_y = ch.y
        for line in sorted(lines, key=lambda l: l.y):
            if text.endswith("."):
                break
            if (last_y + 0.5 * h < line.y <= ch.y + 2.5 * h and abs(line.x - ch.x) < 0.04
                    and _counter(line.text) is None):
                text = f"{text} {line.text.strip()}"
                last_y = line.y
        for line in lines:
            if line is not ch and ch.y - 0.5 * h <= line.y <= ch.y + 3 * h and line.x > ch.x + ch.w * 0.5:
                progress = _counter(line.text)
                if progress:
                    break

    access = next((l for l in lines if "BTENEZ" in norm(_strip_icons(l.text))
                   and name.y < l.y < zone_bottom), None)
    checked = access is not None and any(
        l.text.strip() in _CHECK_MARKS and l.x < access.x and abs(l.y - access.y) < access.h for l in lines)
    if progress is not None or checked:
        access_met: bool | None = True
    elif access is not None:
        access_met = False
    else:
        access_met = None

    section = _category(lines, name, zone_bottom)
    if section is None:
        return ApparenceReading([], _section_counts(lines), at, weapon=_weapon(lines))
    camo = ApparenceCamo(
        name_fr=_strip_icons(name.text),
        section=section,
        access_text=_strip_icons(access.text) if access else None,
        access_met=access_met,
        access_progress=None,
        challenge_fr=text,
        progress=progress,
        locked=progress is None and access_met is False,
        position=None,
    )
    return ApparenceReading([camo], _section_counts(lines), at, weapon=_weapon(lines))


# ---------- hover tracking ----------

class HoverTracker:
    """Collects the camos hovered during one visit of the Apparence screen."""

    def __init__(self):
        self._camos: list[ApparenceCamo] = []
        self._counts: dict[str, tuple[int, int]] = {}
        self._at: float | None = None
        self._weapon: str | None = None
        self._weapon_reads: list[str] = []

    @property
    def active(self) -> bool:
        return self._at is not None

    @property
    def weapon(self) -> str | None:
        return self._weapon

    def feed(self, reading: ApparenceReading) -> None:
        self._at = reading.at
        for section, (done, total) in reading.section_counts.items():
            old = self._counts.get(section)
            if old is not None and old[1] == total and old[0] != done:
                done = -1  # frames of the same visit disagree: the digit is not trustworthy
            self._counts[section] = (done, total)
        self._weapon = reading.weapon or self._weapon
        if reading.weapon:
            self._weapon_reads.append(reading.weapon)
        for new in reading.camos:
            old = next((c for c in self._camos if c.section == new.section
                        and re.findall(r"\d+", c.name_fr) == re.findall(r"\d+", new.name_fr)
                        and fuzz.ratio(norm(c.name_fr), norm(new.name_fr)) >= _SAME_NAME), None)
            if old is None:
                self._camos.append(new)
                continue
            old.name_reads.extend(new.name_reads)
            for field in ("access_text", "access_met", "access_progress", "challenge_fr", "progress"):
                value = getattr(new, field)
                if value is not None:
                    setattr(old, field, value)
            old.locked = old.progress is None and old.access_met is False

    def finish(self) -> ApparenceReading | None:
        if self._at is None:
            return None
        per_section: dict[str, int] = {}
        for camo in self._camos:
            per_section[camo.section] = per_section.get(camo.section, 0) + 1
            if camo.position is None:
                camo.position = per_section[camo.section]
        reading = ApparenceReading(self._camos, self._counts, self._at, weapon=self._weapon,
                                   weapon_reads=self._weapon_reads)
        self.__init__()
        return reading
