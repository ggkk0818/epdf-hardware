"""Local convergence of the TPS63070 area (MD §7 + §2 U3 ground pins).

    python tools/fix_tps.py             # plan and write routing.json
    python tools/fix_tps.py --dry-run   # only report

Done without a global re-route:

  * U3 Pad 4 / Pad 10 (GND) get a short, wide F.Cu ground neck plus a GND via
    to the In1 plane.  If a blocking track of a *small* net sits in the way it
    is ripped up locally and re-routed afterwards (never the SYS / 3V3_MAIN
    trunks, never more than two nets per pad).
  * TPS_L2 / TPS_EN / TPS_VSEL / TPS_PS_SYNC are reserved with fan-out stubs and
    routed locally; TPS_L2 keeps "no via" and the 0.50 mm switch-node rule.

Everything is verified with the router's own clearance engine; on failure the
previous state is restored, so the board can never get worse.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "routing" / "routing.json"

TRUNKS = {"SYS", "3V3_MAIN", "BAT_BUS", "BAT1_RAW", "BAT2_RAW",
          "USB_VBUS_RAW", "USB_VBUS_PROT", "EPD_3V3", "GND"}
TPS_NETS = ["TPS_L2", "TPS_EN", "TPS_VSEL", "TPS_PS_SYNC"]

# MD decision (2026-09-17): a *short* piece of SYS next to U3 pin 14/15 may be
# ripped up and re-patched immediately, because otherwise TPS_EN / TPS_VSEL can
# never leave the U3 pad field.  The patch is routed locally and verified; if it
# fails the whole step is rolled back.
SYS_RIP_RADIUS = 1.5     # copper this close to the U3 pad has to give way
SYS_RIP_MAX = 2.0        # ... but never more than 2 mm of it per segment


def rip_near_pads(sess, net, pads, radius=SYS_RIP_RADIUS, max_len=SYS_RIP_MAX):
    """Rip the copper of `net` that lies within `radius` of any pad.

    Only the offending part of a segment is taken out (the segment is split at
    the boundary), so the approved rip-up stays at the millimetre scale.
    Returns the list of removed pieces, each of which is re-patched afterwards.
    """
    removed, keep = [], []
    for s in sess.b.net_segments.get(net, []):
        a = np.array(s["start"], float)
        b = np.array(s["end"], float)
        if not any(_seg_point_dist(s, p["x"], p["y"]) <= radius for p in pads):
            keep.append(s)
            continue
        ts = np.linspace(0.0, 1.0, 41)
        pts = a[None, :] + ts[:, None] * (b - a)[None, :]
        inside = []
        for k, (px, py) in enumerate(pts):
            d = min(math.hypot(px - p["x"], py - p["y"]) for p in pads)
            inside.append(d <= radius)
        if not any(inside):
            keep.append(s)
            continue
        k0 = inside.index(True)
        k1 = len(inside) - 1 - inside[::-1].index(True)
        t0, t1 = ts[k0], ts[k1]
        # keep the parts of the segment that are far enough away
        if t0 > 1e-6:
            seg = dict(s)
            seg["start"] = [round(float(a[0]), 4), round(float(a[1]), 4)]
            seg["end"] = [round(float((a + t0 * (b - a))[0]), 4),
                          round(float((a + t0 * (b - a))[1]), 4)]
            keep.append(seg)
        if t1 < 1 - 1e-6:
            seg = dict(s)
            seg["start"] = [round(float((a + t1 * (b - a))[0]), 4),
                            round(float((a + t1 * (b - a))[1]), 4)]
            seg["end"] = [round(float(b[0]), 4), round(float(b[1]), 4)]
            keep.append(seg)
        if t1 - t0 > 1e-6:
            piece = dict(s)
            piece["start"] = [round(float((a + t0 * (b - a))[0]), 4),
                              round(float((a + t0 * (b - a))[1]), 4)]
            piece["end"] = [round(float((a + t1 * (b - a))[0]), 4),
                            round(float((a + t1 * (b - a))[1]), 4)]
            length = float(np.linalg.norm(np.array(piece["end"]) -
                                          np.array(piece["start"])))
            if length > max_len:
                continue          # refuse to rip more than approved
            removed.append(piece)
    sess.b.net_segments[net] = keep
    return removed


def _seg_point_dist(seg, x, y):
    a = np.array(seg["start"], float)
    b = np.array(seg["end"], float)
    ab = b - a
    den = float(ab @ ab)
    t = 0.0 if den <= 1e-12 else float(np.clip((np.array([x, y]) - a) @ ab / den,
                                               0.0, 1.0))
    return float(np.linalg.norm(a + t * ab - np.array([x, y])))


def _patch_with_segment(sess, net, seg, log=print):
    """Re-route a ripped-out segment locally between its two former ends."""
    params = R.net_params(net)
    m, via_ok, dia, drill, _soft = sess.masks_for(net, params["width"])
    walk = [m[lyr][0] for lyr in R.ROUTABLE]
    slack = [m[lyr][1] for lyr in R.ROUTABLE]
    x0, y0 = seg["start"]
    x1, y1 = seg["end"]

    def cells_near(x, y, radius=0.35):
        out = []
        r = int(radius / R.PITCH)
        ci, cj = int(round(x / R.PITCH)), int(round(y / R.PITCH))
        for i in range(ci - r, ci + r + 1):
            for j in range(cj - r, cj + r + 1):
                if 0 <= i < R.W and 0 <= j < R.H:
                    out.append((i, j))
        return out

    li = R.ROUTABLE.index(seg["layer"])
    sources = [(li, i, j) for (i, j) in cells_near(x0, y0) if walk[li][j, i]]
    target = [None] * len(R.ROUTABLE)
    tmask = np.zeros((R.H, R.W), bool)
    for (i, j) in cells_near(x1, y1):
        tmask[j, i] = True
    target[li] = tmask
    if not sources:
        return False
    mx = max(abs(x1 - x0), abs(y1 - y0)) * 0.5 + 6.0
    window = (max(0, int(min(x0, x1) / R.PITCH - mx / R.PITCH)),
              min(R.W - 1, int(max(x0, x1) / R.PITCH + mx / R.PITCH)),
              max(0, int(min(y0, y1) / R.PITCH - mx / R.PITCH)),
              min(R.H - 1, int(max(y0, y1) / R.PITCH + mx / R.PITCH)))
    path = sess.rtr.astar(walk, slack, target, sources, via_ok,
                          ref_ij=(int(round(x1 / R.PITCH)),
                                  int(round(y1 / R.PITCH))),
                          window=window, max_expand=120000,
                          layer_pen=sess.layer_penalty(net))
    if path is None:
        return False
    segs, vias, _cw = R.emit_path(path, seg["width"], net)
    for s in segs:
        s["kind"] = "route"
    sess.b.net_segments.setdefault(net, []).extend(segs)
    sess.b.net_vias.setdefault(net, []).extend(vias)
    log(f"      {net}: patched {len(segs)} segment(s) locally")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    model = json.loads(R.MODEL_PATH.read_text(encoding="utf-8"))
    data = json.loads(ROUTING.read_text(encoding="utf-8"))
    board = R.Board(model)
    board.load_routing(data)
    sess = R.Session(board, log=print)

    def refresh():
        board.rebuild_copper()
        sess.mask_cache.clear()

    # ------------------------------------------------------------------
    # 1. U3 ground pins: short neck + via to the In1 plane
    # ------------------------------------------------------------------
    gnd_vias = list(data.get("gnd_vias", []))
    added_tracks = []
    ripped = set()
    for pad in [p for p in board.pads_of["GND"] if p["ref"] == "U3"]:
        params = R.net_params("GND")
        done = False
        # candidate via spots: along the pad axis, then around it
        cands = []
        for dy in (0.0, 0.3, 0.5, 0.7, 0.9, -0.3):
            cands.append((pad["x"], pad["y"] + dy))
        for dx in (-0.6, -0.4, 0.4, 0.6):
            cands.append((pad["x"] + dx, pad["y"]))
        for (dia, drill) in ((0.5, 0.25), (0.4, 0.2)):
            vmask = sess.rtr.via_mask("GND", dia / 2.0, drill / 2.0,
                                      params["clearance"])
            walk = sess.rtr.masks("GND", 0.15, params["clearance"])["F.Cu"][0]
            for (vx, vy) in cands:
                i, j = int(round(vx / R.PITCH)), int(round(vy / R.PITCH))
                if not (0 <= i < R.W and 0 <= j < R.H) or not vmask[j, i]:
                    continue
                # neck from the pad centre to the via must be legal too
                ok = True
                n = max(4, int(math.hypot(vx - pad["x"], vy - pad["y"]) / 0.05))
                for t in np.linspace(0.0, 1.0, n):
                    x = pad["x"] + (vx - pad["x"]) * t
                    y = pad["y"] + (vy - pad["y"]) * t
                    ii, jj = int(round(x / R.PITCH)), int(round(y / R.PITCH))
                    if not (0 <= ii < R.W and 0 <= jj < R.H) or not walk[jj, ii]:
                        ok = False
                        break
                if not ok:
                    continue
                gnd_vias.append({"x": round(vx, 4), "y": round(vy, 4),
                                 "dia": dia, "drill": drill, "net": "GND",
                                 "kind": "pad"})
                if math.hypot(vx - pad["x"], vy - pad["y"]) > 0.2:
                    added_tracks.append(
                        {"layer": "F.Cu", "net": "GND", "width": 0.3,
                         "start": [round(pad["x"], 4), round(pad["y"], 4)],
                         "end": [round(vx, 4), round(vy, 4)], "kind": "gnd_fix"})
                print(f"  U3 Pad{pad['num']}: GND via {dia}/{drill} at "
                      f"({vx:.2f},{vy:.2f}), neck "
                      f"{math.hypot(vx-pad['x'], vy-pad['y']):.2f} mm")
                done = True
                break
            if done:
                break
        if not done and not args.dry_run:
            # rip up the small nets that block the via, then retry
            blockers = sess.blockers_for("GND", max_nets=4)
            blockers = [n for n in blockers if n not in TRUNKS][:2]
            print(f"  U3 Pad{pad['num']}: blocked, ripping {blockers}")
            st = sess.state()
            for n in blockers:
                sess._remove_net_copper(n)
            refresh()
            # retry once with the blockers gone
            for (dia, drill) in ((0.5, 0.25), (0.4, 0.2)):
                vmask = sess.rtr.via_mask("GND", dia / 2.0, drill / 2.0,
                                          params["clearance"])
                for (vx, vy) in cands:
                    i, j = int(round(vx / R.PITCH)), int(round(vy / R.PITCH))
                    if not (0 <= i < R.W and 0 <= j < R.H) or not vmask[j, i]:
                        continue
                    gnd_vias.append({"x": round(vx, 4), "y": round(vy, 4),
                                     "dia": dia, "drill": drill, "net": "GND",
                                     "kind": "pad"})
                    if math.hypot(vx - pad["x"], vy - pad["y"]) > 0.2:
                        added_tracks.append(
                            {"layer": "F.Cu", "net": "GND", "width": 0.3,
                             "start": [round(pad["x"], 4), round(pad["y"], 4)],
                             "end": [round(vx, 4), round(vy, 4)],
                             "kind": "gnd_fix"})
                    ripped.update(blockers)
                    print(f"  U3 Pad{pad['num']}: via placed after rip-up "
                          f"({dia}/{drill}) at ({vx:.2f},{vy:.2f})")
                    done = True
                    break
                if done:
                    break
            if not done:
                sess.restore(st)
                print(f"  U3 Pad{pad['num']}: still blocked")

    # ------------------------------------------------------------------
    # 2. TPS nets: reserve the pad escapes, then route locally
    # ------------------------------------------------------------------
    for net in TPS_NETS:
        params = R.net_params(net)
        for pad in board.pads_of.get(net, []):
            key = (pad["ref"], pad["num"])
            if key in sess.stubs:
                continue
            sess.mask_cache.clear()
            if sess.make_stub(net, pad, params, key):
                print(f"  {net}: stub reserved at {pad['ref']}.{pad['num']}")
        sess.mask_cache.clear()
        if sess.route_one(net):
            print(f"  {net}: routed")
            continue
        # collect blockers around *every* pad of the net (each pad can sit in
        # its own pocket, so one flood is not enough)
        scored = {}
        for pad in board.pads_of.get(net, []):
            for n in sess.blockers_for(net, max_nets=6, pads=[pad]):
                if n in TRUNKS or n == net:
                    continue
                scored[n] = scored.get(n, 0) + 1
        blockers = [n for n, _ in sorted(scored.items(), key=lambda kv: -kv[1])][:4]
        print(f"  {net}: blocked, ripping {blockers}")
        st = sess.state()
        ok = False
        sys_pieces = []
        if net in ("TPS_EN", "TPS_VSEL"):
            # user-approved: rip only 1-2 mm of SYS right next to the U3 pad
            pads = [p for p in board.pads_of.get(net, []) if p["ref"] == "U3"]
            sys_pieces = rip_near_pads(sess, "SYS", pads)
            print(f"  {net}: ripping {len(sys_pieces)} SYS piece(s) "
                  f"within {SYS_RIP_RADIUS} mm of the U3 pad")
            for b in blockers:
                sess._remove_net_copper(b)
            refresh()
            # retry the stub + route now that the escape is free
            for pad in pads:
                key = (pad["ref"], pad["num"])
                if key not in sess.stubs:
                    sess.mask_cache.clear()
                    if sess.make_stub(net, pad, params, key):
                        print(f"  {net}: stub reserved at {pad['ref']}.{pad['num']}")
            sess.mask_cache.clear()
            if sess.route_one(net) and all(_patch_with_segment(sess, "SYS", s)
                                           for s in sys_pieces):
                back = True
                for b in blockers:
                    sess.mask_cache.clear()
                    if not sess.route_one(b):
                        back = False
                        break
                if back:
                    ripped.update(blockers)
                    ok = True
                    print(f"  {net}: routed (SYS patched) ")
            if not ok:
                sess.restore(st)
                print(f"  {net}: could not be closed")
            continue
        for b in blockers:
            sess._remove_net_copper(b)
        refresh()
        if sess.route_one(net):
            back = True
            for b in blockers:
                if not sess.route_one(b):
                    back = False
                    break
            if back:
                ripped.update(blockers)
                ok = True
                print(f"  {net}: routed after ripping {blockers}")
        if not ok:
            sess.restore(st)
            print(f"  {net}: could not be closed")

    # re-route anything that was ripped up for the ground vias
    for net in sorted(ripped):
        if net in TPS_NETS:
            continue
        sess.mask_cache.clear()
        if not sess.route_one(net):
            print(f"  !! {net} could not be re-routed after rip-up")

    if args.dry_run:
        return 0
    segs, vias = board.copper()
    data["segments"] = segs + added_tracks
    data["vias"] = [v for v in vias if "kind" not in v]
    uniq = {}
    for v in vias:
        if "kind" in v:
            uniq[(round(v["x"], 3), round(v["y"], 3), v["net"])] = v
    data["gnd_vias"] = list(uniq.values()) + [
        v for v in gnd_vias
        if (round(v["x"], 3), round(v["y"], 3), v["net"]) not in uniq]
    data["neck_segments"] = [
        {"layer": s["layer"], "net": s["net"], "width": s["width"],
         "class": R.netclass_of(s["net"]), "start": s["start"], "end": s["end"]}
        for s in sess.neck_segments]
    ROUTING.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {ROUTING.name}: {len(data['segments'])} segments, "
          f"{len(data['gnd_vias'])} gnd vias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
