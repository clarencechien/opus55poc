#!/usr/bin/env python3
"""Automatic geometry checks for stage S2 (the look is graded separately by the judge and by people).

    python s2_rack.py --run RUN_DIR [--out score_s2_auto.json]

40 points: dimensions A 10, dimensions B 10, placement 5, structure / orientation 10, triangle budget 5.
Also renders the fixed review views into RUN_DIR/review/ for the visual reviewers.
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
SPEC = {"RackA": {"size": (0.6, 1.2, 2.0), "center": (0.0, 0.0)},
        "RackB": {"size": (0.6, 1.0, 2.0), "center": (1.5, 0.0)}}
VIEWS = ["front", "back", "right", "iso", "close"]


def probe(blend: pathlib.Path):
    with tempfile.TemporaryDirectory() as td:
        q, o = pathlib.Path(td) / "q.json", pathlib.Path(td) / "o.json"
        q.write_text("{}")
        subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "blender_probe.py"), "--", str(q), str(o)],
                       capture_output=True, timeout=600)
        return json.loads(o.read_text())["objects"]


def dim_credit(rel):
    return max(0.0, min(1.0, 1 - (rel - 0.01) / 0.09)) if rel > 0.01 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run = pathlib.Path(a.run)
    blend = run / "s2.blend"
    det, pts = {}, {"dims_A": 0.0, "dims_B": 0.0, "placement": 0.0, "structure": 0.0, "budget": 0.0}
    if not blend.exists():
        res = {"stage": "s2", "auto_total_40": 0, "error": "s2.blend missing"}
        print(json.dumps(res))
        return
    objs = probe(blend)
    by = {o["name"]: o for o in objs}

    def under(n, root):
        while n:
            if n == root:
                return True
            n = by.get(n, {}).get("parent")
        return False
    place = []
    for root, spec in SPEC.items():
        meshes = [o for o in objs if o["min"] is not None and under(o["name"], root)]
        d = {"meshes": len(meshes), "tris": sum(o["tris"] for o in meshes)}
        if meshes:
            lo = [min(o["min"][i] for o in meshes) for i in range(3)]
            hi = [max(o["max"][i] for o in meshes) for i in range(3)]
            size = [hi[i] - lo[i] for i in range(3)]
            rel = [abs(size[i] - spec["size"][i]) / spec["size"][i] for i in range(3)]
            d.update(size_m=[round(v, 4) for v in size], rel_err=[round(v, 4) for v in rel])
            pts["dims_A" if root == "RackA" else "dims_B"] = 10 * sum(dim_credit(r) for r in rel) / 3
            cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
            err = max(math.dist((cx, cy), spec["center"]), abs(lo[2]))
            d["placement_err_m"] = round(err, 4)
            place.append(1.0 if err <= 0.01 else max(0.0, 1 - (err - 0.01) / 0.09))
            d["within_budget"] = d["tris"] <= 50000
            pts["budget"] += 2.5 * d["within_budget"]
            d["materials"] = sorted({m for o in meshes for m in o["materials"]})[:30]
        else:
            place.append(0.0)
        det[root] = d
    pts["placement"] = 5 * sum(place) / 2
    s = 0.0
    fd, rd = by.get("RackA_FrontDoor"), by.get("RackA_RearDoor")
    s += 2 * (fd is not None and under("RackA_FrontDoor", "RackA")) + 2 * (rd is not None and under("RackA_RearDoor", "RackA"))
    if fd and rd and fd["min"] and rd["min"]:
        fy, ry = (fd["min"][1] + fd["max"][1]) / 2, (rd["min"][1] + rd["max"][1]) / 2
        s += 2 * (fy < ry)
        s += 1 * (abs(fd["min"][1] - (SPEC["RackA"]["center"][1] - SPEC["RackA"]["size"][1] / 2)) <= 0.1)
    posts = [by.get(f"RackB_Post_{i}") for i in range(1, 5)]
    s += 2 * (all(p is not None and p["min"] for p in posts) and all(under(f"RackB_Post_{i}", "RackB") for i in range(1, 5)))
    if all(p and p["min"] for p in posts):
        xs = sorted(round((p["min"][0] + p["max"][0]) / 2, 2) for p in posts)
        ys = sorted(round((p["min"][1] + p["max"][1]) / 2, 2) for p in posts)
        s += 1 * ((xs[-1] - xs[0]) > 0.4 and (ys[-1] - ys[0]) > 0.7)  # posts spread to the four corners
    pts["structure"] = s
    stray = [o["name"] for o in objs if o["min"] is not None and not under(o["name"], "RackA") and not under(o["name"], "RackB")]
    det["stray_meshes"] = stray[:20]
    total = sum(pts.values())
    res = {"stage": "s2", "auto_total_40": round(total, 2), "auto_pct": round(total / 40 * 100, 1),
           "parts": {k: round(v, 2) for k, v in pts.items()}, "detail": det}
    if not a.no_render:
        for root in SPEC:
            subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "render_views.py"), "--",
                            str(run / "review"), "--isolate", root, *VIEWS], capture_output=True, timeout=900)
        subprocess.run([BLENDER, "-b", str(blend), "--python", str(HERE / "render_views.py"), "--",
                        str(run / "review"), "front", "iso"], capture_output=True, timeout=900)
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
