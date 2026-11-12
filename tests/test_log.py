import logging

from trackcod.log import setup_logging


def test_setup_logging_writes_file(tmp_path):
    path = setup_logging(tmp_path)
    logging.getLogger("trackcod").error("boom %s", 1)
    for h in logging.getLogger("trackcod").handlers:
        h.flush()
    assert path == tmp_path / "trackcod.log" and "boom 1" in path.read_text(encoding="utf-8")
