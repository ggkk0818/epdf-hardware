"""List pads of one or more nets from the local geometry snapshot."""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    g = geom.load()
    nets = sys.argv[1].split(",")
    for net in nets:
        rows = []
        for c, p in geom.iter_pads(g["components"]):
            if p.get("net") == net:
                rows.append((c["designator"], p.get("padNumber"), p["x"], p["y"],
                             p.get("layer"), p.get("width"), p.get("height")))
        rows.sort(key=lambda r: (r[2], r[3]))
        print(f"=== {net}: {len(rows)} pads ===")
        for r in rows:
            print(f"  {r[0]:<5} pad {r[1]:<4} ({r[2]:8.1f},{r[3]:8.1f}) L{r[4]} "
                  f"{r[5]}x{r[6]}")
        vias = [v for v in g["vias"] if v.get("net") == net]
        print(f"  vias: {len(vias)}")
        for v in vias:
            print(f"    ({v['x']:.1f},{v['y']:.1f}) d={v.get('diameter')} "
                  f"hole={v.get('holeDiameter')} {v.get('primitiveId','')}")
        print()


if __name__ == "__main__":
    main()
