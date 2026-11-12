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
