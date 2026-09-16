"""Print a short routing status summary (nets, widths, vias, DRC counts)."""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    r = json.loads((ROOT / "routing" / "routing.json").read_text(encoding="utf-8"))
    vias = collections.Counter(v["net"] for v in r["vias"])
    widths = collections.Counter(s["width"] for s in r["segments"])
    print(f"segments {len(r['segments'])}  signal vias {len(r['vias'])}  "
          f"gnd vias {len(r['gnd_vias'])}  unrouted {len(r['failed'])}")
    print("widths:", dict(sorted(widths.items())))
    print("0.8 mm trunk nets:",
          sorted({s["net"] for s in r["segments"] if s["width"] >= 0.79}))
    for net in ("CHG_SW", "EPD_SW", "TPS_L1", "TPS_L2", "BAT_BUS", "SYS",
                "3V3_MAIN", "USB_VBUS_PROT"):
        segs = [s for s in r["segments"] if s["net"] == net]
        ws = sorted({s["width"] for s in segs})
        print(f"  {net:<14s} vias={vias.get(net, 0):<3d} segments={len(segs):<4d} "
              f"widths={ws}")
    print("unrouted:", r["failed"])
    drc = json.loads((ROOT / "drc.json").read_text(encoding="utf-8"))
    print("DRC violations", len(drc["violations"]), "unconnected",
          len(drc["unconnected_items"]))
    print(dict(collections.Counter(v["type"] for v in drc["violations"])))


if __name__ == "__main__":
    main()
