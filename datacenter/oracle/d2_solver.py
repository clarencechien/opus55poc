#!/usr/bin/env python3
"""Reference design for stage D2: fill an empty data hall with as many rule-conforming racks as possible.

    python d2_solver.py --room room.json --out layout_design.json [--budget 600] [--seed 0] [--log search.json]

The result passes every rule of score/d2_design.py (it is checked with the same code) and its rack count is the
N_REF that defines 100 % for the stage. Keep the output out of the repo.

Method
  1. Row bands. For a rectangular zone and a row direction (rows along x = racks face N/S, rows along y = racks face
     E/W) the best set of parallel rows is found by dynamic programming over the row position (50 mm steps): a row at
     a given position and facing holds floor(free length / 600) racks per free interval, where "free" already accounts
     for the hall outline, columns, CRAH units and their service zones, door zones, keep-out corridors and racks placed
     earlier. Consecutive rows must be front-to-front >= 1200 apart, back-to-back >= 900 apart, or >= 3000 apart when
     they face the same way.
  2. Access. Each zone gets one cross aisle ("spine", 900 wide) across its rows, or none; rows may dead-end at a wall.
  3. Search. Whole hall in one direction, and the hall split in two zones by a north-south or an east-west line with
     every combination of row directions, spine positions and packing side; the rule checker removes bad racks.
  4. Polish of the best candidates: bad racks removed, removed racks re-inserted one by one where they fit, then greedy
     insertion of extra racks on a 50 mm lattice (any facing), then 8 racks near CRAH units widened to 800 mm GPU racks
     where the rows have slack (or at the lowest cost in racks), then insertion again. The best result is kept.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import sys
import time

import numpy as np
import shapely
from shapely.geometry import box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "score"))
import d2_design as D  # noqa: E402

W0, DEPTH, SPINE = 600, D.RACK_D, 900
STEP = 50
SIGN_FACING = {(0, 1): 0, (0, -1): 1, (1, 1): 2, (1, -1): 3}   # (axis, sign) -> index into "NSEW"


def swap(R):
    return R[:, [1, 0, 3, 2]]


def merge_free(forb, lo, hi):
    """Complement of the union of intervals `forb` inside [lo, hi]."""
    out, cur = [], lo
    for a, b in sorted(forb):
        if b <= cur:
            continue
        if a >= hi:
            break
        if a > cur:
            out.append((cur, a))
        cur = b
    if cur < hi:
        out.append((cur, hi))
    return out


class Frame:
    """The room seen with u = along the rows, v = across the rows."""

    def __init__(self, room: D.Room, axis: int):
        self.axis = axis
        tr = (lambda R: R) if axis == 0 else swap
        self.poly = room.poly if axis == 0 else shapely.transform(room.poly, lambda a: a[:, ::-1])
        self.fixed = tr(room.fixed)
        self.zones = tr(np.vstack([room.crah_zones, room.door_zones]))
        self.u0, self.v0, self.u1, self.v1 = self.poly.bounds
        self._cache = {}

    def band(self, v0, sign):
        """(vlo, vhi) of footprint plus both clearances for a row whose footprint band starts at v0."""
        if sign > 0:
            return v0 - D.REAR_CLR, v0 + DEPTH + D.FRONT_CLR
        return v0 - D.FRONT_CLR, v0 + DEPTH + D.REAR_CLR

    def static_forbid(self, v0, sign):
        key = (v0, sign)
        if key not in self._cache:
            vlo, vhi = self.band(v0, sign)
            forb = []
            out = box(self.u0 - 1, vlo, self.u1 + 1, vhi).difference(self.poly)
            for g in getattr(out, "geoms", [out]):
                if not g.is_empty and g.area > 1.0:
                    forb.append((g.bounds[0], g.bounds[2]))
            m = (np.minimum(self.fixed[:, 3], vhi) - np.maximum(self.fixed[:, 1], vlo)) > D.EPS
            forb += [(r[0], r[2]) for r in self.fixed[m]]
            m = (np.minimum(self.zones[:, 3], v0 + DEPTH) - np.maximum(self.zones[:, 1], v0)) > D.EPS
            forb += [(r[0], r[2]) for r in self.zones[m]]
            self._cache[key] = forb
        return self._cache[key]


class Obstacles:
    """Racks already placed, prepared for the row-interval computation of a later zone (in that zone's frame)."""

    def __init__(self, racks, axis):
        tr = (lambda R: R) if axis == 0 else swap
        if len(racks) == 0:
            self.n = 0
            return
        self.n = len(racks)
        f = racks[:, 3].astype(int)
        F = D.footprints(racks[:, 0], racks[:, 1], racks[:, 2], f)
        self.f = f
        self.F = tr(F)
        self.clr = tr(np.vstack([D.extend(F, f, D.FRONT_CLR), D.extend(F, D.OPP[f], D.REAR_CLR)]))
        self.corr = tr(D.extend(F, f, D.CORRIDOR))

    def forbid(self, fr: Frame, v0, sign, fi):
        if self.n == 0:
            return []
        vlo, vhi = fr.band(v0, sign)
        ov = lambda R, a, b: (np.minimum(R[:, 3], b) - np.maximum(R[:, 1], a)) > D.EPS  # noqa: E731
        forb = []
        m = ov(self.F, vlo, vhi)                                   # R2, R3, R4 against existing racks
        forb += list(zip(self.F[m, 0], self.F[m, 2]))
        m = ov(self.clr, v0, v0 + DEPTH)                           # existing clearances
        forb += list(zip(self.clr[m, 0], self.clr[m, 2]))
        c0, c1 = (v0 + DEPTH, v0 + DEPTH + D.CORRIDOR) if sign > 0 else (v0 - D.CORRIDOR, v0)
        m = ov(self.F, c0, c1) & (self.f != D.OPP[fi])             # R5: my corridor
        forb += list(zip(self.F[m, 0], self.F[m, 2]))
        m = ov(self.corr, v0, v0 + DEPTH) & (D.OPP[self.f] != fi)  # R5: their corridors
        forb += list(zip(self.corr[m, 0], self.corr[m, 2]))
        return forb


class Solver:
    def __init__(self, room_json: dict, seed: int = 0, verbose: bool = True):
        self.room = D.Room(room_json)
        self.frames = [Frame(self.room, 0), Frame(self.room, 1)]
        self.rng = random.Random(seed)
        self.verbose = verbose
        self.bounds = self.room.poly.bounds
        self.n_checks = 0

    def log(self, *a):
        if self.verbose:
            print(*a, file=sys.stderr, flush=True)

    # ------------------------------------------------------------------ checking helpers
    def check(self, racks):
        self.n_checks += 1
        return self.room.check(racks[:, 0], racks[:, 1], racks[:, 2], racks[:, 3].astype(int))

    def drop_bad(self, racks):
        """Remove every bad rack (removal never creates a violation, so the rest is valid)."""
        if len(racks) == 0:
            return racks, racks
        bad = self.check(racks).any(axis=1)
        return racks[~bad], racks[bad]

    def repair(self, racks):
        """drop_bad, then try to put each removed rack back."""
        keep, removed = self.drop_bad(racks)
        for r in removed:
            trial = np.vstack([keep, r[None, :]])
            if not self.check(trial).any():
                keep = trial
        return keep

    # ------------------------------------------------------------------ row bands
    def fill_zone(self, zone, axis, keepouts=(), existing=None, align="lo", strict=False):
        """Best parallel rows in `zone` (x0, y0, x1, y1). Returns racks (n, 4) = cx, cy, w, facing index.
        strict: no row may have a column inside its front or rear clearance band (columns end up inside rows,
        so they do not cut the aisles)."""
        fr = self.frames[axis]
        z = zone if axis == 0 else (zone[1], zone[0], zone[3], zone[2])
        zu0, zv0, zu1, zv1 = max(z[0], fr.u0), max(z[1], fr.v0), min(z[2], fr.u1), min(z[3], fr.v1)
        K = np.array(keepouts, dtype=float).reshape(-1, 4)
        K = K if axis == 0 else swap(K)
        obst = Obstacles(existing if existing is not None else np.zeros((0, 4)), axis)
        vs = np.arange(zv0, zv1 - DEPTH + 1e-6, STEP)
        n = len(vs)
        if n == 0 or zu1 - zu0 < W0:
            return np.zeros((0, 4))
        cnt = np.zeros((n, 2), dtype=int)
        ivs = {}
        cols = self.room.columns if axis == 0 else swap(self.room.columns)
        cols = cols[(np.minimum(cols[:, 2], zu1) - np.maximum(cols[:, 0], zu0)) > D.EPS]
        for i, v0 in enumerate(vs):
            km = (np.minimum(K[:, 3], v0 + DEPTH) - np.maximum(K[:, 1], v0)) > D.EPS
            kf = [(r[0], r[2]) for r in K[km]]
            for s, sign in enumerate((1, -1)):
                fi = SIGN_FACING[(axis, sign)]
                forb = fr.static_forbid(float(v0), sign) + kf + obst.forbid(fr, v0, sign, fi)
                free = [(a, b) for a, b in merge_free(forb, zu0, zu1) if b - a >= W0 - 1e-6]
                ivs[(i, s)] = free
                cnt[i, s] = sum(int((b - a + 1e-6) // W0) for a, b in free)
                if strict and len(cols):
                    vlo, vhi = fr.band(v0, sign)
                    hit = ((np.minimum(cols[:, 3], v0) - np.maximum(cols[:, 1], vlo)) > D.EPS) | \
                          ((np.minimum(cols[:, 3], vhi) - np.maximum(cols[:, 1], v0 + DEPTH)) > D.EPS)
                    if hit.any():
                        cnt[i, s] = -10 ** 6
        # DP over row positions; state = (index of the row's lower edge, sign)
        off = {(0, 1): math.ceil((DEPTH + D.FRONT_CLR) / STEP), (1, 0): math.ceil((DEPTH + D.REAR_CLR) / STEP),
               (0, 0): math.ceil((DEPTH + D.CORRIDOR) / STEP), (1, 1): math.ceil((DEPTH + D.CORRIDOR) / STEP)}
        best = np.zeros((n, 2), dtype=int)
        prev = {}
        pm = np.zeros((n, 2), dtype=int)       # prefix max of best[:, s]
        pa = np.zeros((n, 2), dtype=int)       # its argmax
        for i in range(n):
            for s in range(2):
                b, p = 0, None
                for ps in range(2):
                    j = i - off[(ps, s)]
                    if j >= 0 and pm[j, ps] > b:
                        b, p = pm[j, ps], (pa[j, ps], ps)
                best[i, s] = cnt[i, s] + b
                prev[(i, s)] = p
            for s in range(2):
                if i > 0 and pm[i - 1, s] >= best[i, s]:
                    pm[i, s], pa[i, s] = pm[i - 1, s], pa[i - 1, s]
                else:
                    pm[i, s], pa[i, s] = best[i, s], i
        if best.max() <= 0:
            return np.zeros((0, 4))
        cur = np.unravel_index(np.argmax(best), best.shape)
        cur = (int(cur[0]), int(cur[1]))
        racks = []
        while cur is not None:
            i, s = cur
            sign = (1, -1)[s]
            fi = SIGN_FACING[(axis, sign)]
            vc = vs[i] + DEPTH / 2
            for a, b in ivs[(i, s)]:
                k = int((b - a + 1e-6) // W0)
                start = a if align == "lo" else (b - k * W0 if align == "hi" else a + STEP * round((b - a - k * W0) / 2 / STEP))
                for t in range(k):
                    uc = start + W0 / 2 + t * W0
                    racks.append((uc, vc, W0, fi) if axis == 0 else (vc, uc, W0, fi))
            cur = prev[cur]
        return np.array(racks, dtype=float).reshape(-1, 4)

    def spine_rect(self, zone, axis, q):
        """Keep-out corridor across the rows of a zone at along-row position q."""
        if axis == 0:
            return (q, zone[1], q + SPINE, zone[3])
        return (zone[0], q, zone[2], q + SPINE)

    def spine_positions(self, zone, axis, step):
        lo, hi = (zone[0], zone[2]) if axis == 0 else (zone[1], zone[3])
        qs = [None, lo, hi - SPINE]
        qs += [float(q) for q in np.arange(math.ceil(lo / step) * step, hi - SPINE, step)]
        seen, out = set(), []
        for q in qs:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out

    def build(self, parts):
        """parts = [(zone, axis, q, align, strict), ...] filled in order. Returns valid racks (bad ones dropped)."""
        racks = np.zeros((0, 4))
        keep = [self.spine_rect(p[0], p[1], p[2]) for p in parts if p[2] is not None]
        for zone, axis, q, align, strict in parts:
            new = self.fill_zone(zone, axis, keepouts=keep, existing=racks, align=align, strict=strict)
            racks = np.vstack([racks, new])
        return self.drop_bad(racks)[0]

    # ------------------------------------------------------------------ greedy insertion on a lattice
    def _static_candidates(self):
        """Per facing: bool lattice of 600-wide rack positions that satisfy every rule not involving other racks."""
        if hasattr(self, "_static"):
            return self._static
        x0, y0, x1, y1 = self.bounds
        self.lx = np.arange(x0, x1 + 1, STEP)
        self.ly = np.arange(y0, y1 + 1, STEP)
        XX, YY = np.meshgrid(self.lx, self.ly)
        cx, cy = XX.ravel(), YY.ravel()
        room = self.room
        out = []
        for fi in range(4):
            f = np.full(len(cx), fi)
            F = D.footprints(cx, cy, np.full(len(cx), float(W0)), f)
            fr_, re_ = D.extend(F, f, D.FRONT_CLR), D.extend(F, D.OPP[f], D.REAR_CLR)
            ok = room.inside(F) & room.inside(fr_) & room.inside(re_)
            idx = np.where(ok)[0]
            for R in (F, fr_, re_):
                ok[idx] &= ~D.overlap(R[idx], room.fixed).any(axis=1)
            ok[idx] &= ~D.overlap(F[idx], np.vstack([room.crah_zones, room.door_zones])).any(axis=1)
            out.append(ok.reshape(XX.shape))
        self._static = out
        return out

    def _cells(self, R):
        """Integer cell ranges (i0, j0, i1, j1) of rectangles on the 50 mm raster (clipped)."""
        x0, y0 = self.bounds[0], self.bounds[1]
        nx, ny = len(self.lx) - 1, len(self.ly) - 1
        i0 = np.clip(np.floor((R[:, 0] - x0 + D.EPS) / STEP), 0, nx).astype(int)
        i1 = np.clip(np.ceil((R[:, 2] - x0 - D.EPS) / STEP), 0, nx).astype(int)
        j0 = np.clip(np.floor((R[:, 1] - y0 + D.EPS) / STEP), 0, ny).astype(int)
        j1 = np.clip(np.ceil((R[:, 3] - y0 - D.EPS) / STEP), 0, ny).astype(int)
        return i0, j0, i1, j1

    def _raster(self, R):
        nx, ny = len(self.lx) - 1, len(self.ly) - 1
        g = np.zeros((ny, nx), dtype=np.int32)
        i0, j0, i1, j1 = self._cells(R)
        for a, b, c, d in zip(i0, j0, i1, j1):
            g[b:d, a:c] += 1
        return g

    @staticmethod
    def _integral(g):
        s = np.zeros((g.shape[0] + 1, g.shape[1] + 1), dtype=np.int64)
        s[1:, 1:] = g.cumsum(0).cumsum(1)
        return s

    def _boxsum(self, S, R):
        i0, j0, i1, j1 = self._cells(R)
        return S[j1, i1] - S[j0, i1] - S[j1, i0] + S[j0, i0]

    def candidates(self, racks):
        """Lattice positions (cx, cy, 600, f) that pass R1-R7 against the fixed items and the given racks."""
        static = self._static_candidates()
        f = racks[:, 3].astype(int)
        F = D.footprints(racks[:, 0], racks[:, 1], racks[:, 2], f)
        occ = [self._integral(self._raster(F[f == g])) for g in range(4)]
        occ_all = sum(occ)
        clr = self._integral(self._raster(np.vstack([D.extend(F, f, D.FRONT_CLR), D.extend(F, D.OPP[f], D.REAR_CLR)])))
        corr = [self._integral(self._raster(D.extend(F[f == g], f[f == g], D.CORRIDOR))) for g in range(4)]
        out = []
        for fi in range(4):
            jj, ii = np.where(static[fi])
            if len(ii) == 0:
                continue
            cx, cy = self.lx[ii], self.ly[jj]
            ff = np.full(len(cx), fi)
            Fc = D.footprints(cx, cy, np.full(len(cx), float(W0)), ff)
            bad = self._boxsum(occ_all, Fc) + self._boxsum(clr, Fc)
            bad += self._boxsum(occ_all, D.extend(Fc, ff, D.FRONT_CLR)) + self._boxsum(occ_all, D.extend(Fc, D.OPP[ff], D.REAR_CLR))
            opp = D.OPP[fi]
            bad += self._boxsum(occ_all - occ[opp], D.extend(Fc, ff, D.CORRIDOR))
            # existing corridors may only be entered by racks facing opposite to the corridor's owner
            for g in range(4):
                if D.OPP[g] != fi:
                    bad += self._boxsum(corr[g], Fc)
            m = bad == 0
            out.append(np.stack([cx[m], cy[m], np.full(m.sum(), float(W0)), np.full(m.sum(), float(fi))], axis=1))
        return np.vstack(out) if out else np.zeros((0, 4))

    def insert(self, racks, max_checks=4000):
        """Greedy insertion of 600-wide racks until no lattice position fits."""
        dead = set()
        checks = 0
        while checks < max_checks:
            cand = self.candidates(racks)
            cand = [c for c in cand if tuple(c) not in dead]
            if not cand:
                break
            # prefer positions that continue an existing row (same facing, same row line, touching)
            f = racks[:, 3].astype(int)
            keys = set()
            for r in racks:
                ns = r[3] < 2
                for sgn in (-1, 1):
                    keys.add((r[0] + sgn * (r[2] / 2 + W0 / 2), r[1], r[3]) if ns else (r[0], r[1] + sgn * (r[2] / 2 + W0 / 2), r[3]))
            cand.sort(key=lambda c: (0 if (c[0], c[1], c[3]) in keys else 1, self.rng.random()))
            added = False
            for c in cand:
                trial = np.vstack([racks, c[None, :]])
                checks += 1
                if not self.check(trial).any():
                    racks, added = trial, True
                    break
                dead.add(tuple(c))
                if checks >= max_checks:
                    break
            if not added:
                break
        return racks

    # ------------------------------------------------------------------ GPU racks
    def runs(self, racks):
        """Groups of touching racks on one row line with one facing: lists of indices sorted along the row."""
        groups = {}
        for i, r in enumerate(racks):
            ns = r[3] < 2
            groups.setdefault((int(r[3]), round(r[1] if ns else r[0])), []).append(i)
        out = []
        for (fi, _), idx in groups.items():
            a = 0 if fi < 2 else 1
            idx.sort(key=lambda i: racks[i, a])
            run = [idx[0]]
            for i, j in zip(idx, idx[1:]):
                if abs((racks[j, a] - racks[j, 2] / 2) - (racks[i, a] + racks[i, 2] / 2)) < 1:
                    run.append(j)
                else:
                    out.append(run)
                    run = [j]
            out.append(run)
        return out

    def widen(self, racks, run, k, direction):
        """Turn k standard racks of a run into GPU racks, pushing the rest of the run towards `direction` (+1 / -1);
        racks pushed into trouble at that end are dropped. Returns the new rack array or None."""
        a = 0 if racks[run[0], 3] < 2 else 1
        order = run if direction > 0 else run[::-1]
        std = [i for i in order if racks[i, 2] == W0]
        if len(std) < k:
            return None
        cc = self.room.crah_centers

        def dist(i):
            return np.hypot(cc[:, 0] - racks[i, 0], cc[:, 1] - racks[i, 1]).min()
        # the k consecutive (in run order) standard racks closest to a CRAH
        pos = {i: p for p, i in enumerate(order)}
        best = None
        for s in range(len(std) - k + 1):
            pick = std[s:s + k]
            if pos[pick[-1]] - pos[pick[0]] != k - 1:
                continue
            m = max(dist(i) for i in pick)
            if best is None or m < best[0]:
                best = (m, pick)
        if best is None or best[0] > D.GPU_MAX_DIST + 600:
            return None
        pick = set(best[1])
        new = racks.copy()
        shift = 0.0
        for i in order:
            if i in pick:
                new[i, 2] = D.GPU_W
                new[i, a] += direction * (shift + 100)
                shift += 200
            else:
                new[i, a] += direction * shift
        gone = []
        tail = order[::-1]                       # racks at the end that moves, outermost first
        for t in range(len(tail) + 1):
            keep = np.ones(len(new), dtype=bool)
            keep[gone] = False
            trial = new[keep]
            if not self.check(trial).any():
                return trial if (trial[:, 2] == D.GPU_W).sum() >= (racks[:, 2] == D.GPU_W).sum() + k else None
            if t == len(tail) or tail[t] in pick:
                return None
            gone.append(tail[t])
        return None

    def add_gpus(self, racks):
        """Widen racks until there are exactly GPU_REQUIRED valid GPU racks, losing as few racks as possible."""
        need = D.GPU_REQUIRED - int((racks[:, 2] == D.GPU_W).sum())
        while need > 0:
            options = []
            for run in self.runs(racks):
                for direction in (1, -1):
                    for k in range(1, need + 1):
                        new = self.widen(racks, run, k, direction)
                        if new is None:
                            break
                        loss = len(racks) - len(new)
                        options.append((loss / k, loss, -k, self.rng.random(), new))
                        if loss > 0 and k >= 3:
                            pass
            if not options:
                return None
            options.sort(key=lambda o: o[:4])
            racks = options[0][4]
            need = D.GPU_REQUIRED - int((racks[:, 2] == D.GPU_W).sum())
        return racks

    # ------------------------------------------------------------------ search
    def polish(self, racks):
        racks = self.repair(racks)
        racks = self.insert(racks)
        g = self.add_gpus(racks)
        if g is None:
            return None
        g = self.insert(g)
        return g

    def zone_pair(self, kind, c):
        x0, y0, x1, y1 = self.bounds
        if kind == "x":
            return (x0, y0, c, y1), (c, y0, x1, y1)
        return (x0, y0, x1, c), (x0, c, x1, y1)

    def search(self, budget_s=600.0, coarse=600, cut_step=600, top=12):
        t0 = time.time()
        x0, y0, x1, y1 = self.bounds
        whole = (x0, y0, x1, y1)
        pool = {}                                   # description -> (count, parts)

        def desc_of(parts):
            return " + ".join(f"[{'x' if p[1] == 0 else 'y'}-rows in ({p[0][0]:.0f},{p[0][1]:.0f})-({p[0][2]:.0f},{p[0][3]:.0f}) "
                              f"spine={'none' if p[2] is None else format(p[2], '.0f')} pack={p[3]}{' strict' if p[4] else ''}]"
                              for p in parts)

        def consider(parts):
            d = desc_of(parts)
            if d not in pool:
                pool[d] = (len(self.build(parts)), parts)
            return pool[d][0]

        def best():
            return max(v[0] for v in pool.values())

        # A. whole hall, one row direction
        for axis in (0, 1):
            for q in self.spine_positions(whole, axis, 300):
                for align in ("lo", "hi"):
                    for strict in (False, True):
                        consider([(whole, axis, q, align, strict)])
        self.log(f"[{time.time() - t0:6.1f}s] whole hall, one direction: best {best()}")
        # B. two zones split by a line; rank each zone's (axis, spine, strict) alone, then combine the best few
        pts = self.room.json["room"]["polygon"]
        cuts = [("x", float(c)) for c in sorted({p[0] for p in pts})[1:-1]] + [("y", float(c)) for c in sorted({p[1] for p in pts})[1:-1]]
        rest = [("x", float(c)) for c in np.arange(x0 + 2400, x1 - 2400 + 1, cut_step)]
        rest += [("y", float(c)) for c in np.arange(y0 + 2400, y1 - 2400 + 1, cut_step)]
        self.rng.shuffle(rest)
        cuts += [c for c in rest if c not in cuts]
        for kind, c in cuts:
            if time.time() - t0 > budget_s:
                self.log("search budget used up")
                break
            zones = self.zone_pair(kind, c)
            ranked = []
            for zone in zones:
                sel = []
                for axis in (0, 1):
                    opts = []
                    for strict in (False, True):
                        for q in self.spine_positions(zone, axis, coarse):
                            opts.append((len(self.build([(zone, axis, q, "lo", strict)])), q, strict))
                    opts.sort(key=lambda o: -o[0])
                    none = [o for o in opts if o[1] is None][:1]
                    sel += [(axis, o[1], o[2]) for o in none + [o for o in opts if o[1] is not None][:2]]
                ranked.append(sel)
            here = 0
            for a0, q0, s0 in ranked[0]:
                for a1, q1, s1 in ranked[1]:
                    for al in ("lo", "hi"):
                        parts = [(zones[0], a0, q0, al, s0), (zones[1], a1, q1, al, s1)]
                        here = max(here, consider(parts), consider(parts[::-1]))
            self.log(f"[{time.time() - t0:6.1f}s] split {kind}={c:.0f}: best {here}  (overall {best()})")
        # polish the best distinct candidates
        order = sorted(pool.items(), key=lambda kv: -kv[1][0])
        results, seen = [], set()
        for d, (cnt, parts) in order:
            if len(results) >= top:
                break
            racks = self.build(parts)
            key = tuple(sorted(map(tuple, np.round(racks).astype(int).tolist())))
            if key in seen:
                continue
            seen.add(key)
            final = self.polish(racks)
            if final is None:
                continue
            results.append((len(final), cnt, d, final))
            self.log(f"[{time.time() - t0:6.1f}s] polish: {cnt} -> {len(final)}  {d}")
        results.sort(key=lambda r: -r[0])
        return results, pool


def to_json(racks):
    """Row-wise ids: rows lettered from the south-west, racks numbered along the row."""
    order = sorted(range(len(racks)), key=lambda i: (racks[i, 3] >= 2, round(racks[i, 1]) if racks[i, 3] < 2 else round(racks[i, 0]),
                                                      racks[i, 0] if racks[i, 3] < 2 else racks[i, 1]))
    out, row_key, row_no, k = [], None, 0, 0
    for i in order:
        cx, cy, w, f = racks[i]
        key = (f >= 2, round(cy) if f < 2 else round(cx))
        if key != row_key:
            row_key, row_no, k = key, row_no + 1, 0
        k += 1
        out.append({"id": f"R{row_no:02d}-{k:02d}", "center": [round(float(cx), 1), round(float(cy), 1)],
                    "size": [int(w), DEPTH], "facing": D.FACINGS[int(f)]})
    return {"units": "mm", "racks": out}


def summary(racks):
    f = racks[:, 3].astype(int)
    return {"racks": len(racks), "gpu": int((racks[:, 2] == D.GPU_W).sum()),
            "facing": {D.FACINGS[g]: int((f == g).sum()) for g in range(4)},
            "rows_east_west": len({round(r[1]) for r in racks if r[3] < 2}),
            "rows_north_south": len({round(r[0]) for r in racks if r[3] >= 2})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=float, default=600, help="seconds for the zone-split search")
    ap.add_argument("--top", type=int, default=12, help="candidates to polish")
    ap.add_argument("--cut-step", type=int, default=600, help="spacing of the zone split lines tried (mm)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", help="write the search summary (JSON) here")
    a = ap.parse_args()
    room_json = json.loads(pathlib.Path(a.room).read_text())
    sv = Solver(room_json, seed=a.seed)
    results, pool = sv.search(budget_s=a.budget, top=a.top, cut_step=a.cut_step)
    n, cnt, desc, racks = results[0]
    V = sv.check(racks)
    assert not V.any(), "reference design violates a rule"
    assert (racks[:, 2] == D.GPU_W).sum() == D.GPU_REQUIRED
    pathlib.Path(a.out).write_text(json.dumps(to_json(racks), indent=1))
    info = {"n_ref": n, "config": desc, "before_polish": cnt, "summary": summary(racks),
            "polished": [{"n": r[0], "before": r[1], "config": r[2]} for r in results],
            "configs_tried": len(pool), "rule_checks": sv.n_checks,
            "best_before_polish": [{"n": v[0], "config": k} for k, v in sorted(pool.items(), key=lambda kv: -kv[1][0])[:40]]}
    if a.log:
        pathlib.Path(a.log).write_text(json.dumps(info, indent=1))
    print(json.dumps({k: v for k, v in info.items() if k != "best_before_polish"}, indent=1))


if __name__ == "__main__":
    main()
