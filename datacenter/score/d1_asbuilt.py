#!/usr/bin/env python3
"""Score stage D1 (as-built check: design layout + site photos -> as-built layout).

    python d1_asbuilt.py --run RUN_DIR --design design.json --gt asbuilt.json [--out score_d1.json]

Reads RUN_DIR/asbuilt_pred.json. Racks and CRAH units are pooled into one list of items (centre, facing, width = size[0]).

Changes (70 points)
  Two items are "the same" if their centres are <= 150 mm apart, they face the same way and their widths differ by <= 50 mm
  (pairs are one-to-one, as many as possible).
  A change is a design item with no same item in the other layout (label `gone`) or an item of the other layout with no
  same item in the design (label `new`). True changes come from design vs as-built, predicted changes from design vs prediction.
  Predicted changes are matched one-to-one to true changes: same label and centres <= 300 mm apart; a `new` match also
  needs the same facing and widths within 50 mm.  points = 70 * F1(matched, predicted changes, true changes)
Inventory (30 points)
  As-built items are matched one-to-one to predicted items: centres <= 300 mm apart and same facing.
  surplus = predicted items without a match.  points = 30 * max(0, matched - surplus) / number of as-built items
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib

import numpy as np
from scipy.optimize import linear_sum_assignment

SAME_MM, WIDTH_MM, MATCH_MM = 150.0, 50.0, 300.0
FACINGS = ("N", "S", "E", "W")
BIG = 1e7


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def items(lay):
    """Pooled racks + CRAH as dicts with center, size, width, facing, id, kind. Returns (valid items, number skipped)."""
    out, bad = [], 0
    for kind in ("racks", "crah"):
        src = lay.get(kind) if isinstance(lay, dict) else None
        for it in src if isinstance(src, list) else []:
            try:
                c, s, f = it["center"], it["size"], it["facing"]
                ok = len(c) == 2 and all(_num(v) for v in c) and len(s) == 2 and all(_num(v) for v in s) and f in FACINGS
            except Exception:
                ok = False
            if not ok:
                bad += 1
                continue
            out.append({"kind": kind, "id": str(it.get("id", "")), "center": [float(c[0]), float(c[1])],
                        "size": [float(s[0]), float(s[1])], "width": float(s[0]), "facing": f})
    return out, bad


def pair(A, B, ok):
    """One-to-one pairs (i, j) with ok(A[i], B[j]); as many pairs as possible, then the smallest total distance."""
    if not A or not B:
        return []
    cost = np.full((len(A), len(B)), BIG)
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            if ok(a, b):
                cost[i, j] = math.dist(a["center"], b["center"])
    ri, ci = linear_sum_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(ri, ci) if cost[i, j] < BIG]


def same(a, b):
    return math.dist(a["center"], b["center"]) <= SAME_MM and a["facing"] == b["facing"] and abs(a["width"] - b["width"]) <= WIDTH_MM


def change_match(g, p):
    if g["label"] != p["label"] or math.dist(g["center"], p["center"]) > MATCH_MM:
        return False
    return g["label"] == "gone" or (g["facing"] == p["facing"] and abs(g["width"] - p["width"]) <= WIDTH_MM)


def near(a, b):
    return math.dist(a["center"], b["center"]) <= MATCH_MM and a["facing"] == b["facing"]


def changes(design, other):
    """Changes of `other` against the design; also returns the same-pairs {design index: other index}."""
    pairs = pair(design, other, same)
    di, oi = {i for i, _ in pairs}, {j for _, j in pairs}
    ch = [dict(design[i], label="gone", design_index=i) for i in range(len(design)) if i not in di]
    ch += [dict(other[j], label="new", other_index=j) for j in range(len(other)) if j not in oi]
    return ch, dict(pairs)


def f1(n_true, n_pred, n_match):
    p = n_match / n_pred if n_pred else 0.0
    r = n_match / n_true if n_true else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def evaluate(design_lay, gt_lay, pred_lay):
    design, _ = items(design_lay)
    gt, _ = items(gt_lay)
    pred, bad = items(pred_lay)
    gt_ch, _ = changes(design, gt)
    pr_ch, pred_same = changes(design, pred)
    cm = pair(gt_ch, pr_ch, change_match)
    score_f1, prec, rec = f1(len(gt_ch), len(pr_ch), len(cm))
    inv = pair(gt, pred, near)
    surplus = len(pred) - len(inv)
    inv_frac = max(0, len(inv) - surplus) / len(gt)
    return {"design": design, "gt": gt, "pred": pred, "invalid_pred_items": bad, "gt_changes": gt_ch, "pred_changes": pr_ch,
            "change_pairs": cm, "pred_same": pred_same, "f1": score_f1, "precision": prec, "recall": rec,
            "inventory_pairs": inv, "surplus": surplus, "inventory_fraction": inv_frac}


def describe(ch, design):
    k = min(range(len(design)), key=lambda i: math.dist(design[i]["center"], ch["center"]))
    return {"label": ch["label"], "kind": ch["kind"], "center": [round(v) for v in ch["center"]], "facing": ch["facing"],
            "width": round(ch["width"]), "nearest_design_id": design[k]["id"],
            "nearest_design_dist_mm": round(math.dist(design[k]["center"], ch["center"]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--design", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    design_lay = json.loads(pathlib.Path(a.design).read_text())
    gt_lay = json.loads(pathlib.Path(a.gt).read_text())
    try:
        pred_lay = json.loads((pathlib.Path(a.run) / "asbuilt_pred.json").read_text())
        if not isinstance(pred_lay, dict):
            raise ValueError("top level must be an object")
        ev = evaluate(design_lay, gt_lay, pred_lay)
    except Exception as e:
        res = {"stage": "d1", "total": 0, "error": f"asbuilt_pred.json: {e}"}
        print(json.dumps(res))
        if a.out:
            pathlib.Path(a.out).write_text(json.dumps(res, indent=1))
        return
    d = ev["design"]
    found_g = {i for i, _ in ev["change_pairs"]}
    found_p = {j for _, j in ev["change_pairs"]}
    parts = {"changes": round(70 * ev["f1"], 2), "inventory": round(30 * ev["inventory_fraction"], 2)}
    res = {"stage": "d1", "total": round(70 * ev["f1"] + 30 * ev["inventory_fraction"], 2), "parts": parts,
           "detail": {
               "true_changes": len(ev["gt_changes"]), "predicted_changes": len(ev["pred_changes"]), "matched_changes": len(ev["change_pairs"]),
               "precision": round(ev["precision"], 3), "recall": round(ev["recall"], 3), "f1": round(ev["f1"], 3),
               "items_as_built": len(ev["gt"]), "items_design": len(d), "items_predicted": len(ev["pred"]),
               "items_matched": len(ev["inventory_pairs"]), "items_surplus": ev["surplus"], "invalid_pred_items": ev["invalid_pred_items"],
               "found": [describe(c, d) for i, c in enumerate(ev["gt_changes"]) if i in found_g],
               "missed": [describe(c, d) for i, c in enumerate(ev["gt_changes"]) if i not in found_g],
               "false_alarms": [describe(c, d) for j, c in enumerate(ev["pred_changes"]) if j not in found_p]}}
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
