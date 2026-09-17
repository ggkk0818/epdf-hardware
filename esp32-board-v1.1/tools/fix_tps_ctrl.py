"""Close TPS_EN / TPS_VSEL the way the 2026-09-17 MD prescribes.

    python tools/fix_tps_ctrl.py

  1. keep the SYS trunk where it is, but neck the piece above U3 from 1.20 mm
     down to 0.80 mm (0.80 mm is already the accepted trunk width for
     BAT / SYS / USB_VBUS, so this is a legal neck-down, not a rule change)
  2. escape U3.15 (TPS_VSEL) sideways and U3.14 (TPS_EN) upwards, then dive to
     B.Cu so the long run happens away from the switching node
  3. TPS_L1 / TPS_L2 / TPS_PS_SYNC and the trunks are never touched

Everything is verified with the router's own clearance engine; a step that makes
things worse is rolled back.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

TRUNK_SEG = ((33.25, 42.20), (37.10, 40.90))
# MD §5: U3.14 has to leave upwards and turn *left*, so the corridor above the
# SYS pads (U3.12 / U3.13) stays free and the escape never shadows the SYS
# trunk.  The router would otherwise take the direct route to the right, which
# walls off that corridor.
ESCAPES = {("U3", "14"): [(33.775, 42.95), (32.60, 42.95)]}
# MD §14: SYS has to be connected inside the TPS area as well.  U3's two SYS
# pads sit right under the converter, with C18.1 (also SYS) 1.4 mm above them,
# so one short 0.5 mm escape joins pad -> C18.1 -> SYS island.  It also owns the
# corridor above the pads, which is what forces TPS_EN out to the left.
SYS_ESCAPES = {("U3", "12"): [(34.525, 42.10)]}
FROZEN = {"TPS_L1", "TPS_L2", "TPS_PS_SYNC", "SYS", "3V3_MAIN", "BAT_BUS",
          "BAT1_RAW", "BAT2_RAW", "USB_VBUS_RAW", "USB_VBUS_PROT", "EPD_3V3",
          "GND"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)

    def same(a, b):
        return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3

    # a previous run may already have reserved an escape stub - adopt it so the
    # maze anchors on the existing copper instead of laying a second copy of it
    for net in ("TPS_VSEL", "TPS_EN"):
        for pad in board.pads_of.get(net, []):
            key = (pad["ref"], pad["num"])
            if key in sess.stubs:
                continue
            for s in board.net_segments.get(net, []):
                if s.get("kind") != "stub":
                    continue
                if same(s["start"], (pad["x"], pad["y"])):
                    tip = s["end"]
                elif same(s["end"], (pad["x"], pad["y"])):
                    tip = s["start"]
                else:
                    continue
                li = R.ROUTABLE.index(s["layer"]) if s["layer"] in R.ROUTABLE else 0
                sess.stubs[key] = {
                    "tip": (li, int(round(tip[0] / R.PITCH)),
                            int(round(tip[1] / R.PITCH))),
                    "cells": [], "net": net, "width": s["width"]}
                break

    # ------------------------------------------------------------------
    # 1. neck the SYS trunk above U3 down to 0.80 mm
    # ------------------------------------------------------------------
    baseline = sess.violations("SYS")
    for s in sess.b.net_segments.get("SYS", []):
        if s["layer"] != "F.Cu":
            continue
        if (same(s["start"], TRUNK_SEG[0]) and same(s["end"], TRUNK_SEG[1])) or \
                (same(s["start"], TRUNK_SEG[1]) and same(s["end"], TRUNK_SEG[0])):
            old = s["width"]
            s["width"] = 0.80
            sess.b.rebuild_copper()
            sess.mask_cache.clear()
            score = sess.violations("SYS")
            print(f"  SYS trunk above U3: {old:.2f} -> 0.80 mm, "
                  f"SYS score {baseline} -> {score}")
            if score > baseline:
                s["width"] = old
                sess.b.rebuild_copper()
                sess.mask_cache.clear()
                print("  rejected: neck-down makes clearance worse")
            break

    # ------------------------------------------------------------------
    # 2. route the two control nets locally
    # ------------------------------------------------------------------
    # 2a. first bond U3's SYS pads to C18.1 / the island (MD §14)
    sys_params = R.net_params("SYS")
    for pad in board.pads_of.get("SYS", []):
        key = (pad["ref"], pad["num"])
        pts = SYS_ESCAPES.get(key)
        if pts is None or key in sess.stubs:
            continue
        sess.mask_cache.clear()
        if sess.stub_clear(pts, 0.5, "SYS", "F.Cu", sys_params,
                           pad["x"], pad["y"]):
            sess._commit_stub("SYS", pad, pts, 0.5, "F.Cu", key, [0],
                              sys_params, (0.0, -1.0), pad["h"] / 2.0)
            sess.b.rebuild_copper()
            sess.mask_cache.clear()
            print(f"  SYS: escape reserved at {pad['ref']}.{pad['num']} -> "
                  f"{pts[-1]}")
        else:
            print(f"  SYS: escape at {pad['ref']}.{pad['num']} is not clear")

    for net in ("TPS_VSEL", "TPS_EN"):
        params = R.net_params(net)
        for pad in board.pads_of.get(net, []):
            key = (pad["ref"], pad["num"])
            if key in sess.stubs:
                continue
            sess.mask_cache.clear()
            esc = ESCAPES.get(key)
            if esc is not None:
                # MD §5/§6: hand-placed escape polyline, then the maze only has
                # to reach its tip
                if sess.stub_clear(esc, params["width"], net, "F.Cu", params,
                                   pad["x"], pad["y"]):
                    sess._commit_stub(net, pad, esc, params["width"], "F.Cu",
                                      key, [0], params, (0.0, -1.0),
                                      pad["h"] / 2.0)
                    print(f"  {net}: escape reserved at {pad['ref']}."
                          f"{pad['num']} -> {esc[-1]}")
                    continue
                print(f"  {net}: prescribed escape for {pad['ref']}."
                      f"{pad['num']} is not clear, falling back to the maze")
            if sess.make_stub(net, pad, params, key):
                print(f"  {net}: stub reserved at {pad['ref']}.{pad['num']}")
        sess.mask_cache.clear()
        if sess.route_one(net):
            n = sum(1 for s in sess.b.net_segments.get(net, []))
            v = len(sess.b.net_vias.get(net, []))
            print(f"  {net}: routed ({n} segments, {v} vias)")
            continue
        # rip only small, non-frozen blockers
        scored = {}
        for pad in board.pads_of.get(net, []):
            for b in sess.blockers_for(net, max_nets=6, pads=[pad]):
                if b in FROZEN or b == net:
                    continue
                scored[b] = scored.get(b, 0) + 1
        blockers = [b for b, _ in sorted(scored.items(), key=lambda kv: -kv[1])][:3]
        print(f"  {net}: blocked, ripping {blockers}")
        st = sess.state()
        for b in blockers:
            sess._remove_net_copper(b)
        sess.b.rebuild_copper()
        sess.mask_cache.clear()
        ok = sess.route_one(net)
        if ok:
            for b in blockers:
                sess.mask_cache.clear()
                if not sess.route_one(b):
                    ok = False
                    break
        if ok:
            print(f"  {net}: routed after ripping {blockers}")
        else:
            sess.restore(st)
            print(f"  {net}: could not be closed")

    if args.dry_run:
        return 0
    sess.rebuild_necks()          # keep the published neck list in sync
    segs, vias = board.copper()
    data["segments"] = segs
    data["vias"] = [v for v in vias if "kind" not in v]
    uniq = {}
    for v in vias:
        if "kind" in v:
            uniq[(round(v["x"], 3), round(v["y"], 3), v["net"])] = v
    data["gnd_vias"] = list(uniq.values())
    data["neck_segments"] = [
        {"layer": s["layer"], "net": s["net"], "width": s["width"],
         "class": R.netclass_of(s["net"]), "start": s["start"], "end": s["end"]}
        for s in sess.neck_segments]
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
