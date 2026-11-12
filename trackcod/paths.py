import os
from pathlib import Path

_LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

APP_DIR = _LOCAL / "TrackCOD"


def app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR
