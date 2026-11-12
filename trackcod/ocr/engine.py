"""Windows built-in OCR (Windows.Media.Ocr), French."""

import asyncio
import io

from PIL import Image

from trackcod.readers.common import OcrLine

LANGUAGE = "fr-FR"
_engine = None


def _winrt():
    import winrt.windows.globalization as glob
    import winrt.windows.graphics.imaging as imaging
    import winrt.windows.media.ocr as ocr
    import winrt.windows.storage.streams as streams

    return glob, imaging, ocr, streams


def ocr_available() -> bool:
    try:
        glob, _, ocr, _ = _winrt()
        return bool(ocr.OcrEngine.is_language_supported(glob.Language(LANGUAGE)))
    except Exception:
        return False


def _get_engine():
    global _engine
    if _engine is None:
        glob, _, ocr, _ = _winrt()
        _engine = ocr.OcrEngine.try_create_from_language(glob.Language(LANGUAGE))
        if _engine is None:
            raise RuntimeError("OCR français indisponible")
    return _engine


async def _recognize(png: bytes):
    _, imaging, _, streams = _winrt()
    stream = streams.InMemoryRandomAccessStream()
    writer = streams.DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    return await _get_engine().recognize_async(bitmap)


def ocr_image(img: Image.Image, upscale: float = 1.0) -> list[OcrLine]:
    if upscale != 1.0:
        img = img.resize((int(img.width * upscale), int(img.height * upscale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    result = asyncio.run(_recognize(buf.getvalue()))
    width, height = float(img.width), float(img.height)
    lines: list[OcrLine] = []
    for line in result.lines:
        rects = [w.bounding_rect for w in line.words]
        if not rects:
            continue
        x0 = min(r.x for r in rects)
        y0 = min(r.y for r in rects)
        x1 = max(r.x + r.width for r in rects)
        y1 = max(r.y + r.height for r in rects)
        lines.append(OcrLine(line.text, x0 / width, y0 / height, (x1 - x0) / width, (y1 - y0) / height))
    return lines
