import dataclasses
from datetime import datetime

from trackcod.model import AppState, GlobalStats, MatchStats
from trackcod.sheets import ApparenceCamo, ApparenceReading, apply_apparence, new_sheet
from trackcod.ui.viewmodel import ago, build_view

AT = datetime(2026, 11, 12, 20, 0).timestamp()
W = "ISO NIGHTSHADE"


def _state():
    s = AppState(weapon=W)
    s.sheets[W] = new_sheet(W, "Mitraillette")
    return s


def _learn(s, *camos, counts=None, at=AT):
    apply_apparence(s.sheets[W], ApparenceReading(list(camos), counts or {}, at=at))


def test_empty_sheet_note():
    v = build_view(_state(), AT)
    assert v.sheet_note == "passe dans Apparence pour apprendre cette arme"
    assert v.military == [] and v.specials == [] and v.current is None and v.category == "Mitraillette"


def test_placeholder_rows():
    s = _state()
    _learn(s, counts={"military": (8, 8), "special": (0, 3), "erudit": (0, 4)})
    v = build_view(s, AT)
    assert v.sheet_note == "" and v.military == ["done"] * 8
    assert [(r.icon, r.name) for r in v.specials] == [("?", "Spécial ?")] * 3
    assert v.current.name == "Spécial ?" and v.current.counter == "compteur inconnu"


def test_unconfirmed_name_has_question_mark():
    s = _state()
    _learn(s, ApparenceCamo("ASPHA{3E-", "special", None, True, None, "Faites 50 éliminations", (46, 50), False, 1),
           counts={"special": (0, 3)})
    v = build_view(s, AT + 7200)
    assert v.specials[0].name == "ASPHA 3E ?" and v.specials[0].icon == "▶" and v.specials[0].counter == "46/50"
    assert v.current.name == "ASPHA 3E ?" and v.current.counter == "46/50 · lu il y a 2 h"


def test_locked_row_shows_condition():
    s = _state()
    _learn(s, ApparenceCamo("MARRON", "special", "Obtenez 8 arme(s)", False, None, None, None, True, 3,
                            name_reads=["MARRON", "MARRON"]), counts={"special": (0, 3)})
    row = next(r for r in build_view(s, AT).specials if r.name == "MARRON")
    assert row.icon == "🔒" and row.detail == "encore 8 accessoires à débloquer"


def test_global_not_calibrated():
    assert build_view(_state(), AT).global_note == "non calibré · ouvre ton dossier de combat"


def test_global_calibrated_rows():
    s = _state()
    s.global_stats = GlobalStats(kills=2079, deaths=2330, wins=69, losses=57, games=126,
                                 calibrated_at=AT, matches_since_calibration=3)
    v = build_view(s, AT)
    assert v.global_note == "calibré le 12/11 · +3 parties"
    assert v.global_rows == [("K/D", "0.89"), ("Victoires", "55 %"), ("Élim.", "2 079"), ("Parties", "126")]


def test_global_note_singular():
    s = _state()
    s.global_stats = GlobalStats(kills=1, deaths=1, games=1, calibrated_at=AT, matches_since_calibration=1)
    assert build_view(s, AT).global_note == "calibré le 12/11 · +1 partie"


def test_last_match():
    s = _state()
    s.last_match = MatchStats(AT, 13, 12, 1595, "win", "MATCH À MORT PAR ÉQUIPE HARDCORE", "LITHIUM", W, "fp")
    v = build_view(s, AT)
    assert v.last_match == [("Élim.", "13"), ("Morts", "12"), ("K/D", "1.08"), ("Score", "1595")]
    assert v.last_match_info == "MATCH À MORT PAR ÉQUIPE HARDCORE · LITHIUM · VICTOIRE"


def test_no_weapon():
    v = build_view(AppState(), AT)
    assert v.weapon == "Arme inconnue" and v.current is None and v.last_match is None and v.meta is None


def test_meta_box(meta):
    s = _state()
    v = build_view(s, AT, meta=meta)
    assert v.meta.header == "META · mis à jour le 07/11" and v.meta.selected == "VERSATILE"
    assert v.meta.rows[0] == ("Bouche", "XRK HERDER 40", "niv. 17")
    s.meta_builds[W] = "LOW_LEVEL"
    assert build_view(s, AT, meta=meta).meta.rows[0] == ("Bouche", "FSS CRACKDOWN", "niv. 4")


