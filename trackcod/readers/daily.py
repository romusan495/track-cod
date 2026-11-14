"""Daily challenges ('DÉFIS DU JOUR'): the list shown in the menus, and the in-match notification (top right).

Built from real French OCR reads (13/11/2026). On the list, the counters 'n/m' are often missed by the OCR (the
game's slashed zero, small font): the frame source then measures each progress bar on the image and adds a line
'§BARRE:<fill>' under the challenge (see daily_bars), and the reader turns the fill into n with the total of the text.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from rapidfuzz import fuzz

from trackcod.readers.common import OcrLine, norm

_BONUS = re.compile(r"TERMINEZ\s*(\d+)\s*DEFI")
_COUNTER = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_TIMER = re.compile(r"(\d{1,2})\s*H\s*(\d{1,2})\s*M\b")
_TIMES = re.compile(r"(\d+)\s*FOIS")
_FIRST_NUMBER = re.compile(r"\d+")
_BAR = "§BARRE:"
_ALIGN = 0.008          # challenge lines share the left edge of the bonus line
_MAX_SPAN = 0.6         # the list never goes higher than this above the bonus line
_TOAST = re.compile(r"DEFI\W*\s*DU\s*JOUR")


@dataclass
class DailyRead:
    text: str
    total: int | None
    progress: int | None
    done: bool


@dataclass
class DailyBoard:
    challenges: list[DailyRead]
    bonus: tuple[int, int] | None
    resets_in_s: int | None


@dataclass
class DailyToast:
    text: str
    progress: tuple[int, int] | None
    done: bool


def _bonus_line(lines: list[OcrLine]) -> OcrLine | None:
    return next((l for l in lines if _BONUS.search(norm(l.text))), None)


def _aligned(lines: list[OcrLine], anchor: OcrLine) -> list[OcrLine]:
    return sorted((l for l in lines if abs(l.x - anchor.x) < _ALIGN and anchor.y - _MAX_SPAN < l.y < anchor.y
                   and not l.text.startswith("§")), key=lambda l: l.y)


def is_daily(lines: list[OcrLine]) -> bool:
    anchor = _bonus_line(lines)
    return anchor is not None and sum(1 for l in _aligned(lines, anchor) if len(l.text) > 12) >= 2


def _paragraphs(lines: list[OcrLine], anchor: OcrLine) -> list[tuple[list[OcrLine], bool]]:
    """Challenge paragraphs above the bonus line, each with its 'COMPLÉTÉ' flag (the label sits under it)."""
    aligned = _aligned(lines, anchor)
    if not aligned:
        return []
    h = statistics.median(l.h for l in aligned)
    paragraphs: list[list] = []
    last: OcrLine | None = None
    for i, line in enumerate(aligned):
        text = norm(line.text)
        if _is_complete(text):
            if paragraphs:
                paragraphs[-1][1] = True
            last = None
            continue
        # the title ('DÉFIS DU JOUR') is the topmost line and a bit bigger; a challenge line can also be read
        # taller ('Faitfl2 élimination(s) peu après', console), so only a much bigger line elsewhere is skipped
        title = line.h > (1.2 if i == 0 else 1.9) * h
        if text.startswith("BONUS") or title or sum(c.isalpha() for c in text) < 3:
            last = None  # title, labels, stray marks
            continue
        if last is not None and line.y - (last.y + last.h) < 0.9 * h:  # gap under the previous line
            paragraphs[-1][0].append(line)
        else:
            paragraphs.append([[line], False])
        last = line
    return [(p, done) for p, done in paragraphs]


def _is_complete(text: str) -> bool:
    """'COMPLÉTÉ' under a done challenge, also when read 'COMPÜÉTÉ' (console)."""
    words = text.split()
    return bool(words) and len(words) <= 2 and fuzz.ratio(words[0], "COMPLETE") >= 70


def _total(text: str) -> int | None:
    t = norm(text)
    m = _TIMES.search(t) or _FIRST_NUMBER.search(t)
    return int(m.group(1) if m.re is _TIMES else m.group(0)) if m else None


def _below(lines: list[OcrLine], para: list[OcrLine], until: float) -> list[OcrLine]:
    top, bottom = para[0].y, para[-1].y + para[-1].h
    return [l for l in lines if top - 0.005 < l.y < min(until, bottom + 0.05)]


def read_daily(lines: list[OcrLine]) -> DailyBoard | None:
    anchor = _bonus_line(lines)
    if anchor is None:
        return None
    paragraphs = _paragraphs(lines, anchor)
    challenges: list[DailyRead] = []
    for i, (para, done) in enumerate(paragraphs):
        nxt = paragraphs[i + 1][0][0].y if i + 1 < len(paragraphs) else anchor.y
        near = _below(lines, para, nxt - 0.005)
        text = " ".join(l.text.strip() for l in para)
        total = _total(text)
        counter = next((m for m in (_COUNTER.match(l.text) for l in near if l.x > anchor.x + 0.03) if m), None)
        bar = next((float(l.text[len(_BAR):]) for l in near if l.text.startswith(_BAR)), None)
        progress = None
        if counter is not None:
            progress, total = int(counter.group(1)), int(counter.group(2))
        elif done and total is not None:
            progress = total
        elif bar is not None and total is not None:
            progress = min(total, round(bar * total))
        if total is not None and progress is not None and progress >= total:
            done = True
        challenges.append(DailyRead(text, total, progress, done))
    bonus_counter = next((m for m in (_COUNTER.match(l.text) for l in lines
                                      if abs(l.y - anchor.y) < 0.05 and l.x > anchor.x) if m), None)
    bonus = (int(bonus_counter.group(1)), int(bonus_counter.group(2))) if bonus_counter else None
    if any(_is_complete(norm(l.text)) for l in lines if abs(l.x - anchor.x) < _ALIGN and 0 < l.y - anchor.y < 0.06):
        n = int(_BONUS.search(norm(anchor.text)).group(1))
        bonus = (n, n)  # 'COMPLÉTÉ' under the bonus
    first = paragraphs[0][0][0].y if paragraphs else anchor.y
    timer = next((m for m in (_TIMER.search(norm(l.text)) for l in lines
                              if anchor.y - _MAX_SPAN < l.y < first and abs(l.x - anchor.x) < 0.15) if m), None)
    resets = int(timer.group(1)) * 3600 + int(timer.group(2)) * 60 if timer else None
    return DailyBoard(challenges, bonus, resets)


def read_daily_toast(lines: list[OcrLine]) -> DailyToast | None:
    """Top-right notification during a match: 'DÉFI DU JOUR' (or '... TERMINÉ'), the challenge, maybe 'n/m'."""
    header = next((l for l in lines if l.x > 0.6 and l.y < 0.4 and _TOAST.search(norm(l.text))), None)
    if header is None:
        return None
    body = sorted((l for l in lines if abs(l.x - header.x) < 0.03 and 0 < l.y - header.y < 0.08
                   and not _COUNTER.match(l.text)), key=lambda l: l.y)
    if not body:
        return None
    counter = next((m for m in (_COUNTER.match(l.text) for l in lines
                                if l.x > header.x + 0.05 and abs(l.y - header.y) < 0.06) if m), None)
    return DailyToast(" ".join(l.text.strip() for l in body),
                      (int(counter.group(1)), int(counter.group(2))) if counter else None,
                      "TERMINE" in norm(header.text))


def daily_bars(img, lines: list[OcrLine]) -> list[OcrLine]:
    """Measures the progress bar under each challenge of the list: '§BARRE:<fill 0-1>' lines for read_daily."""
    anchor = _bonus_line(lines)
    if anchor is None:
        return []
    gray = img.convert("L")
    W, H = gray.size
    px = gray.load()
    out: list[OcrLine] = []
    for para, _ in _paragraphs(lines, anchor):
        last = para[-1]
        x0 = int(anchor.x * W)
        x1 = min(W - 1, x0 + int(0.35 * W))
        y_lo, y_hi = int((last.y + last.h) * H), min(H - 8, int((last.y + last.h + 0.04) * H))
        if y_hi <= y_lo:
            continue
        row = max(range(y_lo, y_hi), key=lambda y: sum(1 for x in range(x0, x1) if px[x, y] > 120))
        end, gap = x0, 0
        for x in range(x0, x1):  # the thin line runs from the text's left edge to the dot before the counter
            if px[x, row] > 120 or px[x, row - 1] > 120 or px[x, row + 1] > 120:
                end, gap = x, 0
            else:
                gap += 1
                if gap > 3:
                    break
        length = end - x0 + 1
        if length < 0.04 * W:
            continue
        thick = [sum(1 for dy in range(-6, 7) if 0 <= row + dy < H and px[x, row + dy] > 120)
                 for x in range(x0, end + 1)]
        base = sorted(thick)[len(thick) // 4]
        filled = 0
        for t in thick:
            if t < base + 2:
                break
            filled += 1
        out.append(OcrLine(f"{_BAR}{filled / length:.3f}", anchor.x, row / H, length / W, 0.002))
    return out
