#!/usr/bin/env python3
"""Score stage D2 (design a rack layout for an empty data hall under a rule book).

    python d2_design.py --run RUN_DIR --room room.json --ref N_REF [--out score_d2.json]

Reads RUN_DIR/layout_design.json = {"units": "mm", "racks": [{"id", "center": [x, y], "size": [w, 1200], "facing"}]}.
All geometry is in plan millimetres. A rack footprint is w (along the row) x 1200 (front to back), w = 600 or 800 (GPU),
axis-aligned, `facing` = compass direction the front points to.

Rules (per rack; a rack with any violation is "bad", the others are "valid"):
  R1 footprint inside the hall polygon (inner wall faces)
  R2 no overlap with other racks (touching is fine), columns or CRAH units
  R3 the rectangle of the rack's width reaching 1200 in front of the front face is inside the hall and free of racks,
     columns and CRAH units
  R4 the same for 900 behind the rear face
  R5 any other rack whose footprint intersects the corridor of the rack's width reaching 3000 in front of the front face
     must face the opposite direction
  R6 the rectangle of each CRAH's width reaching 1500 in front of the CRAH is free of racks
  R7 for each door the rectangle (door width + 600) wide x 1500 deep inside the hall, centred on the door, is free of racks
  R8 access: grid points every 50 mm (at multiples of 50); a point is walkable if it is inside the hall and >= 450 from
     every rack, column, CRAH and wall; flood fill (4-neighbour) from the grid point 600 inside door D1; the point 600 in
     front of the front-face centre and the point 450 behind the rear-face centre must each be within 150 of a reached point
  R9 a GPU rack's centre must be within 7000 of the centre of at least one CRAH
For R2/R3/R4/R5 conflicts between two racks both racks are bad; for R6/R7 the intruding rack is bad.
Malformed entries count as bad. Exactly 8 valid GPU racks are required.

  total = 100 * clamp((n_valid - n_bad - 2 * |8 - n_valid_gpu|) / N_REF, 0, 1)

`Room` and `Room.check` are imported by oracle/d2_solver.py and score/d2_overlay.py.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib

import numpy as np
import shapely
from scipy import ndimage
from shapely.geometry import Polygon, box

EPS = 0.5            # mm: overlaps / protrusions smaller than this are ignored ("touching is fine")
RACK_D = 1200
WIDTHS = (600, 800)
GPU_W = 800
FRONT_CLR, REAR_CLR, CORRIDOR = 1200, 900, 3000
CRAH_ZONE, DOOR_ZONE_DEPTH, DOOR_ZONE_EXTRA = 1500, 1500, 600
GRID, HALF_PATH, START_IN, FRONT_PT, REAR_PT, REACH_TOL = 50, 450, 600, 600, 450, 150
GPU_REQUIRED, GPU_MAX_DIST = 8, 7000
FACINGS = "NSEW"
DIRS = np.array([[0, 1], [0, -1], [1, 0], [-1, 0]], dtype=float)   # N S E W
OPP = np.array([1, 0, 3, 2])
INTO = {"S": (0, 1), "N": (0, -1), "E": (-1, 0), "W": (1, 0)}       # direction from a door on that wall into the hall
RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"]
MAX_RACKS = 5000


def footprints(cx, cy, w, f):
    """(N,4) x0 y0 x1 y1; f = facing index into FACINGS."""
    ns = f < 2
    hx = np.where(ns, w / 2, RACK_D / 2)
    hy = np.where(ns, RACK_D / 2, w / 2)
    return np.stack([cx - hx, cy - hy, cx + hx, cy + hy], axis=1)


def extend(F, f, d):
    """Rectangles of the footprint's width reaching d beyond the face that looks towards direction index f."""
    R = F.copy()
    n, s, e, w = f == 0, f == 1, f == 2, f == 3
    R[n, 1], R[n, 3] = F[n, 3], F[n, 3] + d
    R[s, 3], R[s, 1] = F[s, 1], F[s, 1] - d
    R[e, 0], R[e, 2] = F[e, 2], F[e, 2] + d
    R[w, 2], R[w, 0] = F[w, 0], F[w, 0] - d
    return R


def overlap(A, B):
    """(len(A), len(B)) bool: rectangles overlap by more than EPS in both axes."""
    if len(A) == 0 or len(B) == 0:
        return np.zeros((len(A), len(B)), dtype=bool)
    ox = np.minimum(A[:, None, 2], B[None, :, 2]) - np.maximum(A[:, None, 0], B[None, :, 0])
    oy = np.minimum(A[:, None, 3], B[None, :, 3]) - np.maximum(A[:, None, 1], B[None, :, 1])
    return (ox > EPS) & (oy > EPS)


def item_rect(it):
    (cx, cy), (w, d) = it["center"], it["size"]
    if it.get("facing", "N") in "EW":
        w, d = d, w
    return [cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2]


