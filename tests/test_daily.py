"""Daily challenges ('DÉFIS DU JOUR'): the list in the menus, and the in-match notifications (real reads, 13/11)."""

import json
from pathlib import Path

from PIL import Image, ImageDraw

from trackcod.daily import apply_toast, merge_board
from trackcod.model import AppState, DailyChallenge
from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine
from trackcod.readers.daily import daily_bars, read_daily, read_daily_toast
from trackcod.ui.viewmodel import build_view

FIX = Path(__file__).parent / "fixtures" / "ocr"


def load(name):
    return [OcrLine(**d) for d in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))]


def test_list_screen_is_recognised():
    assert classify(load("defis_du_jour_liste")) == "daily"
    assert classify(load("defis_du_jour_capture_defilee")) == "daily"
    assert classify(load("scoreboard_victoire")) != "daily"


def test_list_read_with_progress_bars():
    board = read_daily(load("defis_du_jour_liste"))
    assert [c.text[:12] for c in board.challenges] == ["Faites 2 éli", "Faites 5 éli", "Révélez 2 en", "Marquez au m"]
    assert [c.total for c in board.challenges] == [2, 5, 2, 2]
    assert [c.done for c in board.challenges] == [False, False, True, False]   # 'COMPLÉTÉ' under Révélez
    assert [c.progress for c in board.challenges] == [0, 0, 2, 0]               # empty bars, done = total
    assert board.bonus == (1, 3)


def test_scrolled_list_keeps_partial_challenge_and_counter():
    board = read_daily(load("defis_du_jour_capture_defilee"))
    texts = [c.text for c in board.challenges]
    assert any(t.startswith("grenade sensorielle") for t in texts)
    marquez = next(c for c in board.challenges if c.text.startswith("Marquez"))
    assert (marquez.progress, marquez.total, marquez.done) == (1, 2, False)


def test_notifications_in_match():
    t = read_daily_toast(load("defi_du_jour_notif_termine"))
    assert t.done and t.progress == (2, 2) and "grenade sensorielle" in t.text
    t = read_daily_toast(load("defi_du_jour_notif_progres"))
    assert not t.done and t.progress is None and t.text.startswith("Révélez 2")
    t = read_daily_toast(load("defi_du_jour_notif_elim"))
    assert t.text.startswith("Faites 2 élimination")
    assert read_daily_toast(load("defis_du_jour_liste")) is None


def test_merge_then_notifications_update_the_right_challenge():
    s = AppState()
    assert merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    assert len(s.daily) == 4 and s.daily_bonus == (1, 3) and s.daily_at == 100.0
    # the scrolled view updates 'Marquez' to 1/2 and keeps the four challenges
    merge_board(s, read_daily(load("defis_du_jour_capture_defilee")), now=200.0)
    assert len(s.daily) == 4
    assert next(c for c in s.daily if c.text.startswith("Marquez")).progress == 1
    # a notification without a counter changes nothing it cannot know
    assert not apply_toast(s, read_daily_toast(load("defi_du_jour_notif_elim")))
    s.daily[0].done = False
    s.daily[2].done = False
    assert apply_toast(s, read_daily_toast(load("defi_du_jour_notif_termine")))
    assert s.daily[2].done and s.daily[2].progress == 2 and not s.daily[0].done


def test_new_day_replaces_the_list():
    s = AppState(daily=[DailyChallenge("Tuez 10 ennemis au couteau.", 10, 3, False)], daily_at=1.0)
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    assert len(s.daily) == 4 and not any(c.text.startswith("Tuez") for c in s.daily)


def test_progress_bar_fill_is_measured():
    img = Image.new("RGB", (1000, 400), (20, 24, 30))
    d = ImageDraw.Draw(img)
    d.line([(100, 200), (400, 200)], fill=(230, 230, 220), width=1)                    # bar: thin line
    d.rectangle([(100, 197), (200, 203)], fill=(230, 230, 220))                          # filled third
    lines = [OcrLine("Faites 3 éliminations.", 0.1, 0.44, 0.3, 0.04),
             OcrLine("Terminez 3 défi(s) du jour.", 0.1, 0.8, 0.3, 0.04)]
    bars = daily_bars(img, lines)
    assert len(bars) == 1 and bars[0].text.startswith("§BARRE:")
    assert abs(float(bars[0].text.split(":")[1]) - 1 / 3) < 0.05


