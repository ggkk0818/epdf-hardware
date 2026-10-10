"""Dump the text of selected datasheet pages (read-only helper for the dev manual).

Usage: python dump_pdf_pages.py <pdf-name> <page> [<page> ...]
Example: python dump_pdf_pages.py tusb320li.pdf 3 4
"""
import sys
from pathlib import Path

from pdfplumber import open as pdf_open

DATA = Path(r"C:\Code\epdf-hardware\esp32-board-v1.1\datasheets")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    path = DATA / argv[1]
    pages = [int(p) for p in argv[2:]]
    with pdf_open(str(path)) as pdf:
        for n in pages:
            print(f"\n===== {argv[1]} page {n} =====")
            print(pdf.pages[n - 1].extract_text() or "(no text)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
