"""When the tracker does not know a camo's state, it asks the player: 'Tu l'as déjà ?'."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from trackcod.known_camos import KnownCamos
from trackcod.model import AppState
from trackcod.sheets import answer_camo, ensure_slots, new_sheet, seed_specials
from trackcod.ui.viewmodel import build_view


def _states(s, section):
    return [c.state for c in sorted((c for c in s.camos if c.section == section), key=lambda c: c.order)]


def _sheet():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    ensure_slots(s, "military", 8)
    return s


def test_view_asks_when_state_unknown():
    s = _sheet()
    v = build_view(AppState(weapon="REZI 12", sheets={"REZI 12": s}), 0.0)
    assert v.current.ask_key is not None
    for c in s.camos:
        c.state = "done" if c.section == "special" else "available"
    v = build_view(AppState(weapon="REZI 12", sheets={"REZI 12": s}), 0.0)
    assert v.current.ask_key is None


def test_yes_marks_it_and_the_ones_before_done():
    s = _sheet()
    answer_camo(s, "special:2", True)
    assert _states(s, "special")[:2] == ["done", "done"]


def test_no_makes_it_the_one_to_do_and_locks_the_next():
    s = _sheet()
    sp = sorted((c for c in s.camos if c.section == "special"), key=lambda c: c.order)
    answer_camo(s, sp[0].key, False)
    assert _states(s, "special") == ["available", "locked", "locked"]


def test_window_buttons_answer(qtbot=None):
    from PySide6.QtWidgets import QApplication, QPushButton
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    answers = []
    w = MainWindow(["REZI 12"], lambda n: None, lambda b: None, on_camo_answer=lambda k, has: answers.append((k, has)))
    w.render(build_view(AppState(weapon="REZI 12", sheets={"REZI 12": _sheet()}), 0.0))
    yes = next(b for b in w.findChildren(QPushButton) if b.text() == "Oui")
    yes.click()
    assert answers and answers[0][1] is True
    w.close()
