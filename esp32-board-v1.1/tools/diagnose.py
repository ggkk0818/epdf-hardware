"""Flood-fill diagnostic for unrouted nets.

    python tools/diagnose.py routing/routing.json

For every net listed as failed it reports how much of the board is reachable
from the first pad, and how many cells of each remaining pad are inside that
region.  A pad with 0 reachable cells is walled in by committed copper.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402


def flood(walk, start_cells):
    seen = np.zeros_like(walk)
    q = deque()
    for (i, j) in start_cells:
        if 0 <= i < R.W and 0 <= j < R.H and walk[j, i] and not seen[j, i]:
            seen[j, i] = True
            q.append((i, j))
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < R.W and 0 <= nj < R.H and not seen[nj, ni] \
                    and walk[nj, ni]:
                seen[nj, ni] = True
                q.append((ni, nj))
    return seen


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else str(R.OUT_PATH)
    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    pre = json.loads(Path(path).read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(pre)
    sess = R.Session(board)
    fails = pre.get("failed", [])
    print(f"{len(fails)} failed nets")
    for net in fails:
        params = R.net_params(net)
        sess.mask_cache.clear()
        m, via, vdd, vdr, _soft = sess.masks_for(net, params["width"])
        walk = m["F.Cu"][0]
        pads = board.pads_of[net]
        seen = flood(walk, pads[0]["cells"])
        parts = []
        for p in pads[1:]:
            ok = sum(1 for (i, j) in p["cells"] if seen[j, i])
            parts.append(f"{p['ref']}.{p['num']}={ok}/{len(p['cells'])}")
        print(f"{net:<16s} {str(pads[0]['ref']) + '.' + str(pads[0]['num']):<10s}"
              f" flood={int(seen.sum()):7d}  " + "  ".join(parts))


if __name__ == "__main__":
    main()
