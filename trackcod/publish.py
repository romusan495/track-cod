"""Publishes the player's own stats to the Track COD site, only when he opted in ('Publier mes stats').

Sent: his global, his 5 last matches, level / prestige and (if he chose so) his camo mastery. Never another
player's name. Network work runs in a daemon thread with a 5 s timeout and never raises into the tracker.
"""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable

from trackcod.model import AppState, MatchStats

SITE_URL = "https://track-cod.romusangames.workers.dev"
TIMEOUT_S = 5
MAX_MATCHES = 5
UNREACHABLE = "site injoignable, nouvel essai plus tard"
PSEUDO_TAKEN = "pseudo déjà pris, choisis-en un autre"
REMOVED = "ton profil a été retiré du site ; recoche « Publier » pour le recréer"


class SiteError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _urllib_send(method: str, url: str, headers: dict, body: bytes | None, timeout: float = TIMEOUT_S):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class SiteClient:
    def __init__(self, base_url: str, send=_urllib_send):
        self.base = base_url.rstrip("/")
        self.send = send

    def _call(self, method: str, path: str, body: dict | None = None, key: str | None = None) -> dict:
        headers = {"User-Agent": "TrackCOD"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            status, raw = self.send(method, self.base + path, headers, data, timeout=TIMEOUT_S)
        except OSError as e:  # timeout, DNS, connection refused (urllib.error.URLError is an OSError)
            raise SiteError(str(e)) from e
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        if status >= 400:
            raise SiteError(payload.get("error") or f"HTTP {status}", status)
        return payload

    def register(self, pseudo: str) -> tuple[str, str]:
        r = self._call("POST", "/api/players", {"pseudo": pseudo})
        return r["id"], r["key"]

    def update(self, player_id: str, key: str, payload: dict) -> None:
        self._call("PUT", f"/api/players/{player_id}", payload, key)

    def delete(self, player_id: str, key: str) -> None:
        self._call("DELETE", f"/api/players/{player_id}", key=key)


def _leading_int(text: str) -> int:
    digits = ""
    for ch in text:
        if not ch.isdigit():
            break
        digits += ch
    return int(digits or 0)


def build_payload(state: AppState, matches: list[MatchStats], mastery_rows: list[tuple[str, str]] | None) -> dict:
    g = state.global_stats
    recent = sorted(matches, key=lambda m: m.at, reverse=True)[:MAX_MATCHES]
    mastery = None
    if state.site_show_camos and mastery_rows:
        rows = dict(mastery_rows)
        mastery = {"or": _leading_int(rows.get("Or", "0")), "platine": _leading_int(rows.get("Platine", "0")),
                   "rupture": _leading_int(rows.get("Rupture harmonique", "0"))}
    return {
        "global": {"kills": g.kills, "deaths": g.deaths, "wins": g.wins, "losses": g.losses, "games": g.games,
                   "calibrated": g.calibrated_at is not None},
        "matches": [{"at": int(m.at), "mode": m.mode, "map": m.map, "kills": m.kills, "deaths": m.deaths,
                     "score": m.score, "result": m.result} for m in recent],
        "level": state.player_level,
        "prestige": state.prestige,
        "mastery": mastery,
    }


class Publisher:
    def __init__(self, state: AppState, client: SiteClient, notice: Callable[[str], None],
                 recent_matches: Callable[[], list[MatchStats]],
                 mastery: Callable[[], list[tuple[str, str]] | None] = lambda: None,
                 saved: Callable[[], None] = lambda: None):
        self.state, self.client, self.notice = state, client, notice
        self.recent_matches, self.mastery, self.saved = recent_matches, mastery, saved
        self._lock = threading.Lock()
        self._failing = False  # one notice per failure burst, not per attempt

    def _start(self, target) -> None:
        threading.Thread(target=target, daemon=True, name="trackcod-site").start()

    def publish_async(self) -> None:
        """After a match, a recalibration, a settings change or at startup: publish, or finish a removal
        that failed earlier (profile still online while 'Publier' is unticked)."""
        if self.state.site_publish or self.state.site_id:
            self._start(self.sync_now)

    def unpublish_async(self) -> None:
        self._start(self.unpublish_now)

    def sync_now(self) -> None:
        if self.state.site_publish:
            self.publish_now()
        elif self.state.site_id:
            self.unpublish_now()

    def _fail(self, message: str) -> None:
        if not self._failing:
            self._failing = True
            self.notice(message)

    def publish_now(self) -> None:
        st = self.state
        if not (st.site_publish and st.site_pseudo):
            return
        with self._lock:
            try:
                payload = build_payload(st, self.recent_matches(), self.mastery())
                if not st.site_id:
                    st.site_id, st.site_key = self.client.register(st.site_pseudo)
                    self.saved()
                self.client.update(st.site_id, st.site_key, payload)
                self._failing = False
            except SiteError as e:
                if e.status in (401, 404):
                    # removed by the admin (moderation) or after 90 idle days: never re-created silently
                    st.site_publish, st.site_id, st.site_key = False, None, None
                    self.saved()
                    self.notice(REMOVED)
                elif e.status == 409:
                    st.site_publish = False
                    self.saved()
                    self.notice(PSEUDO_TAKEN)
                elif e.status == 429:
                    pass  # sent less than 30 s ago: the next match will carry these stats
                elif e.status == 400:
                    self.notice(f"site : {e}")
                else:
                    self._fail(UNREACHABLE)
            except Exception:  # never let the site break the tracker
                self._fail(UNREACHABLE)

    def unpublish_now(self) -> None:
        st = self.state
        with self._lock:
            if st.site_publish:
                return  # ticked again before this ran: keep the profile
            if st.site_id and st.site_key:
                try:
                    self.client.delete(st.site_id, st.site_key)
                except SiteError as e:
                    if e.status not in (401, 404):  # already gone is fine; else retried by publish_async
                        self._fail(UNREACHABLE)
                        return
                except Exception:  # never let the site break the tracker
                    self._fail(UNREACHABLE)
                    return
            st.site_id = st.site_key = None
            self._failing = False
            self.saved()
