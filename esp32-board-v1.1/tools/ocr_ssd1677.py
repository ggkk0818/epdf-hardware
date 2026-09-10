import asyncio
import io
import os

import pdfplumber
from PIL import Image
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.globalization import Language
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream


async def ocr_bytes(data: bytes) -> str:
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(data)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_language(Language("en-US"))
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    result = await engine.recognize_async(bitmap)
    lines = []
    for line in result.lines:
        words = []
        for word in line.words:
            words.append(f"{word.text}")
        lines.append(" ".join(words))
    return "\n".join(lines)


pdf = pdfplumber.open(
    "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/SSD1677.pdf"
)
page = pdf.pages[43]
print("images", len(page.images))
page_img = page.to_image(resolution=300)
for idx, im in enumerate(page.images):
    scale = page_img.scale
    bbox = (
        im["x0"] * scale,
        im["top"] * scale,
        im["x1"] * scale,
        im["bottom"] * scale,
    )
    cropped = page_img.original.crop(bbox)
    out = f"C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/ssd1677_fig13_{idx}.png"
    gray = cropped.convert("L")
    # upscale 2x and threshold to help OCR on small component labels
    w, h = gray.size
    gray2 = gray.resize((w * 2, h * 2), Image.LANCZOS)
    gray2 = gray2.point(lambda p: 0 if p < 128 else 255)
    gray.save(out)
    buf = io.BytesIO()
    gray2.save(buf, format="PNG")
    text = asyncio.run(ocr_bytes(buf.getvalue()))
    print(f"--- image {idx} ({out}) ---")
    print(text)
