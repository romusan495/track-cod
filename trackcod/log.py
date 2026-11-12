r"""File log for the windowed exe (no console): %LOCALAPPDATA%\TrackCOD\trackcod.log."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(data_dir: Path) -> Path:
    path = Path(data_dir) / "trackcod.log"
    logger = logging.getLogger("trackcod")
    if not any(isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == path for h in logger.handlers):
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return path
