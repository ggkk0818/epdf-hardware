"""Pick one real EasyEDA library device per BOM line, from live search results.

Every emitted uuid is a value that `easyeda lib search` actually returned; the
script never invents identity. Selection is by preferred LCSC C-number when
given, otherwise first candidate whose footprint/value passes the accept gate.
"""

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "library-candidates.json")
OUT = os.path.join(ROOT, "design", "parts-map.json")
EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"
LIB = "0819f05c4eef4c71ace90d822a990e87"


# key -> (queries, lcsc preference, footprint regex gate)
SPEC = {
    "U1": (["ESP32-S3-WROOM-1-N16R8"], "C2913202", r"ESP32-S3-WROOM-1"),
    "U2": (["BQ25895RTWT"], "C2861263", r"WQFN-24"),
    "U3": (["TPS63070RNMT"], "C964639", r"VQFN"),
    "U4": (["MAX17048G+T10"], "C2682616", r"TDFN-8"),
    "U5": (["TUSB320LIRWBR"], "C2836598", r"X2QFN-12"),
    "U6": (["TPS22918DBVR"], "C131941", r"SOT-23-6"),
    "J1": (["USB4105"], "C5184243", r"USB-C"),
    "J2": (["X05B20U24T"], "C437036", r"FPC"),
    "J3": (["DM3AT-SF-PEJM5"], "C114218", r"SD-SMD"),
    "J4": (["53261-0271"], "C189700", r"CONN-SMD_532610271"),
    "SW": (["B3U-1000P"], "C231329", r"KEY-SMD"),
    "Q1": (["Si1304BDL"], None, r"SOT-323|SC-70"),
    "D1": (["PESD5V0S1BA"], None, r"SOD-323"),
    "D23": (["GBLC05C"], None, r"SOD-323"),
    "D45": (["LESD3Z5.0CMT1G"], None, r"SOD-323"),
    "D6": (["MBR0530"], None, r"SOD-123"),
    "F": (["PPTCSMD0805-200"], "C9900004097", r"F0805"),
    "L1": (["NR5040-1.0uH"], "C49581188", r"IND-SMD"),
    "L2": (["MWSA0402S-1R2MT"], "C408333", r"IND-SMD"),
    "L3": (["FHD4020S-470MT"], "C843300", r"IND-SMD"),
    "NTC1": (["NTCS0603E3103FLT"], "C142556", r"R0603"),
    "C_22uF_0805": (["22uF 0805"], "C45783", r"C0805"),
    "C_10uF_0805": (["10uF 0805 25V"], "C15850", r"C0805"),
    "C_1uF_0603": (["1uF 0603 25V"], "C15849", r"C0603"),
    "C_100nF_0603": (["100nF 0603 50V"], "C14663", r"C0603"),
    "C_1nF_0603": (["1nF 0603"], "C1588", r"C0603"),
    "C_4u7uF_0805": (["4.7uF 0805 25V"], "C1779", r"C0805"),
    "C_47nF_0603": (["47nF 0603"], "C1622", r"C0603"),
    "C_470pF_0603": (["470pF 0603"], "C1620", r"C0603"),
    "C_1uF_25V_0805": (["1uF 25V 0805"], "C28323", r"C0805"),
    "R_10k_0603": (["10k 0603 1%"], "C25804", r"R0603"),
    "R_4k7_0603": (["4.7k 0603 1%"], "C23162", r"R0603"),
    "R_0R_0603": (["0R 0603"], "C21189", r"R0603"),
    "R_22R_0603": (["22R 0603"], "C23345", r"R0603"),
    "R_900k_0603": (["0603WAF9003T5E"], "C407504", r"R0603"),
    "R_180R_0603": (["0603WAF1800T5E"], "C22828", r"R0603"),
    "R_5k23_0603": (["0603WAF5231T5E"], "C23068", r"R0603"),
    "R_30k1_0603": (["0603WAF3012T5E"], "C23000", r"R0603"),
    "R_100k_0603": (["100k 0603 1%"], "C25803", r"R0603"),
    "R_470k_0603": (["470k 0603 1%"], "C23178", r"R0603"),
    "R_150k_0603": (["150k 0603 1%"], "C22807", r"R0603"),
    "R_1M_0603": (["RMC06031M1%N"], "C269705", r"R0603"),
    "R_2R2_0805": (["2.2R 0805"], "C17521", r"R0805"),
}


def search(query, limit=8):
    res = subprocess.run(
        [EASYEDA, "lib", "search", "--query", query, "--limit", str(limit), "--allow-fuzzy"],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        return json.loads(res.stdout)
    except Exception:
        return {"ok": False, "result": {"components": []}}


def load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_cache(cache):
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1)


def gather(cache, key, queries):
    entry = cache.setdefault(key, {"queries": queries, "candidates": []})
    seen = {c["uuid"] for c in entry["candidates"]}
    for q in queries:
        res = search(q)
        for comp in res.get("result", {}).get("components", []):
            uid = comp.get("uuid")
            if uid in seen:
                continue
            seen.add(uid)
            entry["candidates"].append({
                "q": q,
                "lcsc": comp.get("lcsc"),
                "mpn": comp.get("manufacturerId"),
                "name": comp.get("name"),
                "mfr": comp.get("manufacturer"),
                "fp": comp.get("footprintName"),
                "value": comp.get("value"),
                "desc": (comp.get("description") or "")[:100],
                "libraryUuid": comp.get("libraryUuid"),
                "uuid": uid,
            })
    return entry


def pick(entry, lcsc_pref, fp_gate):
    cands = entry["candidates"]
    if lcsc_pref:
        for c in cands:
            if c["lcsc"] == lcsc_pref:
                return c
    gate = re.compile(fp_gate, re.I) if fp_gate else None
    for c in cands:
        if gate and not gate.search(c.get("fp") or ""):
            continue
        return c
    return None


def main():
    cache = load_cache()
    for key, (queries, _, _) in SPEC.items():
        if key in cache and cache[key].get("candidates"):
            continue
        gather(cache, key, queries)
    save_cache(cache)

    parts = {}
    missing = []
    for key, (queries, pref, gate) in SPEC.items():
        entry = cache.get(key, {"candidates": []})
        chosen = pick(entry, pref, gate)
        if not chosen:
            missing.append(key)
            continue
        parts[key] = {
            "value": chosen.get("value") or chosen.get("mpn"),
            "mpn": chosen.get("mpn"),
            "lcsc": chosen.get("lcsc"),
            "fp": chosen.get("fp"),
            "uuid": chosen.get("uuid"),
            "libraryUuid": chosen.get("libraryUuid") or LIB,
            "mfr": chosen.get("mfr"),
            "desc": chosen.get("desc"),
        }

    doc = {
        "_doc": [
            "Part selection for esp32s3-board-v2.0, generated by tools/pick_parts.py from live",
            "`easyeda lib search` results. Every uuid came back from the library; nothing here",
            "is fabricated. LCSC C-numbers recorded for ordering.",
        ],
        "library": LIB,
        "parts": parts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("parts:", len(parts))
    for k, v in parts.items():
        print(f"  {k:16s} {v['lcsc']:14s} {str(v['mpn'])[:28]:28s} {v['fp']}")
    if missing:
        print("MISSING:", missing)


if __name__ == "__main__":
    main()
