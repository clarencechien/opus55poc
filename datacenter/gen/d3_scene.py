#!/usr/bin/env python3
"""Task D3 (overhead coolant pipes): furnished data hall as a list of obstacle boxes, a wall manifold and 6 targets.

    python d3_scene.py --seed N --out DIR      -> DIR/scene.json  (ground truth scene, metres)
                                                  DIR/terminals.json (the participant-visible part: ports, targets, rules)

Everything is in METRES, z up: z = 0 structural slab, raised-floor top 0.6, ceiling underside 3.6.
Plan axes as everywhere else: origin at grid A/1, +x east, +y north. Deterministic from --seed.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from layout_gen import footprint, hard  # noqa: E402

FLOOR, CEIL = 0.6, 3.6
RULES = {
    "endpoint_tol": 0.01,        # C1: first/last point within this distance of the port/target
    "clearance": 0.10,           # C2: centreline to every obstacle box
    "clearance_exempt_len": 0.30,  # C2: path length at each end of a route that is exempt
    "z_max": 3.50,               # C3
    "z_min": 2.75,               # C3
    "target_radius": 0.30,       # C3: horizontal distance from the own target inside which z may go below z_min
    "target_z_min": 2.60,        # C3
    "max_bends": 8,              # C4
    "separation": 0.15,          # C5: centreline to centreline of different routes
    "tolerance": 0.001,          # numerical slack on every distance / height limit
    "sample_step": 0.02,         # the checker samples each route at this spacing
}


def r3(v):
    return round(float(v) + 0.0, 3)


def box(name, x0, x1, y0, y1, z0, z1):
    return {"name": name, "min": [r3(x0), r3(y0), r3(z0)], "max": [r3(x1), r3(y1), r3(z1)]}


def overlap(a, b, gap=0.0):
    return all(a["min"][i] < b["max"][i] + gap and b["min"][i] < a["max"][i] + gap for i in range(3))


def build(seed: int) -> dict:
    rng = random.Random(seed)
    lay = hard(rng)
    mm = 0.001
    gx = {k: v * mm for k, v in lay["grid"]["x"].items()}
    gy = {k: v * mm for k, v in lay["grid"]["y"].items()}
    W, D = max(gx.values()), max(gy.values())
    xD, y3, g2 = gx["D"], gy["3"], gy["2"]
    h = 0.1
    obs = []
    # ---- shell: walls centred on the grid lines (0.2 thick, full height), columns, raised floor, ceiling
    obs += [box("Wall_S", -h, W + h, -h, h, 0, CEIL),
            box("Wall_W", -h, h, h, D - h, 0, CEIL),
            box("Wall_N", -h, xD + h, D - h, D + h, 0, CEIL),
            box("Wall_E", W - h, W + h, h, y3 + h, 0, CEIL),
            box("Wall_UPS_S", xD + h, W - h, y3 - h, y3 + h, 0, CEIL),
            box("Wall_UPS_W", xD - h, xD + h, y3 - h, D - h, 0, CEIL)]
    for c in lay["columns"]:
        cx, cy = c["center"][0] * mm, c["center"][1] * mm
        s = c["size"][0] * mm / 2
        obs.append(box("Column_" + c["id"].replace("/", ""), cx - s, cx + s, cy - s, cy + s, 0, CEIL))
    obs.append(box("RaisedFloor", h, W - h, h, D - h, 0, FLOOR))
    obs.append(box("Ceiling", -h, W + h, -h, D + h, CEIL, CEIL + 0.1))
    # ---- equipment
    rows: dict[str, list] = {}
    for r in lay["racks"]:
        f = [v * mm for v in footprint(r["center"], r["size"], r["facing"])]
        obs.append(box("Rack_" + r["id"], f[0], f[2], f[1], f[3], FLOOR, 2.6))
        rows.setdefault(r["row"], []).append((r, f))
    for c in lay["crah"]:
        f = [v * mm for v in footprint(c["center"], c["size"], c["facing"])]
        obs.append(box(c["id"].replace("-", "_"), f[0], f[2], f[1], f[3], FLOOR, 2.55))
    # ---- cold-aisle containment: roof between the two rows + a panel closing each open end
    for a in lay["aisles"]:
        if a["type"] != "cold":
            continue
        x0, y0, x1, y1 = (v * mm for v in a["rect"])
        pair = "".join(sorted(k for k, items in rows.items()   # the rows whose racks touch this aisle
                              if any(f[0] < x1 + 1e-3 and x0 < f[2] + 1e-3 and f[1] < y1 + 1e-3 and y0 < f[3] + 1e-3 for _, f in items)))
        obs.append(box(f"Containment_{pair}_Roof", x0, x1, y0, y1, 2.58, 2.62))
        t = 0.05
        if (x1 - x0) >= (y1 - y0):   # aisle runs along x: open ends at x0 and x1
            obs.append(box(f"Containment_{pair}_End1", x0, x0 + t, y0, y1, FLOOR, 2.58))
            obs.append(box(f"Containment_{pair}_End2", x1 - t, x1, y0, y1, FLOOR, 2.58))
        else:
            obs.append(box(f"Containment_{pair}_End1", x0, x1, y0, y0 + t, FLOOR, 2.58))
            obs.append(box(f"Containment_{pair}_End2", x0, x1, y1 - t, y1, FLOOR, 2.58))
    # ---- cable trays over each row centreline (first rack to last rack)
    trays = []
    for row, items in sorted(rows.items()):
        x0, y0 = min(f[0] for _, f in items), min(f[1] for _, f in items)
        x1, y1 = max(f[2] for _, f in items), max(f[3] for _, f in items)
        if (x1 - x0) >= (y1 - y0):
            cy = (y0 + y1) / 2
            b = box(f"CableTray_{row}", x0, x1, cy - 0.15, cy + 0.15, 2.9, 3.0)
        else:
            cx = (x0 + x1) / 2
            b = box(f"CableTray_{row}", cx - 0.15, cx + 0.15, y0, y1, 2.9, 3.0)
        trays.append(b)
    obs += trays
    # ---- structural beams along every interior grid line, both directions
    for L in "BCD":
        obs.append(box(f"Beam_{L}", gx[L] - 0.2, gx[L] + 0.2, h, (y3 - h) if L == "D" else (D - h), 3.15, CEIL))
    obs.append(box("Beam_2", h, W - h, g2 - 0.2, g2 + 0.2, 3.15, CEIL))
    obs.append(box("Beam_3", h, xD - h, y3 - 0.2, y3 + 0.2, 3.15, CEIL))

    # ---- targets: one rack per row, spread out
    row_ids = sorted(rows)
    best = None
    for _ in range(400):
        pick = {row: rng.choice(rows[row])[0] for row in row_ids}
        pts = [(pick[r]["center"][0] * mm, pick[r]["center"][1] * mm) for r in row_ids]
        dmin = min(math.dist(p, q) for p, q in itertools.combinations(pts, 2))
        if best is None or dmin > best[0]:
            best = (dmin, pick)
        if dmin >= 3.0:
            best = (dmin, pick)
            break
    pick = best[1]
    tpts = {row: [r3(pick[row]["center"][0] * mm), r3(pick[row]["center"][1] * mm), 2.6] for row in row_ids}

    # ---- manifold: on the inner face of the wall that is far from most targets (largest median distance)
    walls = [  # name, axis the wall runs along (0 = x, 1 = y), inner-face coordinate, inward normal sign, lo, hi
        ("Wall_S", 0, h, +1, h, W - h), ("Wall_N", 0, D - h, -1, h, xD - h), ("Wall_UPS_S", 0, y3 - h, -1, xD + h, W - h),
        ("Wall_W", 1, h, +1, h, D - h), ("Wall_E", 1, W - h, -1, h, y3 - h), ("Wall_UPS_W", 1, xD - h, -1, y3 + h, D - h)]

    def med(wl):
        _, ax, face, _, lo, hi = wl
        mid = ((lo + hi) / 2, face) if ax == 0 else (face, (lo + hi) / 2)
        d = sorted(math.dist(mid, p[:2]) for p in tpts.values())
        return (d[2] + d[3]) / 2
    wname, ax, face, sgn, lo, hi = max(walls, key=med)
    n_ports, pitch, depth, stand = 6, 0.25, 0.20, 0.15
    span = pitch * (n_ports - 1)
    p0 = round(rng.uniform(lo + 1.5, hi - 1.5 - span) * 10) / 10      # first port, on the 0.1 m grid
    a0, a1 = p0 - 0.25, p0 + span + 0.25
    f0, f1 = sorted((face, face + sgn * depth))
    manifold = box("Manifold", a0, a1, f0, f1, 2.9, 3.1) if ax == 0 else box("Manifold", f0, f1, a0, a1, 2.9, 3.1)
    off = face + sgn * (depth + stand)
    ports = []
    for k in range(n_ports):
        s = p0 + k * pitch
        ports.append({"id": f"P{k + 1}", "point": [r3(s), r3(off), 3.0] if ax == 0 else [r3(off), r3(s), 3.0]})

    # ---- two air ducts crossing the hall in different directions (0.8 wide x 0.45 high, z 2.95-3.4), seeded positions:
    #      Duct_1 runs parallel to the manifold wall 2-4.5 m in front of it (every pipe has to pass it),
    #      Duct_2 runs square to that wall with at least two targets on either side.
    def duct_box(name, run_axis, v):       # a duct running along run_axis, centred at v on the other plan axis
        if run_axis == 0:
            return box(name, h, (W - h) if v + 0.4 < y3 - h else (xD - h), v - 0.4, v + 0.4, 2.95, 3.4)
        return box(name, v - 0.4, v + 0.4, h, (D - h) if v + 0.4 < xD - h else (y3 - h), 2.95, 3.4)

    def duct_ok(b, run_axis, v):
        if min(abs(v - g) for g in (gy if run_axis == 0 else gx).values()) < 1.0:   # off the parallel beams, columns, walls
            return False
        if overlap(b, manifold, gap=0.8):
            return False
        return not any(overlap(b, t) and ((t["max"][0] - t["min"][0]) > (t["max"][1] - t["min"][1])) == (run_axis == 0)
                       for t in trays)                                                # not lengthwise through a cable tray
    ducts = []
    for _ in range(500):
        v = round((face + sgn * rng.uniform(2.0, 4.5)) * 10) / 10
        b = duct_box("Duct_1", ax, v)
        if duct_ok(b, ax, v):
            ducts.append(b)
            break
    for _ in range(2000):
        v = round(rng.uniform(lo + 1.0, hi - 1.0) * 10) / 10
        sides = [sum(1 for t in tpts.values() if t[ax] < v - 0.7), sum(1 for t in tpts.values() if t[ax] > v + 0.7)]
        b = duct_box("Duct_2", 1 - ax, v)
        if min(sides) >= 2 and duct_ok(b, 1 - ax, v):
            ducts.append(b)
            break
    assert len(ducts) == 2, "could not place the ducts"
    obs += ducts

    # ---- assignment port -> target row, chosen so that the routes have to cross
    order = sorted(row_ids, key=lambda r: (tpts[r][ax], tpts[r][1 - ax]))   # the order that would not cross
    rank = {r: i for i, r in enumerate(order)}
    while True:
        perm = row_ids[:]
        rng.shuffle(perm)
        inv = sum(1 for i, j in itertools.combinations(range(n_ports), 2) if rank[perm[i]] > rank[perm[j]])
        if 6 <= inv <= 11:
            break
    targets = [{"id": ports[k]["id"], "rack": pick[perm[k]]["id"], "row": perm[k], "point": tpts[perm[k]]} for k in range(n_ports)]
    return {
        "units": "m", "seed": seed,
        "hall": {"polygon": [[r3(p[0] * mm), r3(p[1] * mm)] for p in lay["room"]["polygon"]], "grid": {"x": gx, "y": gy},
                 "raised_floor_top": FLOOR, "ceiling_underside": CEIL},
        "obstacles": obs,
        "manifold": {**manifold, "wall": wname, "ports": ports},
        "targets": targets,
        "routes": [{"id": p["id"], "from": p["point"], "to": t["point"], "target_rack": t["rack"]} for p, t in zip(ports, targets)],
        "rules": RULES,
    }


def terminals(scene: dict) -> dict:
    """What the participants get as JSON: no obstacle list (they read the obstacles from the Blender scene)."""
    return {"units": "m",
            "ports": scene["manifold"]["ports"],
            "targets": [{"id": t["id"], "rack": t["rack"], "point": t["point"]} for t in scene["targets"]],
            "routes": scene["routes"],
            "rules": scene["rules"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sc = build(a.seed)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scene.json").write_text(json.dumps(sc, indent=1))
    (out / "terminals.json").write_text(json.dumps(terminals(sc), indent=1))
    print(f"seed {a.seed}: {len(sc['obstacles'])} obstacles, manifold on {sc['manifold']['wall']}, "
          f"targets {[t['rack'] for t in sc['targets']]} -> {out / 'scene.json'}")


if __name__ == "__main__":
    main()
