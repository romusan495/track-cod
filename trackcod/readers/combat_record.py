"""Reader for the combat record, multiplayer lifetime view (Carrière > Rapport de combat)."""

import re

from trackcod.model import GlobalStats
from trackcod.readers.common import OcrLine, norm

_INT = re.compile(r"^\d{1,3}(?:[ .,  ]\d{3})+$|^\d+$")
_LABELS = {"games": "PARTIES JOUEES", "wins": "VICTOIRES", "losses": "DEFAITES", "kills": "ELIM.", "deaths": "MORTS"}
_PANEL_MARGIN = 0.02
_VALUE_DX = 0.02
_VALUE_DY = 0.06


def parse_int(text: str) -> int | None:
    text = text.strip()
    if not _INT.match(text):
        return None
    return int(re.sub(r"\D", "", text))


def _panel(lines: list[OcrLine]) -> OcrLine | None:
    return next((l for l in lines if norm(l.text) == "MULTIJOUEUR"), None)


def is_combat_record(lines: list[OcrLine]) -> bool:
    panel = _panel(lines)
    if panel is None:
        return False
    texts = {norm(l.text) for l in lines if l.x >= panel.x - _PANEL_MARGIN}
    return all(label in texts for label in _LABELS.values())


def _value_below(lines: list[OcrLine], label: OcrLine) -> int | None:
    below = [l for l in lines if label.y < l.y < label.y + _VALUE_DY and abs(l.x - label.x) < _VALUE_DX]
    for line in sorted(below, key=lambda l: l.y):
        value = parse_int(line.text)
        if value is not None:
            return value
    return None


def read_combat_record(lines: list[OcrLine]) -> GlobalStats | None:
    if not is_combat_record(lines):
        return None
    panel = _panel(lines)
    values: dict[str, int] = {}
    for field, label_text in _LABELS.items():
        label = next((l for l in lines if norm(l.text) == label_text and l.x >= panel.x - _PANEL_MARGIN), None)
        value = _value_below(lines, label) if label else None
        if value is None:
            return None
        values[field] = value
    return GlobalStats(**values)