def test_meta_box_missing(meta):
    s = _state()
    assert build_view(s, AT, meta=None).meta.note == "classes méta indisponibles (site injoignable)"
    s.weapon = "Inconnue"
    assert build_view(s, AT, meta=meta).meta.note == "pas de classe pour cette arme"
    stale = dataclasses.replace(meta, stale=True)
    assert build_view(_state(), AT, meta=stale).meta.header.endswith("(hors ligne)")


def test_ago():
    assert ago(0, 30) == "à l'instant" and ago(0, 300) == "il y a 5 min"
    assert ago(0, 7200) == "il y a 2 h" and ago(0, 3 * 86400) == "il y a 3 j"


# ----- compteur de maîtrise -----

def _erudit_done(s, weapon, category, *ranks):
    s.sheets[weapon] = new_sheet(weapon, category)
    apply_apparence(s.sheets[weapon], ApparenceReading([], {"erudit": (len(ranks), 4)}, at=AT))
    for c in s.sheets[weapon].camos:
        if c.order - 200 in ranks:
            c.state = "done"


def test_mastery_counts_from_learned_sheets(meta):
    s = _state()
    _erudit_done(s, W, "Mitraillette", 1, 2)
    _erudit_done(s, "VEL 46", "Mitraillette", 1)
    _erudit_done(s, "M4", "Fusil d'assaut", 1, 2, 3)
    v = build_view(s, AT, meta=meta)
    assert v.mastery == [("Or", "3"), ("Platine", "2/33"), ("Rupture harmonique", "1/33"), ("Or · Mitraillette", "2/5")]
    assert v.mastery_note == "d'après 3 armes apprises"


def test_mastery_category_row_does_not_need_the_site():
    s = _state()
    _erudit_done(s, W, "Mitraillette", 1)
    v = build_view(s, AT)  # SMG goal: 5 in Or
    assert v.mastery == [("Or", "1"), ("Platine", "0/33"), ("Rupture harmonique", "0/33"), ("Or · Mitraillette", "1/5")]
    assert v.mastery_note == "d'après 1 arme apprise"


def test_mastery_empty_when_nothing_learned():
    v = build_view(AppState(), AT)
    assert v.mastery == [] and v.mastery_note == ""


def test_divergence_row_shows_its_condition():
    s = _state()
    _erudit_done(s, W, "Mitraillette")
    row = next(r for r in build_view(s, AT).erudit if r.name == "Divergence")
    assert "33" in row.detail


# ----- défis Érudit par catégorie -----

def test_erudit_challenges_by_category():
    s = _state()   # ISO NIGHTSHADE, Mitraillette
    _erudit_done(s, W, "Mitraillette")
    rows = {r.name: r.detail for r in build_view(s, AT).erudit}
    assert rows["Or"] == "Tuer 15 joueurs au cours d'une même partie"
    assert rows["Platine"].startswith("Tuer 25 joueurs par derrière")  # then why it's locked
    assert rows["Rupture harmonique"].startswith("Tuer 50 joueurs au tir au jugé")


def test_erudit_challenge_read_on_screen_wins():
    s = _state()
    _erudit_done(s, W, "Mitraillette")
    platine = next(c for c in s.sheets[W].camos if c.order == 202)
    platine.challenge_fr = "Faites 25 éliminations de joueurs par derrière."
    assert next(r for r in build_view(s, AT).erudit if r.name == "Platine").detail.startswith("Faites 25")


def test_erudit_challenge_unknown_category():
    s = _state()
    _erudit_done(s, W, "Catégorie inconnue")
    assert next(r for r in build_view(s, AT).erudit if r.name == "Platine").detail == "après Or"


def test_current_camo_shows_its_learned_thumbnail(tmp_path):
    from PIL import Image
    from trackcod.known_camos import KnownCamos
    from trackcod.sheets import seed_specials
    from trackcod.thumbs import save_thumbs
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    st = AppState(weapon="REZI 12", sheets={"REZI 12": s})
    assert build_view(st, 0.0, thumbs_dir=tmp_path).current.thumb is None  # not learned yet
    save_thumbs(tmp_path, "REZI 12", {("special", 1): Image.new("RGB", (96, 96))})
    v = build_view(st, 0.0, thumbs_dir=tmp_path)
    assert v.current.name == "Or noir" and v.current.thumb.endswith("special-1.png")


