
from trackcod.model import AppState, GlobalStats, MatchStats
from trackcod.stats import calibrate, match_fingerprint, record_match



def test_fingerprint_stable_and_distinct():
    a = match_fingerprint(24, 17, 2475, "Domination", "Cheongun", 1)
    assert a == match_fingerprint(24, 17, 2475, "Domination", "Cheongun", 1)
    assert a != match_fingerprint(24, 18, 2475, "Domination", "Cheongun", 1)


def test_same_match_counted_once():
    st = AppState()
    fp = match_fingerprint(24, 17, 2475, "Domination", "Cheongun", 1)
    m = MatchStats(600.0, 24, 17, 2475, "win", "Domination", "Cheongun", "ISO Nightshade", fp)
    assert record_match(st, m) is True and record_match(st, m) is False
    g = st.global_stats
    assert (g.games, g.wins, g.kills, g.deaths) == (1, 1, 24, 17) and st.last_match == m


def test_calibrate_then_accumulate():
    st = AppState()
    calibrate(st, GlobalStats(kills=8000, deaths=7000, wins=150, losses=140, games=300), at=50.0)
    record_match(st, MatchStats(60.0, 20, 10, None, "loss", None, None, None, "fp1"))
    g = st.global_stats
    assert (g.kills, g.games, g.losses, g.matches_since_calibration, g.calibrated_at) == (8020, 301, 141, 1, 50.0)


def test_recalibrate_resets_counter():
    st = AppState()
    record_match(st, MatchStats(60.0, 20, 10, None, "win", None, None, None, "fp1"))
    calibrate(st, GlobalStats(kills=1, deaths=1, games=1), at=70.0)
    assert st.global_stats.matches_since_calibration == 0 and st.global_stats.kills == 1


