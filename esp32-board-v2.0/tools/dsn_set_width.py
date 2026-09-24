"""Set per-net track width in a Specctra DSN the way Freerouting reads it.

The width belongs inside each net's `(class <net> '<net>' ... (rule (width W) ...))`
block. Injecting `(rule (width ...) (net ...))` into `(structure ...)` does NOT work —
Freerouting treats it as a change of the DEFAULT width, which then breaks routing.
"""

import argparse
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--width", type=float, required=True)
    ap.add_argument("--nets", required=True)
    args = ap.parse_args()

    nets = [n for n in args.nets.split(",") if n]
    with open(args.file, encoding="ascii", errors="replace") as fh:
        text = fh.read()

    changed = 0
    for net in nets:
        # match the class block header for this net, then its first (width N)
        pat = re.compile(r"(\(class\s+" + re.escape(net) + r"\s+'" + re.escape(net) + r"'(?:.|\n)*?\(rule\s*\n\s*)\(width\s+[\d.]+\)")
        text, n = pat.subn(lambda m: m.group(1) + f"(width {args.width:g})", text, count=1)
        changed += n
        print(f"  {net}: {'set to ' + str(args.width) if n else 'NOT FOUND'}")

    with open(args.file, "w", encoding="ascii", errors="replace") as fh:
        fh.write(text)
    print("classes updated:", changed)


if __name__ == "__main__":
    main()
