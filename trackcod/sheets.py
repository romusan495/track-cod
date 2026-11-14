"""Per-weapon camo sheets learned from the game's Apparence screen (no external catalog).

Slots come from the section headers '[done/total]'; specials and érudit camos are identified by a stable
slot key ('special:2') and named by consensus of OCR reads (spec v2 §4.2, §4.3, §9).
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from trackcod.model import Camo, WeaponSheet
from trackcod.readers.common import norm

SAME_NAME = 80        # two reads are the same variant
MATCH_SCORE = 60      # a read belongs to an already-named camo (with a lead over the runner-up)
MATCH_LEAD = 20
CONFIRM_VOTES = 2
ORDER_BASE = {"military": 0, "special": 100, "erudit": 200}
PLACEHOLDER = {"special": "Spécial ?", "erudit": "Érudit ?"}
_MILITARY_FR = re.compile(r"MILITAIRE\s*(\d+)")
# Érudit camos are the same for every weapon, in this order (game rule, told by the player).
ERUDIT = [("OR", "Or", None), ("PLATINE", "Platine", None),
          ("RUPTURE HARMONIQUE", "Rupture harmonique", None),
          ("DIVERGENCE", "Divergence", "Débloqué automatiquement après 33 armes en Rupture harmonique")]
ERUDIT_MATCH = 70
_GOLD = "Tuer 15 joueurs au cours d'une même partie"
# Érudit challenges per weapon category (Or, Platine, Rupture harmonique), as given by the player.
ERUDIT_CHALLENGES = {
    "Fusil à pompe": (_GOLD, "Tuer 50 joueurs au tir au jugé", "Tuer 25 fois 2 joueurs sans recharger"),
    "Fusil d'assaut": (_GOLD, "Tuer 50 joueurs d'un tir dans la tête", "25 doubles éliminations contre des joueurs"),
    "Fusil tactique": (_GOLD, "Tuer 75 joueurs en position allongée", "Tuer 75 joueurs en un tir"),
    "Mitraillette": (_GOLD, "Tuer 25 joueurs par derrière", "Tuer 50 joueurs au tir au jugé"),
    "Mitrailleuse": (_GOLD, "Tuer 15 fois 3 joueurs sans mourir",
                     "Tuer 25 fois 2 joueurs sans relâcher la gâchette"),
    "Fusil de précision": (_GOLD, "Tuer 75 joueurs en position allongée", "Tuer 75 joueurs en un tir"),
    "Pistolet": (_GOLD, "Tuer 20 joueurs par derrière", "Tuer 40 joueurs au tir au jugé"),
    "Lanceur": (_GOLD, "Tuer 15 fois 2 joueurs sans subir de dégâts", "Éliminer 7 fois 10 joueurs dans une même partie"),
}


def erudit_challenge(category: str, order: int) -> str | None:
    """Known challenge of an érudit camo (order 201..203) for a weapon category, else None."""
    challenges = ERUDIT_CHALLENGES.get(category)
    rank = order - ORDER_BASE["erudit"]
    return challenges[rank - 1] if challenges and 1 <= rank <= len(challenges) else None


@dataclass
class ApparenceCamo:
    name_fr: str
    section: Literal["military", "special", "erudit", "prestige"]
    access_text: str | None
    access_met: bool | None
    access_progress: float | None
    challenge_fr: str | None
    progress: tuple[int, int] | None
    locked: bool
    position: int | None
    name_reads: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name_reads:
            self.name_reads = [self.name_fr]


@dataclass
class ApparenceReading:
    camos: list[ApparenceCamo]
    section_counts: dict[str, tuple[int, int]]
    at: float
    weapon: str | None = None
    weapon_reads: list[str] = field(default_factory=list)  # one per frame of the visit


def _digits(s: str) -> list[str]:
    return re.findall(r"\d+", s)


def _same(a: str, b: str) -> bool:
    return fuzz.ratio(a, b) >= SAME_NAME and _digits(a) == _digits(b)


def new_sheet(weapon: str, category: str) -> WeaponSheet:
    return WeaponSheet(weapon=weapon, category=category, camos=[])


def ensure_slots(sheet: WeaponSheet, section: str, total: int) -> None:
    existing = {c.key for c in sheet.camos}
    for i in range(1, total + 1):
        key = f"{section}:{i}"
        if key not in existing:
            sheet.camos.append(Camo(key=key, name_fr=f"Militaire {i}" if section == "military" else None,
                                    section=section, order=ORDER_BASE[section] + i))


def _best_variant(c: Camo) -> tuple[str, int] | None:
    """Reads are counted per exact text; similar texts form a group. Returns the most frequent text of the
    biggest group, with the group's total ('OR NOIR' x3 + 'OR NOIRI' x1 -> ('OR NOIR', 4))."""
    if not c.name_votes:
        return None
    def group(v: str) -> int:
        return sum(n for u, n in c.name_votes.items() if _same(u, v))
    variant = max(c.name_votes, key=lambda v: (group(v), c.name_votes[v]))
    return variant, group(variant)


