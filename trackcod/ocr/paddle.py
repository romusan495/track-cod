"""Fine OCR for the zones the Windows OCR reads badly: PaddleOCR PP-OCRv6 (small) models run with onnxruntime.

Measured on real frames (16/11/2026): the Windows OCR missed every daily counter ('0/3', '0/2'), the '3/3' of a
done challenge, and garbled names ('STRICA', 'DCR-8?', 'bEBLOQl&'); these models read them all. They are slower
(~0.3 s a zone), so they only read zones, never the whole screen every second.

No OpenCV: detection boxes come from the probability map with a small connected-component pass (game text is
horizontal, so axis-aligned boxes are enough), recognition is a greedy CTC decode limited to Latin characters (the
model is multilingual: unmasked, it sometimes answers with Chinese characters).
Models: PaddleOCR (Apache License 2.0), converted to ONNX by RapidOCR — see trackcod/data/ocr/LISEZMOI.txt.
"""

from __future__ import annotations

import logging
import math
import threading
from pathlib import Path

from PIL import Image

from trackcod.readers.common import OcrLine

log = logging.getLogger(__name__)

MODELS = Path(__file__).resolve().parent.parent / "data" / "ocr"
THREADS = 2            # leave the game its CPU
DET_MAX_SIDE = 1600    # detection input, longest side
DET_MIN_SIDE = 64
DET_THRESH = 0.3       # pixel probability of text
BOX_THRESH = 0.5       # mean probability of a kept box
UNCLIP = 1.6           # DB box growth (area * ratio / perimeter)
REC_HEIGHT = 48
TEXT_SCORE = 0.5       # mean character confidence of a kept line
_LATIN = set(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
             "ÀÂÄÆÇÈÉÊËÎÏÔŒÙÛÜŸàâäæçèéêëîïôœùûüÿ°«»’·•×✓✔√")  # check marks: conditions met in Apparence

_lock = threading.Lock()
_engine = None
_failed = False


