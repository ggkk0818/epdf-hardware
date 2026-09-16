#!/usr/bin/env python3
"""Grid based 4-layer router for the ESP32-S3 + GDEM102T91 mainboard.

Stack (see PCB_LAYOUT_NOTES.md):

    L1 F.Cu    signals (microstrip reference = solid L2)
    L2 In1.Cu  solid GND plane - never routed
    L3 In2.Cu  signals / power
    L4 B.Cu    signals / power

GND is not routed as tracks: the L1/L2/L4 pours plus stitching vias carry it.
Every other net is routed by a multi-terminal A* maze router on a 0.1 mm grid
with 45 degree moves in open areas and Manhattan staircases where the room is
tight.  Obstacle distances come from exact rounded-rectangle signed distance
functions of the real pad/track geometry, so the emitted copper honours the
actual clearance rules instead of a raster approximation.

Power nets are routed at the net class width (0.8 mm) wherever the geometry
allows and are necked down only inside the footprint pad field; the necked
segments are reported so that tools/apply_routing.py can publish matching DRC
rule areas.

    & 'C:\\Program Files\\KiCad\\10.0\\bin\\python.exe' tools\\route.py

Writes routing/routing.json.
"""

from __future__ import annotations

import argparse
import fnmatch
import heapq
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "routing" / "model.json"
PRO_PATH = ROOT / "esp32-board-v1.1.kicad_pro"
OUT_PATH = ROOT / "routing" / "routing.json"

PITCH = 0.1
BW, BH = 55.0, 84.0
W = int(round(BW / PITCH)) + 1          # 551
H = int(round(BH / PITCH)) + 1          # 841
ROUTABLE = ("F.Cu", "In2.Cu", "B.Cu")
ALL_CU = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
LAYER_OF_ID = {0: "F.Cu", 4: "In1.Cu", 6: "In2.Cu", 2: "B.Cu"}

EPS = 0.02          # grid discretisation allowance for axis aligned moves (mm)
DIAG_MARGIN = 0.10  # extra slack required at both ends of a 45 degree move
MAXD = 0.95         # distance field saturation (mm)
STEP = 100          # cost of one axis aligned 0.1 mm step (unit = 0.001 mm)
DIAG = 141          # cost of one 45 degree step
DIAG_STEP = 70      # heuristic scale (admissible with 45 degree moves)
# Every SMD pad is on F.Cu, so the two inner layers are pad free.  Making F.Cu
# slightly expensive keeps it for pad escapes and short links and pushes the
# long runs onto In2.Cu / B.Cu, which is what relieves the dense clusters.
VIA_COST = 1900     # cost of a layer change (1.9 mm of track)
LAYER_PENALTY = {"F.Cu": 5, "In2.Cu": 1, "B.Cu": 0}
WIDE_MIN_RUN = 4    # cells of contiguous room needed before widening a neck
STUB_MIN = 1.0      # a fan-out stub may stop this far from the pad centre (mm)
STUB_SLACK = 12     # fewer walkable ring cells than this => reserve a stub
STUB_ALL = False    # True: reserve a stub at every pad, not just pinched ones

BOARD_CX, BOARD_CY, BOARD_HX, BOARD_HY, BOARD_R = 27.5, 42.0, 27.5, 42.0, 2.0

# Routing order: tight switching loops first, then the USB pair (it needs a
# clean corridor), then power, then everything else shortest-span-first.
TIERS = [
    ["CHG_SW", "CHG_SNUB", "CHG_BTST", "CHG_PMID", "CHG_REGN", "CHG_ILIM"],
    ["TPS_L1", "TPS_VAUX", "TPS_FB", "TPS_PG", "TPS_EN",
     "TPS_VSEL", "TPS_PS_SYNC"],
    ["EPD_SW", "EPD_GDR", "EPD_RESE", "EPD_X"],
    # MD §6: after the local switching loops, the highest-constraint nets get
    # the first pick of the remaining board
    ["TPS_L2", "SYS", "USB_DP_CONN", "USB_DN_CONN", "EPD_VGH"],
    ["EPD_VGL", "EPD_VSH1", "EPD_VSH2", "EPD_VSL", "EPD_VDD",
     "EPD_VCOM"],
    ["USB_DP", "USB_DN", "USB_CC1", "USB_CC2", "USB_SHIELD", "USB_VBUS_DET"],
    ["SPI_SCLK", "SPI_MOSI", "SPI_MISO", "I2C_SCL", "I2C_SDA", "TF_CS_N",
     "TF_SCLK", "TF_MOSI", "TF_MISO", "TF_CD_N", "EPD_CS_N", "EPD_DC",
     "EPD_RST_N", "EPD_BUSY", "EPD_PWR_EN", "KEY1_N", "KEY2_N", "KEY3_N",
     "CHG_CE", "CHG_STAT", "CHG_OTG", "CHG_TS", "CHG_INT_N", "CHG_DSEL",
     "TYPEC_INT_N", "FG_ALRT_N", "BOOT", "RESET_N"],
    # power goes last: those nets may pick any layer or detour, the fine pitch
    # signal pads may not
    ["BAT_BUS", "BAT1_RAW", "BAT2_RAW", "EPD_3V3", "3V3_MAIN",
     "USB_VBUS_RAW", "USB_VBUS_PROT"],
    [],   # anything left, shortest span first
]

# differential pair: partner -> (coupling target net, band inner/outer cells)
PAIRS = {"USB_DN_CONN": ("USB_DP_CONN", 4, 7), "USB_DN": ("USB_DP", 4, 7)}
# the USB pair is a controlled impedance microstrip on L1 over the L2 plane
ON_L1 = {"USB_DP_CONN", "USB_DN_CONN", "USB_DP", "USB_DN"}

NEVER_ROUTE = {"GND", ""}
DEBUG = False
DEBUG_POP_CAP = 40000

# --- V1.6 routing decisions (ESP32S3_GDEM102T91_V1.6_Routing_Power_Width_and_
# --- R29_Confirmation.md, 2026-09-16) --------------------------------------
# POWER default routing width is 0.50 mm.  The high current trunks may be
# widened further (or poured) where the geometry allows ...
WIDE_BUS = {"BAT_BUS", "BAT1_RAW", "BAT2_RAW", "SYS", "3V3_MAIN",
            "USB_VBUS_RAW", "USB_VBUS_PROT"}
WIDE_TARGET = 0.80          # trunk target width for WIDE_BUS nets
# ... while the switching nodes stay short, small and via free.
NO_VIA = {"CHG_SW", "TPS_L1", "TPS_L2", "EPD_SW"}


# ---------------------------------------------------------------------------
# net classes (read straight from the project file)
# ---------------------------------------------------------------------------


def load_netclasses():
    pro = json.loads(PRO_PATH.read_text(encoding="utf-8"))
    ns = pro["net_settings"]
    classes = {c["name"]: c for c in ns["classes"]}
    patterns = [(p["pattern"], p["netclass"]) for p in ns["netclass_patterns"]]
    return classes, patterns


CLASSES, PATTERNS = load_netclasses()


def netclass_of(net):
    for pat, cls in PATTERNS:
        if fnmatch.fnmatch(net, pat):
            return cls
    return "Default"


def net_params(net):
    cls = netclass_of(net)
    c = CLASSES[cls]
    return {"class": cls, "width": c["track_width"], "clearance": c["clearance"],
            "via_dia": c["via_diameter"], "via_drill": c["via_drill"]}


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


class Shape:
    """Rounded rectangle; covers rect / roundrect / oval / circle."""

    __slots__ = ("x", "y", "a", "b", "r", "rot", "cosr", "sinr", "net",
                 "x0", "y0", "x1", "y1", "hard")

    def __init__(self, x, y, a, b, r, rot, net, hard=True):
        self.x, self.y, self.a, self.b, self.r = x, y, a, b, r
        self.rot = rot
        self.cosr = math.cos(rot)
        self.sinr = math.sin(rot)
        self.net = net
        self.hard = hard
        ex = abs(a * self.cosr) + abs(b * self.sinr)
        ey = abs(a * self.sinr) + abs(b * self.cosr)
        self.x0, self.x1 = x - ex, x + ex
        self.y0, self.y1 = y - ey, y + ey

    def dist(self, X, Y):
        dx = X - self.x
        dy = Y - self.y
        if self.rot:
            lx = dx * self.cosr + dy * self.sinr
            ly = -dx * self.sinr + dy * self.cosr
        else:
            lx, ly = dx, dy
        qx = np.abs(lx) - (self.a - self.r)
        qy = np.abs(ly) - (self.b - self.r)
        d = (np.minimum(np.maximum(qx, qy), 0.0)
             + np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0)) - self.r)
        return np.maximum(d, 0.0).astype(np.float32)


class Obstacles:
    def __init__(self):
        self.by = {lyr: {"lo": [], "hi": [], "hole": [], "res": []}
                   for lyr in ALL_CU}

    def add(self, layer, group, shape):
        self.by[layer][group].append(shape)

    def snapshot(self):
        return {lyr: {g: len(v) for g, v in self.by[lyr].items()} for lyr in ALL_CU}

    def rollback(self, snap):
        for lyr in ALL_CU:
            for g, n in snap[lyr].items():
                lst = self.by[lyr][g]
                if len(lst) > n:
                    del lst[n:]

    def field(self, layer, group, exclude_net, maxd=MAXD, only_net=None,
              hard=None):
        f = np.full((H, W), maxd, np.float32)
        for s in self.by[layer][group]:
            if s.net == exclude_net or (only_net is not None and s.net != only_net):
                continue
            if hard is not None and s.hard != hard:
                continue
            i0 = max(0, int((s.x0 - maxd) / PITCH) - 1)
            i1 = min(W - 1, int((s.x1 + maxd) / PITCH) + 1)
            j0 = max(0, int((s.y0 - maxd) / PITCH) - 1)
            j1 = min(H - 1, int((s.y1 + maxd) / PITCH) + 1)
            if i1 < i0 or j1 < j0:
                continue
            xs = (np.arange(i0, i1 + 1) * PITCH).astype(np.float32)
            ys = (np.arange(j0, j1 + 1) * PITCH).astype(np.float32)
            X, Y = np.meshgrid(xs, ys)
            d = s.dist(X, Y)
            view = f[j0:j1 + 1, i0:i1 + 1]
            np.minimum(view, d, out=view)
        return f


_BOARD_MARGIN_CACHE: dict = {}


def board_margin(clear):
    key = round(clear, 3)
    hit = _BOARD_MARGIN_CACHE.get(key)
    if hit is not None:
        return hit
    xs = (np.arange(W) * PITCH).astype(np.float32)
    ys = (np.arange(H) * PITCH).astype(np.float32)
    X, Y = np.meshgrid(xs, ys)
    qx = np.maximum(np.abs(X - BOARD_CX) - (BOARD_HX - BOARD_R), 0.0)
    qy = np.maximum(np.abs(Y - BOARD_CY) - (BOARD_HY - BOARD_R), 0.0)
    sdf = np.hypot(qx, qy) - BOARD_R
    out = (sdf + clear) <= 0.0
    _BOARD_MARGIN_CACHE[key] = out
    return out


def _cell_range(x0, y0, x1, y1, pad=0.0):
    i0 = max(0, int(math.floor((x0 - pad) / PITCH)))
    i1 = min(W - 1, int(math.ceil((x1 + pad) / PITCH)))
    j0 = max(0, int(math.floor((y0 - pad) / PITCH)))
    j1 = min(H - 1, int(math.ceil((y1 + pad) / PITCH)))
    return i0, i1, j0, j1


