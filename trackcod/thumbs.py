"""Camo thumbnails learned from the player's own Apparence screen, stored on their PC (never shipped)."""

import re
from pathlib import Path

from PIL import Image

from trackcod.readers.common import norm


SHARED_SECTIONS = ("military", "erudit")  # same camos on every weapon (told by the player)
SHARED = "_TOUTES_ARMES"


def _dir(root: Path, weapon: str) -> Path:
    return Path(root) / (re.sub(r"[^A-Z0-9]+", "_", norm(weapon)).strip("_") or "ARME")


def save_thumbs(root: Path, weapon: str, tiles: dict[tuple[str, int], Image.Image]) -> int:
    if not tiles:
        return 0
    folder = _dir(root, weapon)
    folder.mkdir(parents=True, exist_ok=True)
    shared = Path(root) / SHARED
    for (section, index), tile in tiles.items():
        tile.save(folder / f"{section}-{index}.png")
        if section in SHARED_SECTIONS:
            shared.mkdir(parents=True, exist_ok=True)
            tile.save(shared / f"{section}-{index}.png")
    return len(tiles)


def thumb_path(root: Path, weapon: str | None, section: str, index: int | None) -> Path | None:
    if not weapon or not index:
        return None
    name = f"{section}-{index}.png"
    own = _dir(root, weapon) / name
    if own.exists():
        return own
    if section not in SHARED_SECTIONS:
        return None
    shared = Path(root) / SHARED / name
    if shared.exists():
        return shared
    return next(iter(sorted(Path(root).glob(f"*/{name}"))), None)  # seen on another weapon before sharing
