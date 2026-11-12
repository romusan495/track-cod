import json
from pathlib import Path

from trackcod.meta import MetaSource, find_weapon, parse_meta_page

PAGE = (Path(__file__).parent / "fixtures" / "meta" / "mw4.html").read_text(encoding="utf-8")


def test_parse_real_page():
    meta = parse_meta_page(PAGE)
    assert meta.updated == "2026-11-07" and len(meta.weapons) == 35
    iso = next(w for w in meta.weapons if w.name == "ISO NIGHTSHADE")
    assert iso.tier == "META" and [b.label for b in iso.builds][:2] == ["Polyvalent", "Faible niveau"]
    first = iso.builds[0].attachments[0]
    assert (first.slot_label, first.name, first.level) == ("Bouche", "XRK HERDER 40", 17)
    assert iso.builds[0].attachments[2].name == "POIGNÉE FSS TAC90"


def test_inch_marks_survive():
    meta = parse_meta_page(PAGE)
    names = [a.name for w in meta.weapons for b in w.builds for a in b.attachments]
    assert 'ZLR MAG-Z 9"' in names


def test_unknown_style_label_falls_back_to_readable_text():
    meta = parse_meta_page(PAGE)
    labels = {b.style: b.label for w in meta.weapons for b in w.builds}
    assert labels["MOBILITY"] == "Mobility" and labels["LOW_RECOIL"] == "Low recoil"


def test_page_without_data_gives_none():
    assert parse_meta_page("<html><body>maintenance</body></html>") is None


def test_find_weapon():
    meta = parse_meta_page(PAGE)
    assert find_weapon(meta, "ISO Nightshade").name == "ISO NIGHTSHADE"
    assert find_weapon(meta, "Arme inexistante") is None


class FakeFetch:
    def __init__(self, pages):
        self.pages, self.calls = list(pages), 0

    def __call__(self, url):
        self.calls += 1
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page


def test_source_fetches_then_uses_fresh_cache(tmp_path):
    fetch = FakeFetch([PAGE])
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: 1000.0)
    assert src.get().updated == "2026-11-07" and fetch.calls == 1
    assert src.get().updated == "2026-11-07" and fetch.calls == 1   # in-memory, fresh
    again = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: 2000.0)
    assert again.get() is not None and fetch.calls == 1           # disk cache, fresh


def test_source_refreshes_after_a_day_and_keeps_cache_offline(tmp_path):
    now = [1000.0]
    fetch = FakeFetch([PAGE, OSError("offline")])
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: now[0])
    src.get()
    now[0] += 86400 + 1
    meta = src.get()
    assert fetch.calls == 2 and meta is not None and meta.stale is True


def test_source_broken_page_keeps_cache(tmp_path):
    now = [1000.0]
    fetch = FakeFetch([PAGE, "<html>nouveau format</html>"])
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: now[0])
    src.get()
    now[0] += 86400 + 1
    assert src.get().weapons and src.get().stale is True


def test_source_nothing_at_all(tmp_path):
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=FakeFetch([OSError("x")]), clock=lambda: 1.0)
    assert src.get() is None


def test_corrupt_cache_ignored(tmp_path):
    (tmp_path / "meta.json").write_text("{oops", encoding="utf-8")
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=FakeFetch([PAGE]), clock=lambda: 1.0)
    assert src.get().updated == "2026-11-07"
    assert json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))["updated"] == "2026-11-07"


def test_failed_fetch_waits_an_hour_before_retrying(tmp_path):
    now = [1000.0]
    fetch = FakeFetch([OSError("x"), PAGE])
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: now[0])
    assert src.get() is None and src.get() is None and fetch.calls == 1
    now[0] += 3601
    assert src.get() is not None and fetch.calls == 2


def test_find_weapon_by_name_and_category():
    from trackcod.meta import find_weapon as fw
    meta = parse_meta_page(PAGE)
    assert fw(meta, "ISO NIGHTSHADE").category == "Mitraillette" and fw(meta, "Inconnue") is None


def test_cached_reads_disk_without_network(tmp_path):
    MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=FakeFetch([PAGE]), clock=lambda: 1.0).get()
    offline = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=FakeFetch([]), clock=lambda: 9e9)
    assert offline.cached().updated == "2026-11-07"
    assert MetaSource("https://x/", tmp_path / "none.json", fetch=FakeFetch([])).cached() is None


def test_http_error_does_not_kill_the_source(tmp_path):
    import http.client
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json",
                     fetch=FakeFetch([http.client.IncompleteRead(b"x")]), clock=lambda: 1.0)
    assert src.get() is None


def test_old_cache_without_categories_is_refetched(tmp_path):
    import json as _j
    (tmp_path / "meta.json").write_text(_j.dumps({"updated": "2026-11-07", "fetched_at": 1.0, "stale": False,
        "weapons": [{"name": "ISO NIGHTSHADE", "tier": "META", "builds": []}]}), encoding="utf-8")
    fetch = FakeFetch([PAGE])
    src = MetaSource("https://x/mw4/", tmp_path / "meta.json", fetch=fetch, clock=lambda: 2.0)
    assert src.cached() is None
    assert next(w for w in src.get().weapons if w.name == "ISO NIGHTSHADE").category == "Mitraillette"
