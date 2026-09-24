"""Scan free-space slack along a straight run, to see how much room a serpentine
or a detour has at each point."""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import clearance  # noqa: E402


def main():
    net, layer, x1, y1, x2, y2 = (sys.argv[1], int(sys.argv[2]),
                                  *[float(v) for v in sys.argv[3:7]])
    step = float(sys.argv[7]) if len(sys.argv) > 7 else 100.0
    oracle = clearance.Oracle(net=net)
    L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    n = max(1, int(L / step))
    print(f"{net} L{layer} run {L:.0f} mil, sampling every {L/n:.0f} mil")
    for k in range(n + 1):
        u = k / n
        px = x1 + u * (x2 - x1)
        py = y1 + u * (y2 - y1)
        # how far can we move perpendicular before hitting foreign copper?
        dx, dy = (y2 - y1), -(x2 - x1)
        m = (dx * dx + dy * dy) ** 0.5 or 1.0
        dx, dy = dx / m, dy / m
        up = _reach(oracle, px, py, dx, dy, layer)
        dn = _reach(oracle, px, py, -dx, -dy, layer)
        print(f"   t={u*L:6.0f} ({px:7.1f},{py:7.1f})  +perp {up:6.1f}  -perp {dn:6.1f}")


def _reach(oracle, px, py, dx, dy, layer, limit=250.0, step=2.0):
    r = 5.0            # half of a 10 mil trace
    best = 0.0
    d = 0.0
    while d < limit:
        d += step
        m, _ = oracle.point_margin(px + dx * d, py + dy * d, r, layer)
        if m < 1.0:
            break
        best = d
    return best


if __name__ == "__main__":
    main()
