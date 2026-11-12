"""Player level from the badge at the top left of the menus ('NIV.' / '54'); prestige set once, then follows."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from trackcod.engine import Engine
from trackcod.model import AppState
from trackcod.readers.common import OcrLine
from trackcod.readers.player import read_player_level
from trackcod.store import load_state, save_state
from trackcod.ui.viewmodel import build_view


def _badge(level):
    # real positions (3440x1440 menus): 'NIV.' at (0.139, 0.121), the level just below
    return [OcrLine("NIV.", 0.139, 0.121, 0.009, 0.01), OcrLine(str(level), 0.139, 0.138, 0.009, 0.018)]


def test_read_badge():
    assert read_player_level(_badge(54)) == 54


def test_other_players_levels_are_ignored():
    # scoreboard / lobby: 'NIV.' near the bottom of the screen belongs to other players
    lines = [OcrLine("NIV.", 0.382, 0.885, 0.01, 0.01), OcrLine("53", 0.382, 0.9, 0.01, 0.018)]
    assert read_player_level(lines) is None


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def _engine(tmp_path, registry, frames, state=None):
    clock = Clock()
    e = Engine(registry, state or AppState(), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, clock)
    return e, clock


def _run(e, clock, n):
    for _ in range(n):
        e.step()
        clock.t += 1.0


def test_level_needs_two_matching_reads(tmp_path, registry):
    e, clock = _engine(tmp_path, registry, [_badge(54), _badge(34), _badge(54), _badge(54)])
    _run(e, clock, 2)
    assert e.state.player_level is None  # 54 then 34: not trusted yet
    _run(e, clock, 2)
    assert e.state.player_level == 54


def test_prestige_goes_up_when_the_level_drops(tmp_path, registry):
    st = AppState(player_level=55, prestige=1)
    e, clock = _engine(tmp_path, registry, [_badge(1), _badge(1)], st)
    _run(e, clock, 2)
    assert (e.state.player_level, e.state.prestige) == (1, 2)


def test_view_and_save(tmp_path):
    st = AppState(player_level=54, prestige=1)
    assert build_view(st, 0.0).player == "Niv. 54 · Prestige 1"
    assert build_view(AppState(player_level=54), 0.0).player == "Niv. 54 · Prestige ?"
    save_state(st, tmp_path / "s.json")
    back = load_state(tmp_path / "s.json")
    assert (back.player_level, back.prestige) == (54, 1)


def test_window_shows_level_and_prestige_can_be_set(monkeypatch):
    from PySide6.QtWidgets import QApplication, QInputDialog, QPushButton
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    chosen = []
    w = MainWindow([], lambda n: None, lambda b: None, on_prestige=chosen.append)
    w.render(build_view(AppState(player_level=54), 0.0))
    button = next(b for b in w.findChildren(QPushButton) if b.text().startswith("Niv. 54"))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (1, True)))
    button.click()
    assert chosen == [1]
    w.close()