def name_confirmed(c: Camo) -> bool:
    best = _best_variant(c)
    return best is not None and best[1] >= CONFIRM_VOTES


def display_name(c: Camo) -> str:
    if c.section == "military":
        return c.name_fr or c.key.replace("military:", "Militaire ")
    best = _best_variant(c)
    if best is None:
        return PLACEHOLDER.get(c.section, "?")
    text = _clean(c.name_forms.get(best[0], best[0]))
    return text if best[1] >= CONFIRM_VOTES else f"{text} ?"


def _clean(raw: str) -> str:
    """'RUPTURE+ARMONIQUE-' -> 'RUPTURE ARMONIQUE': OCR glitch marks become spaces, edges trimmed."""
    text = re.sub(r"[^\w' ]+", " ", raw, flags=re.UNICODE).replace("_", " ")
    return " ".join(text.split())


def _vote(c: Camo, reads: list[str]) -> None:
    for raw in reads:
        n = norm(raw)
        if not n:
            continue
        c.name_votes[n] = c.name_votes.get(n, 0) + 1
        c.name_forms.setdefault(n, raw.strip())
    if c.name_votes:
        c.name_fr = display_name(c).removesuffix(" ?")


def _name_erudit_slots(sheet: WeaponSheet) -> None:
    """Give the érudit slots their fixed names and order; an already-read slot keeps its state."""
    erudit = [c for c in sheet.camos if c.section == "erudit"]
    taken: set[str] = set()
    for rank, (key, label, access) in enumerate(ERUDIT, 1):
        scored = [(max(fuzz.ratio(_clean(v), key) for v in c.name_votes), c) for c in erudit
                  if c.name_votes and c.key not in taken]
        owner = max(scored, key=lambda x: x[0])[1] if scored and max(x[0] for x in scored) >= ERUDIT_MATCH else None
        if owner is None:
            owner = next((c for c in erudit if not c.name_votes and c.key not in taken), None)
            if owner is None:
                continue
            owner.name_votes[key] = CONFIRM_VOTES
        for variant in owner.name_votes:
            owner.name_forms[variant] = label
        owner.name_fr = label
        owner.order = ORDER_BASE["erudit"] + rank
        if access and not owner.access_text:
            owner.access_text = access
        taken.add(owner.key)


def _is_erudit_text(text: str) -> bool:
    return any(fuzz.ratio(_clean(norm(text)), key) >= ERUDIT_MATCH for key, _, _ in ERUDIT)


def _clear_misplaced(sheet: WeaponSheet) -> None:
    """Older builds could file an érudit name ('RUPTURE HARMONIQUE') as a special: empty that slot again."""
    for c in sheet.camos:
        best = _best_variant(c) if c.section == "special" else None
        if best is not None and _is_erudit_text(best[0]):
            c.name_votes, c.name_forms, c.name_fr = {}, {}, None
            c.state, c.progress, c.challenge_fr = "unknown", None, None
            c.access_text, c.access_met, c.read_at = None, None, None


SAME_DETAIL = 85  # condition / challenge sentences are read far more reliably than the stylised title


def _detail_key(text: str | None) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", norm(text or "")).split())


def _same_detail(a: str | None, b: str | None) -> bool:
    ka, kb = _detail_key(a), _detail_key(b)
    # numbers carry the meaning ('10 armes' vs '27 armes'): they must match exactly
    return (len(ka) >= 12 and len(kb) >= 12 and fuzz.ratio(ka, kb) >= SAME_DETAIL
            and _digits(ka) == _digits(kb))


