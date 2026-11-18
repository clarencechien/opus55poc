#!/usr/bin/env python3
"""Score stage D3: six overhead coolant pipes routed from a wall manifold to six racks.

    python d3_routes.py --run RUN_DIR --scene scene.json --ref ref.json [--out score_d3.json]

Reads RUN_DIR/routes.json = {"units": "m", "routes": [{"id": "P1", "points": [[x, y, z], ...]}, ...]}.
scene.json comes from gen/d3_scene.py (obstacle boxes, manifold, ports, targets, rules); ref.json from
oracle/d3_router.py (L_ref per route = shortest valid single route ignoring the other routes).

Rules (all numbers are in scene.json["rules"]; every distance/height limit is checked with 1 mm slack):
  C1  consecutive points differ in exactly one coordinate; first point = port, last point = target (within 0.01 m)
  C2  centreline >= 0.10 m from every obstacle box, except within 0.30 m path length of the route's own first / last point
  C3  z <= 3.50 everywhere; z >= 2.75 except within 0.30 m horizontal distance of the own target, where z >= 2.60
  C4  at most 8 bends
  C5  different routes >= 0.15 m apart (centreline to centreline) everywhere; both routes of an offending pair are invalid
Per route: valid -> 60 + 40 * min(1, L_ref / L); invalid or missing -> 0. total = mean over the six routes.
The route is sampled every 0.02 m (plus every vertex) for C2 and C3; C5 uses exact segment-to-segment distances.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib

import numpy as np

EQ = 1e-6  # two coordinates closer than this are "the same"


def load_boxes(scene):
    obs = list(scene["obstacles"]) + [scene["manifold"]]
    names = [o["name"] for o in obs]
    return names, np.array([o["min"] for o in obs], float), np.array([o["max"] for o in obs], float)


def parse_points(raw):
    """-> (N,3) float array or an error string."""
    if not isinstance(raw, list) or len(raw) < 2:
        return "points must be a list of at least 2 [x, y, z] points"
    pts = []
    for i, p in enumerate(raw):
        if not (isinstance(p, (list, tuple)) and len(p) == 3 and
                all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p)):
            return f"point {i} is not [x, y, z] with finite numbers"
        pts.append([float(v) for v in p])
    return np.array(pts, float)


def sample(pts, step):
    """Points along the polyline at spacing <= step, every vertex included. -> (S,3) points, (S,) path length."""
    out, s_out, s0 = [pts[:1]], [np.zeros(1)], 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ln = float(np.linalg.norm(b - a))
        n = max(1, int(math.ceil(ln / step - 1e-9)))
        t = np.arange(1, n + 1) / n
        out.append(a + (b - a) * t[:, None])
        s_out.append(s0 + ln * t)
        s0 += ln
    return np.concatenate(out), np.concatenate(s_out)


def seg_seg(p1, q1, p2, q2):
    """Closest distance between segments p1q1 and p2q2 (any orientation) and the two closest points."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = float(d1 @ d1), float(d2 @ d2), float(d2 @ r)
    if a <= 1e-18 and e <= 1e-18:
        s = t = 0.0
    elif a <= 1e-18:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = float(d1 @ r)
        if e <= 1e-18:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = float(d1 @ d2)
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-18 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    c1, c2 = p1 + d1 * s, p2 + d2 * t
    best = (float(np.linalg.norm(c1 - c2)), c1, c2)
    if a > 1e-18 and e > 1e-18 and a * e - float(d1 @ d2) ** 2 <= 1e-18:   # parallel: also try the end points
        for x, (u, v) in ((p1, (p2, q2)), (q1, (p2, q2)), (p2, (p1, q1)), (q2, (p1, q1))):
            w = v - u
            tt = min(1.0, max(0.0, float((x - u) @ w) / float(w @ w)))
            y = u + w * tt
            d = float(np.linalg.norm(x - y))
            if d < best[0]:
                best = (d, x, y)
    return best


def rnd(p):
    return [round(float(v), 3) for v in p]


