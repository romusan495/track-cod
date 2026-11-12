"""AppState -> texts and icons shown in the window (pure, tested)."""

from dataclasses import dataclass, field
from datetime import datetime

from trackcod.model import AppState, Camo
from trackcod.readers.common import norm
from trackcod.publish import SITE_URL
from trackcod.sheets import ERUDIT, platine_goal, specials_missing, camo_index, camo_items_left, display_name, erudit_challenge, next_camo
from trackcod.thumbs import thumb_path

ICONS = {"done": "✔", "available": "▶", "locked": "🔒", "unknown": "?"}
SECTION_LABELS = {"military": "Militaire", "special": "Spécial", "erudit": "Érudit"}
PHASES = {"menu": "menu", "in_match": "en partie", "post_match": "fin de partie", "unknown": "—"}
RESULTS = {"win": "VICTOIRE", "loss": "DÉFAITE", "draw": "ÉGALITÉ"}


@dataclass
class RowView:
    icon: str
    name: str
    detail: str
    counter: str


@dataclass
class CurrentView:
    name: str
    section_label: str
    challenge: str
    counter: str
    thumb: str | None = None  # thumbnail learned from the player's Apparence screen
    ask_key: str | None = None  # state unknown: ask the player whether they already have it


@dataclass
class MetaView:
    header: str
    builds: list[tuple[str, str]]  # (style, label)
    selected: str | None
    rows: list[tuple[str, str, str]]  # (slot, attachment, level)
    note: str


@dataclass
class SiteView:
    published: bool
    pseudo: str
    show_camos: bool
    url: str | None  # the player's page, once registered


@dataclass
class View:
    header: str
    weapon: str
    category: str
    unverified: bool
    current: CurrentView | None
    military: list[str]
    specials: list[RowView]
    erudit: list[RowView]
    last_match: list[tuple[str, str]] | None
    last_match_info: str
    global_rows: list[tuple[str, str]]
    global_note: str
    notices: list[str]
    meta: MetaView | None = None
    sheet_note: str = ""
    mastery: list[tuple[str, str]] = field(default_factory=list)
    mastery_note: str = ""
    player: str = ""  # 'Niv. 54 · Prestige 1'
    site: SiteView | None = None