def test_view_lists_the_daily_challenges():
    s = AppState()
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    v = build_view(s, 160.0)
    assert [r.counter for r in v.daily] == ["0/2", "0/5", "2/2", "0/2"]
    assert v.daily[2].icon == "✔" and "Bonus 1/3" in v.daily_note
    assert v.daily_summary == "Défis du jour : 1/4"


def test_daily_challenges_are_saved(tmp_path):
    from trackcod.store import load_state, save_state
    s = AppState(daily=[DailyChallenge("Faites 2 élimination(s) en un coup.", 2, 1, False)], daily_bonus=(1, 3),
                 daily_at=5.0, daily_resets_at=9.0)
    save_state(s, tmp_path / "state.json")
    t = load_state(tmp_path / "state.json")
    assert (t.daily, t.daily_bonus, t.daily_at, t.daily_resets_at) == (s.daily, (1, 3), 5.0, 9.0)


def test_window_shows_the_section_and_the_compact_line():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    s = AppState()
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    w = MainWindow(["M4"], lambda n: None, lambda on: None)
    w.render(build_view(s, 160.0))
    texts = [l.text() for l in w.findChildren(QLabel)]
    assert "DÉFIS DU JOUR" in texts and any("Bonus 1/3" in t for t in texts)
    assert any(l.text() == "Défis du jour : 1/4" for l in w.compact_window.findChildren(QLabel))


def test_garbled_start_of_a_known_challenge_is_not_a_new_one():
    """Real session 13/11: 'neveldL C dVb'U Ul le grenade sensorielle...' is 'Révélez 2 ennemi(s) avec une grenade...'."""
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState()
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    garbled = DailyRead("neveldL C dVb'U Ul le grenade sensorielle ou un drone de", 2, None, True)
    merge_board(s, DailyBoard(read_daily(load("defis_du_jour_liste")).challenges[:2] + [garbled], None, None), now=200.0)
    assert len(s.daily) == 4


def test_clean_wording_is_kept_over_a_garbled_longer_read():
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState()
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    garbled = DailyRead("neveldL C dVb'U Ul le grenade sensorielle ou un drone de recherche. xx", 2, None, True)
    merge_board(s, DailyBoard(read_daily(load("defis_du_jour_liste")).challenges[:2] + [garbled], None, None), now=200.0)
    assert s.daily[2].text.startswith("Révélez 2")


def test_a_frame_caught_mid_animation_never_wipes_the_list():
    """Real session 13/11, frame 258: 'Faites-', 'grenade se...', 'tour' while the panel slides in."""
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState()
    merge_board(s, read_daily(load("defis_du_jour_liste")), now=100.0)
    sliding = DailyBoard([DailyRead("Faites-", None, None, False),
                          DailyRead("grenade sensorielle ou un drone de recherche.", None, None, True),
                          DailyRead("tour", None, None, False)], None, None)
    merge_board(s, sliding, now=101.0)
    assert [c.text[:9] for c in s.daily] == ["Faites 2 ", "Faites 5 ", "Révélez 2", "Marquez a"]


def test_console_daily_panel():
    """Console capture (Twitch, 13/11): panel on the right, 'COMPLÉTÉ' read 'COMPÜÉTÉ', one line taller than the
    others ('Faitfl2 élimination(s) peu après'), bonus done."""
    board = read_daily(load("console_defis_du_jour"))
    assert [c.total for c in board.challenges] == [3, 2, 5, 30]
    assert [c.done for c in board.challenges][:3] == [True, True, True]
    assert board.challenges[1].text.startswith("Faitfl2 élimination(s) peu après av")
    assert "COMP" not in board.challenges[0].text
    assert board.bonus == (3, 3) and board.resets_in_s == 12 * 3600 + 31 * 60


