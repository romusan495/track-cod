"""Tells Bing (and the other IndexNow engines: Yandex, Seznam, Naver...) about every page of the sitemap.
Google does not use IndexNow: for Google, the sitemap is sent in Search Console.

Run after each `wrangler deploy`:  .venv/Scripts/python -m tools.indexnow
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://track-cod.romusangames.workers.dev"
HOST = SITE.removeprefix("https://")
KEY = "f45edac4ad22f99c6e4be616f26ef7a3"  # public by design: served at /<KEY>.txt to prove the site is ours
ENDPOINT = "https://api.indexnow.org/indexnow"
SITEMAP = Path(__file__).resolve().parents[1] / "site" / "sitemap.xml"


def sitemap_urls(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


def payload(urls: list[str]) -> dict:
    return {"host": HOST, "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": urls}


def main() -> int:
    urls = sitemap_urls(SITEMAP.read_text(encoding="utf-8"))
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload(urls)).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow : {len(urls)} pages envoyées (HTTP {r.status})")
            return 0
    except urllib.error.HTTPError as e:
        # 403: key file not found online yet (deploy first); 422: URLs not on this host; 429: too many requests
        print(f"IndexNow : refus HTTP {e.code} {e.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
