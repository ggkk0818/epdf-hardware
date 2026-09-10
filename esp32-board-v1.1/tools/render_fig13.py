import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

pdf = pdfium.PdfDocument(r"C:\Code\epdf-hardware\esp32-board-v1.1\datasheets\SSD1677.pdf")
page = pdf[43]
scale = 4.0
bitmap = page.render(scale=scale)
img = bitmap.to_pil()
out = r"C:\Code\epdf-hardware\esp32-board-v1.1\datasheets\ssd1677_fig13_hi.png"
img.save(out)
print("saved", out, img.size)

engine = RapidOCR()
result, _ = engine(out)
if result:
    for box, text, score in result:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = sum(xs) / 4
        cy = sum(ys) / 4
        print(f"{score:.2f}\t{cx:7.1f}\t{cy:7.1f}\t{text}")