def test_garbled_title_is_not_a_challenge():
    """Real session 14/11 (pause menu): 'owz_cTRL.eez' (a tiny line) and '•pÉFlS OU 22H' (the title) were
    taken for a fifth challenge."""
    board = read_daily(load("defis_du_jour_titre_parasite"))
    assert [c.text.split()[0] for c in board.challenges] == ["Faites", "Faites", "Terminez", "Marquez"]
    assert all(c.done for c in board.challenges)
    assert board.resets_in_s is None or board.resets_in_s >= 22 * 3600


def test_whole_board_drops_junk_and_cleans_done_challenges():
    """State left by the 14/11 session: junk lines kept as challenges, 'COMPÜÉTÉ' stuck to a text, and done
    challenges showing their old counter (2/3, 0/2)."""
    state = AppState(daily=[
        DailyChallenge("Faites 3 élimination[s) avec votre arme secondaire. COMPÜÉTÉ", 3, 2, True),
        DailyChallenge("Faites 15 éliminations avec des mitraillettes.", 15, 15, True),
        DailyChallenge("Terminez 2 partiels) avéïülh ratio éliminations/morts positif.-", 2, 2, True),
        DailyChallenge("Marquez au moins 1000 points au cours diune même partie 2 fois. c OMP VÉTÉ", 2, 0, True),
        DailyChallenge("DA r A _ cTREga2", 2, 0, False),
        DailyChallenge("oarz_c1RL.eeZ .PÉElSPU;anl.J8. 23H", 8, 0, False),
        DailyChallenge("DATA _ TRL _gaz .PÉFI%DUUOUR. 23H 4M", 23, 16, False),
    ])
    merge_board(state, read_daily(load("defis_du_jour_titre_parasite")), now=1000.0)
    assert len(state.daily) == 4
    assert all(c.done and c.progress == c.total for c in state.daily)
    assert not any("COMP" in c.text.upper().split()[-1] for c in state.daily)
    assert [c.text.endswith("partie 2 fois.") for c in state.daily if c.text.startswith("Marquez")] == [True]
    assert not any("ï" in c.text or c.text.endswith("-") for c in state.daily)


def test_junk_kept_by_an_older_version_is_gone_at_start_up(tmp_path):
    """2.0.10 cleaned the list only on the next read of the panel: the junk stayed on screen until then."""
    from trackcod.store import load_state, save_state
    state = AppState(daily=[DailyChallenge("Faites 15 éliminations avec des mitraillettes. COMPÜÉTÉ", 15, 9, True),
                            DailyChallenge("oarz_c1RL.eeZ .PÉElSPU;anl.J8. 23H", 8, 0, False)])
    save_state(state, tmp_path / "s.json")
    loaded = load_state(tmp_path / "s.json")
    assert [(c.text, c.progress) for c in loaded.daily] == [("Faites 15 éliminations avec des mitraillettes.", 15)]


def test_number_glued_to_garbled_letters_is_not_another_challenge():
    """Real session 15/11: 'raites d ellrnnatlor11sJ avec aes fusils tactiques sans subir de' (the '11' glued to
    letters) became a fifth challenge next to 'Faites 2 élimination(s) avec des fusils tactiques sans subir de'."""
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState()
    first = [DailyRead("Faites 2 élimination(s) avec des fusils tactiques sans subir de", 2, 0, False),
             DailyRead("Abattez 2 drone(s).", 2, 0, False), DailyRead("Faites 30 éliminations.", 30, 0, False),
             DailyRead("Faites 15 élimination(s) en regardant dans le viseur.", 15, 0, False)]
    merge_board(s, DailyBoard(first, None, None), now=100.0)
    garbled = DailyRead("raites d ellrnnatlor11sJ avec aes fusils tactiques sans subir de", 11, None, False)
    merge_board(s, DailyBoard([garbled] + first[1:], None, None), now=200.0)
    assert len(s.daily) == 4


def test_total_ignores_a_number_glued_to_letters():
    from trackcod.readers.daily import _total
    assert _total("raites d ellrnnatlor11sJ avec aes fusils tactiques") is None
    assert _total("Faites 2 élimination(s) avec des fusils tactiques") == 2


