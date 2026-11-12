"""Main window (mockup A: single narrow column, everything visible)."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from trackcod.ui.viewmodel import RowView, View

BG, PANEL, LINE, TXT, MUTED, ACCENT, OK, WARN, BLUE = (
    "#0d0f12", "#1d222a", "#2a313b", "#e7ebf0", "#8a94a3", "#f2b33d", "#4fc27a", "#e0703c", "#4c9be8")

STYLE = f"""
QMainWindow, QWidget#root {{ background: {BG}; }}
QLabel {{ color: {TXT}; font-family: 'Segoe UI'; font-size: 13px; }}
QLabel[role="muted"] {{ color: {MUTED}; font-size: 11px; }}
QLabel[role="section"] {{ color: {MUTED}; font-size: 11px; letter-spacing: 1px; margin-top: 10px; }}
QLabel[role="tag"] {{ color: {ACCENT}; background: #2b2412; border-radius: 4px; padding: 1px 6px; font-size: 10px; }}
QLabel[role="notice"] {{ color: {WARN}; font-size: 11px; }}
QPushButton#weapon {{ color: {TXT}; background: transparent; border: none; font-size: 19px; font-weight: 700;
                      text-align: left; padding: 0; }}
QPushButton#weapon:hover {{ color: {ACCENT}; }}
QPushButton#player {{ color: {ACCENT}; background: transparent; border: none; font-size: 11px; }}
QPushButton#player:hover {{ text-decoration: underline; }}
QFrame#current {{ background: {PANEL}; border-left: 3px solid {ACCENT}; border-radius: 6px; }}
QFrame#stat {{ background: {PANEL}; border-radius: 6px; }}
QCheckBox {{ color: {MUTED}; font-size: 11px; }}
QFrame#meta {{ background: {PANEL}; border-left: 3px solid {BLUE}; border-radius: 6px; }}
QComboBox {{ color: {TXT}; background: {BG}; border: 1px solid {LINE}; border-radius: 4px; padding: 2px 6px; }}
QScrollArea {{ border: none; background: {BG}; }}
"""

ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "icon.png"


def app_icon() -> QIcon:
    return QIcon(str(ICON_PATH))


MILITARY_COLORS = {"done": OK, "now": ACCENT, "todo": LINE, "unknown": "#3a3f47"}


def _label(text: str, role: str | None = None, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    lab.setWordWrap(wrap)
    return lab


def _row(r: RowView) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 3, 0, 3)
    icon = _label(r.icon)
    icon.setFixedWidth(20)
    color = {"✔": OK, "▶": ACCENT, "🔒": MUTED, "?": MUTED}.get(r.icon, TXT)
    icon.setStyleSheet(f"color: {color};")
    name = _label(r.name, wrap=True)
    name.setStyleSheet("font-weight: 600;")
    name.setFixedWidth(110)
    detail = _label(r.detail, "muted", wrap=True)
    lay.addWidget(icon)
    lay.addWidget(name)
    lay.addWidget(detail, 1)
    if r.counter:
        lay.addWidget(_label(r.counter))
    return w


def _stats_grid(rows: list[tuple[str, str]], columns: int = 4) -> QWidget:
    w = QWidget()
    grid = QGridLayout(w)
    grid.setContentsMargins(0, 4, 0, 0)
    grid.setSpacing(6)
    for i, (label, value) in enumerate(rows):
        box = QFrame()
        box.setObjectName("stat")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 6, 8, 6)
        v = _label(value)
        v.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay.addWidget(v)
        lay.addWidget(_label(label.upper(), "muted"))
        grid.addWidget(box, i // columns, i % columns)
    return w


class MainWindow(QMainWindow):
    state_changed = Signal()
    update_available = Signal(object)   # trackcod.updater.Release, emitted from the update-check thread
    update_downloaded = Signal(object)  # installer Path, or the Exception that stopped the download

    def __init__(self, weapons: list[str], on_weapon_chosen: Callable[[str], None],
                 on_always_on_top: Callable[[bool], None], always_on_top: bool = False,
                 on_build_chosen: Callable[[str], None] = lambda style: None,
                 on_camo_answer: Callable[[str, bool], None] = lambda key, has: None,
                 on_prestige: Callable[[int], None] = lambda prestige: None,
                 on_site_change: Callable[[bool, str, bool], None] = lambda published, pseudo, camos: None):
        super().__init__()
        self.setWindowTitle("Track COD")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(STYLE)
        self.resize(360, 900)
        self._weapons = weapons  # list, or a callable returning the current list (site + learned weapons)
        self._on_weapon_chosen = on_weapon_chosen
        self._on_always_on_top = on_always_on_top
        self._on_build_chosen = on_build_chosen
        self._on_camo_answer = on_camo_answer
        self._on_prestige = on_prestige
        self._on_site_change = on_site_change
        self._site_draft = ""      # pseudo being typed: survives the re-renders
        self._site_hint = ""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)
        self._root = QWidget()
        self._root.setObjectName("root")
        scroll.setWidget(self._root)
        self._layout = QVBoxLayout(self._root)
        self._layout.setContentsMargins(14, 10, 14, 14)
        self._always_on_top = always_on_top
        self._apply_on_top(always_on_top)

    def _apply_on_top(self, on: bool) -> None:
        self._always_on_top = on
        was_visible = self.isVisible()  # changing a window flag hides the window
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if was_visible:
            self.show()

    def _toggle_on_top(self, on: bool) -> None:
        self._apply_on_top(on)
        self._on_always_on_top(on)

    def weapon_names(self) -> list[str]:
        return sorted(self._weapons() if callable(self._weapons) else self._weapons)

    def accept_weapon_choice(self, name: str) -> None:
        """Any typed name is accepted: offline, the list may be empty or miss a new weapon."""
        name = (name or "").strip()
        if name:
            self._on_weapon_chosen(name)

    def _choose_weapon(self) -> None:
        name, ok = QInputDialog.getItem(self, "Arme", "Arme jouée (choisis ou tape son nom) :",
                                        self.weapon_names(), 0, True)
        if ok:
            self.accept_weapon_choice(name)

    def _meta_box(self, meta) -> QFrame:
        box = QFrame()
        box.setObjectName("meta")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 8, 12, 8)
        head = QHBoxLayout()
        k = _label("CLASSE MÉTA")
        k.setStyleSheet(f"color: {BLUE}; font-size: 11px;")
        head.addWidget(k)
        head.addStretch(1)
        if meta.builds:
            combo = QComboBox()
            for style, label in meta.builds:
                combo.addItem(label, style)
            combo.setCurrentIndex([s for s, _ in meta.builds].index(meta.selected))
            combo.currentIndexChanged.connect(lambda i, c=combo: self._on_build_chosen(c.itemData(i)))
            head.addWidget(combo)
        hw = QWidget()
        hw.setLayout(head)
        lay.addWidget(hw)
        if meta.header:
            lay.addWidget(_label(meta.header, "muted"))
        if meta.note:
            lay.addWidget(_label(meta.note, "muted"))
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setVerticalSpacing(3)
        for i, (slot, name, level) in enumerate(meta.rows):
            grid.addWidget(_label(slot, "muted"), i, 0)
            n = _label(name)
            n.setStyleSheet("font-weight: 600;")
            grid.addWidget(n, i, 1)
            grid.addWidget(_label(level, "muted"), i, 2)
        gw = QWidget()
        gw.setLayout(grid)
        lay.addWidget(gw)
        return box

    def _site_box(self, site, add) -> None:
        add(_label("SITE", "section"))
        pseudo = QLineEdit(site.pseudo if site.published else (self._site_draft or site.pseudo))
        pseudo.setObjectName("site_pseudo")
        pseudo.setMaxLength(20)
        pseudo.setPlaceholderText("Ton pseudo sur le site")
        pseudo.setEnabled(not site.published)  # to change it: uncheck, edit, check again
        pseudo.textChanged.connect(lambda t: setattr(self, "_site_draft", t))
        publish = QCheckBox("Publier mes stats sur le site")
        publish.setChecked(site.published)
        camos = QCheckBox("Montrer ma maîtrise des camos")
        camos.setChecked(site.show_camos)

        def changed(*_):
            name = pseudo.text().strip()
            if publish.isChecked() and len(name) < 3:
                self._site_hint = "choisis un pseudo d'abord (3 à 20 caractères)"
                publish.blockSignals(True)  # undoing the tick is not an opt-out
                publish.setChecked(False)
                publish.blockSignals(False)
                hint.setText(self._site_hint)
                return
            self._site_hint = ""
            self._on_site_change(publish.isChecked(), name, camos.isChecked())

        publish.toggled.connect(changed)
        camos.toggled.connect(changed)
        add(pseudo)
        add(publish)
        add(camos)
        hint = _label(self._site_hint, "notice", wrap=True)
        add(hint)
        if site.url:
            leave = QPushButton("Me retirer du site")
            leave.setCursor(Qt.PointingHandCursor)
            leave.clicked.connect(lambda: self._on_site_change(False, pseudo.text().strip(), camos.isChecked()))
            add(leave)
            link = QPushButton("Voir ma page")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(site.url)))
            add(link)
        add(_label("Tes stats sont publiques sous ce pseudo. Décoche pour tout retirer du site.", "muted", wrap=True))

    def _ask_prestige(self) -> None:
        value, ok = QInputDialog.getInt(self, "Prestige", "Ton prestige actuel :", 0, 0, 99)
        if ok:
            self._on_prestige(value)

    def render(self, view: View) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        add = self._layout.addWidget

        top = QHBoxLayout()
        top.addWidget(_label(view.header, "muted"))
        top.addStretch(1)
        if view.player:
            player = QPushButton(view.player)
            player.setObjectName("player")
            player.setCursor(Qt.PointingHandCursor)
            player.setToolTip("Clique pour régler ton prestige (il monte ensuite tout seul)")
            player.clicked.connect(self._ask_prestige)
            top.addWidget(player)
        bar = QWidget()
        bar.setLayout(top)
        add(bar)
        on_top = QCheckBox("Toujours au premier plan")
        on_top.setChecked(self._always_on_top)
        on_top.toggled.connect(self._toggle_on_top)
        add(on_top)

        head = QHBoxLayout()
        weapon = QPushButton(view.weapon.upper())
        weapon.setObjectName("weapon")
        weapon.setCursor(Qt.PointingHandCursor)
        weapon.setToolTip("Cliquer pour changer d'arme")
        weapon.clicked.connect(self._choose_weapon)
        head.addWidget(weapon, 1)
        if view.category:
            head.addWidget(_label(view.category, "tag"))
        hw = QWidget()
        hw.setLayout(head)
        add(hw)
        if view.sheet_note:
            add(_label(view.sheet_note, "notice"))
        elif view.unverified:
            add(_label("fiche non vérifiée · passe dans Apparence", "notice"))

        if view.meta is not None:
            add(self._meta_box(view.meta))

        if view.current is not None:
            box = QFrame()
            box.setObjectName("current")
            row = QHBoxLayout(box)
            row.setContentsMargins(12, 10, 12, 10)
            lay = QVBoxLayout()
            row.addLayout(lay, 1)
            k = _label(f"CAMO À FAIRE · {view.current.section_label.upper()}")
            k.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")
            lay.addWidget(k)
            t = _label(view.current.name)
            t.setStyleSheet("font-size: 17px; font-weight: 700;")
            lay.addWidget(t)
            lay.addWidget(_label(view.current.challenge, wrap=True))
            lay.addWidget(_label(view.current.counter, "muted"))
            if view.current.ask_key:
                ask = QHBoxLayout()
                ask.addWidget(_label("Tu l'as déjà ?", "notice"))
                for text, has in (("Oui", True), ("Non", False)):
                    b = QPushButton(text)
                    b.setCursor(Qt.PointingHandCursor)
                    b.clicked.connect(lambda _=False, k=view.current.ask_key, h=has: self._on_camo_answer(k, h))
                    ask.addWidget(b)
                ask.addStretch(1)
                lay.addLayout(ask)
            if view.current.thumb:
                pix = QPixmap(view.current.thumb)
                if not pix.isNull():
                    img = QLabel()
                    img.setObjectName("thumb")
                    img.setPixmap(pix.scaled(84, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    row.addWidget(img, 0, Qt.AlignVCenter)
            add(box)

        if view.military:
            done = sum(1 for m in view.military if m == "done")
            add(_label(f"MILITAIRES · {done}/{len(view.military)}", "section"))
            dots = QHBoxLayout()
            dots.setSpacing(4)
            for m in view.military:
                d = QFrame()
                d.setFixedHeight(8)
                d.setStyleSheet(f"background: {MILITARY_COLORS[m]}; border-radius: 2px;")
                dots.addWidget(d)
            dw = QWidget()
            dw.setLayout(dots)
            add(dw)
        if view.specials:
            add(_label("SPÉCIAUX", "section"))
            for r in view.specials:
                add(_row(r))
        if view.erudit:
            add(_label("ÉRUDIT", "section"))
            for r in view.erudit:
                add(_row(r))

        add(_label("DERNIÈRE PARTIE", "section"))
        if view.last_match:
            add(_label(view.last_match_info, "muted", wrap=True))
            add(_stats_grid(view.last_match))
        else:
            add(_label("aucune partie lue pour l'instant", "muted"))

        add(_label("GLOBAL", "section"))
        if view.global_rows:
            add(_stats_grid(view.global_rows))
        add(_label(view.global_note, "muted"))

        if view.mastery:
            add(_label("MAÎTRISE", "section"))
            add(_stats_grid([(label, value) for label, value in view.mastery], columns=2))
            add(_label(view.mastery_note, "muted"))

        if view.site is not None:
            self._site_box(view.site, add)

        for n in view.notices:
            add(_label(n, "notice", wrap=True))
        self._layout.addStretch(1)
