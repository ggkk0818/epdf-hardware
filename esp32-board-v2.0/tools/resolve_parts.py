"""Batch-resolve candidate EasyEDA library devices for every BOM line."""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "library-candidates.json")
EASYEDA = r"C:\Users\ggkk2\AppData\Local\Python\bin\easyeda.exe"


QUERIES = {
    "usb_c": ["USB4105", "GCT USB4105", "TYPE-C-16P 卧贴"],
    "cap_22u_0805": ["22uF 0805"],
    "cap_10u_0805": ["10uF 0805 25V"],
    "cap_1u_0603": ["1uF 0603 25V"],
    "cap_100n_0603": ["100nF 0603 50V"],
    "cap_1n_0603": ["1nF 0603"],
    "cap_4u7_0805": ["4.7uF 0805 25V"],
    "cap_47n_0603": ["47nF 0603"],
    "cap_470p_0603": ["470pF 0603"],
    "cap_4u7_25_0805": ["4.7uF 25V 0805"],
    "cap_1u_25_0805": ["1uF 25V 0805"],
    "tvs_sod323": ["PESD5V0S1BA"],
    "esd_sod323": ["GBLC05C"],
    "esd_lesd": ["LESD3Z5.0CMT1G"],
    "diode_mbr0530": ["MBR0530 SOD-123"],
    "ptc_2a_0805": ["PTC 2A 0805"],
    "ind_1u0": ["1.0uH 5x5 shielded", "MWSA0503S-1R0"],
    "ind_1u2": ["1.2uH 4x4 shielded", "MWSA0402S-1R2"],
    "ind_47u": ["47uH 4020 shielded", "FHD4020S-470"],
    "ntc_10k_0603": ["NTC 10K B3435 0603"],
    "mosfet_si1304": ["Si1304BDL"],
    "res_10k_0603": ["10k 0603 1%"],
    "res_4k7_0603": ["4.7k 0603 1%"],
    "res_0r_0603": ["0R 0603"],
    "res_22r_0603": ["22R 0603"],
    "res_900k_0603": ["900k 0603"],
    "res_180r_0603": ["180R 0603"],
    "res_5k23_0603": ["5.23k 0603"],
    "res_30k1_0603": ["30.1k 0603"],
    "res_100k_0603": ["100k 0603 1%"],
    "res_470k_0603": ["470k 0603 1%"],
    "res_150k_0603": ["150k 0603 1%"],
    "res_1m_0603": ["1M 0603 1%"],
    "res_2r2_0805": ["2.2R 0805"],
}


def search(query, limit=6):
    out = subprocess.run(
        [EASYEDA, "lib", "search", "--query", query, "--limit", str(limit), "--allow-fuzzy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        data = json.loads(out.stdout)
    except Exception:
        return {"query": query, "error": out.stdout[:400] + out.stderr[:400]}
    return data


def main():
    existing = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            existing = json.load(fh)
    for key, queries in QUERIES.items():
        if key in existing and existing[key].get("candidates"):
            continue
        entry = {"queries": queries, "candidates": []}
        seen = set()
        for q in queries:
            res = search(q)
            if not res.get("ok"):
                continue
            for comp in res.get("result", {}).get("components", []):
                uid = comp.get("uuid")
                if uid in seen:
                    continue
                seen.add(uid)
                entry["candidates"].append(
                    {
                        "q": q,
                        "lcsc": comp.get("lcsc"),
                        "mpn": comp.get("manufacturerId"),
                        "name": comp.get("name"),
                        "mfr": comp.get("manufacturer"),
                        "fp": comp.get("footprintName"),
                        "value": comp.get("value"),
                        "desc": (comp.get("description") or "")[:120],
                        "libraryUuid": comp.get("libraryUuid"),
                        "uuid": uid,
                    }
                )
        existing[key] = entry
        print(f"{key}: {len(entry['candidates'])} candidates")
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, ensure_ascii=False, indent=1)
    print("wrote", CACHE)


if __name__ == "__main__":
    main()
