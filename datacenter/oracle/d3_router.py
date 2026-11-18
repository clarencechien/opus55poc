#!/usr/bin/env python3
"""Reference router for stage D3 (overhead coolant pipes). Operator side only - its outputs are the answer key.

    python d3_router.py --scene scene.json --out DIR [--tries 10] [--bend-penalty 0.3]

Writes DIR/ref.json    L_ref per route = shortest valid single route (C1-C4, at most 8 bends) ignoring the other routes,
                       plus statistics on naive routes;
       DIR/routes.json a complete valid six-route solution (sequential routing, earlier routes become obstacles,
                       several routing orders are tried and the best-scoring one is kept).

Method: 3D grid at 0.05 m (all scene coordinates lie on it), z levels 2.75 ... 3.50. A cell is free if it is at least
0.10 m from every obstacle box. The search is a dynamic programme over the number of bends: layer k holds, for every cell
and travel direction, the shortest length of a path from the port with at most k bends; a layer is obtained from the
previous one by a turn followed by a straight run (vectorised running minimum along each axis). The last segment is the
vertical drop from (target x, y, 2.75) onto the rack top at z = 2.6.
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import random
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "score"))
from d3_routes import evaluate  # noqa: E402

STEP = 0.05
INF = 30000                    # int16 storage; real lengths are a few thousand cells at most
BIG = 10_000_000
DIRS = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]   # (axis, sign); index 5 = down


class Grid:
    def __init__(self, scene):
        self.scene = scene
        R = scene["rules"]
        self.R = R
        obs = list(scene["obstacles"]) + [scene["manifold"]]
        hi = np.max([o["max"] for o in obs], axis=0)
        self.z0 = R["z_min"]
        self.shape = (int(round(hi[0] / STEP)) + 1, int(round(hi[1] / STEP)) + 1, int(round((R["z_max"] - self.z0) / STEP)) + 1)
        ax = [np.arange(self.shape[0]) * STEP, np.arange(self.shape[1]) * STEP, self.z0 + np.arange(self.shape[2]) * STEP]
        blocked = np.zeros(self.shape, bool)
        lim = (R["clearance"] - 1e-7) ** 2
        for o in obs:
            g = [np.maximum(np.maximum(o["min"][i] - ax[i], ax[i] - o["max"][i]), 0.0) for i in range(3)]
            sl = []
            for i in range(3):
                nz = np.nonzero(g[i] ** 2 < lim)[0]
                if not len(nz):
                    break
                sl.append(slice(nz[0], nz[-1] + 1))
            else:
                d2 = g[0][sl[0], None, None] ** 2 + g[1][None, sl[1], None] ** 2 + g[2][None, None, sl[2]] ** 2
                blocked[sl[0], sl[1], sl[2]] |= d2 < lim
        self.static = blocked

    def cell(self, p):
        return (int(round(p[0] / STEP)), int(round(p[1] / STEP)), int(round((p[2] - self.z0) / STEP)))

    def point(self, c):
        return [round(c[0] * STEP, 3), round(c[1] * STEP, 3), round(self.z0 + c[2] * STEP, 3)]


def flip(a, axis, sign):
    return a if sign > 0 else np.flip(a, axis=axis)


class Search:
    """Bend-layered shortest paths from one start cell in a given blocked mask."""

    def __init__(self, blocked, start, max_bends):
        self.blocked = blocked
        self.start = start
        self.off = []
        for axis, sign in DIRS:
            b = flip(blocked, axis, sign)
            shp = [1, 1, 1]
            shp[axis] = blocked.shape[axis]
            self.off.append(np.arange(blocked.shape[axis], dtype=np.int64).reshape(shp) + BIG * np.cumsum(b, axis=axis, dtype=np.int64))
        s0 = np.full(blocked.shape, INF, np.int64)
        s0[start] = 0
        self.layers = [np.stack([self.sweep(s0, d) for d in range(6)])]
        for _ in range(max_bends):
            prev = self.layers[-1]
            m = [np.minimum(prev[0], prev[1]), np.minimum(prev[2], prev[3]), np.minimum(prev[4], prev[5])]
            turn = [np.minimum(m[1], m[2]), np.minimum(m[0], m[2]), np.minimum(m[0], m[1])]   # best arrival on a perpendicular axis
            self.layers.append(np.stack([self.sweep(turn[DIRS[d][0]].astype(np.int64), d) for d in range(6)]))

    def sweep(self, s, d):
        """out[i] = min over cells j behind i in the same free run of s[j] + (i - j), travelling in direction d."""
        axis, sign = DIRS[d]
        off = self.off[d]
        a = np.minimum.accumulate(flip(s, axis, sign) - off, axis=axis) + off
        a = flip(a, axis, sign)
        out = np.where((a >= INF) | self.blocked, INF, a).astype(np.int16)
        return out

    def backtrace(self, k, end, d=5):
        """Vertices (cells) of a path start -> end arriving in direction d with at most k bends, length layers[k][d][end]."""
        c = tuple(end)
        v = int(self.layers[k][d][c])
        assert v < INF
        verts = [c]
        while True:
            if k == 0:
                assert max(abs(a - b) for a, b in zip(c, self.start)) == v
                verts.append(self.start)
                break
            axis = DIRS[d][0]
            t = next((d2 for d2 in range(6) if DIRS[d2][0] != axis and int(self.layers[k - 1][d2][c]) == v), None)
            if t is not None:
                verts.append(c)
                k, d = k - 1, t
                continue
            axis, sign = DIRS[d]
            c = tuple(c[i] - (sign if i == axis else 0) for i in range(3))
            v -= 1
            assert int(self.layers[k][d][c]) == v
        return verts[::-1]


def simplify(pts):
    """Drop repeated points and straight-through vertices."""
    out = []
    for p in pts:
        if out and max(abs(a - b) for a, b in zip(out[-1], p)) < 1e-9:
            continue
        out.append(list(p))
        while len(out) >= 3:
            a, b, c = out[-3:]
            u = [b[i] - a[i] for i in range(3)]
            w = [c[i] - b[i] for i in range(3)]
            ia = [i for i in range(3) if abs(u[i]) > 1e-9]
            iw = [i for i in range(3) if abs(w[i]) > 1e-9]
            if ia == iw and u[ia[0]] * w[iw[0]] > 0:
                del out[-2]
            else:
                break
    return out


def bends(pts):
    return len(simplify(pts)) - 2


def block_box(mask, c0, c1, r):
    lo = [max(0, min(a, b) - r) for a, b in zip(c0, c1)]
    hi = [min(n, max(a, b) + r + 1) for a, b, n in zip(c0, c1, mask.shape)]
    if all(h > l for l, h in zip(lo, hi)):
        mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = True


def route_one(grid: Grid, blocked, port, target, max_bends, bend_penalty=0.0):
    """-> (points, length, cells per bend count) or None."""
    start = grid.cell(port)
    end = grid.cell([target[0], target[1], grid.z0])
    drop = int(round((grid.z0 - target[2]) / STEP))
    if blocked[start] or blocked[end]:
        return None
    s = Search(blocked, start, max_bends)
    cost = [int(s.layers[k][5][end]) for k in range(max_bends + 1)]
    ks = [k for k in range(max_bends + 1) if cost[k] < INF]
    if not ks:
        return None
    k = min(ks, key=lambda k: cost[k] * STEP + bend_penalty * k)
    pts = [grid.point(c) for c in s.backtrace(k, end)] + [list(target)]
    pts[0] = list(port)
    pts = simplify(pts)
    return pts, round((cost[k] + drop) * STEP, 3), [None if c >= INF else round((c + drop) * STEP, 3) for c in cost]


def solve_order(grid: Grid, order, routes, max_bends, bend_penalty, sep_cells):
    done = {}
    for rid in order:
        blocked = grid.static.copy()
        for other, r in routes.items():
            if other == rid:
                continue
            if other in done:           # an already routed pipe, with the separation margin
                cells = [grid.cell(p) for p in done[other]]
                for a, b in zip(cells[:-1], cells[1:]):
                    block_box(blocked, a, b, sep_cells)
            else:                       # keep the terminals of the pipes still to come reachable
                p, t = grid.cell(r["from"]), grid.cell([r["to"][0], r["to"][1], grid.z0])
                block_box(blocked, p, p, sep_cells)
                block_box(blocked, t, (t[0], t[1], t[2] + 1), sep_cells)
        res = route_one(grid, blocked, routes[rid]["from"], routes[rid]["to"], max_bends, bend_penalty)
        if res is None:
            return None
        done[rid] = res[0]
    return done


def naive_stats(scene, lref):
    """How many routes can be done with a naive route that ignores the other pipes."""
    def ok(rid, pts):
        return evaluate(scene, {rid: pts}, lref)["detail"]["routes"][rid]["valid"]
    three, four, four_pick = [], [], {}
    zs = [round(scene["rules"]["z_min"] + 0.025 * i, 3) for i in range(31)]
    for r in scene["routes"]:
        p, t = r["from"], r["to"]
        good3 = False
        for perm in itertools.permutations(range(3)):   # one straight segment per axis, in any order
            pts, cur = [list(p)], list(p)
            for axis in perm:
                cur = list(cur)
                cur[axis] = t[axis]
                pts.append(cur)
            good3 = good3 or ok(r["id"], simplify(pts))
        three.append(good3)
        good4 = None
        for z in zs:                                   # go to a cruise height, one L in plan, drop onto the rack
            for first in (0, 1):
                mid = [t[0], p[1], z] if first == 0 else [p[0], t[1], z]
                pts = simplify([list(p), [p[0], p[1], z], mid, [t[0], t[1], z], list(t)])
                if good4 is None and ok(r["id"], pts):
                    good4 = pts
        four.append(good4 is not None)
        if good4:
            four_pick[r["id"]] = good4
    joint = evaluate(scene, four_pick, lref)["detail"]["n_valid"] if four_pick else 0
    return {"three_segment_valid": int(sum(three)), "cruise_L_valid_alone": int(sum(four)), "cruise_L_valid_together": int(joint)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tries", type=int, default=10)
    ap.add_argument("--bend-penalty", type=float, default=0.3, help="metres of length one bend is worth in the multi-route search")
    ap.add_argument("--good-enough", type=float, default=97.0)
    a = ap.parse_args()
    scene = json.loads(pathlib.Path(a.scene).read_text())
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    R = scene["rules"]
    grid = Grid(scene)
    routes = {r["id"]: r for r in scene["routes"]}
    t0 = time.time()
    lref, single = {}, {}
    for rid, r in routes.items():
        res = route_one(grid, grid.static, r["from"], r["to"], R["max_bends"])
        assert res is not None, f"{rid}: no single route exists"
        single[rid], lref[rid] = res[0], res[1]
        print(f"{rid}: L_ref {res[1]:.2f} m, {bends(res[0])} bends, by bend count {res[2]}  [{time.time() - t0:.0f}s]", flush=True)
    chk = evaluate(scene, {}, lref)
    for rid in routes:      # each single route must be valid on its own
        d = evaluate(scene, {rid: single[rid]}, lref)["detail"]["routes"][rid]
        assert d["valid"] and abs(d["length"] - lref[rid]) < 1e-6, (rid, d)
    naive = naive_stats(scene, lref)
    print("naive routes:", naive, flush=True)
    (out / "ref.json").write_text(json.dumps({"L_ref": lref, "naive": naive, "single_routes": single, "seed": scene.get("seed")}, indent=1))

    sep_cells = int(np.ceil(R["separation"] / STEP - 1e-9)) - 1     # cells closer than the separation are blocked
    ids = list(routes)
    rng = random.Random(0)
    orders = [sorted(ids, key=lambda i: lref[i]), sorted(ids, key=lambda i: -lref[i]), ids[:], ids[::-1]]
    while len(orders) < a.tries:
        o = ids[:]
        rng.shuffle(o)
        if o not in orders:
            orders.append(o)
    best = None
    for n, order in enumerate(orders[:a.tries]):
        sol = solve_order(grid, order, routes, R["max_bends"], a.bend_penalty, sep_cells)
        if sol is None:
            print(f"try {n} order {order}: no solution  [{time.time() - t0:.0f}s]", flush=True)
            continue
        sc = evaluate(scene, sol, lref)
        print(f"try {n} order {order}: total {sc['total']} valid {sc['detail']['n_valid']} parts {sc['parts']}  [{time.time() - t0:.0f}s]", flush=True)
        if best is None or (sc["detail"]["n_valid"], sc["total"]) > (best[1]["detail"]["n_valid"], best[1]["total"]):
            best = (sol, sc, order)
        if best[1]["detail"]["n_valid"] == len(ids) and best[1]["total"] >= a.good_enough:
            break
    assert best is not None, "no multi-route solution found"
    sol, sc, order = best
    (out / "routes.json").write_text(json.dumps({"units": "m", "routes": [{"id": i, "points": sol[i]} for i in ids]}, indent=1))
    (out / "oracle_report.json").write_text(json.dumps({"order": order, "total": sc["total"], "parts": sc["parts"],
                                                       "n_valid": sc["detail"]["n_valid"], "L_ref": lref, "naive": naive,
                                                       "bends": {i: bends(sol[i]) for i in ids}}, indent=1))
    print(json.dumps({"total": sc["total"], "n_valid": sc["detail"]["n_valid"], "order": order, "L_ref": lref, "naive": naive}))
    del chk


if __name__ == "__main__":
    main()
