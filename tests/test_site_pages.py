"""Static SEO pages, one per MW4 weapon (text only, no game image), generated into site/armes/."""

from tools.site_pages import Weapon, build_pages, slug, weapon_page
from trackcod.known_camos import KnownSpecial

REZI = Weapon("Rezi 12", "Fusil à pompe", [KnownSpecial("Or noir", "Faites 20 éliminations de joueurs à bout portant"),
                                           KnownSpecial("Coup de pinceau", "Faites 10 éliminations de joueurs à longue distance"),
                                           KnownSpecial("Pin blanc", "Faites 40 éliminations de joueurs en sautant")])


def test_slug():
    assert slug("ISO Nightshade") == "iso-nightshade"
    assert slug(".50 GS") == "50-gs"
    assert slug("KG-7 Vulcan") == "kg-7-vulcan"
    assert slug("Déferlante X") == "deferlante-x"


def test_weapon_page_content():
    html = weapon_page(REZI)
    assert "<title>Camos Rezi 12 MW4 : spéciaux, défis et Érudit · Track COD</title>" in html
    # specials in game order with their challenge
    assert html.index("Or noir") < html.index("Coup de pinceau") < html.index("Pin blanc")
    assert "Faites 40 éliminations de joueurs en sautant" in html
    # Érudit for shotguns: challenges + unlock rules
    assert "Tuer 50 joueurs au tir au jugé" in html          # Platine challenge for shotguns
    assert "2 fusils à pompe" in html                         # Platine goal of the category
    assert "33 armes" in html                                 # Rupture harmonique rule
    assert "<img" not in html                                 # never a game image
    assert 'rel="canonical" href="https://track-cod.romusangames.workers.dev/armes/rezi-12"' in html


def test_category_without_known_erudit():
    html = weapon_page(Weapon("Sang 9mm", "Pistolet", REZI.specials))
    assert "à venir" in html


def test_text_is_escaped():
    html = weapon_page(Weapon('A<b>"', "Mitraillette", [KnownSpecial("<x>", "y & z")]))
    assert 'A<b>"' not in html and "A&lt;b&gt;&quot;" in html and "&lt;x&gt;" in html and "y &amp; z" in html


def test_build_pages_writes_index_and_sitemap(tmp_path):
    out = build_pages([REZI, Weapon("M4", "Fusil d'assaut", REZI.specials)], tmp_path)
    assert (tmp_path / "armes" / "rezi-12.html").exists() and (tmp_path / "armes" / "m4.html").exists()
    index = (tmp_path / "armes.html").read_text(encoding="utf-8")
    assert 'href="/armes/rezi-12"' in index and "Fusil à pompe" in index
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "/armes/m4</loc>" in sitemap and "/transparence.html</loc>" in sitemap and "/armes</loc>" in sitemap
    assert out == 2


def test_weapon_page_gives_a_tip_per_challenge():
    html = weapon_page(REZI)
    assert "Conseil" in html and "petite carte" in html and "grande carte" in html
