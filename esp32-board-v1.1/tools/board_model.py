"""Extract a routing-friendly geometry model from the generated KiCad board.

Run with KiCad's bundled interpreter (it ships pcbnew + numpy):

    & 'C:\\Program Files\\KiCad\\10.0\\bin\\python.exe' tools\\board_model.py

The dump (``routing/model.json``) is consumed by ``tools/route.py`` and
``tools/render_board.py`` so that the router never has to parse S-expressions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / "esp32-board-v1.1.kicad_pcb"
OUT = ROOT / "routing" / "model.json"

NM = 1e6  # nanometres -> mm


def mm(v):
    return round(v / NM, 4)


def shape_name(shape):
    return {
        pcbnew.PAD_SHAPE_CIRCLE: "circle",
        pcbnew.PAD_SHAPE_RECT: "rect",
        pcbnew.PAD_SHAPE_OVAL: "oval",
        pcbnew.PAD_SHAPE_TRAPEZOID: "trapezoid",
        pcbnew.PAD_SHAPE_ROUNDRECT: "roundrect",
        pcbnew.PAD_SHAPE_CHAMFERED_RECT: "chamfered_rect",
        pcbnew.PAD_SHAPE_CUSTOM: "custom",
    }.get(shape, "unknown")


def attr_name(attr):
    return {
        pcbnew.PAD_ATTRIB_PTH: "pth",
        pcbnew.PAD_ATTRIB_SMD: "smd",
        pcbnew.PAD_ATTRIB_CONN: "conn",
        pcbnew.PAD_ATTRIB_NPTH: "npth",
    }.get(attr, "unknown")


def pad_layers(pad):
    out = []
    for lid in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        if pad.IsOnLayer(lid):
            out.append(lid)
    return out


def polygon_points(poly):
    """First outline of a SHAPE_POLY_SET as a list of (x, y) mm."""
    outline = poly.Outline(0)
    return [(mm(outline.CPoint(i).x), mm(outline.CPoint(i).y))
            for i in range(outline.PointCount())]


def collect():
    board = pcbnew.LoadBoard(str(PCB))
    model = {
        "board": {},
        "footprints": [],
        "pads": [],
        "keepouts": [],
        "zones": [],
        "tracks": [],
        "vias": [],
        "nets": {},
    }

    # board outline -----------------------------------------------------
    poly = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(poly, True)
    model["board"]["outline"] = polygon_points(poly)
    bb = board.GetBoardEdgesBoundingBox()
    model["board"]["edges_bbox"] = [mm(bb.GetLeft()), mm(bb.GetTop()),
                                    mm(bb.GetRight()), mm(bb.GetBottom())]
    model["board"]["thickness"] = mm(board.GetDesignSettings().GetBoardThickness())

    # design settings ---------------------------------------------------
    ds = board.GetDesignSettings()
    model["board"]["min_clearance"] = mm(ds.m_MinClearance)
    model["board"]["min_track_width"] = mm(ds.m_TrackMinWidth)
    model["board"]["min_via_dia"] = mm(ds.m_ViasMinSize)
    model["board"]["min_via_drill"] = mm(ds.m_MinThroughDrill)
    model["board"]["edge_clearance"] = mm(ds.m_CopperEdgeClearance)

    # netclasses --------------------------------------------------------
    classes = {}
    for name, nc in board.GetAllNetClasses().items():
        classes[str(name)] = {
            "clearance": mm(nc.GetClearance()),
            "track_width": mm(nc.GetTrackWidth()),
            "via_dia": mm(nc.GetViaDiameter()),
            "via_drill": mm(nc.GetViaDrill()),
        }
    model["netclasses"] = classes

    netclass_of = {}
    for name, nc in board.GetNetClasses().items():
        netclass_of[str(name)] = str(nc.GetName())
    for code, net in board.GetNetInfo().NetsByNetcode().items():
        if code == 0:
            continue
        model["nets"][str(net.GetNetname())] = {
            "code": code,
            "class": netclass_of.get(str(net.GetNetname())),
        }

    # footprints and pads ----------------------------------------------
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        pos = fp.GetPosition()
        entry = {
            "ref": ref,
            "value": fp.GetValue(),
            "lib_id": f"{fp.GetFPID().GetLibNickname()}:{fp.GetFPID().GetLibItemName()}",
            "x": mm(pos.x),
            "y": mm(pos.y),
            "rot": round(fp.GetOrientationDegrees(), 3),
            "layer": board.GetLayerName(fp.GetLayer()),
            "courtyard": [],
            "bbox": [],
        }
        cy = pcbnew.SHAPE_POLY_SET()
        fp.BuildCourtyardCaches()
        if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount():
            cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        elif fp.GetCourtyard(pcbnew.B_CrtYd).OutlineCount():
            cy = fp.GetCourtyard(pcbnew.B_CrtYd)
        if cy.OutlineCount():
            for i in range(cy.OutlineCount()):
                o = cy.Outline(i)
                entry["courtyard"].append(
                    [(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())])
            b = cy.BBox()
            entry["bbox"] = [mm(b.GetLeft()), mm(b.GetTop()),
                             mm(b.GetRight()), mm(b.GetBottom())]

        for pad in fp.Pads():
            p = pad.GetPosition()
            size = pad.GetSize()
            drill = pad.GetDrillSize()
            layers = pad_layers(pad)
            rec = {
                "ref": ref,
                "num": pad.GetNumber(),
                "net": pad.GetNetname(),
                "x": mm(p.x),
                "y": mm(p.y),
                "w": mm(size.x),
                "h": mm(size.y),
                "shape": shape_name(pad.GetShape()),
                "rot": round(pad.GetOrientationDegrees() % 180.0, 3),
                "type": attr_name(pad.GetAttribute()),
                "drill": mm(min(drill.x, drill.y)) if drill.x else 0.0,
                "layers": layers,
                "rr_ratio": round(pad.GetRoundRectRadiusRatio(), 4),
            }
            entry.setdefault("pads", []).append(rec["num"])
            model["pads"].append(rec)
        model["footprints"].append(entry)

    # zones -------------------------------------------------------------
    for zone in board.Zones():
        layers = [board.GetLayerName(l) for l in
                  (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
                  if zone.IsOnLayer(l)]
        rec = {
            "name": zone.GetZoneName(),
            "net": zone.GetNetname(),
            "layers": layers,
            "is_rule_area": bool(zone.GetIsRuleArea()),
            "polygon": polygon_points(zone.Outline()) if zone.Outline().OutlineCount() else [],
        }
        if zone.GetIsRuleArea():
            rec["keepout"] = {
                "tracks": bool(zone.GetDoNotAllowTracks()),
                "vias": bool(zone.GetDoNotAllowVias()),
                "copperpour": bool(zone.GetDoNotAllowZoneFills()),
                "pads": bool(zone.GetDoNotAllowPads()),
                "footprints": bool(zone.GetDoNotAllowFootprints()),
            }
            model["keepouts"].append(rec)
        else:
            model["zones"].append(rec)

    # existing routing (normally empty before the routing pass) ----------
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            model["vias"].append({
                "x": mm(t.GetPosition().x), "y": mm(t.GetPosition().y),
                "dia": mm(t.GetWidth()), "drill": mm(t.GetDrill()),
                "net": t.GetNetname(),
            })
        else:
            model["tracks"].append({
                "layer": board.GetLayerName(t.GetLayer()),
                "net": t.GetNetname(),
                "width": mm(t.GetWidth()),
                "start": [mm(t.GetStart().x), mm(t.GetStart().y)],
                "end": [mm(t.GetEnd().x), mm(t.GetEnd().y)],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  footprints {len(model['footprints'])}  pads {len(model['pads'])}"
          f"  nets {len(model['nets'])}  zones {len(model['zones'])}"
          f"  keepouts {len(model['keepouts'])}")
    print(f"  tracks {len(model['tracks'])}  vias {len(model['vias'])}")


if __name__ == "__main__":
    sys.exit(collect())
