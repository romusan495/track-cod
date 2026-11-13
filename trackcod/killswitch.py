"""Remote switch read from the site (etat.json): lets the author suspend screen reading on every tracker at once,
for example if Activision objects to the tool, without shipping a new version.

etat.json: {"lecture_active": true|false, "message": "texte affiché aux joueurs"}
"""

from collections.abc import Callable
from dataclasses import dataclass

from trackcod.publish import SITE_URL
from trackcod.updater import fetch_json

STATUS_URL = f"{SITE_URL}/etat.json"
CHECK_EVERY_S = 1800


@dataclass(frozen=True)
class ReadingStatus:
    active: bool
    message: str


def fetch_status(fetch: Callable[[str], object] = fetch_json) -> ReadingStatus | None:
    """The switch's state, or None when it can't be known (offline, bad file): the caller keeps the last one."""
    try:
        data = fetch(STATUS_URL)
    except Exception:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("lecture_active"), bool):
        return None
    message = data.get("message")
    return ReadingStatus(data["lecture_active"], message.strip() if isinstance(message, str) else "")