def _merge_duplicates(sheet: WeaponSheet) -> None:
    """Slots of one section holding the same condition/challenge are one camo read under several names."""
    for section in ("special", "erudit"):
        members = [c for c in sheet.camos if c.section == section and c.name_votes]
        for i, keep in enumerate(members):
            if not keep.name_votes:
                continue
            for dup in members[i + 1:]:
                if not dup.name_votes:
                    continue
                if (_same_detail(keep.access_text, dup.access_text)
                        or _same_detail(keep.challenge_fr, dup.challenge_fr)):
                    for v, n in dup.name_votes.items():
                        keep.name_votes[v] = keep.name_votes.get(v, 0) + n
                        keep.name_forms.setdefault(v, dup.name_forms.get(v, v))
                    keep.progress = keep.progress or dup.progress
                    keep.challenge_fr = keep.challenge_fr or dup.challenge_fr
                    if dup.state == "done" or (keep.state == "unknown" and dup.state != "unknown"):
                        keep.state = dup.state
                    dup.name_votes, dup.name_forms, dup.name_fr = {}, {}, None
                    dup.state, dup.progress, dup.challenge_fr = "unknown", None, None
                    dup.access_text, dup.access_met, dup.read_at = None, None, None


KNOWN_VOTES = 1000  # a name from the shipped list always wins over OCR variants


def _is_known(c: Camo) -> bool:
    """Named from the shipped list: the screen reading that same name again adds votes on top (1000 -> 1001)."""
    return any(v >= KNOWN_VOTES for v in c.name_votes.values())


def _reset(c: Camo) -> None:
    c.name_votes, c.name_forms, c.name_fr = {}, {}, None
    c.state, c.progress, c.challenge_fr = "unknown", None, None
    c.access_text, c.access_met, c.read_at = None, None, None


def seed_specials(sheet: WeaponSheet, known: list) -> None:
    """Name the special slots from the shipped list (trackcod.known_camos). Slots already read keep their
    state when their name or challenge matches a known camo; unmatched OCR junk is dropped."""
    if not known:
        return
    if sum(1 for c in sheet.camos if c.section == "special") < len(known):
        ensure_slots(sheet, "special", len(known))
    slots = sorted((c for c in sheet.camos if c.section == "special"), key=lambda c: c.order)
    owners: dict[int, Camo] = {}
    for i, k in enumerate(known):
        key = norm(k.name_fr)
        best, best_score = None, 0.0
        for c in slots:
            if c in owners.values() or not c.name_votes:
                continue
            score = max(fuzz.ratio(_clean(v), key) for v in c.name_votes)
            if _same_detail(c.challenge_fr, k.challenge_fr):
                score = max(score, 100.0)
            if score > best_score:
                best, best_score = c, score
        if best is not None and best_score >= MATCH_SCORE:
            owners[i] = best
    for c in slots:
        if c not in owners.values() and c.name_votes and not _is_known(c):
            _reset(c)
    free = [c for c in slots if c not in owners.values()]
    for i, k in enumerate(known):
        owner = owners.get(i) or (free.pop(0) if free else None)
        if owner is None:
            continue
        key = norm(k.name_fr)
        owner.name_votes, owner.name_forms, owner.name_fr = {key: KNOWN_VOTES}, {key: k.name_fr}, k.name_fr
        owner.challenge_fr = owner.challenge_fr or k.challenge_fr or None
        owner.order = ORDER_BASE["special"] + i  # shipped list = in-game left-to-right unlock order


def _find(sheet: WeaponSheet, read: ApparenceCamo) -> Camo | None:
    if read.section == "military":
        nums = _MILITARY_FR.findall(norm(read.name_fr))
        if not nums:
            return None
        return next((c for c in sheet.camos if c.key == f"military:{int(nums[0])}"), None)
    reads = [norm(r) for r in read.name_reads if norm(r)]
    sections = (read.section,) if read.section in ("special", "erudit") else ("special", "erudit")
    for c in sheet.camos:  # same condition or challenge text -> same camo, whatever the title OCR says
        if c.section in sections and c.name_votes and (_same_detail(c.access_text, read.access_text)
                                                        or _same_detail(c.challenge_fr, read.challenge_fr)):
            return c
    # Noisy reads ('ASPHA{3E-' vs 'ASPHALTE'): best already-named camo if clearly ahead of the runner-up.
    scored = sorted(((max(fuzz.ratio(v, r) for v in c.name_votes for r in reads), c) for c in sheet.camos
                     if c.section in sections and c.name_votes and reads), key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] >= MATCH_SCORE and (len(scored) == 1 or scored[0][0] - scored[1][0] >= MATCH_LEAD):
        return scored[0][1]
    return next((c for c in sheet.camos if c.section == sections[0] and not c.name_votes), None)


