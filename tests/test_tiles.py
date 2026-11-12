"""Camo thumbnails cut from real Apparence screens (kept on the player's PC only)."""

import json
from pathlib import Path

from PIL import Image

from trackcod.readers.common import OcrLine
from trackcod.readers.tiles import THUMB, grab_tiles
from trackcod.sheets import camo_index, ensure_slots, new_sheet, seed_specials
from trackcod.known_camos import KnownCamos
from trackcod.thumbs import save_thumbs, thumb_path

FIX = Path(__file__).parent / "fixtures"


def _screen(name):
    lines = [OcrLine(**d) for d in json.loads((FIX / "ocr" / f"{name}.json").read_text(encoding="utf-8"))]
    return Image.open(FIX / "img" / f"{name}.webp").convert("RGB"), lines


def test_grab_tiles_skips_the_hovered_one():
    img, lines = _screen("apparence_full_asphalte")  # Asphalte (special 1) hovered
    tiles = grab_tiles(img, lines)
    assert ("special", 1) not in tiles
    assert {("special", 2), ("special", 3)} <= set(tiles)
    assert all(("military", n) in tiles for n in range(1, 9))
    assert tiles[("special", 3)].image.size == (THUMB, THUMB)


def test_grab_tiles_military_screen():
    img, lines = _screen("apparence_full_militaire1")  # military 1 hovered
    tiles = grab_tiles(img, lines)
    assert ("military", 1) not in tiles and ("military", 8) in tiles


def test_tiles_are_real_squares_not_background():
    img, lines = _screen("apparence_full_asphalte")
    orange = grab_tiles(img, lines)[("special", 3)].image  # ISO 'Marron': a plain orange tile
    r, g, b = orange.resize((1, 1), Image.BOX).getpixel((0, 0))
    assert r > 150 and r > g > b
    top = orange.crop((0, 0, THUMB, 3)).resize((1, 1), Image.BOX).getpixel((0, 0))
    assert top[0] > 120  # no dark header strip on top: the grid is snapped on the tiles


def test_save_and_find_thumbnails(tmp_path):
    tile = Image.new("RGB", (THUMB, THUMB), (200, 100, 50))
    save_thumbs(tmp_path, "REZI 12", {("special", 1): tile})
    p = thumb_path(tmp_path, "REZI 12", "special", 1)
    assert p is not None and p.exists()
    assert thumb_path(tmp_path, "REZI 12", "special", 2) is None


def test_camo_index_follows_game_order():
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    specials = sorted((c for c in s.camos if c.section == "special"), key=lambda c: c.order)
    assert [camo_index(s, c) for c in specials] == [1, 2, 3]
    ensure_slots(s, "military", 8)
    m3 = next(c for c in s.camos if c.key == "military:3")
    assert camo_index(s, m3) == 3


def test_military_and_erudit_thumbnails_shared_between_weapons(tmp_path):
    tile = Image.new("RGB", (THUMB, THUMB), (10, 200, 10))
    save_thumbs(tmp_path, "ISO NIGHTSHADE", {("military", 4): tile, ("erudit", 1): tile, ("special", 1): tile})
    assert thumb_path(tmp_path, "REZI 12", "military", 4) is not None
    assert thumb_path(tmp_path, "REZI 12", "erudit", 1) is not None
    assert thumb_path(tmp_path, "REZI 12", "special", 1) is None  # specials differ per weapon


def test_military_thumbnail_saved_before_sharing_is_found_for_other_weapons(tmp_path):
    (tmp_path / "REZI_12").mkdir()
    Image.new("RGB", (THUMB, THUMB)).save(tmp_path / "REZI_12" / "military-2.png")
    assert thumb_path(tmp_path, "ISO NIGHTSHADE", "military", 2) is not None


def test_padlocks_read_without_hovering():
    img, lines = _screen("apparence_full_asphalte")  # ISO: militaries done, Topo noir locked, Rupture/Divergence locked
    tiles = grab_tiles(img, lines)
    assert tiles[("special", 2)].locked is True
    assert tiles[("erudit", 3)].locked is True and tiles[("erudit", 4)].locked is True
    assert all(tiles[("military", n)].locked is False for n in (1, 2, 4, 5, 6, 7, 8))
    # too bright to tell (white padlock on a white/orange tile, Platine in HDR): never a wrong answer
    assert tiles[("special", 3)].locked is None and tiles[("military", 3)].locked is None


def test_tile_locks_update_sheet():
    from trackcod.sheets import apply_tile_locks
    s = new_sheet("REZI 12", "Fusil à pompe")
    seed_specials(s, KnownCamos.load().specials("REZI 12"))
    ensure_slots(s, "erudit", 4)
    sp = sorted((c for c in s.camos if c.section == "special"), key=lambda c: c.order)
    sp[0].state = "done"
    apply_tile_locks(s, {("special", 1): False, ("special", 2): False, ("special", 3): True,
                         ("erudit", 2): None, ("erudit", 3): True})
    assert [c.state for c in sp] == ["done", "unknown", "locked"]  # no padlock seen: left as it was
    er = sorted((c for c in s.camos if c.section == "erudit"), key=lambda c: c.order)
    assert er[1].state == "unknown" and er[2].state == "locked"


def test_tile_locks_ignored_for_unlisted_specials():
    from trackcod.sheets import apply_tile_locks
    s = new_sheet("ARME INCONNUE", "Mitraillette")
    ensure_slots(s, "special", 3)
    apply_tile_locks(s, {("special", 1): True})
    assert all(c.state == "unknown" for c in s.camos if c.section == "special")
