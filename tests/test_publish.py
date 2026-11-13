"""Publishing the player's own stats to the Track COD site (opt-in), with a fake HTTP layer."""

import json

import pytest

from trackcod.model import AppState, GlobalStats, MatchStats
from trackcod.publish import Publisher, SiteClient, build_payload
from trackcod.store import append_match, load_state, read_matches, save_state


def _match(i, kills=20, deaths=10, result="win"):
    return MatchStats(at=1_794_500_000.0 + i, kills=kills, deaths=deaths, score=3000, result=result,
                      mode="Match à mort par équipe", map="Village", weapon="ISO NIGHTSHADE", fingerprint=f"f{i}")


def _state(**over):
    st = AppState(global_stats=GlobalStats(kills=2134, deaths=2372, wins=70, losses=58, games=128,
                                           calibrated_at=1_794_000_000.0),
                  player_level=54, prestige=1, site_publish=True, site_pseudo="Romusan")
    for k, v in over.items():
        setattr(st, k, v)
    return st


class FakeHttp:
    def __init__(self, *answers):
        self.calls, self.answers = [], list(answers)

    def __call__(self, method, url, headers, body, timeout=5):
        self.calls.append((method, url, headers, json.loads(body) if body else None))
        answer = self.answers.pop(0) if self.answers else (204, b"")
        if isinstance(answer, Exception):
            raise answer
        return answer


REGISTERED = (201, json.dumps({"id": "11111111-2222-3333-4444-555555555555", "key": "k" * 64}).encode())


def _publisher(state, http, notices, matches=None, mastery=None):
    return Publisher(state, SiteClient("https://site.test", send=http), notices.append,
                     recent_matches=lambda: matches if matches is not None else [_match(i) for i in range(7)],
                     mastery=lambda: mastery, saved=lambda: None)


def test_matches_history_read_back(tmp_path):
    for i in range(7):
        append_match(_match(i), tmp_path / "m.jsonl")
    got = read_matches(tmp_path / "m.jsonl", 5)
    assert [m.fingerprint for m in got] == ["f6", "f5", "f4", "f3", "f2"]
    assert read_matches(tmp_path / "absent.jsonl", 5) == []


def test_payload_from_state():
    payload = build_payload(_state(), [_match(i) for i in range(7)], None)
    assert set(payload) == {"global", "matches", "level", "prestige", "mastery"}
    assert payload["global"] == {"kills": 2134, "deaths": 2372, "wins": 70, "losses": 58, "games": 128,
                                 "calibrated": True}
    assert [m["at"] for m in payload["matches"]] == [1_794_500_006, 1_794_500_005, 1_794_500_004,
                                                     1_794_500_003, 1_794_500_002]
    assert set(payload["matches"][0]) == {"at", "mode", "map", "kills", "deaths", "score", "result"}
    assert (payload["level"], payload["prestige"]) == (54, 1)


def test_mastery_only_when_enabled():
    rows = [("Or", "6"), ("Platine", "1/33"), ("Rupture harmonique", "0/33"), ("Or · Mitraillette", "2/5")]
    assert build_payload(_state(site_show_camos=False), [], rows)["mastery"] is None
    assert build_payload(_state(site_show_camos=True), [], rows)["mastery"] == {"or": 6, "platine": 1, "rupture": 0}


def test_no_publish_when_not_opted_in():
    http, notices = FakeHttp(), []
    _publisher(_state(site_publish=False), http, notices).publish_now()
    assert http.calls == []


def test_first_publish_registers_then_updates():
    st, http, notices = _state(), FakeHttp(REGISTERED, (204, b"")), []
    _publisher(st, http, notices).publish_now()
    assert [c[0] for c in http.calls] == ["POST", "PUT"]
    assert http.calls[0][3] == {"pseudo": "Romusan"}
    assert http.calls[1][1].endswith("/api/players/11111111-2222-3333-4444-555555555555")
    assert http.calls[1][2]["Authorization"] == "Bearer " + "k" * 64
    assert (st.site_id, st.site_key) == ("11111111-2222-3333-4444-555555555555", "k" * 64)
    assert notices == []


def test_send_failure_adds_one_notice_and_does_not_raise():
    st, notices = _state(), []
    pub = _publisher(st, FakeHttp(OSError("timeout"), OSError("timeout")), notices)
    pub.publish_now()
    pub.publish_now()
    assert len(notices) == 1 and "site injoignable" in notices[0]


def test_pseudo_taken():
    st, notices = _state(), []
    _publisher(st, FakeHttp((409, json.dumps({"error": "pseudo déjà pris"}).encode())), notices).publish_now()
    assert notices == ["pseudo déjà pris, choisis-en un autre"]
    assert st.site_publish is False


def test_profile_removed_is_not_recreated():
    # removed by the admin (moderation) or by the 90-day cleanup: never re-created behind the player's back
    st = _state(site_id="99999999-2222-3333-4444-555555555555", site_key="old")
    http, notices = FakeHttp((404, b'{"error":"introuvable"}')), []
    _publisher(st, http, notices).publish_now()
    assert [c[0] for c in http.calls] == ["PUT"]
    assert st.site_publish is False and (st.site_id, st.site_key) == (None, None)
    assert notices == ["ton profil a été retiré du site ; recoche « Publier » pour le recréer"]


