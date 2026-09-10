import pdfplumber

p = r"C:\Code\epdf-hardware\esp32-board-v1.1\datasheets\DESPI-C1248_SCH.pdf"
with pdfplumber.open(p) as pdf:
    print("pages", len(pdf.pages))
    for i, page in enumerate(pdf.pages):
        txt = page.extract_text() or ""
        print(f"=== PAGE {i+1} chars={len(txt)} ===")
        print(txt[:12000])
