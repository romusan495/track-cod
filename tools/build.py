"""Builds dist/TrackCOD/TrackCOD.exe (PyInstaller onedir) and the installer dist/TrackCOD-Setup-<version>.exe.

Run:  python -m tools.build
"""

import shutil
import subprocess
import sys
import os
from pathlib import Path

from trackcod import __version__

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
# Qt modules Track COD never uses (keeps the zip small): web engine, QML/Quick, 3D, multimedia, charts...
EXCLUDED = ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
            "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf",
            "PySide6.QtDesigner", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest", "tkinter",
            "numpy", "pytest"]


def find_iscc(env) -> Path | None:
    """Inno Setup compiler: $ISCC, the per-user install (winget), or Program Files (GitHub runners, choco)."""
    candidates = [Path(env["ISCC"])] if env.get("ISCC") else []
    if env.get("LOCALAPPDATA"):
        candidates.append(Path(env["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    for key in ("ProgramFiles(x86)", "ProgramFiles"):
        if env.get(key):
            candidates.append(Path(env[key]) / "Inno Setup 6" / "ISCC.exe")
    return next((c for c in candidates if c.is_file()), None)


def main() -> int:
    for folder in (DIST / "TrackCOD", ROOT / "build"):
        shutil.rmtree(folder, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--name", "TrackCOD",
           "--distpath", str(DIST), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
           "--collect-all", "winrt",
           "--icon", str(ROOT / "assets" / "trackcod.ico"),
           "--add-data", f"{ROOT / 'trackcod' / 'assets'};trackcod/assets",
           "--add-data", f"{ROOT / 'trackcod' / 'data'};trackcod/data",
           *[arg for mod in EXCLUDED for arg in ("--exclude-module", mod)],
           str(ROOT / "trackcod_app.py")]
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        return 1
    iscc = find_iscc(os.environ)
    if iscc is None:
        print("Inno Setup introuvable : winget install JRSoftware.InnoSetup")
        return 1
    iss = ROOT / "installer" / "trackcod.iss"
    if subprocess.run([str(iscc), f"/DAppVersion={__version__}", f"/DSourceDir={DIST / 'TrackCOD'}", str(iss)],
                      cwd=ROOT).returncode != 0:
        return 1
    setup = DIST / f"TrackCOD-Setup-{__version__}.exe"
    print(f"{setup} ({setup.stat().st_size // (1024 * 1024)} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