def test_duplicate_kept_by_an_older_version_is_merged_at_start_up(tmp_path):
    from trackcod.store import load_state, save_state
    state = AppState(daily=[
        DailyChallenge("Faites 2 élimination(s) avec des fusils tactiques sans subir de", 2, 0, False),
        DailyChallenge("Abattez 2 drone(s).", 2, 0, False),
        DailyChallenge("raites d ellrnnatlor11sJ avec aes fusils tactiques sans subir de", 11, None, False)])
    save_state(state, tmp_path / "s.json")
    assert [c.text[:6] for c in load_state(tmp_path / "s.json").daily] == ["Faites", "Abatte"]


# ----- real session 15/11: the panel beside the lobby -----

def test_lobby_counters_are_not_challenge_counters():
    """The lobby's '12/12' and '2/20' (players in the lobby/party), far right, were read as challenge counters:
    'Faites 2 élimination(s)...' showed 12/12, then 2/20."""
    board = read_daily(load("defis_salon_compteur_du_salon"))
    tactical = next(c for c in board.challenges if "tactiques" in c.text)
    assert (tactical.total, tactical.progress, tactical.done) == (2, 2, True)
    assert all(c.total not in (12, 20) for c in read_daily(load("defis_panneau_debut_coupe")).challenges)


def test_garbled_timer_title_is_not_a_challenge():
    """'DÉFIS DU JOUR 23H 17M' read '•PFFF.PUAB• 17M' became a fifth challenge 'out of 17'."""
    board = read_daily(load("defis_panneau_minuteur_parasite"))
    assert [c.text[:6] for c in board.challenges] == ["Faites", "Faites", "Abatte", "Faites"]
    s = AppState()
    merge_board(s, board, now=100.0)
    assert len(s.daily) == 4


def test_lost_zero_of_a_goal_is_the_same_challenge():
    """The game's slashed zero: 'Faites 30 éliminations.' read 'Faites 3 éliminations.' (even '3/3'), which
    became another challenge, and the 30 one showed out of 3."""
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState()
    merge_board(s, read_daily(load("defis_panneau_minuteur_parasite")), now=100.0)
    merge_board(s, read_daily(load("defis_panneau_chiffre_perdu")), now=200.0)
    merge_board(s, DailyBoard([DailyRead("Faites 3, ,éliminations.", 3, 0, False)], None, None), now=300.0)
    assert len(s.daily) == 4
    assert next(c for c in s.daily if "30" in c.text).total == 30


def test_never_more_than_four_daily_challenges(tmp_path):
    """The game gives 4 challenges a day; the 15/11 session ended with 6 in the window."""
    from trackcod.store import load_state, save_state
    state = AppState(daily=[
        DailyChallenge("Faites 3, ,éliminations.", 2, 0, False), DailyChallenge("Abattez 2 drone[s).", 2, 0, False),
        DailyChallenge("Faites 30 éliminations...", 30, 0, False), DailyChallenge("•PFFF.PUAB• 17M", 17, 0, False),
        DailyChallenge(",Faites 15 élimination[s) en regardant dans le viseur.", 15, 0, False),
        DailyChallenge("Faites 2 élimination[s) avec des fusils tactiques sans subir de", 2, 0, False)])
    save_state(state, tmp_path / "s.json")
    texts = [c.text for c in load_state(tmp_path / "s.json").daily]
    assert len(texts) == 4 and not any("PFFF" in t for t in texts)
    assert sum("30" in t or "Faites 3," in t for t in texts) == 1


def test_garbled_read_never_changes_the_goal_of_a_known_challenge():
    """Real session 14/11: 'Marquez au moins 1000 points au cours d'une même partie 2 fois.' (goal 2) was read
    without 'fois' ('... ausw F cours d'une même pa'), its goal became 1000 and its bar gave 722/1000."""
    from trackcod.readers.daily import DailyBoard, DailyRead
    s = AppState(daily=[DailyChallenge("Marquez au moins 1000 points au cours d'une même partie 2 fois.", 2, 0, False)])
    merge_board(s, DailyBoard([DailyRead("Marquez au moins 1000 points ausw F cours d'une même pa", 1000, 722, False)],
                              None, None), now=100.0)
    assert (s.daily[0].total, s.daily[0].progress, s.daily[0].done) == (2, 1, False)