def test_platine_waits_for_or_on_the_whole_category(meta):
    from trackcod.sheets import ensure_slots
    s = new_sheet("PATRIOT XMR", "Fusil d'assaut")
    ensure_slots(s, "special", 3)
    ensure_slots(s, "erudit", 4)
    for c in s.camos:
        c.state = "done" if c.section == "special" or c.order == 201 else "unknown"
    st = AppState(weapon="PATRIOT XMR", sheets={"PATRIOT XMR": s})
    platine = build_view(st, 0.0, meta=meta).erudit[1]
    # fixed goal (8 assault rifles), even when the season adds weapons to the category
    assert platine.icon == "🔒" and "1/8" in platine.detail and "fusils d'assaut" in platine.detail


def test_platine_goal_read_from_the_game_wins():
    from trackcod.sheets import ensure_slots
    s = new_sheet("M4", "Fusil d'assaut")
    ensure_slots(s, "special", 3)
    ensure_slots(s, "erudit", 4)
    for c in s.camos:
        c.state = "done" if c.section == "special" or c.order == 201 else "unknown"
    next(c for c in s.camos if c.order == 202).access_text = "Obtenez Or sur 7 fusils d'assaut"
    platine = build_view(AppState(weapon="M4", sheets={"M4": s}), 0.0).erudit[1]
    assert "1/7" in platine.detail


def test_category_without_known_goal_shows_no_invented_total():
    from trackcod.sheets import ensure_slots
    s = new_sheet("COUTEAU", "Mêlée")  # no Platine goal known
    ensure_slots(s, "special", 3)
    ensure_slots(s, "erudit", 4)
    for c in s.camos:
        c.state = "done" if c.section == "special" or c.order == 201 else "unknown"
    platine = build_view(AppState(weapon="COUTEAU", sheets={"COUTEAU": s}), 0.0).erudit[1]
    assert "/" not in platine.detail


def test_platine_not_proposed_as_next_camo_before_the_category_is_gold(meta):
    from trackcod.sheets import ensure_slots
    s = new_sheet("PATRIOT XMR", "Fusil d'assaut")
    for section, n in (("special", 3), ("military", 8), ("erudit", 4)):
        ensure_slots(s, section, n)
    for c in s.camos:
        c.state = "unknown" if c.section == "erudit" and c.order > 201 else "done"
    v = build_view(AppState(weapon="PATRIOT XMR", sheets={"PATRIOT XMR": s}), 0.0, meta=meta)
    assert v.current is None or v.current.name != "Platine"


# ----- Platine / Rupture harmonique gates (rules given by the player) -----

def _gold_sheet(weapon, category, done_upto):
    """Sheet with specials done and Érudit done up to order `done_upto` (200 = none)."""
    from trackcod.sheets import _name_erudit_slots, ensure_slots
    s = new_sheet(weapon, category)
    for section, n in (("special", 3), ("military", 8), ("erudit", 4)):
        ensure_slots(s, section, n)
    _name_erudit_slots(s)
    for c in s.camos:
        c.state = "done" if c.section != "erudit" or c.order <= done_upto else "unknown"
    return s


def test_platine_goals_per_category():
    from trackcod.sheets import PLATINE_GOAL
    assert PLATINE_GOAL == {"Fusil d'assaut": 8, "Mitraillette": 5, "Fusil à pompe": 2, "Mitrailleuse": 3,
                            "Fusil tactique": 3, "Fusil de précision": 3, "Pistolet": 4, "Lanceur": 4}


def test_platine_open_once_the_category_goal_is_reached():
    sheets = {w: _gold_sheet(w, "Fusil à pompe", 201) for w in ("REZI 12", "WARLORD")}  # 2 shotguns in Or
    v = build_view(AppState(weapon="REZI 12", sheets=sheets), 0.0)
    assert v.erudit[1].icon != "🔒" and v.current.name == "Platine"


def test_rupture_waits_for_33_platine_all_categories():
    sheets = {f"ARME {i}": _gold_sheet(f"ARME {i}", "Fusil d'assaut", 202) for i in range(9)}
    v = build_view(AppState(weapon="ARME 0", sheets=sheets), 0.0)
    rupture = v.erudit[2]
    assert rupture.icon == "🔒" and "9/33" in rupture.detail
    assert v.current is None or v.current.name != "Rupture harmonique"
    assert ("Platine", "9/33") in v.mastery


