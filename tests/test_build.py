from pathlib import Path

from tools.build import find_iscc


def _touch(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")
    return p


def test_iscc_from_env_variable_first(tmp_path):
    exe = _touch(tmp_path / "custom" / "ISCC.exe")
    _touch(tmp_path / "local" / "Programs" / "Inno Setup 6" / "ISCC.exe")
    assert find_iscc({"ISCC": str(exe), "LOCALAPPDATA": str(tmp_path / "local")}) == exe


def test_iscc_user_install_then_program_files(tmp_path):
    user = _touch(tmp_path / "local" / "Programs" / "Inno Setup 6" / "ISCC.exe")
    assert find_iscc({"LOCALAPPDATA": str(tmp_path / "local")}) == user
    machine = _touch(tmp_path / "pf86" / "Inno Setup 6" / "ISCC.exe")  # GitHub runners (choco)
    assert find_iscc({"ProgramFiles(x86)": str(tmp_path / "pf86")}) == machine
    assert find_iscc({}) is None


def test_the_fine_ocr_is_packaged():
    """numpy was excluded from the build: the fine OCR would have fallen back to the Windows OCR on every PC."""
    from tools.build import EXCLUDED
    assert "numpy" not in EXCLUDED and "onnxruntime" not in EXCLUDED
