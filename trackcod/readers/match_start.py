"""Reader for the class selection screen shown at the start of a match ('CHOISIR LA CLASSE').

The primary weapon line ('Mitraillette - ISO Nightshade') is small pale-green text over the
map preview, so it gets its own colour-filtered OCR pass.
"""

from PIL import Image, ImageChops

from trackcod.weapons import WeaponRegistry
from trackcod.readers.common import OcrLine, norm

_GREEN_LEADS = (20, 30, 45)  # weapon text is pale green: G above B by at least this
_RED_MIN = 100


def is_match_start(lines: list[OcrLine]) -> bool:
    texts = [norm(l.text) for l in lines]
    return any("CHOISIR LA CLASSE" in t for t in texts) and any(t.startswith("PRINCIPAL") for t in texts)


def _anchor(lines: list[OcrLine]) -> OcrLine | None:
    return next((l for l in lines if norm(l.text).startswith("PRINCIPAL")), None)


def _green_text_mask(img: Image.Image, min_lead: int) -> Image.Image:
    r, g, b = img.convert("RGB").split()
    lead = ImageChops.subtract(g, b).point(lambda p: 255 if p > min_lead else 0)
    bright = r.point(lambda p: 255 if p > _RED_MIN else 0)
    text = ImageChops.multiply(lead, bright)
    return ImageChops.invert(text)  # black text on white


def ocr_match_start(img: Image.Image, base: list[OcrLine]) -> list[OcrLine]:
    from trackcod.ocr.engine import ocr_image

    anchor = _anchor(base)
    if anchor is None:
        return []
    h = anchor.h
    left, top = max(0.0, anchor.x - 0.01), anchor.y + 2 * h
    right, bottom = min(1.0, anchor.x + 0.2), min(1.0, anchor.y + 6.5 * h)
    W, H = img.size
    crop = img.crop((int(left * W), int(top * H), int(right * W), int(bottom * H)))
    sx, sy = right - left, bottom - top
    out: list[OcrLine] = []
    for lead in _GREEN_LEADS:
        mask = _green_text_mask(crop, lead)
        mask = mask.resize((mask.width * 2, mask.height * 2), Image.LANCZOS)
        out += [OcrLine(l.text, left + l.x * sx, top + l.y * sy, l.w * sx, l.h * sy) for l in ocr_image(mask)]
    return out


def read_match_start(lines: list[OcrLine], registry: WeaponRegistry) -> str | None:
    if not is_match_start(lines):
        return None
    anchor = _anchor(lines)
    band = sorted(
        (l for l in lines if anchor.y < l.y < anchor.y + 7 * anchor.h and abs(l.x - anchor.x) < 0.05),
        key=lambda l: (l.y, l.x))
    texts = [l.text for l in band]
    candidates = texts + [" ".join(texts[i:i + 2]) for i in range(len(texts) - 1)]
    after_dash = [t.split("-", 1)[1].strip(" -") for t in candidates if "-" in t]
    for text in after_dash + candidates:
        weapon = registry.match(text.strip(" -"))
        if weapon is not None:
            return weapon
    # Not a known weapon: only the 'Catégorie - Arme' form is trusted to learn a new name.
    after_dash = [t for t in after_dash if t]
    return registry.observe(after_dash[0]) if after_dash else None


def read_breadcrumb(lines: list[OcrLine]) -> str | None:
    """'MITRAILLETTE - ISO NIGHTSHADE' under 'CRÉER UNE CLASSE / ...' in the class editor menus."""
    top = next((l for l in lines if norm(l.text).startswith("CREER UNE CLASSE")), None)
    if top is None:
        return None
    for line in sorted(lines, key=lambda l: l.y):
        if top.y < line.y < top.y + 0.06 and " - " in line.text:
            return line.text.split(" - ", 1)[1].strip() or None
    return None


def _without_category(text: str) -> str:
    """'Fusil d' assaut Patriot XMR' -> 'Patriot XMR' (the OCR often drops the ' - ' between them)."""
    from trackcod.meta import CATEGORY_FR

    words = text.split()
    for cat in CATEGORY_FR.values():
        target = "".join(c for c in norm(cat) if c.isalnum())
        acc = ""
        for i, w in enumerate(words):
            acc += "".join(c for c in norm(w) if c.isalnum())
            if acc == target:
                return " ".join(words[i + 1:])
            if not target.startswith(acc):
                break
    return text


def read_weapon_title(lines: list[OcrLine], registry: WeaponRegistry) -> str | None:
    """Known weapon named under 'CRÉER UNE CLASSE / ...' on the weapon screen (Armurerie / Apparence /
    Progression tabs): the 'Catégorie - Arme' line first (with a blueprint the big title is the blueprint's
    name, e.g. 'VEILLE DU DÉMON'), then the big title ('PATRIOT XMR')."""
    # the path at the very top ('CRÉER UNE CLASSE / ...'), not 'CRÉER UNE CLASSE : MEILLEURES ARMES' (combat record)
    top = next((l for l in lines if norm(l.text).startswith("CREER UNE CLASSE") and "/" in l.text and l.y < 0.06), None)
    if top is None:
        return None
    near = sorted((l for l in lines if top.y < l.y < top.y + 0.1 and abs(l.x - top.x) < 0.04), key=lambda l: l.y)
    texts = [l.text.strip(" <") for l in near]
    with_category = [_without_category(t.split(" - ", 1)[1] if " - " in t else t) for t in texts]
    for text in [t for t, raw in zip(with_category, texts) if t != raw] + texts:
        text = text.strip(" -<")
        if sum(c.isalpha() for c in text) >= 3:
            weapon = registry.match(text)
            if weapon:
                return weapon
    return None


def read_match_info(lines: list[OcrLine]) -> tuple[str | None, str | None]:
    """(mode, map) from the top-right corner of the class selection screen."""
    top = [l for l in lines if l.y < 0.15 and l.x > 0.5]
    mode = next((l for l in sorted(top, key=lambda l: l.y) if "MATCH" in norm(l.text) or len(l.text) > 12), None)
    if mode is None:
        return None, None
    below = [l for l in top if mode.y < l.y < mode.y + 0.08 and sum(c.isalpha() for c in l.text) >= 3]
    game_map = min(below, key=lambda l: l.y).text.strip() if below else None
    return mode.text.strip(), game_map
