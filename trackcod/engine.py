"""Worker loop: reads the game screen, updates and saves AppState."""

import logging

from rapidfuzz import fuzz
import threading
import time
from collections.abc import Callable
from pathlib import Path

from trackcod.model import AppState, MatchStats, WeaponSheet
from trackcod.readers.apparence import HoverTracker, read_apparence
from trackcod.readers.classify import classify
from trackcod.readers.combat_record import read_combat_record
from trackcod.readers.common import OcrLine
from trackcod.readers.match_start import read_breadcrumb, read_match_info, read_match_start, read_weapon_title
from trackcod.readers.scoreboard import read_scoreboard
from trackcod.known_camos import KnownCamos
from trackcod.readers.unlock_banner import has_unlocked_word, read_banner
from trackcod.thumbs import save_thumbs
from trackcod.readers.class_screen import read_class_weapon
from trackcod.readers.item_unlock import read_item_unlock
from trackcod.readers.player import read_player_level
from trackcod.sheets import _erudit_needs_specials, answer_camo, apply_tile_locks, count_item_unlock, display_name
from trackcod.sheets import apply_apparence, mark_unlocked, new_sheet, seed_specials
from trackcod.stats import calibrate, record_match
from trackcod.store import append_match, save_state
from trackcod.weapons import WeaponRegistry

log = logging.getLogger("trackcod")

STEP_INTERVAL_S = 1.0
APPARENCE_INTERVAL_S = 0.1
APPARENCE_VISIT_END_S = 3.0
SAME_MATCH_WINDOW_S = 300.0
BANNER_CONFIRM_S = 8.0   # 'DÉBLOQUÉ' must follow the banner within this delay
ITEM_GAP_S = 2.5          # an unreadable item card seen again after this gap is a new unlock
ITEM_REPEAT_S = 30.0      # the same item name seen again within this delay is the same unlock
UNLOCK_REPEAT_S = 60.0   # the same unlock seen again within this delay is ignored
MAX_NOTICES = 5
SUSPENDED = "Lecture de l'écran suspendue par Track COD"