class Room:
    """Everything about the empty hall that does not depend on the racks."""

    def __init__(self, room: dict):
        self.json = room
        pts = [tuple(map(float, p)) for p in room["room"]["polygon"]]
        self.poly = Polygon(pts)
        self.edges = list(zip(pts, pts[1:] + pts[:1]))
        self.rectilinear = all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9 for a, b in self.edges)
        xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
        cells = [[x0, y0, x1, y1] for x0, x1 in zip(xs, xs[1:]) for y0, y1 in zip(ys, ys[1:])
                 if self.poly.contains(shapely.Point((x0 + x1) / 2, (y0 + y1) / 2))]
        self.hall_rects = np.array(cells, dtype=float)
        half_t = room["room"]["wall_thickness"] / 2
        self.columns = np.array([item_rect(c) for c in room["columns"]], dtype=float).reshape(-1, 4)
        self.crah = np.array([item_rect(c) for c in room["crah"]], dtype=float).reshape(-1, 4)
        self.fixed = np.vstack([self.columns, self.crah])
        self.crah_centers = np.array([c["center"] for c in room["crah"]], dtype=float).reshape(-1, 2)
        cf = np.array([FACINGS.index(c["facing"]) for c in room["crah"]], dtype=int)
        self.crah_zones = extend(self.crah, cf, CRAH_ZONE) if len(cf) else np.zeros((0, 4))
        zones, self.start_xy = [], None
        for dr in room["doors"]:
            ix, iy = INTO[dr["wall"]]
            fx, fy = dr["center"][0] + ix * half_t, dr["center"][1] + iy * half_t   # door centre on the inner wall face
            hw = (dr["width"] + DOOR_ZONE_EXTRA) / 2
            if ix == 0:
                zones.append([fx - hw, min(fy, fy + iy * DOOR_ZONE_DEPTH), fx + hw, max(fy, fy + iy * DOOR_ZONE_DEPTH)])
            else:
                zones.append([min(fx, fx + ix * DOOR_ZONE_DEPTH), fy - hw, max(fx, fx + ix * DOOR_ZONE_DEPTH), fy + hw])
            if dr["id"] == "D1":
                self.start_xy = (fx + ix * START_IN, fy + iy * START_IN)
        self.door_zones = np.array(zones, dtype=float).reshape(-1, 4)
        # ---- access grid: points at multiples of GRID ----
        x0, y0, x1, y1 = self.poly.bounds
        self.gx0, self.gy0 = math.floor(x0 / GRID) * GRID, math.floor(y0 / GRID) * GRID
        self.nx = int(math.ceil(x1 / GRID) - self.gx0 / GRID) + 1
        self.ny = int(math.ceil(y1 / GRID) - self.gy0 / GRID) + 1
        self.X = self.gx0 + GRID * np.arange(self.nx)
        self.Y = self.gy0 + GRID * np.arange(self.ny)
        XX, YY = np.meshgrid(self.X, self.Y)
        blocked = ~shapely.contains_xy(self.poly.buffer(EPS), XX, YY)
        lim2 = (HALF_PATH - EPS) ** 2
        for (ax, ay), (bx, by) in self.edges:      # distance to every wall segment
            dx, dy = bx - ax, by - ay
            t = np.clip(((XX - ax) * dx + (YY - ay) * dy) / (dx * dx + dy * dy), 0, 1)
            blocked |= (XX - ax - t * dx) ** 2 + (YY - ay - t * dy) ** 2 < lim2
        self.static_blocked = blocked
        for r in self.fixed:
            self._block(self.static_blocked, r)
        self.start_idx = None
        if self.start_xy is not None:
            i, j = round((self.start_xy[0] - self.gx0) / GRID), round((self.start_xy[1] - self.gy0) / GRID)
            if 0 <= i < self.nx and 0 <= j < self.ny:
                self.start_idx = (j, i)
        k = int(REACH_TOL // GRID) + 1
        oy, ox = np.meshgrid(np.arange(-k, k + 1), np.arange(-k, k + 1), indexing="ij")
        self._off = (oy.ravel(), ox.ravel())

    def _block(self, blocked, r):
        """Mark grid points closer than HALF_PATH to rectangle r."""
        rad = HALF_PATH
        i0 = max(0, math.ceil((r[0] - rad - self.gx0) / GRID))
        i1 = min(self.nx - 1, math.floor((r[2] + rad - self.gx0) / GRID))
        j0 = max(0, math.ceil((r[1] - rad - self.gy0) / GRID))
        j1 = min(self.ny - 1, math.floor((r[3] + rad - self.gy0) / GRID))
        if i1 < i0 or j1 < j0:
            return
        xs, ys = self.X[i0:i1 + 1], self.Y[j0:j1 + 1]
        dx = np.maximum(np.maximum(r[0] - xs, xs - r[2]), 0)
        dy = np.maximum(np.maximum(r[1] - ys, ys - r[3]), 0)
        blocked[j0:j1 + 1, i0:i1 + 1] |= dx[None, :] ** 2 + dy[:, None] ** 2 < (HALF_PATH - EPS) ** 2

    def inside(self, R):
        """bool per rectangle: lies inside the hall (protrusions up to EPS ignored)."""
        if len(R) == 0:
            return np.zeros(0, dtype=bool)
        if not self.rectilinear:
            big = self.poly.buffer(EPS)
            return np.array([big.contains(box(*r)) for r in R])
        S = R + np.array([EPS, EPS, -EPS, -EPS])
        H = self.hall_rects
        ox = np.clip(np.minimum(S[:, None, 2], H[None, :, 2]) - np.maximum(S[:, None, 0], H[None, :, 0]), 0, None)
        oy = np.clip(np.minimum(S[:, None, 3], H[None, :, 3]) - np.maximum(S[:, None, 1], H[None, :, 1]), 0, None)
        area = (S[:, 2] - S[:, 0]) * (S[:, 3] - S[:, 1])
        return (ox * oy).sum(axis=1) >= area - 1.0

    def reach(self, F):
        """Flood fill from door D1 with the rack footprints F as obstacles -> bool grid of reached points."""
        blocked = self.static_blocked.copy()
        for r in F:
            self._block(blocked, r)
        if self.start_idx is None or blocked[self.start_idx]:
            return np.zeros_like(blocked)
        lab, _ = ndimage.label(~blocked)
        return lab == lab[self.start_idx]

    def near_reached(self, reached, P):
        """bool per point: some reached grid point within REACH_TOL."""
        if len(P) == 0:
            return np.zeros(0, dtype=bool)
        bi = np.rint((P[:, 0] - self.gx0) / GRID).astype(int)[:, None] + self._off[1][None, :]
        bj = np.rint((P[:, 1] - self.gy0) / GRID).astype(int)[:, None] + self._off[0][None, :]
        ok = (bi >= 0) & (bi < self.nx) & (bj >= 0) & (bj < self.ny)
        ci, cj = np.clip(bi, 0, self.nx - 1), np.clip(bj, 0, self.ny - 1)
        d2 = (self.gx0 + ci * GRID - P[:, 0:1]) ** 2 + (self.gy0 + cj * GRID - P[:, 1:2]) ** 2
        return (ok & reached[cj, ci] & (d2 <= (REACH_TOL + EPS) ** 2)).any(axis=1)

    def check(self, cx, cy, w, f, want_reached=False):
        """Rule check for well-formed racks. Returns V (N, 9) bool, column k = rule R(k+1) violated."""
        cx, cy, w = (np.asarray(v, dtype=float) for v in (cx, cy, w))
        f = np.asarray(f, dtype=int)
        n = len(cx)
        V = np.zeros((n, 9), dtype=bool)
        if n == 0:
            return (V, self.reach(np.zeros((0, 4)))) if want_reached else V
        F = footprints(cx, cy, w, f)
        front, rear, corr = extend(F, f, FRONT_CLR), extend(F, OPP[f], REAR_CLR), extend(F, f, CORRIDOR)
        off = ~np.eye(n, dtype=bool)
        V[:, 0] = ~self.inside(F)
        rr = overlap(F, F) & off
        V[:, 1] = rr.any(axis=1) | overlap(F, self.fixed).any(axis=1)
        for k, Z in ((2, front), (3, rear)):
            zr = overlap(Z, F) & off                      # [i, j]: clearance of i hit by rack j -> both bad
            V[:, k] = ~self.inside(Z) | overlap(Z, self.fixed).any(axis=1) | zr.any(axis=1) | zr.any(axis=0)
        cr = overlap(corr, F) & off & (f[None, :] != OPP[f][:, None])
        V[:, 4] = cr.any(axis=1) | cr.any(axis=0)
        V[:, 5] = overlap(F, self.crah_zones).any(axis=1)
        V[:, 6] = overlap(F, self.door_zones).any(axis=1)
        reached = self.reach(F)
        d = DIRS[f]
        c = np.stack([cx, cy], axis=1)
        pf = c + d * (RACK_D / 2 + FRONT_PT)
        pr = c - d * (RACK_D / 2 + REAR_PT)
        V[:, 7] = ~(self.near_reached(reached, pf) & self.near_reached(reached, pr))
        gpu = np.abs(w - GPU_W) < 1e-6
        if len(self.crah_centers):
            dist = np.hypot(cx[:, None] - self.crah_centers[None, :, 0], cy[:, None] - self.crah_centers[None, :, 1]).min(axis=1)
        else:
            dist = np.full(n, np.inf)
        V[:, 8] = gpu & (dist > GPU_MAX_DIST + EPS)
        return (V, reached) if want_reached else V


def parse_racks(entries):
    """Split the submitted list into well-formed racks (arrays) and malformed entries (index, reason)."""
    good, bad = [], []
    if not isinstance(entries, list):
        return good, [(-1, "racks is not a list")]
    for i, r in enumerate(entries):
        try:
            if not isinstance(r, dict):
                raise ValueError("entry is not an object")
            c, s, fc = r.get("center"), r.get("size"), r.get("facing")
            for name, v in (("center", c), ("size", s)):
                if not (isinstance(v, (list, tuple)) and len(v) == 2 and
                        all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)):
                    raise ValueError(f"{name} must be two finite numbers")
            if fc not in ("N", "S", "E", "W"):
                raise ValueError("facing must be N, S, E or W")
            if not any(abs(s[0] - wd) <= EPS for wd in WIDTHS) or abs(s[1] - RACK_D) > EPS:
                raise ValueError("size must be [600, 1200] or [800, 1200]")
            if max(abs(c[0]), abs(c[1])) > 1e7:
                raise ValueError("center out of range")
            wd = min(WIDTHS, key=lambda v: abs(v - s[0]))
            good.append((i, str(r.get("id", i)), float(c[0]), float(c[1]), float(wd), FACINGS.index(fc)))
        except ValueError as e:
            bad.append((i, str(e)))
    return good, bad


