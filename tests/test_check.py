from trackcod import __version__
import os
import subprocess
import sys

import pytest


@pytest.mark.windows
def test_check_exit_code(tmp_path):
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    r = subprocess.run([sys.executable, "-m", "trackcod", "--check"], env=env, cwd=os.getcwd())
    assert r.returncode == 0
    text = (tmp_path / "TrackCOD" / "check.txt").read_text(encoding="utf-8")
    assert "OCR fr-FR : OK" in text and f"Track COD {__version__}" in text