def evaluate(scene: dict, routes: dict, lref: dict) -> dict:
    """routes: id -> raw points list (missing ids allowed). Returns {"total", "parts", "detail"}."""
    R = scene["rules"]
    tol = R.get("tolerance", 0.001)
    names, bmin, bmax = load_boxes(scene)
    ports = {p["id"]: np.array(p["point"], float) for p in scene["manifold"]["ports"]}
    targets = {t["id"]: np.array(t["point"], float) for t in scene["targets"]}
    detail, geom = {}, {}
    for rid in ports:
        d = {"valid": False, "length": None, "L_ref": lref.get(rid), "bends": None, "fails": [], "first_fail": None,
             "min_clearance": None, "min_separation": None}
        detail[rid] = d
        if rid not in routes:
            d["fails"].append({"rule": "missing", "msg": "no route with this id in routes.json"})
            continue
        pts = parse_points(routes[rid])
        if isinstance(pts, str):
            d["fails"].append({"rule": "C1", "msg": pts})
            continue
        geom[rid] = pts
        seg = np.diff(pts, axis=0)
        d["length"] = round(float(np.linalg.norm(seg, axis=1).sum()), 4)
        # ---- C1: end points and axis-aligned segments
        c1 = []
        e0, e1 = float(np.linalg.norm(pts[0] - ports[rid])), float(np.linalg.norm(pts[-1] - targets[rid]))
        if e0 > R["endpoint_tol"]:
            c1.append({"rule": "C1", "msg": f"first point is {e0:.3f} m from port {rid}", "at": rnd(pts[0]), "expected": rnd(ports[rid])})
        if e1 > R["endpoint_tol"]:
            c1.append({"rule": "C1", "msg": f"last point is {e1:.3f} m from the target", "at": rnd(pts[-1]), "expected": rnd(targets[rid])})
        nchg = (np.abs(seg) > EQ).sum(axis=1)
        for i in np.nonzero(nchg != 1)[0][:1]:
            what = "are the same point" if nchg[i] == 0 else f"differ in {int(nchg[i])} coordinates (segment not axis-aligned)"
            c1.append({"rule": "C1", "msg": f"points {int(i)} and {int(i) + 1} {what}", "at": rnd(pts[i]), "to": rnd(pts[i + 1])})
        # ---- C4: bends = interior vertices where the direction changes (straight-through vertices do not count)
        dirs = [s / n for s, n in zip(seg, np.linalg.norm(seg, axis=1)) if n > EQ]
        bends = sum(1 for u, v in zip(dirs[:-1], dirs[1:]) if float(u @ v) < 1 - 1e-9)
        d["bends"] = bends
        # ---- C2 / C3 on samples
        P, S = sample(pts, R["sample_step"])
        L = float(S[-1])
        c3 = []
        zhi = np.nonzero(P[:, 2] > R["z_max"] + tol)[0]
        if len(zhi):
            c3.append({"rule": "C3", "msg": f"z = {P[zhi[0], 2]:.3f} is above {R['z_max']}", "at": rnd(P[zhi[0]])})
        near = np.linalg.norm(P[:, :2] - targets[rid][:2], axis=1) <= R["target_radius"] + tol
        zlo = np.nonzero(P[:, 2] < np.where(near, R["target_z_min"], R["z_min"]) - tol)[0]
        if len(zlo):
            i = zlo[0]
            lim = R["target_z_min"] if near[i] else R["z_min"]
            c3.append({"rule": "C3", "msg": f"z = {P[i, 2]:.3f} is below {lim}" + ("" if near[i] else
                       f" more than {R['target_radius']} m (horizontally) from the target"), "at": rnd(P[i])})
        c2 = []
        keep = (S > R["clearance_exempt_len"] + tol) & (S < L - R["clearance_exempt_len"] - tol)
        if keep.any():
            Q = P[keep]
            gap = np.maximum(np.maximum(bmin[None] - Q[:, None], Q[:, None] - bmax[None]), 0.0)
            dist = np.linalg.norm(gap, axis=2)                       # (samples, boxes)
            j = dist.argmin(axis=1)
            dmin = dist[np.arange(len(Q)), j]
            k = int(dmin.argmin())
            d["min_clearance"] = {"distance": round(float(dmin[k]), 4), "obstacle": names[j[k]], "at": rnd(Q[k])}
            bad = np.nonzero(dmin < R["clearance"] - tol)[0]
            if len(bad):
                i = int(bad[0])
                c2.append({"rule": "C2", "msg": f"{dmin[i]:.3f} m from {names[j[i]]} (needs {R['clearance']})",
                           "obstacle": names[j[i]], "at": rnd(Q[i]), "distance": round(float(dmin[i]), 4),
                           "samples_too_close": int(len(bad)), "worst": d["min_clearance"]})
        c4 = [{"rule": "C4", "msg": f"{bends} bends (max {R['max_bends']})"}] if bends > R["max_bends"] else []
        d["fails"] = c1 + c2 + c3 + c4
    # ---- C5: every pair of submitted routes (also routes that are invalid for another reason still occupy space)
    ids = sorted(geom)
    c5 = {rid: None for rid in ids}
    for ia, a in enumerate(ids):
        for b in ids[ia + 1:]:
            best = (math.inf, None, None)
            A, B = geom[a], geom[b]
            for i in range(len(A) - 1):
                for j in range(len(B) - 1):
                    r = seg_seg(A[i], A[i + 1], B[j], B[j + 1])
                    if r[0] < best[0]:
                        best = r
            for x, y, pa, pb in ((a, b, best[1], best[2]), (b, a, best[2], best[1])):
                ms = detail[x]["min_separation"]
                if ms is None or best[0] < ms["distance"]:
                    detail[x]["min_separation"] = {"distance": round(best[0], 4), "other": y, "at": rnd(pa), "other_at": rnd(pb)}
                if best[0] < R["separation"] - tol and (c5[x] is None or best[0] < c5[x]["distance"]):
                    c5[x] = {"rule": "C5", "msg": f"{best[0]:.3f} m from route {y} (needs {R['separation']})", "other": y,
                             "at": rnd(pa), "other_at": rnd(pb), "distance": round(best[0], 4)}
    parts = {}
    for rid, d in detail.items():
        if c5.get(rid):
            d["fails"].append(c5[rid])
        d["first_fail"] = d["fails"][0] if d["fails"] else None
        d["valid"] = not d["fails"]
        sc = 0.0
        if d["valid"]:
            ref = lref.get(rid)
            sc = 60.0 + 40.0 * (min(1.0, ref / d["length"]) if ref else 0.0)
        d["score"] = parts[rid] = round(sc, 2)
    total = round(sum(parts.values()) / len(parts), 2)
    return {"total": total, "parts": parts, "detail": {"n_valid": sum(d["valid"] for d in detail.values()), "routes": detail}}