def evaluate(room: Room, entries, n_ref: float) -> dict:
    """Full result dict (total, parts, detail) plus private keys used by the overlay (prefixed with '_')."""
    good, malformed = parse_racks(entries)
    if len(good) > MAX_RACKS:
        malformed += [(g[0], "more than %d racks" % MAX_RACKS) for g in good[MAX_RACKS:]]
        good = good[:MAX_RACKS]
    cx = np.array([g[2] for g in good])
    cy = np.array([g[3] for g in good])
    w = np.array([g[4] for g in good])
    f = np.array([g[5] for g in good], dtype=int)
    V, reached = room.check(cx, cy, w, f, want_reached=True)
    badmask = V.any(axis=1)
    gpu = w == GPU_W
    n_valid = int((~badmask).sum())
    n_bad = int(badmask.sum()) + len(malformed)
    n_gpu_valid = int((gpu & ~badmask).sum())
    gpu_pen = 2 * abs(GPU_REQUIRED - n_gpu_valid)
    raw = (n_valid - n_bad - gpu_pen) / n_ref
    total = round(100 * min(1.0, max(0.0, raw)), 2)
    per_rack = [{"index": g[0], "id": g[1], "rules": [RULES[k] for k in range(9) if V[i, k]]}
                for i, g in enumerate(good) if badmask[i]]
    per_rack += [{"index": i, "id": None, "rules": ["malformed"], "reason": why} for i, why in malformed]
    detail = {
        "n_ref": n_ref, "racks_submitted": len(good) + len(malformed), "n_valid": n_valid, "n_bad": n_bad,
        "n_malformed": len(malformed), "n_gpu_submitted": int(gpu.sum()), "n_gpu_valid": n_gpu_valid,
        "gpu_required": GPU_REQUIRED, "gpu_penalty": gpu_pen, "net_racks": n_valid - n_bad - gpu_pen,
        "raw_ratio": round(raw, 4),
        "violations_per_rule": {RULES[k]: int(V[:, k].sum()) for k in range(9)},
        "it_footprint_m2_valid": round(float((w[~badmask] * RACK_D).sum()) / 1e6, 2),
        "it_footprint_m2_all": round(float((w * RACK_D).sum()) / 1e6, 2),
        "door_d1_reachable": bool(reached.any()),
        "bad_racks": per_rack,
    }
    return {"stage": "d2", "total": total,
            "parts": {"valid_racks": n_valid, "bad_racks": -n_bad, "gpu_count_penalty": -gpu_pen},
            "detail": detail,
            "_racks": good, "_V": V, "_reached": reached}


def public(res: dict) -> dict:
    return {k: v for k, v in res.items() if not k.startswith("_")}


def load_design(run: pathlib.Path):
    d = json.loads((run / "layout_design.json").read_text())
    if not isinstance(d, dict):
        raise ValueError("top level must be an object with a 'racks' list")
    return d.get("racks")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--room", required=True)
    ap.add_argument("--ref", type=float, required=True, help="N_REF: valid racks in the reference design")
    ap.add_argument("--out")
    a = ap.parse_args()
    try:
        entries = load_design(pathlib.Path(a.run))
        res = public(evaluate(Room(json.loads(pathlib.Path(a.room).read_text())), entries, a.ref))
    except Exception as e:
        res = {"stage": "d2", "total": 0, "parts": {}, "error": f"layout_design.json: {e}"}
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
