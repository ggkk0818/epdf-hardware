"""Replace the project TPS63070 symbol with the TI RNM0015A (15 pin, no EP) one.

Pin geometry is taken verbatim from the Ultra Librarian export the user supplied
(``Downloads/ul_TPS630701RNMR/KiCADv6/*.kicad_sym``); only the electrical types
are corrected so ERC behaves:

  * pin 7  VOUT -> power_out   (single driver for 3V3_MAIN)
  * pin 8  VOUT -> passive     (second output pad, paralleled on the PCB)
  * pin 5  FB   -> input       (feedback divider input, not an output)
  * pin 3/9/11 VAUX/L2/L1 -> passive

Everything else (PS_SYNC, PG, GND, FB2, PGND, VIN, EN, VSEL) keeps the vendor
type.  The old 16 pin symbol is removed - it had an EP pin that the RNM package
does not have.
"""

import sys
from pathlib import Path

sys.path.insert(0, "C:/Code/epdf-hardware/esp32-board-v1.1/tools")
from gen_sch import read_balanced_blocks

LIB = Path("C:/Code/epdf-hardware/esp32-board-v1.1/lib/esp32-board-v1.1.kicad_sym")

# (number, name, type, x, y, angle) - coordinates from the vendor symbol
PINS = [
    ("1", "PS/SYNC", "input", -20.32, -7.62, 0),
    ("2", "PG", "open_collector", 20.32, -7.62, 180),
    ("3", "VAUX", "passive", -20.32, -2.54, 0),
    ("4", "GND", "power_in", 20.32, -20.32, 180),
    ("5", "FB", "input", 20.32, 2.54, 180),
    ("6", "FB2", "input", 20.32, -2.54, 180),
    ("7", "VOUT", "power_out", 20.32, 12.7, 180),
    ("8", "VOUT", "passive", 20.32, 15.24, 180),
    ("9", "L2", "passive", 20.32, 20.32, 180),
    ("10", "PGND", "power_in", 20.32, -15.24, 180),
    ("11", "L1", "passive", -20.32, 20.32, 0),
    ("12", "VIN", "power_in", -20.32, 15.24, 0),
    ("13", "VIN", "power_in", -20.32, 12.7, 0),
    ("14", "EN", "input", -20.32, 7.62, 0),
    ("15", "VSEL", "input", -20.32, 2.54, 0),
]


def prop(name, value, x, y, hide=False):
    lines = [f'\t\t(property "{name}" "{value}"', f"\t\t\t(at {x} {y} 0)"]
    if hide:
        lines.append("\t\t\t(hide yes)")
    lines += ["\t\t\t(effects", "\t\t\t\t(font", "\t\t\t\t\t(size 1.27 1.27)",
              "\t\t\t\t)", "\t\t\t)", "\t\t)"]
    return "\n".join(lines)


def build_symbol():
    out = ['\t(symbol "TPS63070RNM"']
    out.append("\t\t(pin_names\n\t\t\t(offset 0.762)\n\t\t)")
    out.append("\t\t(exclude_from_sim no)")
    out.append("\t\t(in_bom yes)")
    out.append("\t\t(on_board yes)")
    out.append(prop("Reference", "U", 0, 28.0))
    out.append(prop("Value", "TPS63070RNMT", 0, -28.0))
    out.append(prop("Footprint", "esp32-board-v1.1:RNM0015A", 0, 0, hide=True))
    out.append(prop("Datasheet", "https://www.ti.com/lit/ds/symlink/tps63070.pdf", 0, 0, hide=True))
    out.append(prop("ki_fp_filters", "RNM0015A", 0, 0, hide=True))
    out.append('\t\t(symbol "TPS63070RNM_0_1"')
    out.append("\t\t\t(rectangle")
    out.append("\t\t\t\t(start -15.24 25.4)")
    out.append("\t\t\t\t(end 15.24 -25.4)")
    out.append("\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)")
    out.append("\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)")
    out.append("\t\t\t)")
    out.append("\t\t)")
    out.append('\t\t(symbol "TPS63070RNM_1_1"')
    for num, name, ptype, x, y, ang in PINS:
        out.append(f"\t\t\t(pin {ptype} line")
        out.append(f"\t\t\t\t(at {x} {y} {ang})")
        out.append("\t\t\t\t(length 5.08)")
        out.append(f'\t\t\t\t(name "{name}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)')
        out.append(f'\t\t\t\t(number "{num}"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)')
        out.append("\t\t\t)")
    out.append("\t\t)")
    out.append("\t)")
    return "\n".join(out)


def main():
    text = LIB.read_text(encoding="utf-8")
    # drop the old 16 pin symbol
    marker = '\t(symbol "TPS63070"\n'
    if marker in text:
        start = text.index(marker)
        end, _ = read_balanced_blocks(text, text.index("(", start))
        text = text[:start] + text[end:].lstrip("\n")
    # also drop a previously imported RNM symbol so re-running is idempotent
    marker2 = '\t(symbol "TPS63070RNM"\n'
    if marker2 in text:
        start = text.index(marker2)
        end, _ = read_balanced_blocks(text, text.index("(", start))
        text = text[:start] + text[end:].lstrip("\n")
    new = build_symbol()
    # insert before the final closing paren of the symbol library
    close = text.rstrip().rfind(")")
    text = text[:close] + new + "\n" + text[close:]
    LIB.write_text(text, encoding="utf-8")
    print("wrote", LIB)


if __name__ == "__main__":
    main()
