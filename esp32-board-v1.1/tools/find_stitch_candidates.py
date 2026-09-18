"""Off-pad stitching-via candidates for every orphan GND patch.

    python tools/find_stitch_candidates.py

Read-only: it re-uses the GND component map and, for every orphan patch, lists
the spots *inside* the copper (never on a pad) where a 0.40/0.20 via passes the
router's clearance engine, ranked by how roomy the spot is.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gnd_components as G  # noqa: E402

if __name__ == "__main__":
    G.analyse(with_candidates=True)
