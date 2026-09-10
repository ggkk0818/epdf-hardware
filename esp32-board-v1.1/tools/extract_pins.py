import pdfplumber
import re
import sys

files = {
    "tps63070": "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/tps63070.pdf",
    "max17048": "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/MAX17048-MAX17049.pdf",
    "tusb320li": "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/tusb320li.pdf",
    "tps22918": "C:/Code/epdf-hardware/esp32-board-v1.1/datasheets/tps22918.pdf",
}

for key, path in files.items():
    print("\n\n########", key, "########")
    pdf = pdfplumber.open(path)
    for i, p in enumerate(pdf.pages):
        t = p.extract_text() or ""
        if re.search(r"PIN|Pin Configuration|Terminal|DEVICE INFORMATION|TYPICAL APPLICATION|pin function", t, re.I):
            print(f"--- page {i+1} ---")
            print(t[:8000])