def test_unpublish_deletes_and_forgets_the_key():
    st = _state(site_publish=False, site_id="11111111-2222-3333-4444-555555555555", site_key="k" * 64)
    http, notices = FakeHttp((204, b"")), []
    _publisher(st, http, notices).unpublish_now()
    assert [c[0] for c in http.calls] == ["DELETE"]
    assert (st.site_id, st.site_key) == (None, None)


def test_site_fields_saved(tmp_path):
    st = _state(site_id="abc", site_key="secret", site_show_camos=True)
    save_state(st, tmp_path / "s.json")
    back = load_state(tmp_path / "s.json")
    assert (back.site_publish, back.site_pseudo, back.site_id, back.site_key, back.site_show_camos) == \
        (True, "Romusan", "abc", "secret", True)


# ----- Task 7: engine hook, settings flow, window section -----

def test_engine_calls_on_stats_changed_after_a_scoreboard(tmp_path, registry):
    from tests.test_engine import load
    from trackcod.engine import Engine
    frames = [load("match_start_iso"), load("scoreboard_victoire"), load("scoreboard_victoire")]
    calls = []
    e = Engine(registry, AppState(), tmp_path / "s.json", tmp_path / "m.jsonl",
               lambda: frames.pop(0) if frames else None, lambda: 1_000_000.0,
               on_stats_changed=lambda: calls.append(1))
    for _ in range(3):
        e.step()
    assert calls == [1]  # the same scoreboard seen twice counts once


def test_unpublish_then_republish():
    st = _state(site_id="11111111-2222-3333-4444-555555555555", site_key="k" * 64)
    http, notices = FakeHttp((204, b""), REGISTERED, (204, b"")), []
    pub = _publisher(st, http, notices)
    st.site_publish = False
    pub.unpublish_now()
    st.site_publish = True
    pub.publish_now()
    assert [c[0] for c in http.calls] == ["DELETE", "POST", "PUT"]


def test_site_view():
    from trackcod.ui.viewmodel import build_view
    v = build_view(_state(site_id="abc"), 0.0)
    assert (v.site.published, v.site.pseudo, v.site.show_camos) == (True, "Romusan", False)
    assert v.site.url.endswith("/p/abc")  # share link: Discord shows a card
    assert build_view(AppState(), 0.0).site.url is None


def test_window_site_section():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit
    from trackcod.ui.viewmodel import build_view
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    changes = []
    w = MainWindow([], lambda n: None, lambda b: None, on_site_change=lambda *a: changes.append(a))
    w.render(build_view(AppState(), 0.0))
    publish = next(c for c in w.findChildren(QCheckBox) if c.text().startswith("Publier mes stats"))
    publish.click()
    assert changes == [] and any("choisis un pseudo" in l.text() for l in w.findChildren(QLabel))
    w.render(build_view(AppState(), 0.0))
    w.findChild(QLineEdit, "site_pseudo").setText("Romusan")
    next(c for c in w.findChildren(QCheckBox) if c.text().startswith("Publier mes stats")).click()
    assert changes == [(True, "Romusan", False)]
    w.close()


# ----- final review fixes -----

def test_failed_removal_is_retried_later():
    st = _state(site_publish=False, site_id="11111111-2222-3333-4444-555555555555", site_key="k" * 64)
    http, notices = FakeHttp(OSError("down"), (204, b"")), []
    pub = _publisher(st, http, notices)
    pub.sync_now()   # site down: the profile is still online, remember it
    assert st.site_id is not None and len(notices) == 1
    pub.sync_now()   # next event (match, startup): the removal is sent again
    assert [c[0] for c in http.calls] == ["DELETE", "DELETE"]
    assert (st.site_id, st.site_key) == (None, None)


def test_removal_never_raises():
    st = _state(site_publish=False, site_id="11111111-2222-3333-4444-555555555555", site_key="k" * 64)
    notices = []
    _publisher(st, FakeHttp(ValueError("bad body")), notices).unpublish_now()
    assert len(notices) == 1


def test_recheck_before_the_removal_runs_keeps_the_profile():
    # uncheck then re-check quickly: the removal thread runs after the box is ticked again
    st = _state(site_publish=True, site_id="11111111-2222-3333-4444-555555555555", site_key="k" * 64)
    http = FakeHttp()
    _publisher(st, http, []).unpublish_now()
    assert http.calls == [] and st.site_id is not None


def test_window_remove_button():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton
    from trackcod.ui.viewmodel import build_view
    from trackcod.ui.window import MainWindow
    app = QApplication.instance() or QApplication([])
    changes = []
    w = MainWindow([], lambda n: None, lambda b: None, on_site_change=lambda *a: changes.append(a))
    w.render(build_view(_state(site_id="abc", site_show_camos=True), 0.0))
    next(b for b in w.findChildren(QPushButton) if b.text() == "Me retirer du site").click()
    assert changes == [(False, "Romusan", True)]
    w.close()
