"""Collect mode: saves labelled game screenshots + OCR while you play.

Run:  python -m tools.collect      (Ctrl+C to stop)
"""

import dataclasses
import json
import time
from datetime import datetime

from rapidfuzz import fuzz

from trackcod.capture.screen import find_game_window, grab
from trackcod.ocr.engine import ocr_image
from trackcod.paths import app_dir
from trackcod.readers.classify import classify
from trackcod.readers.common import norm

INTERVAL_S = 1.0
MIN_CHANGE = 70  # keep a frame when its OCR text similarity to the last kept one is below this
BURST_S = 10.0   # after a kept frame, keep every frame for this long (short-lived unlock banners)
BURST_INTERVAL_S = 0.5


def main() -> None:
    out = app_dir() / "captures" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    print(f"Collecte dans {out}\nLaisse le jeu au premier plan. Ctrl+C pour arrêter.")
    kept, last_text, burst_until = 0, None, 0.0
    try:
        while True:
            started = time.time()
            rect = find_game_window()
            if rect is not None:
                img = grab(rect)
                lines = ocr_image(img)
                text = norm(" ".join(l.text for l in lines))
                in_burst = started < burst_until
                changed = last_text is None or fuzz.ratio(text, last_text) < MIN_CHANGE
                if changed or in_burst:
                    kept += 1
                    kind = classify(lines)
                    img.save(out / f"{kept:04d}.png")
                    (out / f"{kept:04d}.json").write_text(json.dumps(
                        {"at": started, "rect": rect, "kind": kind,
                         "lines": [dataclasses.asdict(l) for l in lines]}, ensure_ascii=False), encoding="utf-8")
                    last_text = text
                    if changed:
                        burst_until = started + BURST_S
                    print(f"  {kept:04d}  {kind}{'  (rafale)' if in_burst and not changed else ''}")
            interval = BURST_INTERVAL_S if time.time() < burst_until else INTERVAL_S
            time.sleep(max(0.0, interval - (time.time() - started)))
    except KeyboardInterrupt:
        pass
    print(f"\n{kept} image(s) enregistrée(s) dans {out}")


if __name__ == "__main__":
    main()
