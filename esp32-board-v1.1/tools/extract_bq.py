import pdfplumber
import sys

sys.stdout.reconfigure(encoding="utf-8")

path = "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/bq25895.pdf"
pdf = pdfplumber.open(path)
for i, p in enumerate(pdf.pages):
    t = p.extract_text() or ""
    if any(k in t for k in ["DSEL", "QON", "Pin Functions", "Table 6-1", "TERMINAL FUNCTIONS"]):
        print(f"--- page {i+1} ---")
        print(t[:9000])
