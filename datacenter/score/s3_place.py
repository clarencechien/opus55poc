#!/usr/bin/env python3
"""Score stage S3: rack placement, cold-aisle containment, perforated tiles, cable trays.

    python s3_place.py --run RUN_DIR --layout inputs/easy-s3/layout.json [--out score_s3.json]

100 points: position 25, facing 20, height 5, ids 5, collisions 10, containment 15, perforated tiles 10, cable trays 10.
A rack is the object with custom property rackId (its root). Its footprint centre and bottom come from the bounding box of
its mesh descendants, or from the root transform for a collection instance; facing comes from the root's rotation of the
template front (-y).
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
BLENDER = "/opt/blender/blender"
DIRS = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
FLOOR = 0.6
RACK_H = 2.0


def probe(blend, rays):
    with tempfile.TemporaryDirectory() as td:
        q, o = pathlib.Path(td) / "q.json", pathlib.Path(td) / "o.json"
        q.write_text(json.dumps({"rays": rays}))
        subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "blender_probe.py"), "--", str(q), str(o)],
                       capture_output=True, timeout=900)
        return json.loads(o.read_text())


def facing_of(front):
    fx, fy = front[0], front[1]
    best = max(DIRS, key=lambda k: DIRS[k][0] * fx + DIRS[k][1] * fy)
    ang = math.degrees(math.acos(max(-1, min(1, (DIRS[best][0] * fx + DIRS[best][1] * fy) / (math.hypot(fx, fy) or 1)))))
    return best, ang


def rect_overlap(a, b, tol=0.005):
    return min(a[2], b[2]) - max(a[0], b[0]) > tol and min(a[3], b[3]) - max(a[1], b[1]) > tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run = pathlib.Path(a.run)
    lay = json.loads(pathlib.Path(a.layout).read_text())
    blend = run / "s3.blend"
    if not blend.exists():
        print(json.dumps({"stage": "s3", "total": 0, "error": "s3.blend missing"}))
        return
    mm = 0.001
    cold = [[v * mm for v in x["rect"]] for x in lay["aisles"] if x["type"] == "cold"]
    rays, kinds = [], []
    for (x0, y0, x1, y1) in cold:  # roof: rays straight down over the aisle; ends: rays along the aisle into each open end
        for i in range(1, 8):
            for j in range(1, 4):
                rays.append([x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * j / 4, 3.4, 0, 0, -1, 1.2]); kinds.append("roof")
        long_x = (x1 - x0) >= (y1 - y0)
        for k in range(1, 4):
            if long_x:
                yy = y0 + (y1 - y0) * k / 4
                rays.append([x0 - 0.6, yy, 1.6, 1, 0, 0, 0.9]); kinds.append("end")
                rays.append([x1 + 0.6, yy, 1.6, -1, 0, 0, 0.9]); kinds.append("end")
            else:
                xx = x0 + (x1 - x0) * k / 4
                rays.append([xx, y0 - 0.6, 1.6, 0, 1, 0, 0.9]); kinds.append("end")
                rays.append([xx, y1 + 0.6, 1.6, 0, -1, 0, 0.9]); kinds.append("end")
    res = probe(blend, rays)
    objs, hits = res["objects"], res["hits"]
    by = {o["name"]: o for o in objs}
    children = {}
    for o in objs:
        children.setdefault(o.get("parent"), []).append(o["name"])

    def mesh_desc(n):
        out, stack = [], [n]
        while stack:
            c = stack.pop()
            if by[c]["min"] is not None:
                out.append(by[c])
            stack += children.get(c, [])
        return out

    # ---- racks ----
    roots = {}
    for o in objs:
        rid = (o.get("props") or {}).get("rackId")
        if isinstance(rid, str):
            roots.setdefault(rid, o)
    det_r, pos_c, face_c, z_c, id_c, foot = {}, [], [], [], 0, {}
    for r in lay["racks"]:
        o = roots.get(r["id"])
        if o is None:
            det_r[r["id"]] = "missing"
            pos_c.append(0); face_c.append(0); z_c.append(0)
            continue
        ms = mesh_desc(o["name"])
        if ms:
            lo = [min(m["min"][i] for m in ms) for i in range(3)]
            hi = [max(m["max"][i] for m in ms) for i in range(3)]
            cx, cy, bz = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]
        else:
            cx, cy, bz = o["loc"]
        err = math.dist((cx, cy), (r["center"][0] * mm, r["center"][1] * mm))
        fdir, fang = facing_of(o["front"])
        w_exp, d_exp = r["size"][0] * mm, r["size"][1] * mm
        if r["facing"] in "EW":
            w_exp, d_exp = d_exp, w_exp
        size_ok = True
        if ms:
            size_ok = abs((hi[0] - lo[0]) - w_exp) <= 0.05 and abs((hi[1] - lo[1]) - d_exp) <= 0.05
        pos_c.append((1.0 if err <= 0.01 else max(0.0, 1 - (err - 0.01) / 0.29)) * (1.0 if size_ok else 0.5))
        face_c.append(1.0 if fdir == r["facing"] and fang <= 2 else 0.0)
        z_c.append(1.0 if abs(bz - FLOOR) <= 0.01 else max(0.0, 1 - (abs(bz - FLOOR) - 0.01) / 0.09))
        id_c += o["name"] == f"Rack_{r['id']}"
        w, d = r["size"][0] * mm, r["size"][1] * mm
        if fdir in "EW":
            w, d = d, w
        foot[r["id"]] = [cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2]
        det_r[r["id"]] = {"err_mm": round(err * 1000, 1), "facing": fdir, "facing_dev_deg": round(fang, 1),
                          "bottom_z": round(bz, 3), "size_ok": size_ok}
    n = len(lay["racks"])
    extra = sorted(set(roots) - {r["id"] for r in lay["racks"]})
    # ---- collisions (racks vs racks, columns, room) ----
    coll = 0
    ids = list(foot)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            coll += rect_overlap(foot[ids[i]], foot[ids[j]])
    obst = [[(c["center"][0] - c["size"][0] / 2) * mm, (c["center"][1] - c["size"][1] / 2) * mm,
             (c["center"][0] + c["size"][0] / 2) * mm, (c["center"][1] + c["size"][1] / 2) * mm] for c in lay["columns"]]
    rx = [p[0] * mm for p in lay["room"]["polygon"]]
    ry = [p[1] * mm for p in lay["room"]["polygon"]]
    room = [min(rx), min(ry), max(rx), max(ry)]
    for f in foot.values():
        coll += any(rect_overlap(f, ob) for ob in obst)
        coll += not (f[0] >= room[0] - 0.005 and f[1] >= room[1] - 0.005 and f[2] <= room[2] + 0.005 and f[3] <= room[3] + 0.005)
    coll_c = max(0.0, 1 - coll / 4) if foot else 0.0
    # ---- containment ----
    roof = [h for h, k in zip(hits, kinds) if k == "roof"]
    ends = [h for h, k in zip(hits, kinds) if k == "end"]
    roof_ok = sum(1 for h in roof if h and h.startswith("Containment")) / max(len(roof), 1)
    end_ok = sum(1 for h in ends if h and h.startswith("Containment")) / max(len(ends), 1)
    cont = [o for o in objs if o["name"].startswith("Containment") and o["min"] is not None]
    roof_z_ok = 1.0 if cont and abs(max(o["max"][2] for o in cont) - (FLOOR + RACK_H)) <= 0.15 else 0.0
    cont_c = 0.5 * roof_ok + 0.3 * end_ok + 0.2 * roof_z_ok
    # ---- perforated tiles ----
    cells = []
    for (x0, y0, x1, y1) in cold:
        i0, i1 = math.ceil(round(x0 / 0.6, 6)), math.floor(round(x1 / 0.6, 6))
        j0, j1 = math.ceil(round(y0 / 0.6, 6)), math.floor(round(y1 / 0.6, 6))
        cells += [((i + 0.5) * 0.6, (j + 0.5) * 0.6) for i in range(i0, i1) for j in range(j0, j1)]
    tiles = [o for o in objs if o["name"].startswith("PerfTile") and o["min"] is not None]
    tile_ctr = [((t["min"][0] + t["max"][0]) / 2, (t["min"][1] + t["max"][1]) / 2, t["max"][2],
                 t["max"][0] - t["min"][0], t["max"][1] - t["min"][1]) for t in tiles]
    covered = sum(1 for (cx, cy) in cells if any(math.dist((cx, cy), t[:2]) <= 0.05 and abs(t[2] - FLOOR) <= 0.015
                                               and abs(t[3] - 0.6) <= 0.03 and abs(t[4] - 0.6) <= 0.03 for t in tile_ctr))
    tile_c = covered / len(cells) if cells else 0.0
    # ---- cable trays ----
    rows = {}
    for r in lay["racks"]:
        rows.setdefault(r.get("row", r["id"][0]), []).append(r)
    trays = [o for o in objs if o["name"].startswith("CableTray") and o["min"] is not None]
    tray_scores = {}
    for row, rs in rows.items():
        ax = 0 if rs[0]["facing"] in "NS" else 1  # axis the row runs along
        xs0 = min((r["center"][ax] - r["size"][0] / 2) * mm for r in rs)
        xs1 = max((r["center"][ax] + r["size"][0] / 2) * mm for r in rs)
        yc = sum(r["center"][1 - ax] for r in rs) / len(rs) * mm
        want_z = FLOOR + RACK_H + 0.3
        o_ = 1 - ax
        good = [t for t in trays if t["min"][o_] <= yc <= t["max"][o_] and abs(t["min"][2] - want_z) <= 0.05
                and abs((t["min"][o_] + t["max"][o_]) / 2 - yc) <= 0.05 and abs((t["max"][o_] - t["min"][o_]) - 0.3) <= 0.05]
        cov = 0.0
        if good:
            segs = sorted((max(t["min"][ax], xs0), min(t["max"][ax], xs1)) for t in good)
            cur, tot = xs0, 0.0
            for s0, s1 in segs:
                s0 = max(s0, cur)
                if s1 > s0:
                    tot += s1 - s0
                    cur = s1
            cov = tot / (xs1 - xs0)
        tray_scores[row] = round(min(1.0, cov / 0.95), 3)
    tray_c = sum(tray_scores.values()) / len(tray_scores) if tray_scores else 0.0

    parts = {"position": 25 * sum(pos_c) / n, "facing": 20 * sum(face_c) / n, "height": 5 * sum(z_c) / n,
             "ids": 5 * id_c / n, "collisions": 10 * coll_c, "containment": 15 * cont_c,
             "perf_tiles": 10 * tile_c, "cable_trays": 10 * tray_c}
    total = sum(parts.values())
    det = {"racks_found": n - sum(1 for v in det_r.values() if v == "missing"), "racks_expected": n,
           "extra_rackIds": extra, "per_rack": det_r, "collisions": coll,
           "containment": {"roof_hit_rate": round(roof_ok, 3), "end_hit_rate": round(end_ok, 3), "roof_height_ok": roof_z_ok},
           "perf_tiles": {"cells": len(cells), "covered": covered, "tile_objects": len(tiles)},
           "cable_trays": tray_scores, "objects": len(objs),
           "tris_total": sum(o["tris"] for o in objs)}
    res = {"stage": "s3", "total": round(total, 2), "parts": {k: round(v, 2) for k, v in parts.items()}, "detail": det}
    if not a.no_render:
        views = ["top", "iso"]
        for k, (x0, y0, x1, y1) in enumerate(cold):
            yc, xc = (y0 + y1) / 2, (x0 + x1) / 2
            views.append(f"cam:{x0 + 0.4:.2f},{yc:.2f},1.75>{x1:.2f},{yc:.2f},1.35")      # inside the cold aisle
            views.append(f"cam:{xc - 3.5:.2f},{y0 - 4.5:.2f},4.2>{xc:.2f},{yc:.2f},1.2")  # overview from the south-west
        names = ["top", "iso"] + [n for k in range(len(cold)) for n in (f"coldaisle{k}", f"overview{k}")]
        subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "render_views.py"), "--", str(run / "review"),
                        "--names", ",".join(names), *views], capture_output=True, timeout=900)
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
