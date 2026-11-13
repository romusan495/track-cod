from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "windows: needs Windows OCR on this machine")


@pytest.fixture
def meta():
    from trackcod.meta import parse_meta_page

    return parse_meta_page((FIXTURES / "meta" / "mw4.html").read_text(encoding="utf-8"))


@pytest.fixture
def registry(meta):
    from trackcod.weapons import WeaponRegistry

    return WeaponRegistry.from_meta(meta, [])


@pytest.fixture(scope="session", autouse=True)
def _free_qt_windows_before_exit():
    """Windows left by the tests must be freed while QApplication still exists: if Python frees them at exit,
    after it, Qt aborts the process (0xC0000409) and pytest reports a failure although every test passed."""
    yield
    import sys
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
