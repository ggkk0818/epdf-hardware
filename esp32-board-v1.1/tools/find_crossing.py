"""Locate where two nets' copper crosses (debug helper)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    layer, a, b = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.loads((ROOT / "routing" / "routing.json").read_text(encoding="utf-8"))
    sa = [s for s in d["segments"] if s["layer"] == layer and s["net"] == a]
    sb = [s for s in d["segments"] if s["layer"] == layer and s["net"] == b]
    for s1 in sa:
        for s2 in sb:
            ax = np.linspace(s1["start"][0], s1["end"][0], 60)
            ay = np.linspace(s1["start"][1], s1["end"][1], 60)
            bx = np.linspace(s2["start"][0], s2["end"][0], 60)
            by = np.linspace(s2["start"][1], s2["end"][1], 60)
            dd = np.hypot(ax[:, None] - bx[None, :], ay[:, None] - by[None, :])
            m = float(dd.min())
            if m < 0.35:
                k = np.unravel_index(dd.argmin(), dd.shape)
                print(f"{a}: {s1['start']} -> {s1['end']} w{s1['width']}")
                print(f"{b}: {s2['start']} -> {s2['end']} w{s2['width']}")
                print(f"   min {m:.3f} mm at ({ax[k[0]]:.2f},{ay[k[0]]:.2f})"
                      f" <-> ({bx[k[1]]:.2f},{by[k[1]]:.2f})")


if __name__ == "__main__":
    main()