def _infer_done_from_count(sheet: WeaponSheet, section: str, done: int, total: int) -> None:
    """Header '[done/total]': every section unlocks left to right, so the first `done` camos are done. A done
    camo is never undone (a misread digit must not erase progress); done < 0 means the digit was unreadable.
    Only militaries open by themselves (weapon level): the next special or Érudit may still wait on a
    condition, so its state is left to what the screen shows."""
    members = sorted((c for c in sheet.camos if c.section == section), key=lambda c: c.order)
    if not total or len(members) != total or done < 0:
        return
    if section == "special" and not all(_is_known(c) for c in members):
        # specials not in the shipped list: slot order is reading order, not the game's -> count only
        if done == total:
            for c in members:
                c.state = "done"
            return
        unknown = [c for c in members if c.state == "unknown"]
        if 0 < done - sum(1 for c in members if c.state == "done") == len(unknown):
            for c in unknown:
                c.state = "done"
        return
    for i, c in enumerate(members, 1):
        if i <= done:
            c.state = "done"
        elif c.state == "done":
            continue
        elif section == "military":
            c.state = "available" if i == done + 1 else "locked"


def apply_apparence(sheet: WeaponSheet, reading: ApparenceReading, weapon_confirmed: bool = True) -> None:
    """weapon_confirmed=False: the weapon name was not read on screen, so section counts, military numbers and
    verified_at are skipped (they could belong to another weapon)."""
    if weapon_confirmed:
        for section, (_, total) in reading.section_counts.items():
            if section in ORDER_BASE:
                ensure_slots(sheet, section, total)
    _clear_misplaced(sheet)
    _merge_duplicates(sheet)
    _name_erudit_slots(sheet)
    for read in reading.camos:
        if read.section == "prestige" or (not weapon_confirmed and read.section == "military"):
            continue
        camo = _find(sheet, read)
        if camo is None:
            continue
        if camo.section != "military":
            _vote(camo, read.name_reads)
        camo.access_text = read.access_text or camo.access_text
        if read.access_met is not None:
            camo.access_met = read.access_met
        camo.access_progress = read.access_progress
        if read.access_met is False and items_left(read.access_text) is not None:
            camo.items_left = items_left(read.access_text)
        elif read.access_met:
            camo.items_left = None
        camo.challenge_fr = read.challenge_fr or camo.challenge_fr
        if read.progress is not None:
            camo.matches_stalled = camo.matches_stalled + camo.matches_unread if camo.progress == read.progress else 0
            camo.matches_unread = 0
            camo.progress = read.progress
        camo.read_at = reading.at
        if read.progress is not None and read.progress[0] >= read.progress[1]:
            camo.state = "done"
        elif read.locked or read.access_met is False:
            camo.state = "locked"
        elif read.progress is not None or read.access_met is True:
            camo.state = "available"
    _name_erudit_slots(sheet)
    if not weapon_confirmed:
        return
    in_progress = {s for s, (d, t) in reading.section_counts.items() if d == t and any(
        r.section == s and r.progress is not None and r.progress[0] < r.progress[1] for r in reading.camos)}
    for section, (done, total) in reading.section_counts.items():
        if section in in_progress:
            continue  # '[3/3]' while a camo of that section is seen in progress: the header was misread
        _infer_done_from_count(sheet, section, done, total)
    special_done = reading.section_counts.get("special", (-1, 0))
    _erudit_needs_specials(sheet, special_done[0] >= 0 and special_done[0] < special_done[1])
    sheet.verified_at = reading.at


def _erudit_needs_specials(sheet: WeaponSheet, specials_missing: bool = False) -> None:
    """Game rule: Or asks for the 3 special camos, and each Érudit needs the one before. While a special is
    known not done, no Érudit can be done (undoes a misread count)."""
    if specials_missing or any(c.section == "special" and c.state in ("locked", "available") for c in sheet.camos):
        for c in sheet.camos:
            if c.section == "erudit" and c.state == "done":
                c.state = "unknown"


def mark_unlocked(sheet: WeaponSheet, section: str, number: int | None = None, name: str | None = None) -> bool:
    """Unlock seen in match (banner). Militaries unlock in order: 1..number done, the next one available."""
    if section == "military" and number:
        ensure_slots(sheet, "military", max(8, number))
        for c in sheet.camos:
            if c.section == "military":
                i = int(c.key.split(":")[1])
                if i <= number:
                    c.state = "done"
                elif i == number + 1 and c.state != "done":
                    c.state = "available"
        return True
    target = norm(name or "")
    for c in sheet.camos:
        if c.section == section and target and fuzz.ratio(norm(display_name(c)), target) >= 85:
            c.state = "done"
            return True
    return False


def specials_missing(sheet: WeaponSheet) -> bool:
    """Or (first Érudit) needs the 3 special camos: while one is not done, the whole Érudit is out of reach."""
    return any(c.section == "special" and c.state != "done" for c in sheet.camos)


