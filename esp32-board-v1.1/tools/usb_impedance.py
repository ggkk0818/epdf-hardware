"""Solver for the USB 90 ohm differential pair geometry.

Stackup (from the fab drawing):
    L1 F.Cu   0.035 mm finished (1 oz)
    PP 7628   0.195 mm, Dk = 4.2
    L2 In1.Cu solid GND

Edge coupled differential microstrip, Hammerstad single ended microstrip plus
the usual coupling correction.  Pure geometry - the fab must confirm the final
numbers with their own field solver.
"""

import math

ER = 4.2
H = 0.195      # mm, L1 -> L2 dielectric
T = 0.035      # mm, 1 oz finished copper


def z_single(w, h=H, er=ER, t=T):
    """Single ended microstrip impedance (Hammerstad, with thickness)."""
    we = w + (t / math.pi) * (1 + math.log(4 * math.e / ((t / h) ** 2 + (1 / math.pi / (w / t + 1.1)) ** 2)))
    u = we / h
    a = 1 + (1 / 49) * math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) \
        + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3)
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    return (60 / math.sqrt(eeff)) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))


def z_diff(w, s, h=H, er=ER):
    """Edge coupled differential microstrip."""
    z0 = z_single(w, h, er)
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s / h))


def solve(target=90.0, gap=None, w_lo=0.05, w_hi=1.0):
    best = None
    if gap is None:
        # scan gap, solve width
        for i in range(1, 200):
            s = round(0.05 + i * 0.005, 4)
            lo, hi = w_lo, w_hi
            for _ in range(80):
                mid = (lo + hi) / 2
                if z_diff(mid, s) > target:
                    lo = mid
                else:
                    hi = mid
            w = (lo + hi) / 2
            if 0.12 <= w <= 0.4:
                cost = abs(s - 0.18)  # prefer a comfortable, symmetric gap
                if best is None or cost < best[0]:
                    best = (cost, w, s)
        return best[1], best[2]
    lo, hi = w_lo, w_hi
    for _ in range(80):
        mid = (lo + hi) / 2
        if z_diff(mid, gap) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2, gap


if __name__ == "__main__":
    print(f"stackup: h={H} mm, Dk={ER}, outer copper {T*1000:.0f} um (1 oz)")
    w, s = solve(90.0)
    print(f"90 ohm differential  ->  W = {w:.3f} mm, S = {s:.3f} mm  (Zdiff = {z_diff(w, s):.1f})")
    for gap in (0.15, 0.18, 0.2, 0.25):
        w, s = solve(90.0, gap=gap)
        print(f"  fixed gap {gap:.2f} mm  ->  W = {w:.3f} mm  (Zdiff = {z_diff(w, s):.1f})")
    print()
    for w in (0.16, 0.18, 0.20, 0.22, 0.25):
        for s in (0.15, 0.18, 0.20, 0.25):
            print(f"  W={w:.2f} S={s:.2f} -> {z_diff(w, s):6.1f} ohm", end="")
        print()
