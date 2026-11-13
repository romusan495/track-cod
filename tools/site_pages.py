"""Static SEO pages for the stats site: one page per MW4 weapon (special camos in order with their challenges, Érudit
challenges and unlock rules of its category), an index of all weapons, and the sitemap. Text only: no game image.

Run: .venv/Scripts/python -m tools.site_pages   (writes into site/)
"""

from __future__ import annotations

import html
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from trackcod.known_camos import KnownCamos, KnownSpecial
from trackcod.sheets import ERUDIT_CHALLENGES, PLATINE_GOAL

SITE = "https://track-cod.romusangames.workers.dev"
DOWNLOAD_URL = "https://github.com/romusan495/track-cod/releases/latest"
STATIC_PAGES = [("/", "daily", "1.0"), ("/armes", "weekly", "0.8"), ("/transparence.html", "monthly", "0.6")]
CATEGORY_ORDER = ["Fusil d'assaut", "Mitraillette", "Fusil à pompe", "Mitrailleuse", "Fusil tactique",
                  "Fusil de précision", "Pistolet", "Lanceur", "Corps à corps"]
EXTRA_CATEGORY = {"LAUNCHER": "Lanceur", "MELEE": "Corps à corps"}
# Plural used in the Platine rule ("Or sur 2 fusils à pompe").
PLURAL = {"Fusil d'assaut": "fusils d'assaut", "Mitraillette": "mitraillettes", "Fusil à pompe": "fusils à pompe",
          "Mitrailleuse": "mitrailleuses", "Fusil tactique": "fusils tactiques",
          "Fusil de précision": "fusils de précision", "Pistolet": "pistolets", "Lanceur": "lanceurs"}


@dataclass
class Weapon:
    name: str
    category: str
    specials: list[KnownSpecial]


