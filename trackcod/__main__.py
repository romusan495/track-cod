"""Entry point: python -m trackcod [--demo | --check]"""

import argparse
import sys
import threading
import time

from PySide6.QtWidgets import QApplication, QMessageBox

from trackcod.paths import app_dir

OCR_HELP = ("La reconnaissance de texte française de Windows est introuvable.\n\n"
            "Installe-la : Paramètres > Heure et langue > Langue et région > Français > Options "
            "> Reconnaissance optique de caractères, puis relance Track COD.")


def single_instance(data_dir):
    """Lock held for the app's lifetime; None if another Track COD is already running."""
    from PySide6.QtCore import QLockFile

    lock = QLockFile(str(data_dir / "trackcod.lock"))
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(0) else None


def _demo_state():
    from trackcod.model import AppState, GlobalStats, MatchStats
    from trackcod.sheets import ApparenceCamo, ApparenceReading, apply_apparence, new_sheet

    now = time.time()
    weapon = "ISO NIGHTSHADE"
    s = AppState(weapon=weapon, phase="in_match")
    sheet = new_sheet(weapon, "Mitraillette")
    apply_apparence(sheet, ApparenceReading([
        ApparenceCamo("ASPHALTE", "special", None, True, None,
                      "Faites 50 éliminations de joueurs en regardant dans le viseur.", (46, 50), False, 1,
                      name_reads=["ASPHALTE", "ASPHALTE"]),
        ApparenceCamo("TOPO NOIR", "special", None, True, None, None, None, False, 2, name_reads=["TOPO NOIR"]),
        ApparenceCamo("MARRON", "special", "Obtenez tous les camouflages militaires", False, None, None, None,
                      True, 3, name_reads=["MARRON", "MARRON"])],
        {"military": (8, 8), "special": (0, 3), "erudit": (0, 4)}, at=now - 7200))
    s.sheets[weapon] = sheet
    s.last_match = MatchStats(now, 13, 12, 1595, "win", "MATCH À MORT PAR ÉQUIPE HARDCORE", "LITHIUM", weapon, "demo")
    s.global_stats = GlobalStats(kills=2092, deaths=2342, wins=70, losses=57, games=127,
                                 calibrated_at=now - 3600, matches_since_calibration=1)
    return s


