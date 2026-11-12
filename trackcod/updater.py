"""Update check at startup against the GitHub releases of romusan495/track-cod (installed exe only).

An update downloads the new Inno Setup installer and runs it silently: the installer closes Track COD,
replaces only its own install folder (%LOCALAPPDATA%\\Programs\\TrackCOD) and relaunches it. The player's
data in %LOCALAPPDATA%\\TrackCOD is never touched.
"""

import json
import os
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from trackcod import __version__

LATEST_URL = "https://api.github.com/repos/romusan495/track-cod/releases/latest"
ASSET = re.compile(r"^TrackCOD-Setup-[\d.]+\.exe$")
TIMEOUT_S = 5


class UpdateError(Exception):
    pass


@dataclass
class Release:
    version: str
    notes: str
    asset_url: str
    asset_size: int


def parse_version(tag: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """Where the installer puts Track COD (per-user, no admin rights)."""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "TrackCOD"


def running_from_install_dir(executable: Path | str = sys.executable) -> bool:
    try:
        return Path(executable).resolve().parent == install_dir().resolve()
    except OSError:
        return False


def _get(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"TrackCOD/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str) -> dict:
    return json.loads(_get(url, TIMEOUT_S).decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    return _get(url, 120)


def check_latest(current: str, fetch: Callable[[str], dict] = fetch_json) -> Release | None:
    """Newer release with a TrackCOD-Setup-x.y.z.exe asset, else None (also on any error: never blocks start)."""
    try:
        data = fetch(LATEST_URL)
        latest, mine = parse_version(data.get("tag_name", "")), parse_version(current)
        if latest is None or mine is None or latest <= mine:
            return None
        asset = next(a for a in data.get("assets", []) if ASSET.match(a.get("name", "")))
        return Release(".".join(map(str, latest)), data.get("body") or "", asset["browser_download_url"],
                       int(asset["size"]))
    except Exception:
        return None


def download(release: Release, dest_dir: Path, fetch: Callable[[str], bytes] = fetch_bytes) -> Path:
    try:
        data = fetch(release.asset_url)
    except Exception as exc:  # network drop (IncompleteRead is not an OSError), HTTP error...
        raise UpdateError(f"téléchargement impossible : {exc}") from exc
    if len(data) != release.asset_size:
        raise UpdateError("taille du fichier inattendue")
    if not data.startswith(b"MZ"):
        raise UpdateError("fichier de mise à jour invalide")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = Path(dest_dir) / f"TrackCOD-Setup-{release.version}.exe"
        path.write_bytes(data)
    except OSError as exc:
        raise UpdateError(f"écriture impossible : {exc}") from exc
    return path


def installer_command(setup: Path) -> list[str]:
    return [str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART", f"/DIR={install_dir()}"]