def ago(at: float, now: float) -> str:
    seconds = max(0.0, now - at)
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {int(seconds // 60)} min"
    if seconds < 86400:
        return f"il y a {int(seconds // 3600)} h"
    return f"il y a {int(seconds // 86400)} j"


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _name(c: Camo) -> str:
    if c.section == "erudit":  # fixed names (Or, Platine...): never shown as uncertain
        label = next((lab for _, lab, _ in ERUDIT if norm(lab) == norm(c.name_fr or "")), None)
        if label:
            return label
    return display_name(c)


def _counter(c: Camo) -> str:
    return f"{c.progress[0]}/{c.progress[1]}" if c.progress else ""


def _challenge(c: Camo, category: str) -> str | None:
    if c.challenge_fr:
        return c.challenge_fr
    return erudit_challenge(category, c.order) if c.section == "erudit" else None


def _row(c: Camo, category: str = "") -> RowView:
    left = camo_items_left(c)
    if left:
        detail = f"encore {left} accessoire{'s' if left > 1 else ''} à débloquer"
    elif c.state == "locked" and c.access_text:
        detail = c.access_text
    elif c.state == "locked" and c.section == "special":
        detail = "survole-le dans Apparence pour lire les accessoires restants"
    else:
        detail = _challenge(c, category) or c.access_text or ""
    return RowView(ICONS[c.state], _name(c), detail, _counter(c))


def _special_rows(camos: list[Camo], category: str) -> list[RowView]:
    """Specials unlock left to right: one not read yet after a locked one is locked too."""
    rows, blocker = [], None
    for c in camos:
        if blocker is not None and c.state == "unknown":
            rows.append(RowView(ICONS["locked"], _name(c), f"après {_name(blocker)}", ""))
            continue
        rows.append(_row(c, category))
        if c.state == "locked" and blocker is None:
            blocker = c
    return rows


def _plural(category: str) -> str:
    words = category.lower().split(" ", 1)
    return " ".join([words[0] + ("" if words[0].endswith("s") else "s")] + words[1:])


def _erudit_block(state: AppState, sheet, camos: list[Camo], i: int) -> str | None:
    """Why the i-th Érudit can't be started yet (rules given by the player), or None.
    Or: the 3 specials of the weapon. Platine: Or on the weapon + the category's Or goal (fixed per category).
    Rupture harmonique: Platine on the weapon + 33 weapons in Platine, all categories together.
    Divergence: 33 weapons in Rupture harmonique. A condition read ticked in the game wins over our counts
    (we only know the weapons the tracker has learned)."""
    c = camos[i]
    if c.state == "done" or c.access_met is True:
        return None
    if i == 0:
        return "après les 3 spéciaux" if specials_missing(sheet) else None
    if camos[i - 1].state != "done":
        return f"après {_name(camos[i - 1])}"
    sheets = [sh for sh in state.sheets.values() if sh.camos]
    if i == 1:
        goal = platine_goal(sheet)
        gold = sum(1 for sh in sheets if sh.category == sheet.category and _erudit_done(sh, 1))
        return f"après l'Or sur {goal} {_plural(sheet.category)} ({gold}/{goal})" if goal and gold < goal else None
    if i == 2:
        plat = sum(1 for sh in sheets if _erudit_done(sh, 2))
        return f"après le Platine sur {HARMONIC_GOAL} armes ({plat}/{HARMONIC_GOAL})" if plat < HARMONIC_GOAL else None
    rupt = sum(1 for sh in sheets if _erudit_done(sh, 3))
    return (f"après {HARMONIC_GOAL} armes en Rupture harmonique ({rupt}/{HARMONIC_GOAL})"
            if rupt < HARMONIC_GOAL else None)


def _erudit_rows(state: AppState, sheet, camos: list[Camo]) -> list[RowView]:
    rows = []
    for i, c in enumerate(camos):
        row = _row(c, sheet.category)
        block = _erudit_block(state, sheet, camos, i)
        if block is not None:  # keep the challenge, then why it can't be started yet
            row.icon, row.detail = ICONS["locked"], f"{row.detail} · {block}" if row.detail else block
        rows.append(row)
    return rows


def _meta_view(state: AppState, meta) -> MetaView | None:
    if not state.weapon:
        return None
    if meta is None:
        return MetaView("", [], None, [], "classes méta indisponibles (site injoignable)")
    from trackcod.meta import find_weapon

    weapon = find_weapon(meta, state.weapon)
    if weapon is None or not weapon.builds:
        return MetaView("", [], None, [], "pas de classe pour cette arme")
    styles = [b.style for b in weapon.builds]
    selected = state.meta_builds.get(state.weapon)
    if selected not in styles:
        selected = styles[0]
    build = weapon.builds[styles.index(selected)]
    header = weapon.tier
    if meta.updated:
        header += f" · mis à jour le {meta.updated[8:10]}/{meta.updated[5:7]}"
    if meta.stale:
        header += " (hors ligne)"
    rows = [(a.slot_label, a.name, f"niv. {a.level}" if a.level is not None else "") for a in build.attachments]
    return MetaView(header, [(b.style, b.label) for b in weapon.builds], selected, rows, "")


HARMONIC_GOAL = 33  # Rupture harmonique on 33 weapons unlocks Divergence


def _erudit_done(sheet, rank: int) -> bool:
    return any(c.section == "erudit" and c.order == 200 + rank and c.state == "done" for c in sheet.camos)


def _mastery(state: AppState, meta) -> tuple[list[tuple[str, str]], str]:
    """Or / Platine / Rupture harmonique counts over the weapons the tracker has learned."""
    learned = [sh for sh in state.sheets.values() if sh.camos]
    if not learned:
        return [], ""
    rows = [("Or", str(sum(_erudit_done(sh, 1) for sh in learned))),
            ("Platine", f"{sum(_erudit_done(sh, 2) for sh in learned)}/{HARMONIC_GOAL}"),  # 33 opens Rupture
            ("Rupture harmonique", f"{sum(_erudit_done(sh, 3) for sh in learned)}/{HARMONIC_GOAL}")]
    current = state.sheets.get(state.weapon) if state.weapon else None
    if current is not None and current.category:
        goal = platine_goal(current)  # fixed by the game, not the number of weapons listed this season
        gold = sum(1 for sh in learned if sh.category == current.category and _erudit_done(sh, 1))
        rows.append((f"Or · {current.category}", f"{gold}/{goal}" if goal else str(gold)))
    n = len(learned)
    return rows, f"d'après {n} arme{'s' if n > 1 else ''} apprise{'s' if n > 1 else ''}"


def build_view(state: AppState, now: float, meta=None, thumbs_dir=None) -> View:
    sheet = state.sheets.get(state.weapon) if state.weapon else None
    current = None
    military: list[str] = []
    specials: list[RowView] = []
    erudit: list[RowView] = []
    if sheet is not None:
        erudit_camos = sorted((c for c in sheet.camos if c.section == "erudit"), key=lambda c: c.order)
        nxt = next_camo(sheet)
        if nxt in erudit_camos and _erudit_block(state, sheet, erudit_camos, erudit_camos.index(nxt)):
            nxt = None  # not within reach yet (category Or goal, 33 Platine...)
        if nxt is not None:
            counter = f"{_counter(nxt)} · lu {ago(nxt.read_at, now)}" if nxt.progress and nxt.read_at else "compteur inconnu"
            current = CurrentView(_name(nxt), SECTION_LABELS[nxt.section],
                                  _challenge(nxt, sheet.category) or "défi inconnu", counter)
            if nxt.state == "unknown":
                current.ask_key = nxt.key
            if thumbs_dir is not None:
                path = thumb_path(thumbs_dir, state.weapon, nxt.section, camo_index(sheet, nxt))
                current.thumb = str(path) if path else None
        by_order = sorted(sheet.camos, key=lambda c: c.order)
        for c in by_order:
            if c.section == "military":
                if c is nxt:
                    military.append("now")
                elif c.state in ("done", "unknown"):
                    military.append(c.state)
                else:
                    military.append("todo")
        specials = _special_rows([c for c in by_order if c.section == "special"], sheet.category)
        erudit = _erudit_rows(state, sheet, erudit_camos)

    last_match = None
    last_info = ""
    if state.last_match is not None:
        m = state.last_match
        last_match = [("Élim.", str(m.kills)), ("Morts", str(m.deaths)), ("K/D", f"{m.kd:.2f}"),
                      ("Score", str(m.score) if m.score is not None else "—")]
        last_info = " · ".join(p for p in (m.mode, m.map, RESULTS.get(m.result or "")) if p)

    g = state.global_stats
    global_rows: list[tuple[str, str]] = []
    if g.games or g.kills or g.deaths:
        global_rows = [("K/D", f"{g.kd:.2f}"),
                       ("Victoires", f"{round(g.win_rate * 100)} %" if g.win_rate is not None else "—"),
                       ("Élim.", _thousands(g.kills)), ("Parties", _thousands(g.games))]
    if g.calibrated_at is None:
        note = "non calibré · ouvre ton dossier de combat"
    else:
        note = f"calibré le {datetime.fromtimestamp(g.calibrated_at):%d/%m}"
        if g.matches_since_calibration:
            n = g.matches_since_calibration
            note += f" · +{n} partie{'s' if n > 1 else ''}"

    mastery_rows, mastery_note = _mastery(state, meta)
    return View(
        header=f"TRACK COD · MW4 · {PHASES[state.phase]}",
        player=(f"Niv. {state.player_level} · Prestige {state.prestige if state.prestige is not None else '?'}"
                if state.player_level is not None else ""),
        weapon=state.weapon or "Arme inconnue",
        category=sheet.category if sheet else "",
        unverified=sheet is not None and sheet.verified_at is None,
        sheet_note="passe dans Apparence pour apprendre cette arme" if sheet is not None and not sheet.camos else "",
        current=current,
        military=military,
        specials=specials,
        erudit=erudit,
        last_match=last_match,
        last_match_info=last_info,
        global_rows=global_rows,
        global_note=note,
        notices=list(state.notices),
        meta=_meta_view(state, meta),
        site=SiteView(state.site_publish, state.site_pseudo or "", state.site_show_camos,
                      f"{SITE_URL}/joueur.html?id={state.site_id}" if state.site_id else None),
        mastery=mastery_rows,
        mastery_note=mastery_note,
    )
