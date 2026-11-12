"""Finds the foreground game window and grabs (parts of) it. Screen capture only."""

import ctypes
from ctypes import wintypes

import mss
from PIL import Image

GAME_TITLE = "Call of Duty"
_user32 = ctypes.windll.user32
try:
    _user32.SetProcessDPIAware()
except Exception:
    pass


_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def is_game_title(title: str) -> bool:
    """The game pads its title with zero-width spaces between letters."""
    return GAME_TITLE.lower() in (title or "").translate(_INVISIBLE).lower()


def find_game_window() -> tuple[int, int, int, int] | None:
    """Screen rect (left, top, width, height) of the foreground game window, else None."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = _user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    if not is_game_title(buf.value):
        return None
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return rect.left, rect.top, width, height


def grab(rect: tuple[int, int, int, int],
         region: tuple[float, float, float, float] | None = None) -> Image.Image:
    left, top, width, height = rect
    if region is not None:
        rx, ry, rw, rh = region
        left, top = left + int(rx * width), top + int(ry * height)
        width, height = max(1, int(rw * width)), max(1, int(rh * height))
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
