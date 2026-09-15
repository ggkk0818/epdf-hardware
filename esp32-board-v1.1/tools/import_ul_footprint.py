"""Convert the Ultra Librarian RNM0015A footprint (KiCad v6 syntax) to the
current KiCad footprint syntax used by this project.

Pads, silkscreen and paste geometry are copied verbatim - only the file syntax is
modernised, one stray Ultra Librarian "Designator9" text item is dropped, and a
courtyard is added (the vendor file has none, which would otherwise make the
placer fall back to the much smaller pad bounding box).
"""

import re
import sys
import uuid
from pathlib import Path

SRC = Path("C:/Users/ggkk2/Downloads/ul_TPS630701RNMR/KiCADv6/footprints.pretty/RNM0015A.kicad_mod")
DST = Path("C:/Code/epdf-hardware/esp32-board-v1.1/lib/esp32-board-v1.1.pretty/RNM0015A.kicad_mod")


def u():
    return str(uuid.uuid4())


def main():
    t = SRC.read_text(encoding="utf-8")

    # --- header ----------------------------------------------------------
    t = t.replace(
        '(footprint "RNM0015A" (version 20211014) (generator pcbnew)',
        '(footprint "RNM0015A"\n'
        "\t(version 20241229)\n"
        '\t(generator "pcbnew")\n'
        '\t(generator_version "9.0")',
    )
    t = t.replace('\t(layer "F.Cu")', f'\t(layer "F.Cu")\n\t(uuid "{u()}")', 1)

    # --- layer names -----------------------------------------------------
    t = re.sub(r"\(layer (F\.[A-Za-z.]+|B\.[A-Za-z.]+|Dwgs\.User)\)", r'(layer "\1")', t)

    # --- graphics --------------------------------------------------------
    # NOTE: inside a footprint, graphic fill is the boolean form (fill yes|no),
    # not the (type none|solid) enum used by drawing sheets / zones.
    t = re.sub(r"\(width ([-\d.]+)\)\s*\(fill none\)",
               r"(stroke (width \1) (type default)) (fill no)", t)
    t = re.sub(r"\(width ([-\d.]+)\)\s*\(fill solid\)",
               r"(stroke (width \1) (type default)) (fill yes)", t)
    # fp_line has no fill - give it a stroke only
    t = re.sub(r"(\(fp_line \(start [^)]*\) \(end [^)]*\) \(layer \"[^\"]+\"\)) \(width ([-\d.]+)\)",
               r"\1 (stroke (width \2) (type default))", t)

    # --- footprint text -> modern properties ------------------------------
    def to_property(m):
        kind, value, x, y, layer = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        name = "Reference" if kind == "reference" else "Value"
        # nudge the designator off the pad array so it stays readable
        y = float(y) - 2.6 if kind == "reference" else float(y) + 2.6
        return (
            f'(property "{name}" "{value}"\n'
            f"\t\t(at {x} {y} 0)\n"
            "\t\t(unlocked yes)\n"
            f'\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{u()}")\n'
            "\t\t(effects (font (size 1 1) (thickness 0.15)))\n"
            "\t)"
        )

    t = re.sub(
        r'\(fp_text (reference|value) "?([^"\s)]+)"? \(at ([-\d.]+) ([-\d.]+) unlocked\) \(layer "?([A-Za-z.]+)"?\)\s*\n\s*\(effects[^\n]*\)\n\s*\)',
        to_property, t)

    # drop the stray Ultra Librarian designator text
    t = re.sub(r'\s*\(fp_text user "Designator9".*?\n\s*\)', "", t, flags=re.S)

    # --- uuids for the remaining graphics / user text ---------------------
    def add_uuid(m):
        blk = m.group(0)
        if "(uuid " in blk:
            return blk
        return blk[:-1].rstrip() + f'\n\t\t(uuid "{u()}")\n\t)'

    t = re.sub(r"(?ms)^\t\(fp_(?:line|poly|circle)\b.*?\n\t\)", add_uuid, t)

    # --- courtyard (the vendor file has none) -----------------------------
    crt = (
        '\t(fp_rect (start -1.62 -1.87) (end 1.62 1.87)\n'
        "\t\t(stroke (width 0.05) (type default))\n"
        "\t\t(fill no)\n"
        '\t\t(layer "F.CrtYd")\n'
        f'\t\t(uuid "{u()}")\n'
        "\t)\n"
    )
    # --- 3D model (STEP supplied alongside the footprint) -----------------
    model = (
        '\t(model "${KIPRJMOD}/lib/3dmodels/RNM0015A.stp"\n'
        "\t\t(offset (xyz 0 0 0))\n"
        "\t\t(scale (xyz 1 1 1))\n"
        "\t\t(rotate (xyz 0 0 0))\n"
        "\t)\n"
    )

    close = t.rstrip().rfind(")")
    t = t[:close] + crt + model + "\t(embedded_fonts no)\n" + t[close:]

    DST.write_text(t, encoding="utf-8")
    print("wrote", DST, len(t), "bytes")


if __name__ == "__main__":
    main()
