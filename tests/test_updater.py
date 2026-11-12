import http.client
from pathlib import Path

import pytest

from trackcod import paths
from trackcod.updater import (Release, UpdateError, check_latest, download, install_dir, installer_command,
                              parse_version, running_from_install_dir)

EXE = b"MZ" + b"\0" * 64


def _release_json(tag="v2.1.0", name="TrackCOD-Setup-2.1.0.exe", size=66):
    return {"tag_name": tag, "body": "Corrections", "assets": [
        {"name": "TrackCOD-2.1.0.zip", "browser_download_url": "https://x/z.zip", "size": 1},
        {"name": name, "browser_download_url": f"https://x/{name}", "size": size}]}


def test_parse_version():
    assert parse_version("v2.0.1") == (2, 0, 1) and parse_version("2.10.0") == (2, 10, 0)
    assert parse_version("x") is None and parse_version("v2.0") is None


def test_check_latest_newer_installer():
    r = check_latest("2.0.0", lambda url: _release_json())
    assert r == Release("2.1.0", "Corrections", "https://x/TrackCOD-Setup-2.1.0.exe", 66)


def test_check_latest_same_or_older_is_none():
    assert check_latest("2.1.0", lambda url: _release_json()) is None
    assert check_latest("3.0.0", lambda url: _release_json()) is None


def test_check_latest_without_installer_asset_is_none():
    assert check_latest("2.0.0", lambda url: _release_json(name="notes.txt")) is None


def test_check_latest_any_error_is_none():
    def boom(url):
        raise RuntimeError("anything")
    assert check_latest("2.0.0", boom) is None
    assert check_latest("2.0.0", lambda url: {"message": "API rate limit exceeded"}) is None


def test_download_ok(tmp_path):
    path = download(Release("2.1.0", "", "https://x/s.exe", len(EXE)), tmp_path, lambda url: EXE)
    assert path.name == "TrackCOD-Setup-2.1.0.exe" and path.read_bytes() == EXE


def test_download_size_mismatch_raises(tmp_path):
    with pytest.raises(UpdateError):
        download(Release("2.1.0", "", "https://x/s.exe", len(EXE) + 1), tmp_path, lambda url: EXE)


def test_download_not_an_exe_raises(tmp_path):
    with pytest.raises(UpdateError):
        download(Release("2.1.0", "", "https://x/s.exe", 5), tmp_path, lambda url: b"hello")


def test_download_connection_drop_raises_update_error(tmp_path):
    def drop(url):
        raise http.client.IncompleteRead(b"partial")
    with pytest.raises(UpdateError):
        download(Release("2.1.0", "", "https://x/s.exe", 10), tmp_path, drop)


def test_install_dir_is_dedicated_and_not_data_dir():
    d = install_dir()
    assert d.name == "TrackCOD" and d.parent.name == "Programs"
    assert d.resolve() != paths.APP_DIR.resolve() and paths.APP_DIR.resolve() not in d.resolve().parents


def test_running_from_install_dir(tmp_path):
    assert running_from_install_dir(install_dir() / "TrackCOD.exe")
    assert not running_from_install_dir(Path.home() / "Desktop" / "TrackCOD" / "TrackCOD.exe")


def test_installer_command_is_silent_and_targets_install_dir(tmp_path):
    cmd = installer_command(tmp_path / "TrackCOD-Setup-2.1.0.exe")
    assert cmd[0].endswith("TrackCOD-Setup-2.1.0.exe")
    assert "/SILENT" in cmd and "/SUPPRESSMSGBOXES" in cmd and "/CLOSEAPPLICATIONS" in cmd
    assert f'/DIR={install_dir()}' in cmd
