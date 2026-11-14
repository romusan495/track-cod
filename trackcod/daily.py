"""Keeps AppState.daily up to date from the list screen and the in-match notifications."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from trackcod.model import AppState, DailyChallenge
from trackcod.readers.common import norm
from trackcod.readers.daily import DailyBoard, DailyToast

_MATCH = 85


def _key(text: str) -> str:
    """Words only: OCR punctuation noise ('un; drone' 'de') never decides a match."""
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text)).split())


def _score(a: str, b: str) -> float:
    """partial: a cut read. Shared words: a read whose first words are garbled ('NEVELDL C DVB U UL LE GRENADE
    SENSORIELLE OU UN DRONE DE' is 'REVELEZ 2 ENNEMI S AVEC UNE GRENADE ...'), unless a number differs
    ('FAITES 2 ...' and 'FAITES 5 ...' are two challenges)."""
    score = fuzz.partial_ratio(a, b)
    nums_a, nums_b = set(re.findall(r"\d+", a)), set(re.findall(r"\d+", b))
    if nums_a and nums_b and not nums_a & nums_b:
        return min(score, _MATCH - 1)
    words_a, words_b = set(re.findall(r"[A-Z]{4,}", a)), set(re.findall(r"[A-Z]{4,}", b))
    shared = words_a & words_b
    if len(shared) >= 3 and len(shared) >= 0.6 * min(len(words_a), len(words_b)):
        score = max(score, 90.0)
    return score


def _find(challenges: list[DailyChallenge], text: str) -> DailyChallenge | None:
    """Best match; partial reads (a scrolled list, a notification cut on two lines) still find their challenge."""
    t = _key(text)
    scored = [(_score(t, _key(c.text)) if min(len(t), len(c.text)) >= 12 else 0, c) for c in challenges]
    best = max(scored, key=lambda s: s[0], default=(0, None))
    return best[1] if best[0] >= _MATCH else None


def merge_board(state: AppState, board: DailyBoard | None, now: float) -> bool:
    if board is None or not board.challenges:
        return False
    before = (repr(state.daily), state.daily_bonus, state.daily_resets_at)
    _merge(state, board, now)
    resets_moved = (before[2] is None) != (state.daily_resets_at is None) or (
        before[2] is not None and abs(before[2] - state.daily_resets_at) > 120)  # the timer counts in minutes
    return before[:2] != (repr(state.daily), state.daily_bonus) or resets_moved


def _strip_complete(text: str) -> str:
    """'... arme secondaire. COMPÜÉTÉ': the done label read on the same line as the end of the challenge."""
    words = text.split()
    for n in (3, 2, 1):  # the longest: 'c OMP VÉTÉ' leaves no 'c'
        if len(words) > n and fuzz.ratio(norm("".join(words[-n:])), "COMPLETE") >= 70:
            return " ".join(words[:-n])
    return text


_CLEAN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 éèêàâçîôûùÉÈÊÀÂÇÎÔÛ'.,()[]/:-")


def _noise(text: str) -> int:
    """Characters a French challenge never holds ('avéïülh'), plus stray marks at the end ('positif.-')."""
    return sum(c not in _CLEAN for c in text) + text.rstrip().endswith(("-", "•"))


def _looks_like_challenge(text: str) -> bool:
    """A challenge starts with a verb ('Faites', 'Terminez', 'Révélez'...), even garbled ('neveldL'); the title
    and labels read on 14/11 did not ('DA r A _ cTREga2', 'oarz_c1RL.eeZ .PÉElSPU;anl.J8. 23H')."""
    first = text.split()[0] if text.split() else ""
    return "_" not in text and sum(c.isalpha() for c in first) >= 5


def _whole(read) -> bool:
    return read.total is not None and len(read.text) >= 15


def _merge(state: AppState, board: DailyBoard, now: float) -> None:
    expired = state.daily_resets_at is not None and now >= state.daily_resets_at
    matches = [_find(state.daily, r.text) for r in board.challenges]
    # a whole challenge always states its goal ('Faites 2 ...'); pieces of text caught while the panel slides in
    # ('Faites-', 'tour') or a scrolled-off first line only update what they match, never start a new list
    whole = [(r, m) for r, m in zip(board.challenges, matches) if _whole(r)]
    new_day = len(whole) >= 2 and sum(m is not None for _, m in whole) * 2 < len(whole)
    if expired or new_day or (not state.daily and len(whole) >= 2):
        state.daily = []  # a new day: other challenges
        matches = [None] * len(board.challenges)
    for read, known in zip(board.challenges, matches):
        if known is None:
            if _whole(read) and _looks_like_challenge(read.text):
                state.daily.append(DailyChallenge(read.text, read.total, read.progress, read.done))
            continue
        if len(read.text) > len(known.text) and fuzz.partial_ratio(_key(known.text), _key(read.text)) >= 95:
            known.text = read.text  # the same wording, more of it (never a garbled read over a clean one)
        elif _noise(read.text) < _noise(known.text) and len(read.text) >= 0.8 * len(known.text):
            known.text = read.text  # a cleaner read of it ('avec un ratio' over 'avéïülh ratio')
        known.total = read.total or known.total
        if read.progress is not None:
            known.progress = read.progress
        known.done = known.done or read.done
    state.daily = [c for c in state.daily if _looks_like_challenge(c.text)]  # also junk kept by older versions
    for c in state.daily:
        c.text = _strip_complete(c.text)
        if c.done and c.total:
            c.progress = c.total  # a done challenge shows its full counter, not the last one read
    if board.bonus is not None:
        state.daily_bonus = board.bonus
    if board.resets_in_s is not None:
        state.daily_resets_at = now + board.resets_in_s
    elif expired:
        state.daily_resets_at = None
    state.daily_at = now


def apply_toast(state: AppState, toast: DailyToast | None) -> bool:
    if toast is None or not state.daily:
        return False
    known = _find(state.daily, toast.text)
    if known is None:
        return False
    changed = False
    if toast.progress is not None and toast.progress[0] != known.progress:
        known.progress, known.total = toast.progress
        changed = True
    if toast.done and not known.done:
        known.done = True
        known.progress = known.total
        changed = True
    return changed
