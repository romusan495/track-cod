"""Live frame source: game window capture -> OCR lines (with extra passes for the screens that need them)."""

from trackcod.capture.screen import find_game_window, grab
from trackcod.ocr.engine import ocr_image
from trackcod.readers.apparence import ocr_apparence
from trackcod.readers.classify import classify
from trackcod.readers.common import OcrLine
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
    base = ocr_image(img)
    kind = classify(base)
    if kind == "apparence":
        lines = ocr_apparence(img, raw=base)
        tiles.feed(img, lines)
        return lines
    if kind in ("match_start", "class"):  # green weapon name above 'MULTI', often hidden by the gun picture
        return base + ocr_match_start(img, base)
    return base
