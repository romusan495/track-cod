"""Remote switch: the site's etat.json can suspend screen reading on every tracker (e.g. if Activision objects)."""

from trackcod.engine import Engine
from trackcod.killswitch import STATUS_URL, ReadingStatus, fetch_status
from trackcod.model import AppState
from trackcod.store import load_state, save_state


def test_status_url_is_on_the_site():
    assert STATUS_URL.endswith("/etat.json") and STATUS_URL.startswith("https://")


def test_fetch_status():
    assert fetch_status(lambda url: {"lecture_active": False, "message": "pause"}) == ReadingStatus(False, "pause")
    assert fetch_status(lambda url: {"lecture_active": True}) == ReadingStatus(True, "")


def test_fetch_status_unknown_on_error_or_bad_file():
    def down(url):
        raise OSError("offline")
    assert fetch_status(down) is None
    assert fetch_status(lambda url: {"autre": 1}) is None
    assert fetch_status(lambda url: {"lecture_active": "non"}) is None
    assert fetch_status(lambda url: ["pas", "un", "objet"]) is None


def _engine(tmp_path, registry, state=None):
    calls = []

    def source():
        calls.append(1)
        return None
    e = Engine(registry, state or AppState(), tmp_path / "s.json", tmp_path / "m.jsonl", source, lambda: 1.0)
    return e, calls


def test_suspended_engine_never_reads_the_screen(tmp_path, registry):
    e, calls = _engine(tmp_path, registry)
    e.apply_status(ReadingStatus(False, "Activision a demandé une vérification"))
    for _ in range(3):
        e.step()
    assert calls == []
    assert any("Activision a demandé une vérification" in n for n in e.state.notices)


def test_reading_resumes_when_switched_back_on(tmp_path, registry):
    e, calls = _engine(tmp_path, registry)
    e.apply_status(ReadingStatus(False, ""))
    e.apply_status(ReadingStatus(True, ""))
    e.step()
    assert calls == [1]
    assert not any("suspendue" in n for n in e.state.notices)


def test_unknown_status_keeps_the_last_known_one(tmp_path, registry):
    e, calls = _engine(tmp_path, registry)
    e.apply_status(ReadingStatus(False, ""))
    e.apply_status(None)  # site unreachable
    e.step()
    assert calls == []


def test_suspension_remembered_across_restarts(tmp_path, registry):
    e, _ = _engine(tmp_path, registry)
    e.apply_status(ReadingStatus(False, "pause"))
    save_state(e.state, tmp_path / "s.json")
    restarted, calls = _engine(tmp_path, registry, load_state(tmp_path / "s.json"))
    restarted.step()  # offline at start: still suspended
    assert calls == []