def run_check() -> int:
    """Startup diagnostics for a player's machine (the windowed exe has no console)."""
    from trackcod import __version__
    from trackcod.ocr.engine import ocr_available

    lines = [f"Track COD {__version__}"]
    try:
        data = app_dir()
        lines.append(f"Dossier de données : OK ({data})")
    except OSError as exc:
        lines.append(f"Dossier de données : ERREUR {exc}")
        return 3
    ok = ocr_available()
    lines.append("OCR fr-FR : OK" if ok else "OCR fr-FR : ABSENT")
    from trackcod.ocr.paddle import available
    lines.append("OCR fin : OK" if available() else "OCR fin : ABSENT (OCR Windows seul)")
    (data / "check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 2


UPDATE_FAILED = "La mise à jour a échoué, Track COD continue avec la version actuelle."
NOT_INSTALLED = ("Une nouvelle version {v} est disponible.\n\nPour recevoir les mises à jour automatiquement, "
                 "installe Track COD avec l'installateur (TrackCOD-Setup) depuis la page GitHub du projet.")


def offer_update(window, release, on_ready) -> None:
    """Ask, then download the installer off the UI thread behind a progress dialog.
    on_ready(setup_path) is called on the UI thread when the installer is ready to run."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QProgressDialog

    from trackcod.updater import download, running_from_install_dir

    if not running_from_install_dir():
        QMessageBox.information(window, "Track COD", NOT_INSTALLED.format(v=release.version))
        return
    notes = "\n\n" + release.notes.strip() if release.notes.strip() else ""
    answer = QMessageBox.question(window, "Track COD",
                                  f"Nouvelle version {release.version} disponible. Mettre à jour maintenant ?{notes}",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if answer != QMessageBox.Yes:
        return
    progress = QProgressDialog("Téléchargement de la mise à jour…", None, 0, 0, window)
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.show()

    def finished(result) -> None:
        progress.close()
        if isinstance(result, Exception):
            QMessageBox.warning(window, "Track COD", UPDATE_FAILED)
        else:
            on_ready(result)

    window.update_downloaded.connect(finished)

    def work() -> None:
        try:
            result = download(release, Path(tempfile.gettempdir()))
        except Exception as exc:  # any failure leaves the current app untouched
            result = exc
        window.update_downloaded.emit(result)

    threading.Thread(target=work, daemon=True).start()


def _install_error_hooks() -> None:
    """Windowed exe has no console: log every unexpected error and tell the player where the log is."""
    import logging

    from trackcod.log import setup_logging

    log_path = setup_logging(app_dir())
    log = logging.getLogger("trackcod")

    def on_error(exc_type, exc, tb) -> None:
        log.error("erreur inattendue", exc_info=(exc_type, exc, tb))
        if QApplication.instance() is not None and threading.current_thread() is threading.main_thread():
            QMessageBox.warning(None, "Track COD", f"Erreur inattendue : {exc}\n\nDétails dans {log_path}")

    sys.excepthook = on_error
    threading.excepthook = lambda a: log.error("erreur dans %s", a.thread, exc_info=(a.exc_type, a.exc_value,
                                                                                      a.exc_traceback))


def main() -> int:
    parser = argparse.ArgumentParser(prog="trackcod")
    parser.add_argument("--demo", action="store_true", help="affiche des données d'exemple, sans lire le jeu")
    parser.add_argument("--check", action="store_true", help="vérifie la machine et écrit check.txt")
    args = parser.parse_args()
    if args.check:
        return run_check()

    app = QApplication(sys.argv)
    _install_error_hooks()
    from trackcod.ui.window import app_icon
    app.setWindowIcon(app_icon())

    from trackcod.ocr.engine import ocr_available
    if not args.demo and not ocr_available():
        QMessageBox.critical(None, "Track COD", OCR_HELP)
        return 1

    from trackcod.engine import Engine
    from trackcod.meta import META_URL, MetaSource
    from trackcod.store import load_state, save_state
    from trackcod.ui.viewmodel import build_view
    from trackcod.ui.window import MainWindow
    from trackcod.weapons import WeaponRegistry

    data = app_dir()
    instance_lock = single_instance(data)
    if instance_lock is None and not args.demo:
        QMessageBox.information(None, "Track COD", "Track COD est déjà lancé.")
        return 0
    state_path = data / "state.json"
    state = _demo_state() if args.demo else load_state(state_path)

    meta_source = MetaSource(META_URL, data / "meta-cache.json")
    meta_holder = {"meta": meta_source.cached()}
    registry = WeaponRegistry.from_meta(meta_holder["meta"], state.learned_weapons)

    from trackcod.publish import SITE_URL, Publisher, SiteClient
    from trackcod.store import read_matches, save_state
    from trackcod.ui.viewmodel import _mastery

    def site_notice(text: str) -> None:  # called from the publisher thread
        if text not in state.notices:
            state.notices.append(text)
            del state.notices[:-5]
        window.state_changed.emit()

    def site_saved() -> None:
        if engine is not None:
            engine.save()
        elif not args.demo:
            save_state(state, state_path)
        window.state_changed.emit()

    publisher = Publisher(state, SiteClient(SITE_URL), site_notice,
                          recent_matches=lambda: read_matches(data / "matches.jsonl", 5),
                          mastery=lambda: _mastery(state, meta_holder["meta"])[0], saved=site_saved)

    engine = None
    if not args.demo:
        from trackcod.frames import live_frame_source, tiles
        engine = Engine(registry, state, state_path, data / "matches.jsonl", live_frame_source,
                        tile_source=tiles.take, thumbs_dir=data / "vignettes",
                        on_stats_changed=publisher.publish_async)

    def on_weapon(name: str) -> None:
        if engine is not None:
            engine.set_weapon(name)
        else:
            state.weapon = name
        window.state_changed.emit()

    def on_top(on: bool) -> None:
        state.always_on_top = on

    def on_compact(on: bool) -> None:
        state.compact = on
        window.state_changed.emit()

    def on_build(style: str) -> None:
        if state.weapon:
            state.meta_builds[state.weapon] = style
            window.state_changed.emit()

    def on_prestige(value: int) -> None:
        if engine is not None:
            engine.set_prestige(value)
        else:
            state.prestige = value
        window.state_changed.emit()

    def on_answer(key: str, has: bool) -> None:
        if engine is not None:
            engine.answer_camo(key, has)
        window.state_changed.emit()

    def on_site_change(published: bool, pseudo: str, show_camos: bool) -> None:
        was = state.site_publish
        state.site_pseudo, state.site_show_camos, state.site_publish = pseudo, show_camos, published
        if args.demo:
            pass  # the demo never talks to the site
        elif published:
            publisher.publish_async()
        elif was:
            publisher.unpublish_async()
        site_saved()

    def view():
        return build_view(state, time.time(), meta=meta_holder["meta"], thumbs_dir=data / "vignettes",
                          history=read_matches(data / "matches.jsonl", 20))

    window = MainWindow(lambda: [w.name for w in registry.weapons()], on_weapon, on_top, state.always_on_top,
                        on_build_chosen=on_build, on_camo_answer=on_answer,
                        on_prestige=on_prestige, on_site_change=on_site_change,
                        on_league=lambda action, value: publisher.league_async(action, value),
                        on_compact=on_compact)
    window.state_changed.connect(lambda: window.render(view()))
    if state.window_geometry:
        window.setGeometry(*state.window_geometry)
    if state.compact_geometry:
        window.compact_window.move(*state.compact_geometry[:2])
    window.render(view())
    if not state.compact:
        window.show()
    if not args.demo:
        publisher.publish_async()  # sends the stats, or finishes a removal that failed last time

    stop = threading.Event()

    def meta_loop() -> None:  # network off the UI thread; MetaSource caches 1 day and backs off on failure
        while not stop.is_set():
            meta = meta_source.get()
            if meta is not None and (meta is not meta_holder["meta"] or meta.stale):
                meta_holder["meta"] = meta
                if engine is not None:
                    with engine.lock:
                        registry.update_site(meta)
                else:
                    registry.update_site(meta)
                window.state_changed.emit()
            stop.wait(600)

    threading.Thread(target=meta_loop, daemon=True).start()

    def switch_loop() -> None:  # remote switch on the site: suspend screen reading on every tracker if needed
        from trackcod.killswitch import CHECK_EVERY_S, fetch_status
        while not stop.is_set():
            if engine is not None:
                engine.apply_status(fetch_status())
                window.state_changed.emit()
            stop.wait(CHECK_EVERY_S)

    threading.Thread(target=switch_loop, daemon=True).start()

    from trackcod import __version__
    from trackcod.updater import check_latest, is_frozen

    def run_installer(setup) -> None:
        import subprocess

        from trackcod.updater import installer_command
        try:
            subprocess.Popen(installer_command(setup), creationflags=0x00000008)  # DETACHED_PROCESS
        except OSError:
            QMessageBox.warning(window, "Track COD", UPDATE_FAILED)
            return
        app.quit()  # the installer closes/replaces Track COD and relaunches it

    def on_update(release) -> None:
        offer_update(window, release, run_installer)

    window.update_available.connect(on_update)
    if is_frozen() and not args.demo:  # only the packaged exe updates itself
        threading.Thread(target=lambda: (lambda r: r and window.update_available.emit(r))(check_latest(__version__)),
                         daemon=True).start()

    worker = None
    if engine is not None:
        worker = threading.Thread(target=engine.run, args=(stop, lambda _s: window.state_changed.emit()),
                                  daemon=True)
        worker.start()

    # refresh "lu il y a ..." once a minute even without new data
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(window.state_changed.emit)
    timer.start(60_000)

    code = app.exec()
    stop.set()
    if worker is not None:
        worker.join(timeout=3)
    if not args.demo:
        g = window.geometry()
        state.window_geometry = (g.x(), g.y(), g.width(), g.height())
        c = window.compact_window.geometry()
        state.compact_geometry = (c.x(), c.y(), c.width(), c.height())
        if engine is not None:
            with engine.lock:
                state.learned_weapons = list(registry.learned)
                save_state(state, state_path)
        else:
            save_state(state, state_path)
    # free the windows while QApplication exists: freed by Python after it, Qt aborts the process on quit
    from PySide6.QtCore import QCoreApplication, QEvent
    for w in app.topLevelWidgets():
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return code


if __name__ == "__main__":
    sys.exit(main())