class Engine:
    def __init__(self, registry: WeaponRegistry, state: AppState, state_path: Path, matches_path: Path,
                 frame_source: Callable[[], list[OcrLine] | None], clock: Callable[[], float] = time.time,
                 known: KnownCamos | None = None, tile_source: Callable[[], dict] | None = None,
                 thumbs_dir: Path | None = None, on_stats_changed: Callable[[], None] = lambda: None):
        self.registry = registry
        self.known = known if known is not None else KnownCamos.load()
        self.state = state
        self.state_path = Path(state_path)
        self.matches_path = Path(matches_path)
        self.frame_source = frame_source
        self.on_stats_changed = on_stats_changed  # new match or recalibration: the site gets the new stats
        self.tile_source = tile_source      # camo thumbnails cut during the Apparence visit
        self.thumbs_dir = Path(thumbs_dir) if thumbs_dir else None
        self.clock = clock
        self.hover = HoverTracker()
        self._last_apparence = 0.0
        self._current_map: str | None = None
        self._scoreboard_seen_at = state.last_match.at if state.last_match else 0.0
        self.lock = threading.Lock()
        self._banner: tuple | None = None          # (BannerRead, seen_at) waiting for 'DÉBLOQUÉ'
        self._unlocks_seen: dict[tuple, float] = {}
        self._level_read: int | None = None             # last badge read, waiting for a second one
        self._items_seen: list[tuple[str, float]] = []   # (item card text, last seen)
        self._item_card_at = -1e9

    # ----- helpers -----

    def sheet(self, weapon: str) -> WeaponSheet:
        if weapon not in self.state.sheets:
            self.state.sheets[weapon] = new_sheet(weapon, self.registry.category(weapon))
        sheet = self.state.sheets[weapon]
        seed_specials(sheet, self.known.specials(weapon))
        _erudit_needs_specials(sheet)
        if not sheet.category:  # created offline, before the site list arrived
            sheet.category = self.registry.category(weapon)
        return sheet

    def _notice(self, text: str) -> None:
        if text not in self.state.notices:
            self.state.notices.append(text)
            del self.state.notices[:-MAX_NOTICES]

    def save(self) -> None:
        with self.lock:
            self._save()

    def set_weapon(self, weapon: str) -> None:
        """Manual weapon choice from the window."""
        with self.lock:
            weapon = self.registry.add(weapon) or weapon
            self.state.weapon = weapon
            self.sheet(weapon)
            self._save()

    def answer_camo(self, key: str, has: bool) -> None:
        """The player's answer to 'Tu l'as déjà ?' for the current weapon."""
        with self.lock:
            if self.state.weapon:
                answer_camo(self.sheet(self.state.weapon), key, has)
                self._save()

    # ----- steps -----

    def _save(self) -> None:
        self.state.learned_weapons = list(self.registry.learned)
        save_state(self.state, self.state_path)

    def _is_same_match(self, m: MatchStats) -> bool:
        """Same numbers seen again while the scoreboard stays up (mode text is OCR-unstable, so ignored)."""
        last = self.state.last_match
        same = (last is not None and m.at - self._scoreboard_seen_at < SAME_MATCH_WINDOW_S
                and (last.kills, last.deaths, last.score, last.result) == (m.kills, m.deaths, m.score, m.result))
        if same:
            self._scoreboard_seen_at = m.at
        return same

    def _apply_unlock(self, banner, now: float) -> bool:
        key = (banner.weapon, banner.section, banner.number, banner.name)
        self._banner = None
        if now - self._unlocks_seen.get(key, -1e9) < UNLOCK_REPEAT_S:
            return False
        self._unlocks_seen[key] = now
        mark_unlocked(self.sheet(banner.weapon), banner.section, banner.number, banner.name)
        self._notice(f"Débloqué : {banner.weapon} — {banner.label}")
        return True

    def _count_item(self, lines: list[OcrLine], now: float, camo_pending: bool) -> bool:
        """Level-up card 'DÉBLOQUÉ' + item: one weapon item closer to the next special (not for camos)."""
        unlock = read_item_unlock(lines)
        if unlock is None:
            return False
        gap = now - self._item_card_at
        self._item_card_at = now
        self._items_seen = [(t, at) for t, at in self._items_seen if now - at <= ITEM_REPEAT_S]
        if unlock.item:
            same = next((i for i, (t, _) in enumerate(self._items_seen) if fuzz.ratio(t, unlock.item) >= 75), None)
            if same is not None:
                self._items_seen[same] = (self._items_seen[same][0], now)
                return False
            self._items_seen.append((unlock.item, now))
        elif gap <= ITEM_GAP_S:
            return False
        if unlock.is_camo or camo_pending or not self.state.weapon:
            return False
        sheet = self.sheet(self.state.weapon)
        opened = count_item_unlock(sheet)
        log.info("élément d'arme débloqué (%s) : %s", self.state.weapon, unlock.item or "?")
        for c in opened:
            self._notice(f"Spécial accessible : {self.state.weapon} — {display_name(c)}")
        return True

    def _finish_apparence(self) -> bool:
        reading = self.hover.finish()
        tiles = self.tile_source() if self.tile_source else {}
        if reading is None:
            return False
        reads = reading.weapon_reads or ([reading.weapon] if reading.weapon else [])
        on_screen = None
        for read in reads:  # each frame counts as one read (spec v2 §9)
            on_screen = self.registry.observe(read) or on_screen
            if on_screen:
                break
        if reads and on_screen is None:
            # A weapon name was read but is not known yet: never put this visit on another weapon's sheet.
            self._notice("Arme pas encore reconnue : reste un peu plus longtemps sur Apparence")
            return True
        weapon = on_screen or self.state.weapon
        if weapon is None:
            self._notice("Arme inconnue : choisis-la dans la fenêtre")
            return True
        self.state.weapon = weapon
        apply_apparence(self.sheet(weapon), reading, weapon_confirmed=on_screen is not None)
        if on_screen is not None and tiles:
            apply_tile_locks(self.sheet(weapon), {k: getattr(t, "locked", None) for k, t in tiles.items()})
        if on_screen is not None and tiles and self.thumbs_dir is not None:
            try:
                save_thumbs(self.thumbs_dir, weapon, {k: getattr(t, "image", t) for k, t in tiles.items()})
            except OSError as e:
                log.warning("vignettes non enregistrées : %s", e)
        return True

    def _read_level(self, lines: list[OcrLine]) -> bool:
        level = read_player_level(lines)
        if level is None:
            return False
        confirmed, self._level_read = level == self._level_read, level
        old = self.state.player_level
        if not confirmed or level == old:
            return False
        if old is not None and self.state.prestige is not None and level < old - 10:
            self.state.prestige += 1  # a prestige puts the level back to the start
            self._notice(f"Prestige {self.state.prestige}")
        self.state.player_level = level
        return True

    def set_prestige(self, prestige: int) -> None:
        with self.lock:
            self.state.prestige = prestige
            self._save()

    def _read_frame(self, lines: list[OcrLine], now: float) -> bool:
        if self._read_level(lines):
            self._read_frame_inner(lines, now)
            return True
        return self._read_frame_inner(lines, now)

    def _read_frame_inner(self, lines: list[OcrLine], now: float) -> bool:
        kind = classify(lines)
        if kind == "apparence":
            reading = read_apparence(lines, now)
            if reading is None:
                return False
            changed = False
            weapon = self.registry.match(reading.weapon) if reading.weapon else None
            if weapon and self.hover.active and self.registry.match(self.hover.weapon or "") not in (None, weapon):
                changed = self._finish_apparence()  # another weapon chosen meanwhile: close the previous visit
            self.hover.feed(reading)
            self._last_apparence = now
            if self.state.phase != "menu":  # Apparence is a menu screen: any match is over
                self.state.phase, self.state.phase_at = "menu", now
                changed = True
            if weapon and weapon != self.state.weapon:  # show the new weapon at once, not when leaving Apparence
                self.state.weapon = weapon
                self.sheet(weapon)
                changed = True
            return changed
        if kind == "match_start":
            weapon = read_match_start(lines, self.registry)
            _, self._current_map = read_match_info(lines)
            if weapon is None or (weapon == self.state.weapon and self.state.phase == "in_match"):
                return False
            self.state.weapon, self.state.phase, self.state.phase_at = weapon, "in_match", now
            self.sheet(weapon)
            return True
        if kind == "scoreboard":
            m = read_scoreboard(lines, now, self.state.weapon)
            if m is None or self._is_same_match(m):
                return False
            m.map = self._current_map
            self._scoreboard_seen_at = now
            if record_match(self.state, m):
                append_match(m, self.matches_path)
                self.state.phase, self.state.phase_at = "post_match", now
                self.on_stats_changed()
                return True
            return False
        if kind == "class":
            weapon = read_class_weapon(lines, self.registry)
            if weapon is None or weapon == self.state.weapon:
                return False
            self.state.weapon = weapon
            self.sheet(weapon)
            return True
        if kind == "combat_record":
            g = read_combat_record(lines)
            cur = self.state.global_stats
            if g is None or (cur.calibrated_at is not None and cur.matches_since_calibration == 0
                             and (g.kills, g.deaths, g.games) == (cur.kills, cur.deaths, cur.games)):
                return False
            calibrate(self.state, g, now)
            self.on_stats_changed()
            return True
        banner = read_banner(lines, self.registry, self.known)
        if banner is not None:
            self._banner = (banner, now)
        changed = self._count_item(lines, now, camo_pending=self._banner is not None
                                   and now - self._banner[1] <= BANNER_CONFIRM_S)
        if changed:
            return True
        if self._banner and has_unlocked_word(lines) and now - self._banner[1] <= BANNER_CONFIRM_S:
            return self._apply_unlock(self._banner[0], now)
        titled = read_weapon_title(lines, self.registry)
        if titled and titled != self.state.weapon:
            self.state.weapon = titled
            self.sheet(titled)
            return True
        crumb = read_breadcrumb(lines)
        if crumb:
            before = len(self.registry.learned)
            self.registry.observe(crumb)
            return len(self.registry.learned) != before
        return False

    def apply_status(self, status) -> None:
        """Remote switch (trackcod.killswitch): None = unknown, keep the last known state."""
        if status is None:
            return
        with self.lock:
            self.state.notices = [n for n in self.state.notices if not n.startswith(SUSPENDED)]
            if status.active:
                self.state.reading_suspended = None
            else:
                self.state.reading_suspended = status.message or ""
                self._notice(SUSPENDED + (f" : {status.message}" if status.message else ""))
            self._save()

    def step(self) -> bool:
        with self.lock:
            if self.state.reading_suspended is not None:
                return False  # suspended from the site: the screen is not read at all
            now = self.clock()
            changed = False
            lines = self.frame_source()
            if lines:
                changed |= self._read_frame(lines, now)
            if self.hover.active and now - self._last_apparence > APPARENCE_VISIT_END_S:
                changed |= self._finish_apparence()
            if changed:
                self._save()
            return changed

    def next_interval(self) -> float:
        """No pause while the player browses Apparence: each hovered camo needs 2 reads in ~2 s."""
        return APPARENCE_INTERVAL_S if self.hover.active else STEP_INTERVAL_S

    def run(self, stop: threading.Event, on_change: Callable[[AppState], None]) -> None:
        while not stop.is_set():
            started = time.time()
            try:
                if self.step():
                    on_change(self.state)
            except Exception as exc:  # keep the tracker alive; surface the problem in the window
                log.exception("erreur pendant la lecture")
                with self.lock:
                    self._notice(f"Erreur de lecture : {exc.__class__.__name__}")
                on_change(self.state)
            stop.wait(max(0.0, self.next_interval() - (time.time() - started)))
