"""Camo thumbnails cut from the Apparence screen (the player's own screen, kept on their PC only).

The tiles sit on a fixed grid under each section header (left edge = header text, sizes proportional to the
screen height). The OCR box of a header jitters by a few pixels, so the top of the grid is snapped to the
strongest horizontal edge just below the header. The hovered tile (green dotted frame, zoomed) is skipped.
"""

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

from trackcod.readers.classify import header_section
from trackcod.readers.common import OcrLine

# section: (columns, rows, tile size, pitch), sizes in screen heights (measured at 3440x1440)
LAYOUT = {
    "military": (4, 2, 0.0854, 0.1),
    "special": (3, 1, 0.1188, 0.1333),
    "erudit": (4, 1, 0.0854, 0.1),
}
THUMB = 96  # saved thumbnail side, px

# Padlock drawn by the game in the top-left corner of a locked tile, measured at 1440 px screen height on a
# 40x40 corner: white body with a dark keyhole, and a shackle with a dark hole. Same size on every tile.
_CORNER = 40
_BODY = (10, 15, 27, 32)
_KEYHOLE = (18, 21, 20, 27)
_HOLE = (14, 10, 23, 14)
_BESIDE = (31, 14, 39, 31)


@dataclass
class Tile:
    image: Image.Image          # thumbnail, THUMB x THUMB
    locked: bool | None         # padlock seen / not seen / can't tell (tile too bright, e.g. Platine in HDR)


def _edge_top(img: Image.Image, left: int, right: int, start: int, stop: int, side: int, step: int,
              rows: int) -> int:
    """Top of the grid in [start, stop): the row where the tiles' top AND bottom edges line up best (a lone
    bright line, like the section highlight, only matches one of them)."""
    y0, y1 = max(1, start - 1), min(img.height, stop + (rows - 1) * step + side + 1)
    strip = img.crop((left, y0, right, y1)).convert("L")
    prof = strip.resize((1, strip.height), Image.BOX).tobytes()

    def jump(y: int) -> int:
        i = y - y0
        return abs(prof[i] - prof[i - 1]) if 0 < i < len(prof) else 0

    def score(t: int) -> int:
        return sum(jump(t + r * step) + jump(t + r * step + side) for r in range(rows))

    return max(range(start, stop), key=score)


def _mean(img: Image.Image, box) -> float:
    return ImageStat.Stat(img.crop(box)).mean[0]


def lock_state(corner: Image.Image) -> bool | None:
    """corner: the tile's top-left 40x40 at the 1440p scale (grey levels)."""
    best: bool | None = False
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            def sh(b):
                return (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
            body = _mean(corner, sh(_BODY))
            keyhole, hole, beside = _mean(corner, sh(_KEYHOLE)), _mean(corner, sh(_HOLE)), _mean(corner, sh(_BESIDE))
            if body >= 185 and body - keyhole >= 30 and body - hole >= 25 and body - beside >= 25:
                return True
            if body >= 185 and beside >= 185:
                best = None  # bright all over: a white padlock would not show
    return best


def is_hovered(tile: Image.Image) -> bool:
    """The hovered tile has a bright light-green dotted frame along its border."""
    w, h = tile.size
    ring = Image.new("L", (w, h), 0)
    border = max(2, w // 30)
    ring.paste(255, (0, 0, w, h))
    ring.paste(0, (border, border, w - border, h - border))
    r, g, b = tile.convert("RGB").split()
    green = ImageChops.subtract(g, r).point(lambda v: 255 if v > 15 else 0)
    bright = g.point(lambda v: 255 if v > 190 else 0)
    hit = ImageChops.multiply(ImageChops.multiply(green, bright), ring)
    share = ImageStat.Stat(hit).sum[0] / max(1, ImageStat.Stat(ring).sum[0])
    return share > 0.12


def grab_tiles(img: Image.Image, lines: list[OcrLine]) -> dict[tuple[str, int], Tile]:
    """{(section, index from 1, left to right then top to bottom): Tile} for the tiles on screen."""
    W, H = img.size
    tiles: dict[tuple[str, int], Image.Image] = {}
    seen = set()
    for line in sorted(lines, key=lambda l: l.y):
        section = header_section(line)
        if section not in LAYOUT or section in seen:
            continue
        seen.add(section)
        cols, rows, size, pitch = LAYOUT[section]
        side, step = round(size * H), round(pitch * H)
        left = round(line.x * W)
        bottom = round((line.y + line.h) * H)
        top = _edge_top(img, left, left + (cols - 1) * step + side, bottom - round(0.01 * H),
                        bottom + round(0.04 * H), side, step, rows)
        for r in range(rows):
            for c in range(cols):
                box = (left + c * step, top + r * step, left + c * step + side, top + r * step + side)
                if box[2] > W or box[3] > H:
                    continue
                tile = img.crop(box).convert("RGB")
                if is_hovered(tile):
                    continue
                k = round(_CORNER * H / 1440)
                corner = tile.crop((0, 0, k, k)).convert("L").resize((_CORNER, _CORNER), Image.BILINEAR)
                tiles[(section, r * cols + c + 1)] = Tile(tile.resize((THUMB, THUMB), Image.LANCZOS),
                                                          lock_state(corner))
    return tiles
