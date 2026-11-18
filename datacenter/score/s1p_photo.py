#!/usr/bin/env python3
"""Score stage S1P (survey photos -> layout).

    python s1p_photo.py --run RUN_DIR --gt GT_DIR/layout.json [--out score_s1p.json]

100 points:
  racks 70 = count F1 15 + position 25 + facing 15 + width 15
      matched by Hungarian assignment on centre distance, a match only if <= 600 mm;
      position credit per GT rack: 1 at <= 100 mm, falling linearly to 0 at 600 mm (unmatched = 0)
  crah 10 = F1 5 + facing 5 (<= 600 mm)
  cold aisles 20 = mean best IoU per GT cold aisle
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib

import numpy as np
from scipy.optimize import linear_sum_assignment

TOL = 600.0


def match(gt, pred, tol=TOL):
    if not gt or not pred:
        return []
    c = np.array([[math.dist(g["center"], p["center"]) for p in pred] for g in gt])
    gi, pi = linear_sum_assignment(c)
    return [(a, b, c[a, b]) for a, b in zip(gi, pi) if c[a, b] <= tol]


def f1(ng, np_, nm):
    p = nm / np_ if np_ else 0.0
    r = nm / ng if ng else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def iou(a, b):
    a = [min(a[0], a[2]), min(a[1], a[3]), max(a[0], a[2]), max(a[1], a[3])]
    b = [min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3])]
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def valid(items, keys=("center", "size", "facing")):
    out = []
    for it in items or []:
        try:
            if all(k in it for k in keys) and len(it["center"]) == 2:
                out.append(it)
        except TypeError:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    gt = json.loads(pathlib.Path(a.gt).read_text())
    try:
        pred = json.loads((pathlib.Path(a.run) / "layout_pred.json").read_text())
    except Exception as e:
        res = {"stage": "s1p", "total": 0, "error": f"layout_pred.json: {e}"}
        print(json.dumps(res))
        return
    gr, pr = gt["racks"], valid(pred.get("racks"))
    m = match(gr, pr)
    pos = sum(1.0 if d <= 100 else max(0.0, 1 - (d - 100) / (TOL - 100)) for *_, d in m) / len(gr)
    face = sum(gr[i]["facing"] == pr[j]["facing"] for i, j, _ in m) / len(gr)
    width = sum(abs(gr[i]["size"][0] - pr[j]["size"][0]) <= 50 for i, j, _ in m) / len(gr)
    errs = sorted(d for *_, d in m)
    s_r = 15 * f1(len(gr), len(pr), len(m)) + 25 * pos + 15 * face + 15 * width
    gc, pc = gt["crah"], valid(pred.get("crah"))
    mc = match(gc, pc)
    s_c = 5 * f1(len(gc), len(pc), len(mc)) + 5 * (sum(gc[i]["facing"] == pc[j]["facing"] for i, j, _ in mc) / len(gc))
    cold = [x for x in gt["aisles"] if x["type"] == "cold"]
    pa = [x for x in pred.get("aisles") or [] if x.get("type") == "cold" and isinstance(x.get("rect"), list) and len(x["rect"]) == 4]
    ious = [max((iou(c["rect"], p["rect"]) for p in pa), default=0.0) for c in cold]
    s_a = 20 * sum(ious) / len(ious)
    # per-row breakdown so a reader can see where the misses are
    rows = {}
    matched_gt = {i: (j, d) for i, j, d in m}
    for i, r in enumerate(gr):
        row = r.get("row", r["id"][0])
        e = rows.setdefault(row, {"racks": 0, "matched": 0, "facing_ok": 0, "err_mm": []})
        e["racks"] += 1
        if i in matched_gt:
            j, d = matched_gt[i]
            e["matched"] += 1
            e["facing_ok"] += gr[i]["facing"] == pr[j]["facing"]
            e["err_mm"].append(round(d))
    for e in rows.values():
        e["median_err_mm"] = sorted(e["err_mm"])[len(e["err_mm"]) // 2] if e["err_mm"] else None
        del e["err_mm"]
    parts = {"rack_count": round(15 * f1(len(gr), len(pr), len(m)), 2), "rack_position": round(25 * pos, 2),
             "rack_facing": round(15 * face, 2), "rack_width": round(15 * width, 2), "crah": round(s_c, 2), "cold_aisles": round(s_a, 2)}
    res = {"stage": "s1p", "total": round(s_r + s_c + s_a, 2), "parts": parts,
           "detail": {"racks_gt": len(gr), "racks_pred": len(pr), "racks_matched": len(m),
                      "median_err_mm": round(errs[len(errs) // 2]) if errs else None, "p90_err_mm": round(errs[int(len(errs) * 0.9)]) if errs else None,
                      "facing_acc": round(face, 3), "width_acc": round(width, 3), "per_row": rows,
                      "crah": {"gt": len(gc), "pred": len(pc), "matched": len(mc)}, "cold_aisle_iou": [round(v, 3) for v in ious]}}
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