def _seg_in_box(seg, box):
    """Does the segment's (inflated) bounding box meet the box?"""
    x0, y0, x1, y1 = box
    half = seg["width"] / 2.0
    sx0 = min(seg["start"][0], seg["end"][0]) - half
    sx1 = max(seg["start"][0], seg["end"][0]) + half
    sy0 = min(seg["start"][1], seg["end"][1]) - half
    sy1 = max(seg["start"][1], seg["end"][1]) + half
    return not (sx0 > x1 or sx1 < x0 or sy0 > y1 or sy1 < y0)


def _seg_seg_gap(a, b):
    """Exact gap between two segments' copper edges (0 if they touch)."""
    p0, p1 = np.array(a["start"], float), np.array(a["end"], float)
    q0, q1 = np.array(b["start"], float), np.array(b["end"], float)
    if _segments_cross(p0, p1, q0, q1):
        d = 0.0
    else:
        def pt_seg(p, s0, s1):
            v = s1 - s0
            den = float(v @ v)
            t = 0.0 if den <= 1e-12 else float(np.clip((p - s0) @ v / den, 0, 1))
            return float(np.linalg.norm(s0 + t * v - p))
        d = min(pt_seg(p0, q0, q1), pt_seg(p1, q0, q1),
                pt_seg(q0, p0, p1), pt_seg(q1, p0, p1))
    return d - (a["width"] + b["width"]) / 2.0


def _segments_cross(p0, p1, q0, q1):
    def cr(u, v):
        return float(u[0] * v[1] - u[1] * v[0])

    d1, d2 = cr(p1 - p0, q0 - p0), cr(p1 - p0, q1 - p0)
    d3, d4 = cr(q1 - q0, p0 - q0), cr(q1 - q0, p1 - q0)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def mark_cells(mask, cells, half_w):
    d = max(1, int(math.ceil((half_w + 0.03) / PITCH)))
    for cell in cells:
        i, j = cell[1], cell[2]
        i0, i1 = max(0, i - d), min(W - 1, i + d)
        j0, j1 = max(0, j - d), min(H - 1, j + d)
        mask[j0:j1 + 1, i0:i1 + 1] = True


# ---------------------------------------------------------------------------
# board
# ---------------------------------------------------------------------------


class Board:
    def __init__(self, model):
        self.model = model
        self.ob = Obstacles()
        self.keepout = {lyr: np.zeros((H, W), bool) for lyr in ALL_CU}
        self.pads = []
        self.pads_of = {}
        self.net_segments = {}
        self.net_vias = {}
        self.pad_obstacles = []
        self.fp_centre = {f["ref"]: (f["x"], f["y"]) for f in model["footprints"]}
        self._build_pads()
        self._build_keepouts()

    def _shape_from_pad(self, p):
        w, h = p["w"], p["h"]
        kind = p["shape"]
        if kind == "circle":
            a = b = r = min(w, h) / 2.0
        elif kind == "oval":
            # stadium: full extent along x is w, along y is h - swapping these
            # used to rotate every oval pad by 90 degrees (J1's shield pads)
            a, b, r = w / 2.0, h / 2.0, min(w, h) / 2.0
        elif kind in ("roundrect", "chamfered_rect"):
            a, b = w / 2.0, h / 2.0
            r = min(a, b) * max(p.get("rr_ratio", 0.25), 0.0)
        else:
            a, b, r = w / 2.0, h / 2.0, 0.0
        return Shape(p["x"], p["y"], a, b, r, math.radians(p["rot"]), p["net"])

    def _build_pads(self):
        for raw in self.model["pads"]:
            p = dict(raw)
            if p["type"] == "npth":
                if p["drill"] > 0:
                    r = p["drill"] / 2.0
                    hole = Shape(p["x"], p["y"], r, r, r, 0.0, "<hole>")
                    for lyr in ALL_CU:
                        self.ob.add(lyr, "hole", hole)
                        self.pad_obstacles.append((lyr, "hole", hole))
                continue
            if not p["layers"]:
                continue
            cu = [LAYER_OF_ID[l] for l in p["layers"] if l in LAYER_OF_ID]
            p["cu_layers"] = cu
            if p["type"] == "pth" and p["drill"] > 0:
                # model the barrel as a hole too: vias must keep the
                # hole-to-hole clearance from pads that are already drilled
                r = p["drill"] / 2.0
                hole = Shape(p["x"], p["y"], r, r, r, 0.0, "<hole>")
                for lyr in ALL_CU:
                    self.ob.add(lyr, "hole", hole)
                    self.pad_obstacles.append((lyr, "hole", hole))
            group = "hi" if (not p["net"]
                             or net_params(p["net"])["clearance"] > 0.15) else "lo"
            shape = self._shape_from_pad(p)
            for lyr in cu:
                self.ob.add(lyr, group, shape)
                self.pad_obstacles.append((lyr, group, shape))
            p["cells"] = self._pad_cells(p)
            self.pads.append(p)
            if p["net"]:
                self.pads_of.setdefault(p["net"], []).append(p)

    def _pad_cells(self, p):
        s = self._shape_from_pad(p)
        half = max(p["w"], p["h"]) / 2.0
        i0, i1, j0, j1 = _cell_range(p["x"] - half, p["y"] - half,
                                     p["x"] + half, p["y"] + half, 0.1)
        xs = (np.arange(i0, i1 + 1) * PITCH).astype(np.float32)
        ys = (np.arange(j0, j1 + 1) * PITCH).astype(np.float32)
        X, Y = np.meshgrid(xs, ys)
        d = s.dist(X, Y)
        cells = [(i0 + a, j0 + b) for b, a in zip(*np.nonzero(d <= 0.0))]
        if not cells:
            cells = [(int(round(p["x"] / PITCH)), int(round(p["y"] / PITCH)))]
        return cells

    def _build_keepouts(self):
        self.keepout_dil = {lyr: np.zeros((H, W), bool) for lyr in ALL_CU}
        for ko in self.model["keepouts"]:
            k = ko.get("keepout", {})
            if not (k.get("tracks") or k.get("vias")):
                continue
            if not ko["polygon"]:
                continue
            xs = [q[0] for q in ko["polygon"]]
            ys = [q[1] for q in ko["polygon"]]
            i0, i1, j0, j1 = _cell_range(min(xs), min(ys), max(xs), max(ys))
            for lyr in ko["layers"]:
                if lyr in self.keepout and i1 >= i0 and j1 >= j0:
                    self.keepout[lyr][j0:j1 + 1, i0:i1 + 1] = True
        # vias are wider than tracks: keep their centres clear of the keepout
        # boundary as well (a 0.6 mm via needs 0.3 mm)
        for lyr in ALL_CU:
            self.keepout_dil[lyr] = dilate(self.keepout[lyr], 4)

    # -- preload existing copper (retry passes / debugging) --------------
    def copper(self):
        segs = [s for v in self.net_segments.values() for s in v]
        vias = [v for v in self.net_vias.values() for v in v]
        return segs, vias

    def rebuild_copper(self):
        """Re-derive the obstacle model from pads + the committed copper."""
        segs, vias = self.copper()
        self.ob = Obstacles()
        for (lyr, grp, shape) in self.pad_obstacles:
            self.ob.add(lyr, grp, shape)
        self.net_segments = {}
        self.net_vias = {}
        self.load_routing({"segments": segs, "vias": vias})

    def load_routing(self, data):
        for s in data.get("segments", []):
            params = net_params(s["net"])
            x0, y0 = s["start"]
            x1, y1 = s["end"]
            half = s["width"] / 2.0
            grp = "hi" if params["clearance"] > 0.15 else "lo"
            self.ob.add(s["layer"], grp,
                        Shape((x0 + x1) / 2.0, (y0 + y1) / 2.0,
                              abs(x1 - x0) / 2.0 + half,
                              abs(y1 - y0) / 2.0 + half, 0.0, 0.0, s["net"]))
            self.net_segments.setdefault(s["net"], []).append(s)
        for v in data.get("vias", []) + data.get("gnd_vias", []):
            params = net_params(v["net"])
            grp = "hi" if params["clearance"] > 0.15 else "lo"
            r = v["dia"] / 2.0
            for lyr in ALL_CU:
                self.ob.add(lyr, grp, Shape(v["x"], v["y"], r, r, r, 0.0, v["net"]))
            self.net_vias.setdefault(v["net"], []).append(v)


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------