def slug(name: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")


def e(s: str) -> str:
    return html.escape(s, quote=False).replace('"', "&quot;")


def _head(title: str, description: str, path: str) -> str:
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Track COD">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:image" content="{SITE}/og-banner.jpg">
<link rel="icon" type="image/png" sizes="64x64" href="/favicon.png">
<meta name="theme-color" content="#0e1116">
<link rel="preload" href="/fonts/chakra-700.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<main class="shell">
  <header class="topbar">
    <a class="brand" href="/"><span class="mark" aria-hidden="true"></span><span><b>TRACK COD</b><small>MW4 · stats des joueurs</small></span></a>
    <a class="dl" href="{DOWNLOAD_URL}" data-download>⬇ Télécharger</a>
  </header>
"""


_FOOT = """  <nav class="foot-links"><a href="/">Classement</a> · <a href="/armes">Camos des armes</a> · <a href="/transparence.html">Transparence</a> · <a href="/mentions-legales.html">Mentions légales</a> · <a href="/confidentialite.html">Confidentialité</a></nav>
</main>
<script type="module" src="/app.js"></script>
</body>
</html>
"""


def _tracker_pitch(name: str) -> str:
    return (f'<h2>Suivre ta progression</h2>\n      <p><strong>Track COD</strong> est un traqueur gratuit pour PC qui lit '
            f'ton écran Apparence et tes fins de partie, et te dit quel camo viser ensuite sur ton {e(name)} et combien '
            f'il t\'en reste. Rien n\'est lu dans la mémoire du jeu (<a class="link" href="/transparence.html">'
            f'ce qu\'il fait, et ne fait jamais</a>).</p>\n'
            f'      <p><a class="dl big" href="{DOWNLOAD_URL}" data-download>⬇ Télécharger Track COD</a></p>')


def _erudit(category: str) -> str:
    challenges = ERUDIT_CHALLENGES.get(category)
    if not challenges:
        return ("<h2>Camos Érudit</h2>\n      <p>Les défis Érudit de cette catégorie sont <strong>à venir</strong> : "
                "ils seront ajoutés dès qu'ils sont connus.</p>")
    gold, platine, rupture = (e(c) for c in challenges)
    goal = PLATINE_GOAL.get(category)
    plat_rule = (f"il faut aussi l'Or sur {goal} {PLURAL.get(category, category.lower())}" if goal
                 else "il faut aussi l'Or sur d'autres armes de la catégorie")
    return f"""<h2>Camos Érudit ({e(category.lower())})</h2>
      <ol class="check">
        <li><strong>Or</strong> : {gold}. Se débloque une fois les 3 camos spéciaux obtenus.</li>
        <li><strong>Platine</strong> : {platine}. En plus de l'Or sur cette arme, {e(plat_rule)}.</li>
        <li><strong>Rupture harmonique</strong> : {rupture}. Demande 33 armes en Platine, toutes catégories confondues.</li>
        <li><strong>Divergence</strong> : débloqué automatiquement après 33 armes en Rupture harmonique.</li>
      </ol>"""


def weapon_page(w: Weapon) -> str:
    title = f"Camos {w.name} MW4 : spéciaux, défis et Érudit · Track COD"
    first = w.specials[0].name_fr if w.specials else ""
    description = (f"Tous les camos {w.name} ({w.category.lower()}) dans Call of Duty MW4 : les camos spéciaux "
                   f"dans l'ordre{' (' + first + '…)' if first else ''}, leurs défis en français, puis Or, Platine, "
                   f"Rupture harmonique et Divergence.")
    specials = "\n".join(f"        <li><strong>{e(s.name_fr)}</strong> : {e(s.challenge_fr)}</li>" for s in w.specials)
    return _head(title, description, f"/armes/{slug(w.name)}") + f"""  <a class="back" href="/armes">← Toutes les armes</a>

  <div class="layout doc">
    <section class="panel">
      <div class="panel-head"><h1>Camos {e(w.name)} (MW4)</h1></div>
      <p class="kicker">{e(w.category)}</p>
      <p>{e(w.name)} : après les camos militaires, {len(w.specials)} camos spéciaux, à débloquer dans cet ordre. Les défis sont donnés tels qu'ils apparaissent dans le jeu en français.</p>

      <h2>Camos spéciaux, dans l'ordre</h2>
      <ol class="check">
{specials}
      </ol>

      {_erudit(w.category)}

      {_tracker_pitch(w.name)}

      <p class="note">Track COD est un projet de fan, sans lien avec Activision. Les noms des camos et des défis appartiennent à Activision.</p>
    </section>
  </div>
""" + _FOOT


def index_page(weapons: list[Weapon]) -> str:
    groups = []
    cats = sorted({w.category for w in weapons}, key=lambda c: (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99, c))
    for cat in cats:
        items = "\n".join(f'          <li><a class="link" href="/armes/{slug(w.name)}">{e(w.name)}</a></li>'
                          for w in sorted((w for w in weapons if w.category == cat), key=lambda w: w.name.lower()))
        groups.append(f"      <h2>{e(cat)}</h2>\n        <ul>\n{items}\n        </ul>")
    body = "\n".join(groups)
    title = "Camos MW4 : toutes les armes, défis spéciaux et Érudit · Track COD"
    description = (f"Les camos des {len(weapons)} armes de Call of Duty MW4 : camos spéciaux dans l'ordre, défis en "
                   "français et règles Or, Platine, Rupture harmonique et Divergence par catégorie.")
    return _head(title, description, "/armes") + f"""  <a class="back" href="/">← Classement</a>

  <div class="layout doc">
    <section class="panel">
      <div class="panel-head"><h1>Camos MW4 : toutes les armes</h1></div>
      <p>Choisis une arme pour voir ses camos spéciaux dans l'ordre, leurs défis en français, et ce qu'il faut pour l'Or, le Platine, la Rupture harmonique et la Divergence.</p>
{body}
    </section>
  </div>
""" + _FOOT


def sitemap(weapons: list[Weapon]) -> str:
    rows = [f"  <url><loc>{SITE}{p}</loc><changefreq>{f}</changefreq><priority>{pr}</priority></url>"
            for p, f, pr in STATIC_PAGES]
    rows += [f"  <url><loc>{SITE}/armes/{slug(w.name)}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>"
             for w in sorted(weapons, key=lambda w: slug(w.name))]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def build_pages(weapons: list[Weapon], site: Path) -> int:
    out = Path(site) / "armes"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.html"):
        old.unlink()
    for w in weapons:
        (out / f"{slug(w.name)}.html").write_text(weapon_page(w), encoding="utf-8", newline="\n")
    (Path(site) / "armes.html").write_text(index_page(weapons), encoding="utf-8", newline="\n")
    (Path(site) / "sitemap.xml").write_text(sitemap(weapons), encoding="utf-8", newline="\n")
    return len(weapons)


def load_weapons() -> list[Weapon]:
    from trackcod.meta import MetaSource
    cache = Path(os.environ["LOCALAPPDATA"]) / "TrackCOD" / "meta-cache.json"
    meta = MetaSource("", cache).cached()
    if meta is None:
        raise SystemExit(f"cache méta introuvable : {cache}")
    known = KnownCamos.load()
    weapons = [Weapon(m.name, EXTRA_CATEGORY.get(m.category, m.category), known.specials(m.name)) for m in meta.weapons]
    return [w for w in weapons if w.specials]


if __name__ == "__main__":
    n = build_pages(load_weapons(), Path(__file__).resolve().parent.parent / "site")
    print(f"{n} pages d'armes écrites")