class _Engine:
    def __init__(self, folder: Path):
        import numpy as np
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = THREADS
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        opts.enable_cpu_mem_arena = False  # the arena kept every buffer: 1.6 GB after a few zones, 120 MB without
        providers = ["CPUExecutionProvider"]
        self.np = np
        self.det = ort.InferenceSession(str(folder / "det.onnx"), opts, providers=providers)
        self.rec = ort.InferenceSession(str(folder / "rec.onnx"), opts, providers=providers)
        chars = self.rec.get_modelmeta().custom_metadata_map["character"].split("\n")
        self.chars = ["", *chars, " "]  # CTC blank first, space last (as PaddleOCR builds its dictionary)
        allowed = np.array([i == 0 or c in _LATIN for i, c in enumerate(self.chars)])
        self.blocked = ~allowed

    # ----- detection -----

    def boxes(self, img: Image.Image) -> list[tuple[int, int, int, int]]:
        np = self.np
        w, h = img.size
        scale = min(1.0, DET_MAX_SIDE / max(w, h))
        if min(w, h) * scale < DET_MIN_SIDE:
            scale = DET_MIN_SIDE / min(w, h)
        rw, rh = max(32, round(w * scale / 32) * 32), max(32, round(h * scale / 32) * 32)
        x = np.asarray(img.convert("RGB").resize((rw, rh), Image.BILINEAR), dtype=np.float32)[:, :, ::-1]
        x = ((x / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None].astype(np.float32)
        prob = self.det.run(None, {self.det.get_inputs()[0].name: x})[0][0, 0]
        out = []
        for x0, y0, x1, y1 in _components(prob > DET_THRESH):
            if min(x1 - x0, y1 - y0) < 3 or prob[y0:y1, x0:x1].mean() < BOX_THRESH * 0.6:
                continue
            region = prob[y0:y1, x0:x1]
            if region[region > DET_THRESH].mean() < BOX_THRESH:
                continue
            bw, bh = x1 - x0, y1 - y0
            d = bw * bh * UNCLIP / (2 * (bw + bh))
            fx, fy = w / rw, h / rh
            out.append((max(0, int((x0 - d) * fx)), max(0, int((y0 - d) * fy)),
                        min(w, int(math.ceil((x1 + d) * fx))), min(h, int(math.ceil((y1 + d) * fy)))))
        return out

    # ----- recognition -----

    def read(self, img: Image.Image, boxes: list[tuple[int, int, int, int]]) -> list[tuple[str, float]]:
        np = self.np
        if not boxes:
            return []
        crops = [img.crop(b).convert("RGB") for b in boxes]
        widths = [max(1, math.ceil(REC_HEIGHT * c.width / max(1, c.height))) for c in crops]
        width = max(320, max(widths))
        batch = np.zeros((len(crops), 3, REC_HEIGHT, width), dtype=np.float32)
        for i, (c, cw) in enumerate(zip(crops, widths)):
            a = np.asarray(c.resize((cw, REC_HEIGHT), Image.BILINEAR), dtype=np.float32)[:, :, ::-1]
            batch[i, :, :, :cw] = ((a / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)
        preds = self.rec.run(None, {self.rec.get_inputs()[0].name: batch})[0]
        preds[:, :, self.blocked] = 0.0  # Latin only
        idx, prob = preds.argmax(axis=2), preds.max(axis=2)
        results = []
        for row, p in zip(idx, prob):
            keep = np.ones(len(row), dtype=bool)
            keep[1:] = row[1:] != row[:-1]
            keep &= row != 0
            text = "".join(self.chars[i] for i in row[keep]).strip()
            results.append((text, float(p[keep].mean()) if keep.any() else 0.0))
        return results


def _components(mask) -> list[tuple[int, int, int, int]]:
    """Bounding boxes (x0, y0, x1, y1) of the 8-connected regions of a boolean map, from its horizontal runs."""
    import numpy as np

    runs = []  # (row, start, end)
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            continue
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
            runs.append((y, int(s), int(e)))
    parent = list(range(len(runs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_row: dict[int, list[int]] = {}
    for i, (y, s, e) in enumerate(runs):
        for j in by_row.get(y - 1, ()):
            _, ps, pe = runs[j]
            if ps <= e and s <= pe:  # touching, diagonals included (ends are exclusive)
                parent[find(i)] = find(j)
        by_row.setdefault(y, []).append(i)
    boxes: dict[int, list[int]] = {}
    for i, (y, s, e) in enumerate(runs):
        b = boxes.setdefault(find(i), [s, y, e, y + 1])
        b[0], b[1], b[2], b[3] = min(b[0], s), min(b[1], y), max(b[2], e), max(b[3], y + 1)
    return [tuple(b) for b in boxes.values()]


def _get() -> _Engine | None:
    global _engine, _failed
    with _lock:
        if _engine is None and not _failed:
            try:
                _engine = _Engine(MODELS)
                log.info("OCR fin actif (%s)", MODELS)
            except Exception as exc:  # missing models or runtime: the Windows OCR keeps working alone
                _failed = True
                log.warning("OCR fin indisponible, OCR Windows seul : %s", exc)
        return _engine


def available() -> bool:
    return _get() is not None


def ocr_zone(img: Image.Image, box: tuple[float, float, float, float]) -> list[OcrLine] | None:
    """Lines read in the zone (x0, y0, x1, y1, fractions of img), positioned on the whole image; None when the
    fine OCR cannot run (the caller keeps its Windows read)."""
    engine = _get()
    if engine is None:
        return None
    W, H = img.size
    x0, y0, x1, y1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return []
    crop = img.crop((x0, y0, x1, y1))
    try:
        with _lock:
            boxes = engine.boxes(crop)
            texts = engine.read(crop, boxes)
    except Exception as exc:
        log.warning("OCR fin en échec sur une zone : %s", exc)
        return None
    lines = []
    for (bx0, by0, bx1, by1), (text, score) in zip(boxes, texts):
        if text and score >= TEXT_SCORE:
            lines.append(OcrLine(text, (x0 + bx0) / W, (y0 + by0) / H, (bx1 - bx0) / W, (by1 - by0) / H))
    return sorted(lines, key=lambda l: (round(l.y, 3), l.x))
