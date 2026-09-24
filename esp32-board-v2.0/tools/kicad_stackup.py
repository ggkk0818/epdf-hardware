"""Print the KiCad stackup (layer / thickness / dielectric) of a .kicad_pcb."""

import re
import sys


def main():
    path = sys.argv[1]
    s = open(path, encoding="utf-8", errors="replace").read()
    i = s.find("(setup")
    seg = s[i:i + 4000]
    for m in re.finditer(r'\(layer "([^"]+)"(.*?)\(thickness ([0-9.]+)\)', seg, re.S):
        name, body, th = m.group(1), " ".join(m.group(2).split()), m.group(3)
        er = re.search(r"\(epsilon_r ([0-9.]+)\)", body)
        mat = re.search(r'\(material "([^"]*)"\)', body)
        print(f"  {name:<14} t={th:>7} mm  er={er.group(1) if er else '-':<5} "
              f"mat={mat.group(1) if mat else '-'}")


if __name__ == "__main__":
    main()
