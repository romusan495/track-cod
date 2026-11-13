from tools.indexnow import KEY, payload, sitemap_urls

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://track-cod.romusangames.workers.dev/</loc></url>
  <url><loc>https://track-cod.romusangames.workers.dev/armes/m4</loc></url>
</urlset>
"""


def test_urls_come_from_the_sitemap():
    assert sitemap_urls(SITEMAP) == ["https://track-cod.romusangames.workers.dev/",
                                     "https://track-cod.romusangames.workers.dev/armes/m4"]


def test_payload_names_the_site_and_its_key_file():
    p = payload(["https://track-cod.romusangames.workers.dev/armes/m4"])
    assert p == {"host": "track-cod.romusangames.workers.dev", "key": KEY,
                 "keyLocation": f"https://track-cod.romusangames.workers.dev/{KEY}.txt",
                 "urlList": ["https://track-cod.romusangames.workers.dev/armes/m4"]}


def test_key_file_is_published_with_the_site():
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "site" / f"{KEY}.txt"
    assert f.read_text(encoding="utf-8").strip() == KEY
