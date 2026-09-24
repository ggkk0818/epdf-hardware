"""Compare the tool's per-net length report with our own track summation for the
USB differential pairs."""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import geom  # noqa: E402


def main():
    r = geom.call(["pcb", "report"])["result"]
    rep = {n["net"]: n["length"] / 1000 * 25.4 for n in r["nets"]}
    g = geom.load()
    own = {}
    for t in g["tracks"]:
        own[t.get("net")] = own.get(t.get("net"), 0.0) + geom.seg_len_mm(t)
    for name in ("USB_DP_CONN", "USB_DN_CONN", "USB_DP", "USB_DN"):
        print(f"  {name:<14} report {rep.get(name, 0):7.2f} mm   "
              f"tracks {own.get(name, 0):7.2f} mm   "
              f"diff {rep.get(name, 0) - own.get(name, 0):6.2f}")
    for a, b in (("USB_DP_CONN", "USB_DN_CONN"), ("USB_DP", "USB_DN")):
        print(f"  skew {a}/{b}: report {abs(rep.get(a,0)-rep.get(b,0)):.3f} mm, "
              f"tracks {abs(own.get(a,0)-own.get(b,0)):.3f} mm")
    print("  pairs:", [p["name"] if "name" in p else "?" for p in
                       r.get("differentialPairs", [])])
    for p in r.get("differentialPairs", []):
        print("   ", p)


if __name__ == "__main__":
    main()
