"""Minimal KiCad footprint (.kicad_mod) reader / re-writer helpers.

Only what gen_pcb.py needs: pad inventory for net assignment, bounding boxes for
placement, and re-emission of a footprint as a .kicad_pcb ``(footprint ...)``
block with fresh UUIDs and an explicit ``(at x y rot)``.
"""

import re
import uuid
from pathlib import Path

FP_ROOT = Path("C:/Program Files/KiCad/10.0/share/kicad/footprints")


def read_mod(lib_nick: str, name: str) -> str:
    p = FP_ROOT / f"{lib_nick}.pretty" / f"{name}.kicad_mod"
    return p.read_text(encoding="utf-8")


def split_children(text: str):
    """Split the children of a top level s-expr, returning (head, [child_texts])."""
    lead = len(text) - len(text.lstrip())
    if lead:
        text = text.lstrip()
    i = text.find("(")
    assert i == 0, text[:40]
    depth = 0
    j = 0
    while j < len(text):
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    head_end = text.find(" ", 1)
    inner = text[head_end:j]
    children = []
    k = 0
    depth = 0
    start = None
    while k < len(inner):
        c = inner[k]
        if c == "(":
            if depth == 0:
                start = k
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                children.append(inner[start : k + 1])
        k += 1
    return text[:head_end], children


def child_key(child: str) -> str:
    m = re.match(r"\((\S+)", child)
    return m.group(1) if m else ""


def parse_pads(footprint_text: str):
    """Return list of dicts: number, type, at(x,y,rot), size, drill, is_th, layers."""
    _, children = split_children(footprint_text)
    pads = []
    for ch in children:
        if child_key(ch) != "pad":
            continue
        num = re.match(r'\(pad\s+"([^"]*)"\s+(\S+)\s+(\S+)', ch)
        at = re.search(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\)", ch)
        size = re.search(r"\(size\s+(-?[\d.]+)\s+(-?[\d.]+)\)", ch)
        drill = re.search(r"\(drill\s+(?:oval\s+)?(-?[\d.]+)(?:\s+(-?[\d.]+))?\)", ch)
        pads.append(
            {
                "number": num.group(1),
                "type": num.group(2),
                "shape": num.group(3),
                "x": float(at.group(1)),
                "y": float(at.group(2)),
                "rot": float(at.group(3) or 0),
                "w": float(size.group(1)) if size else 0.0,
                "h": float(size.group(2)) if size else 0.0,
                "drill": float(drill.group(1)) if drill else 0.0,
            }
        )
    return pads


def pad_nets_set(footprint_text: str, nets: dict):
    """Insert ``(net N "name")`` into each pad given number -> net name."""
    _, children = split_children(footprint_text)
    out = []
    for ch in children:
        if child_key(ch) == "pad":
            num = re.match(r'\(pad\s+"([^"]*)"', ch).group(1)
            if num in nets and nets[num]:
                nid, nname = nets[num]
                # Drop any pre-existing net token, then append ours.
                ch = re.sub(r'\s*\(net\s+\d+\s+"[^"]*"\)', "", ch)
                ch = ch[:-1].rstrip() + f'\n\t\t(net {nid} "{nname}")\n\t)'
        out.append(ch)
    return out


def fresh_uuids(text: str) -> str:
    def rep(m):
        return f'(uuid "{uuid.uuid4()}")'

    text = re.sub(r'\(uuid\s+"[^"]*"\)', rep, text)
    text = re.sub(r'\(tstamp\s+"[^"]*"\)', rep, text)
    text = re.sub(r"\(tstamp\s+[0-9A-Fa-f]+\)", rep, text)
    return text


def set_pad_angle(pad_text: str, rot: float) -> str:
    """KiCad keeps a pad's ``(at x y angle)`` orientation board referenced: when a
    footprint is placed at an angle every pad angle has to carry that angle too,
    otherwise the pad *position* rotates but the pad *shape* does not."""
    if not rot:
        return pad_text

    def rep(m):
        x, y = m.group(1), m.group(2)
        a = float(m.group(3)) if m.group(3) else 0.0
        return f"(at {x} {y} {(a + rot) % 360:g})"

    return re.sub(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\)", rep, pad_text, count=1)


DROP_TOP = {"version", "generator", "generator_version", "layer", "uuid", "tstamp",
            "embedded_fonts", "property", "attr"}


def place(footprint_text: str, lib_id: str, ref: str, value: str, x: float, y: float,
          rot: float, nets: dict, layer: str = "F.Cu") -> str:
    """Return a .kicad_pcb footprint block."""
    _, children = split_children(footprint_text)
    # Keep the original property blocks (they carry Reference/Value placement).
    props = [c for c in children if child_key(c) == "property"]
    attr = [c for c in children if child_key(c) == "attr"]
    meta = [c for c in children if child_key(c) in ("descr", "tags")]
    rest = [c for c in children if child_key(c) not in
            ("version", "generator", "generator_version", "layer", "uuid", "tstamp",
             "property", "attr", "embedded_fonts", "descr", "tags",
             # Some libraries (e.g. the Hirose microSD socket) embed rule areas in
             # the footprint.  KiCad keeps those polygons in the footprint's local
             # frame for DRC and they then punch phantom keep-outs across the board,
             # so they are dropped here and reproduced as board level rule areas.
             "zone")]

    def fix_prop(p):
        if re.match(r'\(property\s+"Reference"', p):
            p = re.sub(r'\(property\s+"Reference"\s+"[^"]*"',
                       f'(property "Reference" "{ref}"', p)
        elif re.match(r'\(property\s+"Value"', p):
            p = re.sub(r'\(property\s+"Value"\s+"[^"]*"',
                       f'(property "Value" "{value}"', p)
        # Hide Reference/Value text on the fab layer of connectors etc. is kept as-is.
        return p

    lines = [f'\t(footprint "{lib_id}"']
    lines.append(f'\t\t(layer "{layer}")')
    lines.append(f'\t\t(uuid "{uuid.uuid4()}")')
    lines.append(f"\t\t(at {x:.4f} {y:.4f}{'' if rot == 0 else f' {rot:g}'})")
    lines.extend(meta)
    for p in props:
        lines.append(fix_prop(p))
    for a in attr:
        lines.append(a)
    for ch in rest:
        if child_key(ch) == "pad" and nets:
            num = re.match(r'\(pad\s+"([^"]*)"', ch).group(1)
            if num in nets and nets[num]:
                nid, nname = nets[num]
                ch = re.sub(r'\s*\(net\s+\d+\s+"[^"]*"\)', "", ch)
                ch = ch[:-1].rstrip() + f'\n\t\t\t(net {nid} "{nname}")\n\t\t)'
        if child_key(ch) == "pad":
            ch = set_pad_angle(ch, rot)
        lines.append(ch)
    lines.append("\t)")
    return fresh_uuids("\n".join(lines))
