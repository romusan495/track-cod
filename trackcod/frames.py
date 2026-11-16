"""Live frame source: game window capture -> OCR lines (with extra passes for the screens that need them)."""

from trackcod.capture.screen import find_game_window, grab
from trackcod.ocr.engine import ocr_image
from trackcod.readers.apparence import ocr_apparence
from trackcod.readers.challenge_done import ocr_center_band
from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine
from trackcod.readers.daily import daily_bars, ocr_daily_panel
from trackcod.readers.scoreboard import ocr_own_row
from trackcod.readers.match_start import ocr_match_start
from trackcod.readers.tiles import grab_tiles
import threading
import time

TILE_EVERY_S = 2.0  # cutting thumbnails on every Apparence frame would slow the hover reads


class TileCollector:
    """Thumbnails seen during the current Apparence visit, taken by the engine when the visit ends."""

    def __init__(self):
        self._tiles: dict = {}
        self._at = 0.0
        self._lock = threading.Lock()

    def feed(self, img, lines) -> None:
        now = time.monotonic()
        if now - self._at < TILE_EVERY_S:
            return
        self._at = now
        try:
            tiles = grab_tiles(img, lines)
        except Exception:  # a thumbnail is a bonus: never break the reading for it
            return
        with self._lock:
            self._tiles.update(tiles)

    def take(self) -> dict:
        with self._lock:
            tiles, self._tiles = self._tiles, {}
        return tiles


tiles = TileCollector()


def live_frame_source() -> list[OcrLine] | None:
    rect = find_game_window()
    if rect is None:
        return None
    img = grab(rect)
    return read_frame(img, ocr_image(img), tiles.feed)


def read_frame(img, base: list[OcrLine], on_apparence=None) -> list[OcrLine]:
    """The lines the engine reads for a frame: the whole-screen Windows OCR (`base`) plus the extra passes the
    screen needs. Also used to replay recorded sessions."""
    kind = classify(base)
    if kind == "apparence":
        lines = ocr_apparence(img, raw=base)
        if on_apparence is not None:
            on_apparence(img, lines)
        return lines
    if kind in ("match_start", "class"):  # green weapon name above 'MULTI', often hidden by the gun picture
        return base + ocr_match_start(img, base)
    if kind == "scoreboard":  # the player's highlighted row is read badly: zoom on it
        return ocr_own_row(img, base)
    if kind == "daily":  # fine OCR of the panel (counters); the progress bars measured when still unreadable
        lines = ocr_daily_panel(img, base)
        return lines + daily_bars(img, lines)
    if kind == "other":  # in match: 'DÉFI TERMINÉ' / 'NOUVEL ÉLÉMENT' in the middle, re-read when something shows
        return ocr_center_band(img, base)
    return base
