"""Extract I2C address / strapping facts from the local datasheets.

Read-only helper: prints matching lines with page numbers so the dev manual can
cite real datasheet values instead of guesses.

Usage: python extract_datasheet_facts.py
"""
import re
import sys
from pathlib import Path

from pdfplumber import open as pdf_open

DATA = Path(r"C:\Code\epdf-hardware\esp32-board-v1.1\datasheets")

TARGETS = {
    "bq25895.pdf": [
        r"0x6[Aa]\b", r"1101\s*010", r"slave address", r"I2C.{0,40}address",
    ],
    "MAX17048-MAX17049.pdf": [
        r"0x36\b", r"0110\s*110", r"slave address", r"device address",
    ],
    "tusb320li.pdf": [
        r"0x6[01]\b", r"slave address", r"ADDR\b.{0,60}", r"I2C.{0,40}address",
    ],
    "SSD1677.pdf": [
        r"0x0[0-9A-F]{2}\b", r"command table",
    ],
}


def scan(name: str, patterns: list[str], max_hits: int = 14) -> None:
    path = DATA / name
    if not path.exists():
        print(f"## {name}: MISSING ({path})")
        return
    print(f"\n## {name}")
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    hits = 0
    with pdf_open(str(path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                if any(c.search(line) for c in compiled):
                    line = " ".join(line.split())
                    if len(line) < 8:
                        continue
                    print(f"  p{page_no:>3}: {line[:180]}")
                    hits += 1
                    if hits >= max_hits:
                        print("  ... (truncated)")
                        return
    if hits == 0:
        print("  (no match)")


def main() -> int:
    for name, patterns in TARGETS.items():
        scan(name, patterns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