def count_match(sheet: WeaponSheet) -> None:
    """A match with kills was played with this weapon: its target camo's counter should move."""
    target = next_camo(sheet)
    if target is not None and target.progress is not None and target.state != "done":
        target.matches_unread += 1


def next_camo(sheet: WeaponSheet) -> Camo | None:
    for section in ("special", "military", "erudit"):
        if section == "erudit" and specials_missing(sheet):
            break
        for c in sorted((c for c in sheet.camos if c.section == section), key=lambda c: c.order):
            if c.state == "locked" and section in ("special", "erudit"):
                break  # these unlock left to right: the ones after a locked one are locked too
            if c.state not in ("done", "locked"):
                return c
    return None


def camo_index(sheet: WeaponSheet, camo: Camo) -> int | None:
    """Tile position of a camo on the Apparence screen (1 = top left, then left to right)."""
    if camo.section == "military":
        m = re.fullmatch(r"military:(\d+)", camo.key or "")
        return int(m.group(1)) if m else None
    same = sorted((c for c in sheet.camos if c.section == camo.section), key=lambda c: c.order)
    return same.index(camo) + 1 if camo in same else None


_ITEMS = re.compile(r"BTENEZ\s+(\d+)")


def items_left(access_text: str | None) -> int | None:
    """'Obtenez 10 arme(s) supplémentaire(s)...' -> 10 (items still to unlock, as the game counts them)."""
    m = _ITEMS.search(norm(access_text or ""))
    return int(m.group(1)) if m else None


def camo_items_left(c: Camo) -> int | None:
    """Items still to unlock for a locked special (also for conditions read before the counter existed)."""
    if c.state != "locked":
        return None
    return c.items_left if c.items_left is not None else items_left(c.access_text)


def count_item_unlock(sheet: WeaponSheet) -> list[Camo]:
    """One weapon item unlocked in match: every waiting special gets one closer. Returns the ones now open."""
    opened = []
    for c in sorted((c for c in sheet.camos if c.section == "special"), key=lambda c: c.order):
        left = camo_items_left(c)
        if not left:
            continue
        c.items_left = left - 1
        if c.items_left == 0:
            c.items_left, c.access_met, c.state = None, True, "available"
            opened.append(c)
    return opened


def apply_tile_locks(sheet: WeaponSheet, locks: dict[tuple[str, int], bool | None]) -> None:
    """Padlocks seen on the tiles (no hover needed): padlock -> locked.
    Militaries are left to their count; specials only when their game order is known (shipped list)."""
    for section in ("special", "erudit"):
        members = sorted((c for c in sheet.camos if c.section == section), key=lambda c: c.order)
        if section == "special" and not all(_is_known(c) for c in members):
            continue
        for i, c in enumerate(members, 1):
            if locks.get((section, i)) is True:
                c.state = "locked"  # a done camo never shows a padlock
            # no padlock seen proves nothing: a missed padlock (small screen, HDR) must never open a camo
    _erudit_needs_specials(sheet)



def answer_camo(sheet: WeaponSheet, key: str, has: bool) -> None:
    """The player's answer to 'Tu l'as déjà ?'. Camos unlock left to right in every section: 'yes' means the
    ones before are done too; 'no' makes it the one to do and the ones after it can't be open yet."""
    camo = next((c for c in sheet.camos if c.key == key), None)
    if camo is None:
        return
    members = sorted((c for c in sheet.camos if c.section == camo.section), key=lambda c: c.order)
    i = members.index(camo)
    if has:
        for c in members[:i + 1]:
            c.state = "done"
        return
    camo.state = "available"
    for c in members[i + 1:]:
        if c.state == "unknown":
            c.state = "locked"


# Platine: Or on N weapons of the category. N is fixed for the game (it does not grow when a season adds
# weapons), told by the player; the number read in the game's own Platine condition wins.
PLATINE_GOAL = {"Fusil d'assaut": 8, "Mitraillette": 5, "Fusil à pompe": 2, "Mitrailleuse": 3,
                "Fusil tactique": 3, "Fusil de précision": 3, "Pistolet": 4, "Lanceur": 4}


def platine_goal(sheet: WeaponSheet) -> int | None:
    platine = next((c for c in sheet.camos if c.section == "erudit" and c.order == ORDER_BASE["erudit"] + 2), None)
    m = re.search(r"(\d+)", platine.access_text or "") if platine else None
    return int(m.group(1)) if m else PLATINE_GOAL.get(sheet.category)