def test_game_condition_ticked_overrides_our_count():
    sheets = {"ARME 0": _gold_sheet("ARME 0", "Fusil d'assaut", 202)}
    rupture = next(c for c in sheets["ARME 0"].camos if c.order == 203)
    rupture.access_met = True  # read ticked in Apparence: the player has 33 Platine, we only learned one
    v = build_view(AppState(weapon="ARME 0", sheets=sheets), 0.0)
    assert v.erudit[2].icon != "🔒" and v.current.name == "Rupture harmonique"


def test_erudit_names_never_carry_a_question_mark():
    from trackcod.sheets import _name_erudit_slots, ensure_slots
    s = new_sheet("ISO NIGHTSHADE", "Mitraillette")
    ensure_slots(s, "erudit", 4)
    _name_erudit_slots(s)
    rupture = next(c for c in s.camos if c.order == 203)
    rupture.name_votes = {"RUPTURE HARMONIQUE": 1}  # a single OCR read: not 'confirmed'
    rows = build_view(AppState(weapon="ISO NIGHTSHADE", sheets={"ISO NIGHTSHADE": s}), 0.0).erudit
    assert [r.name for r in rows] == ["Or", "Platine", "Rupture harmonique", "Divergence"]


# ----- local history (survives the official stats being switched off) -----

def _hist_match(i, kills, deaths, result):
    from trackcod.model import MatchStats
    return MatchStats(at=1_794_500_000.0 + i * 1000, kills=kills, deaths=deaths, score=3000, result=result,
                      mode="Domination", map="Port", weapon="M4", fingerprint=f"h{i}")


def test_history_curve_and_summary():
    newest_first = [_hist_match(3, 30, 10, "win"), _hist_match(2, 10, 0, "win"), _hist_match(1, 5, 10, "loss")]
    v = build_view(AppState(), 0.0, history=newest_first)
    h = v.history
    assert [round(p, 2) for p in h.kds] == [0.5, 10.0, 3.0]  # oldest -> newest, deaths 0 counted as 1
    assert h.results == ["loss", "win", "win"]
    assert h.summary == "3 dernières parties : K/D 2.25 · 67 % de victoires"  # 45 kills / 20 deaths


def test_no_history_section_without_matches():
    assert build_view(AppState(), 0.0, history=[]).history is None
    assert build_view(AppState(), 0.0).history is None


def test_window_draws_the_history_chart():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow([], lambda n: None, lambda b: None)
    w.render(build_view(AppState(), 0.0, history=[_hist_match(2, 20, 10, "win"), _hist_match(1, 5, 10, "loss")]))
    chart = w.findChild(QWidget, "kd_chart")
    assert chart is not None
    w.resize(400, 800)
    w.show()
    chart.grab()  # paints without error
    w.close()


def test_playing_only_during_a_recent_match():
    s = _state()
    assert build_view(s, AT).playing is False
    s.phase, s.phase_at = "in_match", AT - 60
    assert build_view(s, AT).playing is True
    assert build_view(s, AT + 50 * 60).playing is False   # match long over (left without a scoreboard)
    s.phase = "post_match"
    assert build_view(s, AT).playing is False
    s.phase, s.phase_at = "in_match", None                  # state saved by an older version
    assert build_view(s, AT).playing is False


def test_compact_flag_follows_state():
    s = _state()
    assert build_view(s, AT).compact is False
    s.compact = True
    assert build_view(s, AT).compact is True


def test_stalled_counter_warns_after_three_matches():
    s = _state()
    _learn(s, ApparenceCamo("ASPHALTE", "special", None, None, None, "Faites 50 éliminations", (10, 50), False, None),
           counts={"military": (0, 0), "special": (0, 3)})
    c = next(c for c in s.sheets[W].camos if c.name_fr == "ASPHALTE")
    c.matches_stalled = 2
    assert build_view(s, AT).current.stalled is None
    c.matches_stalled = 3
    assert "3 parties" in build_view(s, AT).current.stalled


def test_current_camo_has_a_tip():
    s = _state()
    _learn(s, ApparenceCamo("ASPHALTE", "special", None, None, None, "Faites 20 éliminations de joueurs à bout portant",
                            (1, 20), False, None), counts={"military": (0, 0), "special": (0, 3)})
    assert "petite carte" in build_view(s, AT).current.tip


def test_done_camo_shows_a_full_counter():
    """Real session 15/11: Spectre was seen done with its last read counter 13/20 and showed '13/20'."""
    from trackcod.ui.viewmodel import _row
    from trackcod.model import Camo
    c = Camo(key="special:2", name_fr="Spectre", section="special", order=2, state="done", progress=(13, 20))
    assert _row(c).counter == "20/20"