class Router:
    """A* over a padded grid so that no index arithmetic can wrap."""

    def __init__(self, board):
        self.b = board
        self.PW, self.PH = W + 2, H + 2
        self.size = self.PW * self.PH
        self.n = len(ROUTABLE) * self.size
        self.g = np.zeros(self.n, np.int32)
        self.par = np.zeros(self.n, np.int32)
        self.state = np.zeros(self.n, np.uint8)   # 0 new, 1 open, 2 closed
        self.stamp = np.zeros(self.n, np.int32)
        self.epoch = 0
        self.expansions = 0

    def masks(self, net, half_w, clear):
        """Per layer (walk, slack) using *all* foreign copper (hard rule)."""
        return self._masks(net, half_w, clear, hard=None)

    def hard_masks(self, net, half_w, clear):
        """Per layer (walk, slack) treating copper as soft (pads stay hard)."""
        return self._masks(net, half_w, clear, hard=True)

    def _masks(self, net, half_w, clear, hard):
        rec_lo = half_w + max(clear, 0.15) + EPS
        rec_hi = half_w + max(clear, 0.20) + EPS
        rec_hole = half_w + max(clear, 0.15) + EPS
        rec_res = half_w + max(clear, 0.22) + EPS
        edge = board_margin(half_w + 0.30 + 0.05)
        # a rule area has to be respected by the whole track, not just by its
        # centre line: dilate the keep-out by the track half width
        kd = max(0, int(math.ceil((half_w + 0.02) / PITCH)))
        out = {}
        for lyr in ROUTABLE:
            s1 = self.b.ob.field(lyr, "lo", net, hard=hard) - rec_lo
            s2 = self.b.ob.field(lyr, "hi", net, hard=hard) - rec_hi
            s3 = self.b.ob.field(lyr, "hole", net, hard=hard) - rec_hole
            slack = np.minimum(np.minimum(s1, s2), s3)
            if self.b.ob.by[lyr]["res"]:
                s4 = self.b.ob.field(lyr, "res", net, hard=hard) - rec_res
                np.minimum(slack, s4, out=slack)
            keep = self.b.keepout[lyr] if kd == 0 \
                else dilate(self.b.keepout[lyr], kd)
            walk = (slack >= 0.0) & edge & ~keep
            out[lyr] = (walk, slack)
        return out

    def soft_cost(self, net, half_w, clear, hist=None):
        """Penalty (cost units) for routing near foreign *copper*.

        Zero where the clearance is met, strongly positive where it is not, so
        the maze can still find a path through a congested cluster and the
        negotiation loop can move the offenders out of the way.
        """
        rec_lo = half_w + max(clear, 0.15) + EPS
        rec_hi = half_w + max(clear, 0.20) + EPS
        rec_hole = half_w + max(clear, 0.15) + EPS
        out = {}
        for lyr in ROUTABLE:
            v1 = rec_lo - self.b.ob.field(lyr, "lo", net, hard=False)
            v2 = rec_hi - self.b.ob.field(lyr, "hi", net, hard=False)
            v3 = rec_hole - self.b.ob.field(lyr, "hole", net, hard=False)
            pen = np.zeros((H, W), np.float32)
            for v in (v1, v2, v3):
                np.maximum(pen, v, out=pen)
            pen = np.where(pen > 0.0, 200.0 + 1600.0 * np.maximum(pen, 0.0), 0.0)
            if hist is not None:
                pen = pen + hist[lyr]
            out[lyr] = pen
        return out

    def via_mask(self, net, via_r, drill_r, clear, hard_only=False):
        hard = True if hard_only else None
        rec_lo = via_r + max(clear, 0.15) + EPS
        rec_hi = via_r + max(clear, 0.20) + EPS
        rec_hole = max(via_r + clear, drill_r + 0.25) + EPS
        rec_res = via_r + max(clear, 0.22) + EPS
        ok = board_margin(via_r + 0.30 + 0.05)
        for lyr in ALL_CU:
            if lyr == "In1.Cu":
                ok = ok & (self.b.ob.field(lyr, "hole", net, hard=hard) >= rec_hole)
                continue
            ok = ok & (self.b.ob.field(lyr, "lo", net, hard=hard) >= rec_lo)
            ok = ok & (self.b.ob.field(lyr, "hi", net, hard=hard) >= rec_hi)
            ok = ok & (self.b.ob.field(lyr, "hole", net, hard=hard) >= rec_hole)
            if self.b.ob.by[lyr]["res"]:
                ok = ok & (self.b.ob.field(lyr, "res", net, hard=hard) >= rec_res)
            ok = ok & ~self.b.keepout_dil[lyr]
            # a via that only grazes one of its own pads makes a marginal
            # connection (DRC "connection width" warning): require it either to
            # sit inside the pad or to stand clearly outside it
            own = self.b.ob.field(lyr, "lo", None, only_net=net, hard=hard)
            own = np.minimum(own, self.b.ob.field(lyr, "hi", None, only_net=net,
                                                 hard=hard))
            ok = ok & ((own <= 0.001) | (own >= via_r + 0.12))
        return ok

    def astar(self, walk, slack, target, sources, via_ok, guide=None,
              ref_ij=None, slack_slack=0.0, window=None, max_expand=550000,
              layer_pen=None, soft=None):
        pen_layer = layer_pen or [LAYER_PENALTY[l] for l in ROUTABLE]
        PW, PH, size = self.PW, self.PH, self.size
        self.epoch += 1
        ep = self.epoch
        g, par, state, stamp = self.g, self.par, self.state, self.stamp
        tx, ty = (ref_ij[0] + 1, ref_ij[1] + 1) if ref_ij else (0, 0)
        nlay = len(ROUTABLE)

        def prep(mask):
            a = np.zeros((PH, PW), bool)
            a[1:H + 1, 1:W + 1] = mask
            if window is not None:
                i0, i1, j0, j1 = window
                a[:, :i0 + 1] = False
                a[:, i1 + 2:] = False
                a[:j0 + 1, :] = False
                a[j1 + 2:, :] = False
            return a.astype(np.uint8).tobytes()

        walkB = [prep(walk[k]) for k in range(nlay)]
        diagB = [prep(walk[k] & (slack[k] >= slack_slack)) for k in range(nlay)]
        viaB = prep(via_ok)
        targetB = [prep(t) if t is not None else None for t in target]
        hx = DIAG_STEP * np.abs(np.arange(PW) - tx)
        hy = DIAG_STEP * np.abs(np.arange(PH) - ty)
        hzero = 2 * DIAG_STEP
        guideB = []
        for lyr in range(nlay):
            if guide is None or guide[lyr] is None:
                guideB.append(None)
                continue
            a = np.zeros((PH, PW), np.int32)
            a[1:H + 1, 1:W + 1] = guide[lyr]
            guideB.append(a.tobytes())
        softB = []
        for lyr in range(nlay):
            if soft is None or soft[lyr] is None:
                softB.append(None)
                continue
            a = np.zeros((PH, PW), np.int32)
            a[1:H + 1, 1:W + 1] = soft[lyr]
            softB.append(a.reshape(-1))

        heap = []
        push = heapq.heappush
        for li, i, j in sources:
            idx = li * size + (j + 1) * PW + (i + 1)
            if stamp[idx] == ep and g[idx] == 0:
                continue
            h = hx[i + 1] + hy[j + 1] - hzero
            if h < 0:
                h = 0
            stamp[idx] = ep
            g[idx] = 0
            par[idx] = -1
            state[idx] = 1
            push(heap, (h, idx))

        found = None
        expansions = 0
        pop = heapq.heappop
        if DEBUG:
            tg_walk = [sum(1 for k2 in range(size)
                           if targetB[li2] is not None and targetB[li2][k2]) if False else None
                       for li2 in range(nlay)]
            print(f"    [astar] sources {len(sources)} heap {len(heap)} "
                  f"walkable {[sum(b) for b in walkB]}")
        while heap:
            f, idx = pop(heap)
            if stamp[idx] != ep or state[idx] == 2:
                continue
            diff = f - g[idx]
            li, rem = divmod(idx, size)
            j, i = divmod(rem, PW)
            if diff != max(0, hx[i] + hy[j] - hzero):
                if DEBUG and expansions < 5:
                    print(f"    [astar] stale pop f={f} g={g[idx]} h={max(0, hx[i]+hy[j]-hzero)}")
                continue
            state[idx] = 2
            expansions += 1
            if DEBUG and expansions < 25:
                print(f"    [pop {expansions}] li={li} i={i-1} j={j-1} f={f} "
                      f"g={g[idx]} h={max(0, hx[i]+hy[j]-hzero)} "
                      f"tgt={bool(targetB[li] is not None and targetB[li][rem])}")
            if DEBUG and g[idx] > 2500 and expansions < DEBUG_POP_CAP:
                print(f"    [far pop {expansions}] li={li} i={i-1} j={j-1} f={f} "
                      f"g={g[idx]} h={max(0, hx[i]+hy[j]-hzero)}")
            if expansions > max_expand:
                break
            tb = targetB[li]
            if tb is not None and tb[rem]:
                found = idx
                break
            wl = walkB[li]
            dl = diagB[li]
            pen = guideB[li]
            softl = softB[li]
            base = g[idx] + STEP + pen_layer[li]
            for doff in (1, -1, PW, -PW):
                if not wl[rem + doff]:
                    continue
                nidx = idx + doff
                ng = base
                if pen is not None:
                    ng += pen[rem + doff]
                if softl is not None:
                    ng += int(softl[rem + doff])
                if not (stamp[nidx] == ep and state[nidx] == 2) and (stamp[nidx] != ep or ng < g[nidx]):
                    stamp[nidx] = ep
                    state[nidx] = 1
                    g[nidx] = ng
                    par[nidx] = idx
                    hv = hx[nidx % PW] + hy[nidx // PW % PH] - hzero
                    if hv < 0:
                        hv = 0
                    push(heap, (ng + hv, nidx))
            if dl[rem]:
                dbase = g[idx] + DIAG + pen_layer[li]
                for doff in (PW + 1, PW - 1, -PW + 1, -PW - 1):
                    if not dl[rem + doff]:
                        continue
                    nidx = idx + doff
                    ng = dbase
                    if pen is not None:
                        ng += pen[rem + doff]
                    if softl is not None:
                        ng += int(softl[rem + doff])
                    if not (stamp[nidx] == ep and state[nidx] == 2) and (stamp[nidx] != ep or ng < g[nidx]):
                        stamp[nidx] = ep
                        state[nidx] = 1
                        g[nidx] = ng
                        par[nidx] = idx
                        hv = hx[nidx % PW] + hy[nidx // PW % PH] - hzero
                        if hv < 0:
                            hv = 0
                        push(heap, (ng + hv, nidx))
            if viaB[rem]:
                vbase = g[idx] + VIA_COST
                for li2 in range(nlay):
                    if li2 == li:
                        continue
                    if not walkB[li2][rem]:
                        continue
                    nidx = idx + (li2 - li) * size
                    ng = vbase
                    if guideB[li2] is not None:
                        ng += guideB[li2][rem]
                    if softB[li2] is not None:
                        ng += int(softB[li2][rem])
                    if not (stamp[nidx] == ep and state[nidx] == 2) and (stamp[nidx] != ep or ng < g[nidx]):
                        stamp[nidx] = ep
                        state[nidx] = 1
                        g[nidx] = ng
                        par[nidx] = idx
                        hv = hx[nidx % PW] + hy[nidx // PW % PH] - hzero
                        if hv < 0:
                            hv = 0
                        push(heap, (ng + hv, nidx))
        self.expansions = expansions
        if found is None:
            return None
        path = []
        idx = found
        while idx != -1:
            li, rem = divmod(idx, size)
            j, i = divmod(rem, PW)
            i -= 1
            j -= 1
            path.append((li, i, j))
            idx = par[idx]
        path.reverse()
        return path


# ---------------------------------------------------------------------------
# path -> copper
# ---------------------------------------------------------------------------


def emit_path(path, width_of, net, snap_end=None, snap_start=None):
    """Emit segments for a cell path; width_of(li, k) gives the width to use.

    Returns (segments, vias, cellwidths).
    """
    segments, vias = [], []
    cellwidths = []
    group, gw = [], None
    emitted_layers = []          # layer of the group that produced the last segment
    for k, cell in enumerate(path):
        w = width_of(cell[0], k) if callable(width_of) else width_of
        cellwidths.append((cell, w))
        if group and cell[0] != group[-1][0]:
            if len(group) >= 2:
                emitted_layers.append(group[0][0])
            _emit_group(group, gw, net, segments)
            vias.append({"x": round(cell[1] * PITCH, 4),
                         "y": round(cell[2] * PITCH, 4),
                         "dia": None, "drill": None, "net": net})
            group, gw = [cell], w
            continue
        if not group or (cell[0] == group[-1][0] and abs(w - gw) < 1e-9):
            group.append(cell)
            gw = w
        else:
            if len(group) >= 2:
                emitted_layers.append(group[0][0])
            _emit_group(group, gw, net, segments)
            group, gw = [cell], w
    if group:
        if len(group) >= 2:
            emitted_layers.append(group[0][0])
        _emit_group(group, gw, net, segments)
    # snapping is only legal when the final/first segment really sits on the
    # pad layer.  When the path ends with a via (or starts with one) the last
    # segment belongs to the *previous* layer and must not be stretched towards
    # a pad that lives on another layer - that produced tracks running through
    # neighbouring pads (found by tools/check_routing.py).
    if snap_start is not None and segments and emitted_layers \
            and emitted_layers[0] == path[0][0]:
        segments[0]["start"] = [round(snap_start[0], 4), round(snap_start[1], 4)]
    if snap_end is not None and segments and emitted_layers \
            and emitted_layers[-1] == path[-1][0]:
        segments[-1]["end"] = [round(snap_end[0], 4), round(snap_end[1], 4)]
    return ([s for s in segments if s["start"] != s["end"]], vias, cellwidths)


def _emit_group(group, width, net, segments):
    if len(group) < 2:
        return
    layer = ROUTABLE[group[0][0]]
    idx = [(i, j) for _, i, j in group]
    keep = [idx[0]]
    for k in range(1, len(idx) - 1):
        ax, ay = idx[k - 1]
        bx, by = idx[k]
        cx, cy = idx[k + 1]
        d1 = (bx - ax, by - ay)
        d2 = (cx - bx, cy - by)
        if d1 == d2:
            continue
        keep.append(idx[k])
    keep.append(idx[-1])
    for (ax, ay), (bx, by) in zip(keep, keep[1:]):
        segments.append({"layer": layer, "net": net, "width": round(width, 3),
                         "start": [round(ax * PITCH, 4), round(ay * PITCH, 4)],
                         "end": [round(bx * PITCH, 4), round(by * PITCH, 4)]})


def width_of_from_path(path, wide_ok_by_layer, wide_w, narrow_w):
    """Return a callable giving the width for each cell index."""
    runs = {}
    k = 0
    n = len(path)
    while k < n:
        li, i, j = path[k]
        ok = wide_ok_by_layer.get(li)
        good = ok is not None and ok[j, i]
        start = k
        while k + 1 < n and path[k + 1][0] == li:
            nli, ni, nj = path[k + 1]
            good2 = ok is not None and ok[nj, ni]
            if good2 != good:
                break
            k += 1
        if good and (k - start + 1) >= WIDE_MIN_RUN:
            for t in range(start, k + 1):
                runs[t] = wide_w
        k += 1

    def f(li, k):
        return runs.get(k, narrow_w)
    return f


# ---------------------------------------------------------------------------
# net routing
# ---------------------------------------------------------------------------


def mst_edges(pads):
    n = len(pads)
    if n < 2:
        return []
    cx = [p["x"] for p in pads]
    cy = [p["y"] for p in pads]
    inf = float("inf")
    dist = [inf] * n
    parent = [-1] * n
    used = [False] * n
    dist[0] = 0.0
    order = []
    for _ in range(n):
        best, bi = inf, -1
        for k in range(n):
            if not used[k] and dist[k] < best:
                best, bi = dist[k], k
        if bi < 0:
            break
        used[bi] = True
        order.append((bi, parent[bi]))
        for k in range(n):
            if used[k]:
                continue
            d = math.hypot(cx[bi] - cx[k], cy[bi] - cy[k])
            if d < dist[k]:
                dist[k] = d
                parent[k] = bi
    return order


def width_ladder(params):
    """Widths to *search* with; the result is widened afterwards.

    Searching narrow first keeps the maze fast and always finds a path when one
    exists (the FPC fan-out is 0.5 mm pitch, where a 0.8 mm track simply does
    not fit); tools/route.py then fattens every stretch that has room.
    """
    if params["class"] in ("POWER", "SWITCH_NODE"):
        return [0.5, 0.4, 0.3, 0.25, 0.2, 0.15]
    if params["class"] == "HV_EPD":
        return [0.3, 0.25, 0.2, 0.15]
    if params["class"] == "USB90":
        return [params["width"]]      # impedance controlled: no necking
    return [params["width"]]


class Session:
    def __init__(self, board, log=print):
        self.b = board
        self.rtr = Router(board)
        self.log = log
        self.failed = []
        self.neck_segments = []
        self.mask_cache = {}
        self.paths = {}
        self.stubs = {}          # (ref, num) -> {"tip": (li,i,j), "cells": [...]}
        self.hist = {lyr: np.zeros((H, W), np.float32) for lyr in ROUTABLE}
        self.net_keepout = {}    # net -> [(x0, y0, x1, y1)] route-only barriers
        self.span = {}
        for net, pads in board.pads_of.items():
            xs = [p["x"] for p in pads]
            ys = [p["y"] for p in pads]
            self.span[net] = max(max(xs) - min(xs), max(ys) - min(ys))

    def masks_for(self, net, width, soft=False, boost=None):
        params = net_params(net)
        if boost is None:
            boost = getattr(self, "clear_boost", 0.0)
        key = (net, round(width, 3), bool(soft), round(boost, 3))
        hit = self.mask_cache.get(key)
        if hit is not None:
            return hit
        clear = params["clearance"] + boost
        if soft:
            m = self.rtr.hard_masks(net, width / 2.0, clear)
            pen_d = self.rtr.soft_cost(net, width / 2.0, clear, self.hist)
            pen = [pen_d[lyr] for lyr in ROUTABLE]
        else:
            m = self.rtr.masks(net, width / 2.0, clear)
            pen = None
        boxes = self.net_keepout.get(net)
        if boxes:
            for (bx0, by0, bx1, by1) in boxes:
                i0, i1, j0, j1 = _cell_range(bx0, by0, bx1, by1)
                for lyr in ROUTABLE:
                    m[lyr][0][j0:j1 + 1, i0:i1 + 1] = False
        via_dia, via_drill = params["via_dia"], params["via_drill"]
        if width > 0.45:
            via_dia = max(via_dia, 0.8)
            via_drill = max(via_drill, 0.4)
        via_ok = self.rtr.via_mask(net, via_dia / 2.0, via_drill / 2.0, clear,
                                   hard_only=soft)
        val = (m, via_ok, via_dia, via_drill, pen)
        self.mask_cache[key] = val
        return val

    def layer_penalty(self, net):
        """Per net cost of using F.Cu / In2.Cu / B.Cu.

        Long nets are pushed onto the pad free inner layers so that they stop
        cutting the F.Cu pockets around the fine pitch parts; the USB pair is
        kept on L1 because its impedance is defined against the L2 plane.
        """
        if net in ON_L1:
            return (0, 25, 25)
        span = self.span.get(net, 0.0)
        if span > 15.0:
            return (12, 1, 0)
        if span > 8.0:
            return (7, 1, 0)
        return (1, 1, 0)

    def guide_for(self, net):
        pair = PAIRS.get(net)
        if not pair:
            return None
        partner, inner, outer = pair
        cells = self.paths.get(partner)
        if not cells:
            return None
        out = {}
        for li, lyr in enumerate(ROUTABLE):
            m = np.zeros((H, W), bool)
            for (pli, i, j) in cells:
                if pli == li:
                    m[j, i] = True
            if not m.any():
                out[li] = None
                continue
            d = dilate(m, outer) & ~dilate(m, inner)
            g = np.full((H, W), 150.0, np.float32)
            g[d] = 0.0
            out[li] = g
        return out

    # -- phase A: reserve one escape stub per pad ------------------------
    def fanout(self, order):
        """Route a short stub out of every pad *before* the main routing.

        Dense pad fields (BQ25895, TUSB320, ESP32 module, USB-C, FPC) have
        escapes that are only a few tenths of a millimetre wide.  Without a
        reservation the first nets routed wall them in; the stub keeps every
        pad reachable and later routing simply meets the stub tip.
        """
        made = failed = skipped = 0
        for net in order:
            params = net_params(net)
            self.mask_cache.clear()
            for pad in self.b.pads_of.get(net, []):
                key = (pad["ref"], pad["num"])
                if self.make_stub(net, pad, params, key):
                    made += 1
                elif key not in self.stubs:
                    failed += 1
        self.log(f"  fanout stubs: {made} placed, {failed} not needed/impossible")

    def make_stub(self, net, pad, params, key):
        b, rtr = self.b, self.rtr
        layers_ok = [li for li, lyr in enumerate(ROUTABLE)
                     if lyr in pad["cu_layers"]]
        if not layers_ok:
            return None
        # only pads whose escape is actually pinched need a reservation
        ci = int(round(pad["x"] / PITCH))
        cj = int(round(pad["y"] / PITCH))
        i0 = max(0, min(c[0] for c in pad["cells"]) - 1)
        i1 = min(W - 1, max(c[0] for c in pad["cells"]) + 1)
        j0 = max(0, min(c[1] for c in pad["cells"]) - 1)
        j1 = min(H - 1, max(c[1] for c in pad["cells"]) + 1)
        core = np.zeros((j1 - j0 + 1, i1 - i0 + 1), bool)
        for (i, j) in pad["cells"]:
            core[j - j0, i - i0] = True
        rr = core.copy()
        rr[1:, :] |= core[:-1, :]
        rr[:-1, :] |= core[1:, :]
        rr[:, 1:] |= core[:, :-1]
        rr[:, :-1] |= core[:, 1:]
        ring = rr & ~core
        wide_walk = self.masks_for(net, params["width"])[0]
        escapes = 0
        cols = np.nonzero(core.any(axis=0))[0]
        rows = np.nonzero(core.any(axis=1))[0]
        a0, a1 = cols[0], cols[-1]
        b0, b1 = rows[0], rows[-1]
        sides = []
        for li in layers_ok:
            sub = wide_walk[ROUTABLE[li]][0][j0:j1 + 1, i0:i1 + 1]
            escapes += int((ring & sub).sum())
            for (rr0, rr1, cc0, cc1) in (
                    (max(0, b0 - 1), b0, a0, a1 + 1),          # above
                    (b1 + 1, min(ring.shape[0], b1 + 2), a0, a1 + 1),   # below
                    (b0, b1 + 1, max(0, a0 - 1), a0),          # left
                    (b0, b1 + 1, a1 + 1, min(ring.shape[1], a1 + 2))):  # right
                if rr1 <= rr0 or cc1 <= cc0:
                    sides.append(0)
                    continue
                sides.append(int((ring[rr0:rr1, cc0:cc1]
                                  & sub[rr0:rr1, cc0:cc1]).sum()))
        open_sides = sum(1 for v in sides if v >= 3)
        # a pad with only one usable side has to be reserved even if that side
        # looks roomy right now
        if not STUB_ALL and open_sides >= 2 and escapes >= STUB_SLACK:
            return None
        # A deterministic, straight escape stub: it leaves the pad along the
        # axis that points away from the component centre (which is where the
        # pad's pads/body allow the track to go anyway) and stops 0.7 mm past
        # the pad's copper.  Being short and straight it cannot wall in the
        # neighbouring pads the way a maze-routed stub can.
        origin = self.b.fp_centre.get(pad["ref"], (pad["x"], pad["y"]))
        dx = pad["x"] - origin[0]
        dy = pad["y"] - origin[1]
        if abs(dx) >= abs(dy):
            first = (1.0 if dx >= 0 else -1.0, 0.0)
            half = pad["w"] / 2.0
        else:
            first = (0.0, 1.0 if dy >= 0 else -1.0)
            half = pad["h"] / 2.0
        cap = min(pad["w"], pad["h"]) + 0.10
        cands = [w for w in width_ladder(params) if w <= cap + 1e-9]
        if not cands:
            cands = [min(params["width"], 0.15)]
        dirs = [first, (first[1], first[0]), (-first[0], -first[1]),
                (-first[1], -first[0])]
        for dirv in dirs:
            for extra in (0.70, 0.50, 0.35):
                len1 = half + extra
                x1 = pad["x"] + dirv[0] * len1
                y1 = pad["y"] + dirv[1] * len1
                layer = ROUTABLE[layers_ok[0]]
                for w in sorted(set(cands), reverse=True):
                    if not self.stub_clear([(x1, y1)], w, net, layer, params,
                                           pad["x"], pad["y"]):
                        continue
                    return self._commit_stub(net, pad, [(x1, y1)], w, layer, key,
                                             layers_ok, params, dirv, half)
        return None

    def _commit_stub(self, net, pad, pts, w, layer, key, layers_ok,
                     params, dirv, half):
        b = self.b
        poly = [(pad["x"], pad["y"])] + list(pts)
        segs = []
        for a, bpt in zip(poly, poly[1:]):
            if abs(a[0] - bpt[0]) < 1e-9 and abs(a[1] - bpt[1]) < 1e-9:
                continue
            segs.append({"layer": layer, "net": net, "width": round(w, 3),
                         "start": [round(a[0], 4), round(a[1], 4)],
                         "end": [round(bpt[0], 4), round(bpt[1], 4)],
                         "kind": "stub"})
        if not segs:
            return None
        for seg in segs:
            if seg["width"] < params["width"] - 1e-9:
                self.neck_segments.append(seg)
            b.net_segments.setdefault(net, []).append(seg)
        # only the parts outside the pad are extra copper
        ex = pad["x"] + dirv[0] * half
        ey = pad["y"] + dirv[1] * half
        hw = w / 2.0
        grp = "hi" if params["clearance"] > 0.15 else "lo"
        ring = [(ex, ey)] + list(pts)
        for a, bpt in zip(ring, ring[1:]):
            if abs(a[0] - bpt[0]) < 1e-9 and abs(a[1] - bpt[1]) < 1e-9:
                continue
            b.ob.add(layer, grp,
                     Shape((a[0] + bpt[0]) / 2.0, (a[1] + bpt[1]) / 2.0,
                           abs(bpt[0] - a[0]) / 2.0 + hw,
                           abs(bpt[1] - a[1]) / 2.0 + hw, 0.0, 0.0, net))
        tipx, tipy = pts[-1]
        tip = (layers_ok[0], int(round(tipx / PITCH)), int(round(tipy / PITCH)))
        self.stubs[key] = {"tip": tip, "cells": [], "net": net, "width": w}
        return segs[0]

    def stub_clear(self, pts, width, net, layer, params, px=None, py=None):
        """Sample the stub polyline (started at px,py) against real copper."""
        poly = [(px, py)] + list(pts) if px is not None else list(pts)
        xs, ys = [], []
        for a, bpt in zip(poly, poly[1:]):
            length = math.hypot(bpt[0] - a[0], bpt[1] - a[1])
            n = max(2, int(length / 0.05))
            xs.append(np.linspace(a[0], bpt[0], n, endpoint=False))
            ys.append(np.linspace(a[1], bpt[1], n, endpoint=False))
        xs.append(np.array([poly[-1][0]]))
        ys.append(np.array([poly[-1][1]]))
        xs = np.concatenate(xs).astype(np.float32)
        ys = np.concatenate(ys).astype(np.float32)
        x0, x1 = float(xs.min()), float(xs.max())
        y0, y1 = float(ys.min()), float(ys.max())
        half = width / 2.0
        for grp in ("lo", "hi"):
            gclear = 0.15 if grp == "lo" else 0.20
            need = half + max(params["clearance"], gclear) + 0.03
            for s in self.b.ob.by[layer][grp]:
                if s.net == net:
                    continue
                if (s.x1 < x0 - need or s.x0 > x1 + need
                        or s.y1 < y0 - need or s.y0 > y1 + need):
                    continue
                if float(s.dist(xs, ys).min()) < need:
                    return False
        return True

    def route_net(self, net, guide=None, soft=False):
        boost = getattr(self, "clear_boost", 0.0)
        self.clear_boost = 0.0
        b, rtr = self.b, self.rtr
        params = net_params(net)
        pads = b.pads_of.get(net, [])
        if len(pads) < 2:
            return True
        self.mask_cache.clear()
        snap = b.ob.snapshot()
        own_local = {lyr: np.zeros((H, W), bool) for lyr in ROUTABLE}
        order = mst_edges(pads)
        # every pad is reached at its stub tip (fan-out reservation) or, when
        # no stub was needed, at the pad itself
        def anchor(pad):
            st = self.stubs.get((pad["ref"], pad["num"]))
            if st:
                return [st["tip"]]
            return [(li, i, j) for li, lyr in enumerate(ROUTABLE)
                    for (i, j) in pad["cells"] if lyr in pad["cu_layers"]]

        def anchor_mask(pad):
            t = [None] * len(ROUTABLE)
            st = self.stubs.get((pad["ref"], pad["num"]))
            if st:
                li, i, j = st["tip"]
                m = np.zeros((H, W), bool)
                m[j, i] = True
                t[li] = m
                return t
            for li, lyr in enumerate(ROUTABLE):
                if lyr not in pad["cu_layers"]:
                    continue
                m = np.zeros((H, W), bool)
                for (i, j) in pad["cells"]:
                    m[j, i] = True
                t[li] = m
            return t

        tree_pts = anchor(pads[0])
        segs_all, vias_all = [], []
        path_cells = list(tree_pts)
        tx0 = min(c[1] for c in tree_pts)
        tx1 = max(c[1] for c in tree_pts)
        ty0 = min(c[2] for c in tree_pts)
        ty1 = max(c[2] for c in tree_pts)
        ok = True
        for child, parent in order:
            if parent < 0:
                continue
            pad = pads[child]
            layers_ok = [li for li, lyr in enumerate(ROUTABLE)
                         if lyr in pad["cu_layers"]]
            if not layers_ok:
                continue
            target = anchor_mask(pad)
            has_stub = (pad["ref"], pad["num"]) in self.stubs
            ref = (int(round(pad["x"] / PITCH)), int(round(pad["y"] / PITCH)))
            cx0 = min(tx0, min(c[0] for c in pad["cells"]))
            cx1 = max(tx1, max(c[0] for c in pad["cells"]))
            cy0 = min(ty0, min(c[1] for c in pad["cells"]))
            cy1 = max(ty1, max(c[1] for c in pad["cells"]))
            span = max(cx1 - cx0, cy1 - cy0) * PITCH
            margin = (5.0 + 0.35 * span) / PITCH
            window = (max(0, int(cx0 - margin)), min(W - 1, int(cx1 + margin)),
                      max(0, int(cy0 - margin)), min(H - 1, int(cy1 + margin)))
            path, used_w, used_dia, used_drill, wide = None, None, None, None, None
            # during routing every net is drawn at its net class width (or the
            # neck width that fits); the 0.8 mm trunk widening for the high
            # current nets is applied afterwards by fatten_trunks(), so it does
            # not steal corridor space from the nets routed later
            wide_w = params["width"]
            for w in width_ladder(params):
                m, via_ok, via_dia, via_drill, soft = self.masks_for(net, w, soft)
                if net in NO_VIA:
                    via_ok = np.zeros_like(via_ok)
                walk = [(m[lyr][0] | own_local[lyr]) for lyr in ROUTABLE]
                slack = [(np.where(own_local[lyr], 1.0, m[lyr][1]))
                         for lyr in ROUTABLE]
                wide_m = self.masks_for(net, wide_w, soft)[0]
                wide_ok = {lyr: ((wide_m[lyr][0] | own_local[lyr])
                                 & (np.where(own_local[lyr], 1.0,
                                             wide_m[lyr][1]) >= 0.02))
                           for lyr in ROUTABLE}
                path = rtr.astar(walk, slack, target, tree_pts, via_ok,
                                 guide=guide, ref_ij=ref, slack_slack=DIAG_MARGIN,
                                 window=window,
                                 layer_pen=self.layer_penalty(net), soft=soft)
                if path is not None:
                    used_w, used_dia, used_drill, wide = w, via_dia, via_drill, wide_ok
                    break
            if path is None:
                ok = False
                self.log(f"    !! cannot reach {net} pad {pad['ref']}.{pad['num']}")
                break
            if used_w < params["width"] - 1e-9:
                wo = width_of_from_path(path, wide, wide_w, used_w)
            elif net in WIDE_BUS:
                wo = width_of_from_path(path, wide, wide_w, used_w)
            else:
                wo = used_w
            # only snap the last vertex onto the pad centre when that is a
            # short, harmless move - a long stretched vertex used to sweep
            # across neighbouring copper
            last_i, last_j = path[-1][1], path[-1][2]
            off = math.hypot(last_i * PITCH - pad["x"], last_j * PITCH - pad["y"])
            snap_end = None if (has_stub or off > 0.20) else (pad["x"], pad["y"])
            segs, vias, cellwidths = emit_path(path, wo, net, snap_end=snap_end)
            for s in segs:
                s["kind"] = "route"
            for v in vias:
                v["dia"], v["drill"] = used_dia, used_drill
            for s in segs:
                if s["width"] < params["width"] - 1e-9:
                    self.neck_segments.append(s)
            segs_all.extend(segs)
            vias_all.extend(vias)
            by_layer = {}
            for cell, cw in cellwidths:
                by_layer.setdefault(cell[0], []).append((cell, cw))
            for li, entries in by_layer.items():
                by_w = {}
                for cell, cw in entries:
                    by_w.setdefault(round(cw, 3), []).append(cell)
                for cw, cells in by_w.items():
                    mark_cells(own_local[ROUTABLE[li]], cells, cw / 2.0)
            for v in vias:
                vi, vj = int(round(v["x"] / PITCH)), int(round(v["y"] / PITCH))
                for lyr in ROUTABLE:
                    mark_cells(own_local[lyr], [(None, vi, vj)], v["dia"] / 2.0)
                for li in range(len(ROUTABLE)):
                    tree_pts.append((li, vi, vj))
            tree_pts.extend(path)
            path_cells.extend(path)
            tx0 = min(tx0, min(c[1] for c in path))
            tx1 = max(tx1, max(c[1] for c in path))
            ty0 = min(ty0, min(c[2] for c in path))
            ty1 = max(ty1, max(c[2] for c in path))
            guide = None
        if not ok:
            b.ob.rollback(snap)
            self.discard_necks(net)
            self.failed.append(net)
            return False
        b.net_segments.setdefault(net, []).extend(segs_all)
        b.net_vias.setdefault(net, []).extend(vias_all)
        self.paths[net] = path_cells
        grp = "hi" if params["clearance"] > 0.15 else "lo"
        for s in segs_all:
            x0, y0 = s["start"]
            x1, y1 = s["end"]
            half = s["width"] / 2.0
            b.ob.add(s["layer"], grp,
                     Shape((x0 + x1) / 2.0, (y0 + y1) / 2.0,
                           abs(x1 - x0) / 2.0 + half, abs(y1 - y0) / 2.0 + half,
                           0.0, 0.0, net))
        for v in vias_all:
            r = v["dia"] / 2.0
            for lyr in ALL_CU:
                b.ob.add(lyr, grp, Shape(v["x"], v["y"], r, r, r, 0.0, net))
        return True

    def discard_necks(self, net):
        self.neck_segments = [s for s in self.neck_segments if s["net"] != net]

    # -- repair: rip up the nets that wall a failed net in, then re-route ----
    def route_one(self, net, guide=None, soft=False, boost=0.0):
        self.failed = [n for n in self.failed if n != net]
        self.paths.pop(net, None)
        self.clear_boost = boost
        return self.route_net(net, guide=guide, soft=soft)

    # -- negotiated congestion (PathFinder style) ------------------------
    def violations(self, net):
        """Cells of this net's routed copper that break clearance."""
        params = net_params(net)
        segs = list(self.b.net_segments.get(net, []))
        if not segs:
            return 0
        masks = {}
        bad = 0
        for s in segs:
            w = s["width"]
            key = round(w, 3)
            if key not in masks:
                masks[key] = self.rtr.masks(net, w / 2.0, params["clearance"])
            m = masks[key]
            slack = m[s["layer"]][1]
            x0, y0 = s["start"]
            x1, y1 = s["end"]
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.05))
            xs = np.linspace(x0, x1, n)
            ys = np.linspace(y0, y1, n)
            for (px, py) in zip(xs, ys):
                i = int(round(px / PITCH))
                j = int(round(py / PITCH))
                if not (0 <= i < W and 0 <= j < H):
                    continue
                sev = -(slack[j, i] + EPS)     # true clearance shortfall
                if sev > 0.01:
                    bad += 1
                    self.hist[s["layer"]][j, i] += 900.0 + 6000.0 * sev
        return bad

    def negotiate(self, order, iterations=8, log=print):
        """Route with copper treated as a soft obstacle, then negotiate."""
        for k, net in enumerate(order, 1):
            self.route_one(net, soft=True)
        log(f"  soft pass: {len(self.failed)} failing nets")
        for it in range(iterations):
            bad = {}
            for net in order:
                if net in self.failed:
                    continue
                v = self.violations(net)
                if v:
                    bad[net] = v
            log(f"  iteration {it+1}: {len(bad)} nets with clearance conflicts, "
                f"{len(self.failed)} unrouted")
            if not bad:
                return
            self.mask_cache.clear()
            for net, _ in sorted(bad.items(), key=lambda kv: -kv[1]):
                self._remove_net_copper(net)
                self.b.rebuild_copper()
                self.mask_cache.clear()
                self.route_one(net, soft=True)
            self.failed = [n for n in order
                           if not any(s.get("kind") == "route"
                                      for s in self.b.net_segments.get(n, []))]

    def _remove_net_copper(self, net):
        """Drop a net's routed copper but keep its fan-out stubs."""
        self.b.net_segments[net] = [s for s in self.b.net_segments.get(net, [])
                                    if s.get("kind") == "stub"]
        self.b.net_vias[net] = []

    def blockers_for(self, net, max_nets=3):
        """Nets whose F.Cu copper sits on the boundary of this net's pocket."""
        params = net_params(net)
        m = self.rtr.masks(net, params["width"] / 2.0, params["clearance"])
        walk = m["F.Cu"][0]
        seeds = [(i, j) for p in self.b.pads_of.get(net, [])
                 if "F.Cu" in p["cu_layers"] for (i, j) in p["cells"]]
        seen = flood_fill(walk, seeds)
        if not seen.any():
            return []
        near = dilate(seen, 3)
        counts = {}
        for other, segs in self.b.net_segments.items():
            if other == net:
                continue
            for s in segs:
                if s["layer"] != "F.Cu":
                    continue
                x0, y0 = s["start"]
                x1, y1 = s["end"]
                pad = s["width"] / 2.0 + 0.05
                i0, i1, j0, j1 = _cell_range(min(x0, x1) - pad, min(y0, y1) - pad,
                                             max(x0, x1) + pad, max(y0, y1) + pad)
                if i1 < i0 or j1 < j0:
                    continue
                if near[j0:j1 + 1, i0:i1 + 1].any():
                    counts[other] = counts.get(other, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        return [n for n, _ in ranked[:max_nets]]

    def state(self):
        return ({n: list(v) for n, v in self.b.net_segments.items()},
                {n: list(v) for n, v in self.b.net_vias.items()})

    def restore(self, st):
        segs, vias = st
        self.b.net_segments = {n: list(v) for n, v in segs.items()}
        self.b.net_vias = {n: list(v) for n, v in vias.items()}
        self.b.rebuild_copper()
        self.mask_cache.clear()
        self.rebuild_necks()

    def rebuild_necks(self):
        self.neck_segments = []
        for net, segs in self.b.net_segments.items():
            params = net_params(net)
            for s in segs:
                if s["width"] < params["width"] - 1e-9:
                    self.neck_segments.append(s)

    def trim_dangling_stubs(self):
        """Shorten fan-out stubs back to the copper they actually connect to.

        A stub whose tip was not met by the route is a dangling track end, which
        DRC reports as a warning.  Every stub starts inside its own pad, so
        trimming to the last junction keeps connectivity and removes the
        warning.
        """
        removed = trimmed = 0
        for net, segs in list(self.b.net_segments.items()):
            stubs = [s for s in segs if s.get("kind") == "stub"]
            if not stubs:
                continue
            routes = [s for s in segs if s.get("kind") != "stub"]
            vias = self.b.net_vias.get(net, [])
            pads = {}
            for pad in self.b.pads_of.get(net, []):
                pads[(pad["ref"], pad["num"])] = pad

            def pad_touched(pad, st):
                """Is the pad already connected by other copper?"""
                ps = self.b._shape_from_pad(pad)
                for r in routes:
                    if r["layer"] != st["layer"]:
                        continue
                    a = np.array(r["start"], np.float32)
                    b = np.array(r["end"], np.float32)
                    n = max(3, int(np.linalg.norm(b - a) / 0.05))
                    xs = np.linspace(a[0], b[0], n)
                    ys = np.linspace(a[1], b[1], n)
                    # require the route to bite well into the pad, not just
                    # graze its edge (a grazing joint trips DRC "connection
                    # width")
                    if float(ps.dist(xs, ys).min()) <= r["width"] / 2.0 - 0.25:
                        return True
                for v in vias:
                    if float(ps.dist(np.array([v["x"]], np.float32),
                                     np.array([v["y"]], np.float32))[0]) \
                            <= v["dia"] / 2.0 - 0.25:
                        return True
                return False

            keep = []
            for st in stubs:
                pad = None
                for key, p in pads.items():
                    if abs(p["x"] - st["start"][0]) < 0.05 \
                            and abs(p["y"] - st["start"][1]) < 0.05:
                        pad = p
                        break
                if pad is not None and pad_touched(pad, st):
                    removed += 1
                    continue
                tip = np.array(st["end"], np.float32)
                best = None
                for r in routes:
                    if r["layer"] != st["layer"]:
                        continue
                    a = np.array(r["start"], np.float32)
                    b = np.array(r["end"], np.float32)
                    ab = b - a
                    denom = float(ab @ ab)
                    t = 0.0 if denom == 0 else float(np.clip((tip - a) @ ab / denom,
                                                            0.0, 1.0))
                    point = a + t * ab
                    d = float(np.linalg.norm(point - tip))
                    reach = (r["width"] + st["width"]) / 2.0 + 0.15
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, t, point)
                for v in vias:
                    d = float(np.linalg.norm(np.array([v["x"], v["y"]], np.float32)
                                             - tip))
                    if d <= v["dia"] / 2.0 + st["width"] / 2.0 + 0.15 \
                            and (best is None or d < best[0]):
                        best = (d, 1.0, np.array([v["x"], v["y"]], np.float32))
                if best is None:
                    removed += 1
                    continue
                d, t, point = best
                if d <= 0.02:
                    keep.append(st)
                    continue
                # only shorten, never extend: the trimmed end has to lie on the
                # stub itself
                s0 = np.array(st["start"], np.float32)
                s1 = np.array(st["end"], np.float32)
                sv = s1 - s0
                tt = float(np.clip((point - s0) @ sv / max(float(sv @ sv), 1e-9),
                                   0.0, 1.0))
                if tt >= 0.999:
                    keep.append(st)
                    continue
                point = s0 + tt * sv
                st2 = dict(st)
                st2["end"] = [round(float(point[0]), 4), round(float(point[1]), 4)]
                if (abs(st2["end"][0] - st2["start"][0]) < 1e-6
                        and abs(st2["end"][1] - st2["start"][1]) < 1e-6):
                    removed += 1
                    continue
                keep.append(st2)
                trimmed += 1
            self.b.net_segments[net] = keep + routes
        if removed or trimmed:
            self.b.rebuild_copper()
            self.rebuild_necks()
        return removed, trimmed

    def fatten_trunks(self, target=WIDE_TARGET, log=print):
        """Widen the high current trunks once the board is fully routed.

        V1.6 decision §1.3: BAT / SYS / USB_VBUS / 3V3_MAIN start at 0.5 mm at
        the pads and are then widened towards 0.8 mm (or a pour) wherever the
        finished board still has room.  Doing it last keeps the extra width from
        stealing corridor space from the nets routed afterwards.
        """
        masks = {}
        grown = {}
        for net in sorted(WIDE_BUS):
            params = net_params(net)
            if net not in self.b.net_segments:
                continue
            key = (net, round(target, 3))
            if key not in masks:
                masks[key] = self.rtr.masks(net, target / 2.0,
                                            params["clearance"])
            walk = masks[key]
            n_grown = 0
            for s in self.b.net_segments[net]:
                if s["width"] >= target - 1e-9:
                    continue
                w = walk[s["layer"]][0]
                x0, y0 = s["start"]
                x1, y1 = s["end"]
                length = math.hypot(x1 - x0, y1 - y0)
                n = max(3, int(length / 0.05))
                ok = True
                for t in np.linspace(0.0, 1.0, n):
                    i = int(round((x0 + (x1 - x0) * t) / PITCH))
                    j = int(round((y0 + (y1 - y0) * t) / PITCH))
                    if not (0 <= i < W and 0 <= j < H) or not w[j, i]:
                        ok = False
                        break
                if ok:
                    s["width"] = round(target, 3)
                    n_grown += 1
            if n_grown:
                grown[net] = n_grown
                self.b.rebuild_copper()      # later nets must see the new copper
                self.mask_cache.clear()
        if grown:
            self.rebuild_necks()
        log(f"  trunk widening: {sum(grown.values())} segments -> {target} mm "
            f"({grown})")
        return grown

    # ------------------------------------------------------------------
    # Mandatory finish-up edits
    # (ESP32S3_GDEM102T91_V1.6_Post_First_Routing_Next_Steps.md §3/§4/§5)
    # ------------------------------------------------------------------
    def snap_marginal_endpoints(self, tol=0.20):
        """Land marginal track ends firmly on the copper they belong to.

        MD §5: the three 0.1 mm residuals (EPD_BUSY / EPD_RESE / SPI_SCLK) sit
        on the *edge* of the neighbouring same-net copper, which KiCad reports
        as "track has unconnected end".  Pulling the end onto the neighbour's
        centre line makes the joint unambiguous.
        """
        moved = 0
        for net, segs in list(self.b.net_segments.items()):
            routes = [s for s in segs if s.get("kind") == "route"]
            others = [s for s in segs]
            for s in routes:
                if s["width"] > 0.35:
                    continue
                for which in ("start", "end"):
                    pt = np.array(s[which], float)
                    best = None
                    for o in others:
                        if o is s or o["layer"] != s["layer"]:
                            continue
                        a = np.array(o["start"], float)
                        b = np.array(o["end"], float)
                        ab = b - a
                        den = float(ab @ ab)
                        t = 0.0 if den <= 1e-12 else \
                            float(np.clip((pt - a) @ ab / den, 0.0, 1.0))
                        q = a + t * ab
                        d = float(np.linalg.norm(q - pt))
                        if 1e-4 < d <= tol and (best is None or d < best[0]):
                            best = (d, q)
                    if best is None:
                        continue
                    s[which] = [round(float(best[1][0]), 4),
                                round(float(best[1][1]), 4)]
                    moved += 1
        if moved:
            self.b.rebuild_copper()
            self.rebuild_necks()
        return moved

    def deepen_pad_entries(self, depth=0.25, limit=0.20, log=print):
        """Push marginal track ends properly inside their own pad (MD §5 §20③).

        A track that stops just inside (or just outside) its pad edge is both a
        "dangling end" and a "connection width" warning.  Every such end is
        slid towards the pad centre until it is `depth` mm inside the copper -
        but only when the resulting segment still passes the clearance mask, so
        the fix can never create a new violation.
        """
        fixed = 0
        masks = {}
        for net, segs in list(self.b.net_segments.items()):
            params = net_params(net)
            pads = [(p, self.b._shape_from_pad(p))
                    for p in self.b.pads_of.get(net, [])]
            for s in segs:
                if s.get("kind") == "stub":
                    continue
                for which in ("start", "end"):
                    pt = np.array(s[which], float)
                    best = None
                    for (p, shape) in pads:
                        if s["layer"] not in p["cu_layers"]:
                            continue
                        d = float(shape.dist(pt[:1], pt[1:])[0])   # 0 inside
                        if d > limit and d != 0.0:
                            continue
                        centre = np.array([p["x"], p["y"]], float)
                        vec = centre - pt
                        n = float(np.linalg.norm(vec))
                        if n < 1e-6:
                            continue
                        # distance from the endpoint to the pad boundary,
                        # negative inside the copper
                        if shape.dist(pt[:1], pt[1:])[0] > 0.0:
                            inside = -d
                        else:
                            inside = abs(d)
                        move = depth - inside
                        if move <= 0.02:
                            continue
                        new = pt + vec / n * min(move, n)
                        if best is None or move < best[0]:
                            best = (move, new, p)
                    if best is None:
                        continue
                    move, new, pad = best
                    other = np.array(s["end" if which == "start" else "start"], float)
                    key = round(s["width"], 3)
                    if key not in masks:
                        masks[key] = self.rtr.masks(net, s["width"] / 2.0,
                                                    params["clearance"])
                    walk = masks[key][s["layer"]][0]
                    ok = True
                    nn = max(3, int(np.linalg.norm(new - other) / 0.05))
                    for t in np.linspace(0.0, 1.0, nn):
                        x = other[0] + (new[0] - other[0]) * t
                        y = other[1] + (new[1] - other[1]) * t
                        i, j = int(round(x / PITCH)), int(round(y / PITCH))
                        if not (0 <= i < W and 0 <= j < H) or not walk[j, i]:
                            ok = False
                            break
                    if not ok:
                        continue
                    s[which] = [round(float(new[0]), 4), round(float(new[1]), 4)]
                    fixed += 1
        if fixed:
            self.b.rebuild_copper()
            self.rebuild_necks()
        log(f"  pad entries deepened: {fixed}")
        return fixed

    def _pair_gap(self, net_a, net_b, layer):
        """Smallest copper gap between two nets on one layer (None if far apart)."""
        a = [s for s in self.b.net_segments.get(net_a, []) if s["layer"] == layer]
        b = [s for s in self.b.net_segments.get(net_b, []) if s["layer"] == layer]
        best = None
        for s1 in a:
            for s2 in b:
                g = _seg_seg_gap(s1, s2)
                if best is None or g < best:
                    best = g
        return best

    def manual_finish(self, log=print):
        """Apply the hand edits from MD §3 and §4 (verified, with rollback).

        §3  EPD_GDR / EPD_RESE leave J2 pin 2/3 too early: their first copper
            sections run 0.4 mm apart vertically (0.125 mm gap).  EPD_RESE's
            jog out of the connector is re-drawn 0.3 mm higher and narrowed to
            0.2 mm, and its layer-change via moves with it; EPD_GDR keeps its
            route.  The edit is verified against the real geometry and rolled
            back if the pair is still too close.
        §4  The 0.5 mm EPD_3V3 section next to C31 starts 0.075 mm too close to
            C31's GND pad; its junction with the diagonal is moved up by 0.3 mm.
        §5  The three 0.1 mm residuals are snapped onto the end of the copper
            they belong to (they used to stop on the neighbour's edge).
        """
        # --- §3: re-route the two J2 neighbours with route-only barriers
        st3 = self.state()
        box = (3.40, 46.20, 4.60, 47.00)      # EPD_RESE's jog next to J2 pin 3
        keep = []
        for s in self.b.net_segments.get("EPD_RESE", []):
            # never touch the fan-out stub: it is the pad's own escape
            if s.get("kind") == "stub" or s["layer"] != "F.Cu" \
                    or not _seg_in_box(s, box):
                keep.append(s)
                continue
        self.b.net_segments["EPD_RESE"] = keep
        # drop the via that used to sit at the end of that jog, keep the rest
        for v in list(self.b.net_vias.get("EPD_RESE", [])):
            if box[0] - 0.8 <= v["x"] <= box[2] + 0.8 and \
                    box[1] - 0.8 <= v["y"] <= box[3] + 0.8:
                self.b.net_vias["EPD_RESE"].remove(v)
        # re-draw: straight-ish neck 0.3 mm higher, narrower, via moved with it
        self.b.net_segments.setdefault("EPD_RESE", []).append(
            {"layer": "F.Cu", "net": "EPD_RESE", "width": 0.2,
             "start": [3.6, 46.75], "end": [4.2, 46.5], "kind": "route"})
        self.b.net_vias.setdefault("EPD_RESE", []).append(
            {"x": 4.2, "y": 46.5, "dia": 0.6, "drill": 0.3, "net": "EPD_RESE"})
        for s in self.b.net_segments.get("EPD_RESE", []):
            if s["layer"] == "B.Cu" and abs(s["start"][0] - 4.2) < 0.3 \
                    and abs(s["start"][1] - 46.9) < 0.6:
                s["start"] = [4.2, 46.5]
        self.b.rebuild_copper()
        self.rebuild_necks()
        gap = self._pair_gap("EPD_RESE", "EPD_GDR", "F.Cu")
        if gap is None or gap >= 0.2 - 0.005:
            log(f"    §3 EPD_RESE jog re-drawn (RESE↔GDR gap "
                f"{gap if gap is None else round(gap, 3)} mm)")
        else:
            self.restore(st3)
            log(f"    §3 reverted: gap would be {round(gap, 3)} mm")

        # --- §4 / §5: explicit geometry edits
        drop = [
            ("EPD_3V3", "F.Cu", 10.7, 44.7, 10.7, 43.7),
            ("EPD_3V3", "F.Cu", 10.9, 44.7, 12.2, 46.0),
        ]
        add = [
            ("EPD_3V3", "F.Cu", 0.5, 10.7, 44.4, 10.7, 43.7),
            ("EPD_3V3", "F.Cu", 0.2, 10.7, 44.4, 12.2, 46.0),
        ]
        move_end = [
            ("EPD_BUSY", "F.Cu", 3.6, 43.8, 3.6, 43.75),
            ("SPI_SCLK", "F.Cu", 1.2, 41.8, 1.25, 41.75),
            # EPD_VSH1 used to stop exactly on C32 pad 1's edge (connection
            # width 0.135 mm); push it 0.3 mm into the pad
            ("EPD_VSH1", "F.Cu", 11.7, 40.3, 12.0, 40.3),
        ]
        def same(s, x0, y0, x1, y1):
            f = lambda a, b: abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3
            return f(s["start"], [x0, y0]) and f(s["end"], [x1, y1]) or \
                f(s["start"], [x1, y1]) and f(s["end"], [x0, y0])

        removed = 0
        for (net, layer, x0, y0, x1, y1) in drop:
            lst = self.b.net_segments.get(net, [])
            keep = []
            for s in lst:
                if s["layer"] == layer and same(s, x0, y0, x1, y1):
                    removed += 1
                    continue
                keep.append(s)
            self.b.net_segments[net] = keep
        for (net, layer, w, x0, y0, x1, y1) in add:
            self.b.net_segments.setdefault(net, []).append(
                {"layer": layer, "net": net, "width": w,
                 "start": [x0, y0], "end": [x1, y1], "kind": "route"})
        moved_via = 0
        for (net, layer, ox, oy, nx, ny) in move_end:
            for s in self.b.net_segments.get(net, []):
                if s["layer"] != layer:
                    continue
                for which in ("start", "end"):
                    if abs(s[which][0] - ox) < 1e-3 and abs(s[which][1] - oy) < 1e-3:
                        s[which] = [nx, ny]
                        moved_via += 1
        self.b.rebuild_copper()
        self.rebuild_necks()
        log(f"  manual finish: removed {removed}, added {len(add)} segments, "
            f"moved {moved_via} endpoints")
        return removed, moved_via

    def extend_into_pads(self, reach=0.35, depth=0.25):
        """Pull marginal track ends properly inside their own pad.

        A track that stops just outside its pad (or only grazes the edge) is
        both a dangling end and a "connection width" warning.  Every such end
        is projected onto the pad's centre line until it sits `depth` mm inside
        the pad's copper.
        """
        fixed = 0
        masks = {}
        for net, segs in list(self.b.net_segments.items()):
            params = net_params(net)

            def clear_ok(seg, a, b):
                """Would the moved segment stay inside the legal region?"""
                key = round(seg["width"], 3)
                if key not in masks:
                    masks[key] = self.rtr.masks(net, seg["width"] / 2.0,
                                                params["clearance"])
                walk = masks[key][seg["layer"]][0]
                n = max(3, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
                for t in np.linspace(0.0, 1.0, n):
                    x = a[0] + (b[0] - a[0]) * t
                    y = a[1] + (b[1] - a[1]) * t
                    i, j = int(round(x / PITCH)), int(round(y / PITCH))
                    if not (0 <= i < W and 0 <= j < H) or not walk[j, i]:
                        return False
                return True

            pads = [self.b._shape_from_pad(p) for p in self.b.pads_of.get(net, [])]
            pad_by_layer = {}
            for p, shape in zip(self.b.pads_of.get(net, []), pads):
                for lyr in p["cu_layers"]:
                    pad_by_layer.setdefault((lyr, p["ref"], p["num"]), shape)
            for s in segs:
                if s.get("kind") != "route":
                    continue
                for which in ("start", "end"):
                    pt = np.array(s[which], np.float32)
                    best = None
                    for (key, shape) in pad_by_layer.items():
                        lyr, ref, num = key
                        if lyr != s["layer"]:
                            continue
                        d = float(shape.dist(pt[:1], pt[1:])[0])
                        if d <= reach and (best is None or d < best[0]):
                            best = (d, shape)
                    if best is None:
                        continue
                    centre = np.array([best[1].x, best[1].y], np.float32)
                    vec = centre - pt
                    n = float(np.linalg.norm(vec))
                    if n < 1e-6:
                        continue
                    move = min(best[0] + depth, n)
                    new = pt + vec / n * move
                    if float(np.linalg.norm(new - pt)) < 0.01:
                        continue
                    other = np.array(s["end" if which == "start" else "start"],
                                     np.float32)
                    if not clear_ok(s, other, new):
                        continue          # the detour would break clearance
                    s[which] = [round(float(new[0]), 4), round(float(new[1]), 4)]
                    fixed += 1
        if fixed:
            self.b.rebuild_copper()
            self.rebuild_necks()
        return fixed

    def repair(self, rounds=4, max_nets=3, log=print):
        for rnd in range(rounds):
            if not self.failed:
                return
            progress = False
            for net in list(self.failed):
                blockers = self.blockers_for(net, max_nets=max_nets)
                if not blockers:
                    continue
                st = self.state()
                order_backup = list(self.failed)
                for other in blockers + [net]:
                    self._remove_net_copper(other)
                self.b.rebuild_copper()
                self.mask_cache.clear()
                ok = self.route_one(net)
                if ok:
                    for other in blockers:
                        if not self.route_one(other):
                            ok = False
                            break
                if ok:
                    self.failed = [n for n in self.failed if n != net]
                    self.rebuild_necks()
                    progress = True
                    log(f"    repair: {net} routed after ripping up {blockers}")
                else:
                    self.restore(st)
                    self.failed = order_backup
            if not progress:
                return

    def net_order(self, only=None):
        spans = {}
        for net, pads in self.b.pads_of.items():
            if net in NEVER_ROUTE or len(pads) < 2:
                continue
            xs = [p["x"] for p in pads]
            ys = [p["y"] for p in pads]
            spans[net] = max(max(xs) - min(xs), max(ys) - min(ys))
        rows, placed = [], set()
        for idx, tier in enumerate(TIERS):
            for net in tier:
                if net in spans:
                    rows.append((idx, spans[net], net))
                    placed.add(net)
        for net, span in spans.items():
            if net not in placed:
                rows.append((len(TIERS) - 1, span, net))
        # inside a tier the long buses go first (they need the clean corridors)
        rows.sort(key=lambda t: (t[0], -t[1] if t[0] == 7 else t[1], t[2]))
        out = [r[2] for r in rows]
        if only:
            out = [n for n in out if n in only]
        return out


def dilate(mask, r):
    out = mask.copy()
    for _ in range(r):
        acc = out.copy()
        acc[1:, :] |= out[:-1, :]
        acc[:-1, :] |= out[1:, :]
        acc[:, 1:] |= out[:, :-1]
        acc[:, :-1] |= out[:, 1:]
        out = acc
    return out


def flood_fill(walk, seeds):
    """4-connected flood fill on a bool mask; returns the reached mask."""
    seen = np.zeros_like(walk)
    stack = []
    for (i, j) in seeds:
        if 0 <= i < W and 0 <= j < H and walk[j, i] and not seen[j, i]:
            seen[j, i] = True
            stack.append((i, j))
    while stack:
        i, j = stack.pop()
        if i + 1 < W and walk[j, i + 1] and not seen[j, i + 1]:
            seen[j, i + 1] = True
            stack.append((i + 1, j))
        if i > 0 and walk[j, i - 1] and not seen[j, i - 1]:
            seen[j, i - 1] = True
            stack.append((i - 1, j))
        if j + 1 < H and walk[j + 1, i] and not seen[j + 1, i]:
            seen[j + 1, i] = True
            stack.append((i, j + 1))
        if j > 0 and walk[j - 1, i] and not seen[j - 1, i]:
            seen[j - 1, i] = True
            stack.append((i, j - 1))
    return seen


def plan_gnd_vias(board, sess, spacing=4.0, log=print):
    """GND is carried by the pours; the vias tie the pours to the L2 plane.

    Two families are placed: one via on (or next to) every SMD GND pad, and a
    coarse stitching grid across the board.  Both are checked against the real
    routed copper with the same clearance engine the router uses.
    """
    rtr = sess.rtr
    params = net_params("GND")
    clear = params["clearance"]
    cache = {}

    def vm(dia, drill):
        key = (dia, drill)
        if key not in cache:
            cache[key] = rtr.via_mask("GND", dia / 2.0, drill / 2.0, clear)
        return cache[key]

    placed = []

    def try_place(x, y, sizes=((0.6, 0.3), (0.5, 0.25))):
        i, j = int(round(x / PITCH)), int(round(y / PITCH))
        if not (0 <= i < W and 0 <= j < H):
            return None
        for dia, drill in sizes:
            if not vm(dia, drill)[j, i]:
                continue
            for (px, py, pdia, pdrill) in placed:
                need = (dia + pdia) / 2.0 + 0.3
                if math.hypot(px - x, py - y) < need:
                    break
            else:
                v = {"x": round(x, 4), "y": round(y, 4), "dia": dia,
                     "drill": drill, "net": "GND", "kind": "stitch"}
                placed.append((x, y, dia, drill))
                return v
        return None

    pad_vias = []
    for p in board.pads_of.get("GND", []):
        if p["type"] != "smd" or "F.Cu" not in p["cu_layers"]:
            continue
        cands = [(p["x"], p["y"])]
        ax, ay = p["w"] / 4.0, p["h"] / 4.0
        cands += [(p["x"] + dx, p["y"] + dy)
                  for dx in (-ax, 0.0, ax) for dy in (-ay, 0.0, ay)]
        for (cx, cy) in cands:
            v = try_place(cx, cy)
            if v:
                v["kind"] = "pad"
                v["ref"] = p["ref"]
                pad_vias.append(v)
                break

    grid = []
    y = 1.5
    row = 0
    while y < BH - 1.0:
        x = 1.5 + (spacing / 2.0 if row % 2 else 0.0)
        while x < BW - 1.0:
            v = try_place(x, y)
            if v:
                grid.append(v)
            x += spacing
        y += spacing * 0.866
        row += 1
    log(f"  GND vias: {len(pad_vias)} at pads, {len(grid)} stitching")
    return pad_vias, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nets", help="comma separated subset (debugging)")
    ap.add_argument("--preload", help="routing.json to treat as existing copper")
    ap.add_argument("--keep-gnd-vias", action="store_true",
                    help="do not re-plan GND vias (use the preloaded ones)")
    ap.add_argument("--passes", type=int, default=5,
                    help="rip-up and reroute passes (failed nets first)")
    ap.add_argument("--mode", choices=["soft", "hard"], default="soft",
                    help="soft: negotiated congestion, hard: strict maze")
    ap.add_argument("--iters", type=int, default=6,
                    help="negotiation iterations in soft mode")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--tidy", action="store_true",
                    help="aggressively pull marginal track ends into pads "
                         "(experimental: can create new clearance issues)")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()
    t0 = time.time()
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    pre = None
    if args.preload:
        pre = json.loads(Path(args.preload).read_text(encoding="utf-8"))
        print(f"preloaded {len(pre.get('segments', []))} segments, "
              f"{len(pre.get('vias', []))} vias")
    only = set(args.nets.split(",")) if args.nets else None

    base = Board(model)
    base_order = Session(base).net_order(only)
    print(f"{len(base_order)} nets to route ({time.time()-t0:.1f}s setup)",
          flush=True)

    order = list(base_order)
    best = None
    for p in range(max(1, args.passes)):
        board = Board(model)
        if pre is not None:
            board.load_routing(pre)
        sess = Session(board, log=(lambda *a: None) if args.quiet else print)
        print(f"--- pass {p+1}/{args.passes} ---", flush=True)
        sess.fanout(order)
        if args.mode == "soft":
            sess.negotiate(order, iterations=args.iters, log=print)
        else:
            for k, net in enumerate(order, 1):
                t = time.time()
                guide = sess.guide_for(net)
                ok = sess.route_net(net, guide=guide)
                if not args.quiet:
                    print(f"[{k:3d}/{len(order)}] {net:<16s} "
                          f"{net_params(net)['class']:<8s} "
                          f"{'ok  ' if ok else 'FAIL'} {time.time()-t:5.1f}s",
                          flush=True)
        score = (len(sess.failed),
                 sum(len(v) for v in board.net_vias.values()))
        if sess.failed:
            sess.repair(rounds=3, log=print)
            score = (len(sess.failed),
                     sum(len(v) for v in board.net_vias.values()))
        print(f"pass {p+1}: {len(sess.failed)} failed, "
              f"{score[1]} vias, "
              f"{sum(len(v) for v in board.net_segments.values())} segments",
              flush=True)
        if best is None or score < best[0]:
            best = (score, board, sess, list(order))
        if not sess.failed:
            break
        # next pass: the nets that failed get the first pick of the board
        order = sess.failed + [n for n in base_order if n not in set(sess.failed)]

    score, board, sess, order = best
    print(f"best pass: {score[0]} failed {sess.failed}")
    if not args.nets:
        r, t = sess.trim_dangling_stubs()
        print(f"stub cleanup: removed {r}, trimmed {t}")
        # final legality sweep: any net whose copper breaks clearance is ripped
        # up and re-routed with the finished board around it
        for it in range(3):
            scored = []
            for net in order:
                if net in sess.failed:
                    continue
                v = sess.violations(net)
                if v:
                    scored.append((v, net))
            if not scored:
                break
            scored.sort(reverse=True)
            bad = [n for _, n in scored[:6]]
            print(f"  legality sweep {it+1}: {len(scored)} nets flagged, "
                  f"re-routing {bad}")
            sess.mask_cache.clear()
            for net in bad:
                st = sess.state()
                v_before = None
                sess._remove_net_copper(net)
                sess.b.rebuild_copper()
                sess.mask_cache.clear()
                # soft mode uses the accumulated history, so the maze picks a
                # different corridor instead of reproducing the same conflict
                if not sess.route_one(net, soft=True, boost=0.08):
                    # never lose a net to a failed repair
                    sess.restore(st)
                    if net in sess.failed:
                        sess.failed.remove(net)
                    if net not in sess.failed:
                        pass
                elif sess.violations(net):
                    # the soft re-route is only accepted if it is actually legal
                    sess.restore(st)
                    if net in sess.failed:
                        sess.failed.remove(net)
            sess.trim_dangling_stubs()
        if args.tidy:
            f = sess.extend_into_pads()
            print(f"endpoint tidy-up: {f} track ends pulled into their pads")
            sess.trim_dangling_stubs()
        sess.fatten_trunks()
        sess.manual_finish()
        if sess.failed:
            print(f"still unrouted: {len(sess.failed)}")
    if sess.failed:
        # a failed net keeps no copper: drop its fan-out stubs as well so the
        # final board has no dangling tracks
        bad = set(sess.failed)
        for net in bad:
            board.net_segments.pop(net, None)
            board.net_vias.pop(net, None)
        sess.neck_segments = [s for s in sess.neck_segments if s["net"] not in bad]
        board.rebuild_copper()
    total_seg = sum(len(v) for v in board.net_segments.values())
    total_via = sum(len(v) for v in board.net_vias.values())
    print(f"segments {total_seg}  vias {total_via}  failed {len(sess.failed)}: "
          f"{sess.failed}")
    if pre is not None and args.keep_gnd_vias:
        pad_vias = [v for v in pre.get("gnd_vias", []) if v.get("kind") == "pad"]
        grid_vias = [v for v in pre.get("gnd_vias", []) if v.get("kind") != "pad"]
        print(f"keeping {len(pad_vias)} pad vias, {len(grid_vias)} stitching vias")
    else:
        pad_vias, grid_vias = plan_gnd_vias(board, sess, log=print)
        # safety net: re-verify every planned via against the final copper and
        # drop the rare one that no longer fits (the mask is cached inside
        # plan_gnd_vias and copper can move between planning and placement)
        ok_mask = sess.rtr.via_mask("GND", 0.3, 0.15,
                                    net_params("GND")["clearance"])
        clean = []
        for v in pad_vias + grid_vias:
            i, j = int(round(v["x"] / PITCH)), int(round(v["y"] / PITCH))
            if 0 <= i < W and 0 <= j < H and ok_mask[j, i]:
                clean.append(v)
        if len(clean) != len(pad_vias) + len(grid_vias):
            print(f"  dropped {len(pad_vias)+len(grid_vias)-len(clean)} "
                  f"GND vias that no longer fit")
        pad_vias = [v for v in clean if v.get("kind") == "pad"]
        grid_vias = [v for v in clean if v.get("kind") != "pad"]
    neck = [{"layer": s["layer"], "net": s["net"], "width": s["width"],
             "class": netclass_of(s["net"]),
             "start": s["start"], "end": s["end"]} for s in sess.neck_segments]
    print(f"necked power segments: {len(neck)}")
    data = {
        "segments": [s for v in board.net_segments.values() for s in v],
        "vias": [v for v in board.net_vias.values() for v in v],
        "gnd_vias": pad_vias + grid_vias,
        "failed": sess.failed,
        "neck_segments": neck,
    }
    Path(args.out).write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("wrote", args.out, f"({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    sys.exit(main())
