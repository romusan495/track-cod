import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox

from trackcod.model import AppState
from trackcod.ui.viewmodel import build_view
from trackcod.ui.window import MainWindow
from trackcod.__main__ import single_instance


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_always_on_top_keeps_window_visible(app, tmp_path):
    calls = []
    w = MainWindow(["ISO Nightshade"], lambda n: None, calls.append)
    w.render(build_view(AppState(), 0))
    w.show()
    w.findChild(QCheckBox, "on_top").click()
    assert w.isVisible() and bool(w.windowFlags() & Qt.WindowStaysOnTopHint) and calls == [True]
    w.findChild(QCheckBox, "on_top").click()
    assert w.isVisible() and not (w.windowFlags() & Qt.WindowStaysOnTopHint)
    w.close()


def test_single_instance(app, tmp_path):
    first = single_instance(tmp_path)
    assert first is not None
    assert single_instance(tmp_path) is None
    first.unlock()
    assert single_instance(tmp_path) is not None


def test_meta_box_build_selector(app, tmp_path, meta):
    from PySide6.QtWidgets import QComboBox
    chosen = []
    w = MainWindow(["ISO Nightshade"], lambda n: None, lambda b: None, on_build_chosen=chosen.append)
    w.render(build_view(AppState(weapon="ISO NIGHTSHADE"), 0, meta=meta))
    combo = w.findChild(QComboBox)
    assert combo is not None and combo.currentText() == "Polyvalent"
    combo.setCurrentIndex(1)
    assert chosen == ["LOW_LEVEL"]
    from PySide6.QtWidgets import QLabel
    assert any(lab.text() == "XRK HERDER 40" for lab in w.findChildren(QLabel))
    w.close()


def test_header_shows_only_app_and_phase(app):
    from PySide6.QtWidgets import QLabel
    w = MainWindow(["ISO NIGHTSHADE"], lambda n: None, lambda b: None)
    w.render(build_view(AppState(weapon="ISO NIGHTSHADE"), 0))
    header = [lab.text() for lab in w.findChildren(QLabel) if lab.text().startswith("TRACK COD")]
    assert header == ["TRACK COD · MW4 · —"]
    w.close()


def test_weapon_choice_accepts_typed_name_and_live_list(app):
    chosen = []
    names = ["ISO NIGHTSHADE"]
    w = MainWindow(lambda: list(names), chosen.append, lambda b: None)
    names.append("M4")
    assert w.weapon_names() == ["ISO NIGHTSHADE", "M4"]
    w.accept_weapon_choice("  Nouvelle Arme ")
    w.accept_weapon_choice("   ")
    assert chosen == ["Nouvelle Arme"]
    w.close()


def test_app_icon_available(app):
    from trackcod.ui.window import app_icon
    assert not app_icon().isNull()


def test_mastery_section_rendered(app):
    from PySide6.QtWidgets import QLabel
    from trackcod.sheets import ApparenceReading, apply_apparence, new_sheet
    s = AppState(weapon="ISO NIGHTSHADE")
    s.sheets["ISO NIGHTSHADE"] = new_sheet("ISO NIGHTSHADE", "Mitraillette")
    apply_apparence(s.sheets["ISO NIGHTSHADE"], ApparenceReading([], {"erudit": (1, 4)}, at=1.0))
    w = MainWindow(["ISO NIGHTSHADE"], lambda n: None, lambda b: None)
    w.render(build_view(s, 0))
    texts = [lab.text() for lab in w.findChildren(QLabel)]
    assert "MAÎTRISE" in texts and "0/33" in texts and "d'après 1 arme apprise" in texts
    w.close()


def test_window_has_the_background_image(app):
    from trackcod.ui.window import BACKGROUND_PATH
    w = MainWindow(["ISO Nightshade"], lambda n: None, lambda b: None)
    assert BACKGROUND_PATH.exists()
    assert w._backdrop is not None and not w._backdrop.isNull()
    w.render(build_view(AppState(), 0))
    w.resize(380, 700)
    w.show()
    img = w.grab().toImage()
    # the image shows through the transparent content: not the old flat background colour everywhere
    colors = {img.pixelColor(x, 600).name() for x in range(20, 360, 20)}
    assert len(colors) > 3
    w.close()


def _compact_state():
    from trackcod.sheets import new_sheet
    s = AppState(weapon="M4")
    s.sheets["M4"] = new_sheet("M4", "Fusil d'assaut")
    return s


def test_compact_mode_swaps_windows_and_hides_during_a_match(app):
    from PySide6.QtWidgets import QPushButton
    calls = []
    w = MainWindow(["M4"], lambda n: None, lambda on: None, on_compact=calls.append)
    s = _compact_state()
    w.render(build_view(s, 1000))
    w.show()
    w.findChild(QPushButton, "compact").click()
    assert calls == [True] and not w.isVisible() and w.compact_window.isVisible()
    assert w.compact_window.windowFlags() & Qt.WindowStaysOnTopHint
    s.compact, s.phase, s.phase_at = True, "in_match", 990       # a match starts: never over the game
    w.render(build_view(s, 1000))
    assert not w.compact_window.isVisible() and not w.isVisible()
    s.phase = "post_match"                                         # scoreboard: back
    w.render(build_view(s, 1000))
    assert w.compact_window.isVisible()
    w.compact_window.findChild(QPushButton, "expand").click()
    assert calls == [True, False] and w.isVisible() and not w.compact_window.isVisible()
    w.close()


def test_always_on_top_is_dropped_during_a_match(app):
    w = MainWindow(["M4"], lambda n: None, lambda on: None, always_on_top=True)
    s = _compact_state()
    w.render(build_view(s, 1000))
    w.show()
    assert w.windowFlags() & Qt.WindowStaysOnTopHint
    s.phase, s.phase_at = "in_match", 990
    w.render(build_view(s, 1000))
    assert not (w.windowFlags() & Qt.WindowStaysOnTopHint) and w.isVisible()
    s.phase = "post_match"
    w.render(build_view(s, 1000))
    assert w.windowFlags() & Qt.WindowStaysOnTopHint
    w.close()


def test_closing_the_app_does_not_crash(tmp_path):
    """The compact window must be owned by the main window: otherwise Python frees it after QApplication at exit
    and the process dies with 0xC0000409/0xC0000005 (tracker crashing on quit, CI failing)."""
    import subprocess
    import sys
    code = ("import os; os.environ['QT_QPA_PLATFORM']='offscreen'\n"
            "from PySide6.QtWidgets import QApplication\n"
            "app = QApplication([])\n"
            "from trackcod.model import AppState\n"
            "from trackcod.ui.viewmodel import build_view\n"
            "from trackcod.ui.window import MainWindow\n"
            "w = MainWindow(['M4'], lambda n: None, lambda on: None)\n"
            "w.render(build_view(AppState(), 0))\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], timeout=60)
    assert r.returncode == 0
