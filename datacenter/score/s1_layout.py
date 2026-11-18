#!/usr/bin/env python3
"""Score stage S1: layout_pred.json against the ground truth, plus the Blender room shell.

    python s1_layout.py --run RUN_DIR --gt GT_DIR [--out score_s1.json]

Score out of 100:
  racks 50  (F1 20, position 15, facing 10, ids 5)   matched by Hungarian assignment, <= 300 mm
  room 10   (inner polygon: bbox 3 + polygon IoU 3, heights + wall thickness 4)
  columns 5, crah 5, doors 5, aisles 10 (hard: cold aisles only)
  shell 15  (walls present 5, door openings 2, wall height 2, raised floor 3, columns 3)
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import subprocess
import tempfile

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = pathlib.Path(__file__).resolve().parent
BLENDER = "/opt/blender/blender"
TOL = 300.0


def match(gt, pred, tol=TOL):
    """Hungarian match on centre distance; returns [(gi, pi, dist)] with dist <= tol."""
    if not gt or not pred:
        return []
    c = np.array([[math.dist(g["center"], p["center"]) for p in pred] for g in gt])
    gi, pi = linear_sum_assignment(c)
    return [(a, b, c[a, b]) for a, b in zip(gi, pi) if c[a, b] <= tol]


def f1(n_gt, n_pred, n_match):
    if n_gt == 0 and n_pred == 0:
        return 1.0
    p = n_match / n_pred if n_pred else 0.0
    r = n_match / n_gt if n_gt else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def iou(a, b):
    a = [min(a[0], a[2]), min(a[1], a[3]), max(a[0], a[2]), max(a[1], a[3])]
    b = [min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3])]
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def size_ok(g, p, tol=50):
    return sorted(g) == sorted(g) and all(abs(a - b) <= tol for a, b in zip(g, p))


def score_layout(gt, pred):
    det = {}
    # racks
    gr, pr = gt["racks"], pred.get("racks") or []
    m = match(gr, pr)
    det["racks"] = {
        "gt": len(gr), "pred": len(pr), "matched": len(m),
        "f1": f1(len(gr), len(pr), len(m)),
        "rmse_mm": math.sqrt(sum(d * d for *_, d in m) / len(m)) if m else None,
        "facing_acc": sum(gr[a]["facing"] == pr[b].get("facing") for a, b, _ in m) / len(gr),
        "id_acc": sum(gr[a]["id"] == pr[b].get("id") for a, b, _ in m) / len(gr),
        "size_acc": sum(size_ok(gr[a]["size"], pr[b].get("size", [0, 0])) for a, b, _ in m) / len(gr),
    }
    r = det["racks"]
    pos = (1 - min(r["rmse_mm"], TOL) / TOL) * (len(m) / len(gr)) if m else 0.0
    s_racks = 20 * r["f1"] + 15 * pos + 10 * r["facing_acc"] + 5 * r["id_acc"]

    # room
    groom, proom = gt["room"], pred.get("room") or {}
    try:
        gb, pb = bbox(groom["polygon"]), bbox(proom["polygon"])
        corner_err = max(abs(a - b) for a, b in zip(gb, pb))
    except Exception:
        corner_err = None
    hk = ("wall_thickness", "clear_height", "raised_floor_height")
    h_ok = sum(abs((proom.get(k) or 0) - groom[k]) <= 0.01 * groom[k] for k in hk) / len(hk)
    try:
        from shapely.geometry import Polygon
        pg, pp = Polygon(groom["polygon"]), Polygon(proom["polygon"])
        piou = pg.intersection(pp).area / pg.union(pp).area if pp.is_valid else 0.0
    except Exception:
        piou = 0.0
    det["room"] = {"bbox_max_err_mm": corner_err, "polygon_iou": round(piou, 4), "heights_ok": h_ok}
    s_room = (3 * max(0.0, 1 - corner_err / 500) if corner_err is not None else 0) \
        + 3 * max(0.0, (piou - 0.9) / 0.1) + 4 * h_ok

    # columns, crah, doors
    def simple(key, w, extra=None):
        g, p = gt[key], pred.get(key) or []
        mm = match(g, p)
        d = {"gt": len(g), "pred": len(p), "matched": len(mm), "f1": f1(len(g), len(p), len(mm)),
             "mean_err_mm": (sum(x for *_, x in mm) / len(mm)) if mm else None}
        s = f1(len(g), len(p), len(mm))
        if extra and mm:
            ok = sum(extra(g[a], p[b]) for a, b, _ in mm) / len(g)
            d["attr_acc"] = ok
            s = 0.5 * s + 0.5 * ok
        det[key] = d
        return w * s
    s_cols = simple("columns", 5)
    s_crah = simple("crah", 5, lambda g, p: g["facing"] == p.get("facing"))
    s_door = simple("doors", 5, lambda g, p: abs(g["width"] - (p.get("width") or 0)) <= 100)

    # aisles: best IoU per GT aisle with same type
    pa = pred.get("aisles") or []
    ious = []
    scored_aisles = gt["aisles"] if gt.get("scenario", "easy") == "easy" else [x for x in gt["aisles"] if x["type"] == "cold"]
    for a in scored_aisles:
        cands = [iou(a["rect"], p["rect"]) for p in pa if p.get("type") == a["type"] and isinstance(p.get("rect"), list) and len(p["rect"]) == 4]
        ious.append(max(cands, default=0.0))
    det["aisles"] = {"iou_per_gt": [round(v, 3) for v in ious], "pred": len(pa)}
    s_ais = 10 * (sum(ious) / len(ious)) if ious else 0

    parts = {"racks": s_racks, "room": s_room, "columns": s_cols, "crah": s_crah, "doors": s_door, "aisles": s_ais}
    return parts, det


def shell_rays(gt):
    """Horizontal rays at z = 1.5 m from 0.3 m inside each wall, pointing out. Expect Wall_* except at doors."""
    t = gt["room"]["wall_thickness"] / 1000
    poly = [(x / 1000, y / 1000) for x, y in gt["room"]["polygon"]]
    doors = [(d["center"][0] / 1000, d["center"][1] / 1000, d["width"] / 1000) for d in gt["doors"]]
    rays, kinds = [], []
    n = len(poly)
    area2 = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = (uy, -ux) if area2 > 0 else (-uy, ux)  # outward normal
        for k in range(1, 10):
            px, py = x0 + ux * L * k / 10, y0 + uy * L * k / 10
            if any(math.hypot(px - dx - nx * t / 2, py - dy - ny * t / 2) < w / 2 + 0.15 for dx, dy, w in doors):
                continue
            rays.append([px - nx * 0.3, py - ny * 0.3, 1.5, nx, ny, 0, 0.3 + t + 0.05]); kinds.append("wall")
        for dx, dy, w in doors:
            # door centre lies on this wall's centreline?
            cx, cy = dx - nx * t / 2, dy - ny * t / 2
            proj = (cx - x0) * ux + (cy - y0) * uy
            off = abs((cx - x0) * nx + (cy - y0) * ny)
            if off < 0.05 and 0 < proj < L:
                rays.append([cx - nx * 0.3, cy - ny * 0.3, 1.5, nx, ny, 0, 0.3 + t + 0.3]); kinds.append("door")
    return rays, kinds


def score_shell(run, gt):
    blend = run / "s1.blend"
    if not blend.exists():
        return 0.0, {"error": "s1.blend missing"}
    rays, kinds = shell_rays(gt)
    with tempfile.TemporaryDirectory() as td:
        q, o = pathlib.Path(td) / "q.json", pathlib.Path(td) / "o.json"
        q.write_text(json.dumps({"rays": rays}))
        subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "blender_probe.py"), "--", str(q), str(o)],
                       capture_output=True, timeout=300)
        if not o.exists():
            return 0.0, {"error": "probe failed"}
        res = json.loads(o.read_text())
    objs, hits = [o for o in res["objects"] if o["min"] is not None], res["hits"]
    wall_hits = [h for h, k in zip(hits, kinds) if k == "wall"]
    walls_ok = sum(1 for h in wall_hits if h and h.startswith("Wall")) / max(len(wall_hits), 1)
    door_hits = [h for h, k in zip(hits, kinds) if k == "door"]
    doors_ok = sum(1 for h in door_hits if h is None) / max(len(door_hits), 1) if door_hits else 0.0
    H = (gt["room"]["raised_floor_height"] + gt["room"]["clear_height"]) / 1000
    walls = [o for o in objs if o["name"].startswith("Wall")]
    height_ok = 1.0 if walls and abs(max(o["max"][2] for o in walls) - H) <= 0.02 and min(o["min"][2] for o in walls) <= 0.02 else 0.0
    rf = next((o for o in objs if o["name"].startswith("RaisedFloor")), None)
    floor_ok = 0.0
    if rf:
        ib = [v / 1000 for v in bbox(gt["room"]["polygon"])]
        top_ok = abs(rf["max"][2] - gt["room"]["raised_floor_height"] / 1000) <= 0.02
        cover = (rf["min"][0] <= ib[0] + 0.05 and rf["min"][1] <= ib[1] + 0.05 and
                 rf["max"][0] >= ib[2] - 0.05 and rf["max"][1] >= ib[3] - 0.05)
        floor_ok = 0.5 * top_ok + 0.5 * cover
    cols_ok = 0.0
    for c in gt["columns"]:
        name = "Column_" + c["id"].replace("/", "_")
        o = next((o for o in objs if o["name"] == name or o["name"].startswith(name + ".")), None)
        if o:
            cx, cy = (o["min"][0] + o["max"][0]) / 2, (o["min"][1] + o["max"][1]) / 2
            sx, sy = o["max"][0] - o["min"][0], o["max"][1] - o["min"][1]
            if math.dist((cx, cy), (c["center"][0] / 1000, c["center"][1] / 1000)) <= 0.1 and \
                    abs(sx - c["size"][0] / 1000) <= 0.05 and abs(sy - c["size"][1] / 1000) <= 0.05:
                cols_ok += 1
    cols_ok /= max(len(gt["columns"]), 1)
    det = {"walls_hit_rate": round(walls_ok, 3), "door_open_rate": round(doors_ok, 3), "wall_height_ok": height_ok,
           "raised_floor": floor_ok, "columns_ok": round(cols_ok, 3), "n_objects": len(objs)}
    return 5 * walls_ok + 2 * doors_ok + 2 * height_ok + 3 * floor_ok + 3 * cols_ok, det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    run, gtd = pathlib.Path(a.run), pathlib.Path(a.gt)
    gt = json.loads((gtd / "layout.json").read_text())
    try:
        pred = json.loads((run / "layout_pred.json").read_text())
        parts, det = score_layout(gt, pred)
    except Exception as e:
        parts, det = {k: 0.0 for k in ("racks", "room", "columns", "crah", "doors", "aisles")}, {"layout_error": str(e)}
    parts["shell"], det["shell"] = score_shell(run, gt)
    total = sum(parts.values())
    res = {"stage": "s1", "total": round(total, 2), "parts": {k: round(v, 2) for k, v in parts.items()}, "detail": det}
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