def read_routes(path: pathlib.Path):
    """-> (id -> raw points, list of problems)."""
    if not path.exists():
        return {}, ["routes.json missing"]
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return {}, [f"routes.json is not valid JSON: {e}"]
    rl = data.get("routes") if isinstance(data, dict) else None
    if not isinstance(rl, list):
        return {}, ['routes.json must be {"units": "m", "routes": [...]}']
    out, probs = {}, []
    for r in rl:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            probs.append("a route entry without a string id was ignored")
        elif r["id"] in out:
            probs.append(f"duplicate route id {r['id']}: only the first one is used")
        else:
            out[r["id"]] = r.get("points")
    return out, probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    scene = json.loads(pathlib.Path(a.scene).read_text())
    ref = json.loads(pathlib.Path(a.ref).read_text())
    lref = ref.get("L_ref", ref)
    routes, probs = read_routes(pathlib.Path(a.run) / "routes.json")
    known = {p["id"] for p in scene["manifold"]["ports"]}
    probs += [f"unknown route id {k} ignored" for k in routes if k not in known]
    res = evaluate(scene, {k: v for k, v in routes.items() if k in known}, lref)
    res = {"stage": "d3", "total": res["total"], "parts": res["parts"], "detail": {**res["detail"], "problems": probs}}
    txt = json.dumps(res, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
