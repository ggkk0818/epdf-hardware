import pdfplumber

path = "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/DESPI-C102_SCH.pdf"
pdf = pdfplumber.open(path)
print("pages", len(pdf.pages))
for i, p in enumerate(pdf.pages):
    print(f"=== PAGE {i+1} images={len(p.images)} chars={len(p.chars)} lines={len(p.lines)} ===")
    print((p.extract_text() or "")[:6000])
