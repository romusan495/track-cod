"""Player level: the badge at the top left of the menus, 'NIV.' with the level just below (e.g. 54).

The prestige number drawn inside the emblem is a stylised digit the Windows OCR can't read: the player sets
it once in the window, and the engine moves it up when the level falls back (a prestige resets the level).
"""

import re

from trackcod.readers.common import OcrLine, norm

MAX_LEVEL = 99


def read_player_level(lines: list[OcrLine]) -> int | None:
    for niv in lines:
        if not (niv.x < 0.2 and niv.y < 0.2 and re.fullmatch(r"NIV\W*", norm(niv.text).strip())):
            continue
        for line in lines:
            if 0 < line.y - niv.y < 0.03 and abs(line.x - niv.x) < 0.012 and re.fullmatch(r"\d{1,2}", line.text.strip()):
                level = int(line.text.strip())
                if 1 <= level <= MAX_LEVEL:
                    return level
    return None
