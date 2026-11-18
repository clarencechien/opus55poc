"""Score stage D5 (rebuild a piece of equipment from engineering views) by 3D overlap with the hidden target.

    blender -b RUN/d5.blend --python score/d5_voxel.py -- --gt GT_DIR/target.json --out score.json [--save-occ occ.npz]
    (alternatively: blender -b --factory-startup --python score/d5_voxel.py -- --run RUN_DIR --gt ... )

Method
  * Grid: 10 mm voxels over the target's bounding box padded by 100 mm ("core grid"). Occupancy is sampled at
    voxel centres (moved by a fixed ~0.1 mm so that faces on round coordinates never sit exactly on a sample).
  * Target occupancy: analytic, from the boxes and cylinders in target.json; every voxel is labelled with its
    feature group.
  * Submission occupancy: union over the visible mesh objects under the root object `Target` (the root itself
    included if it is a mesh; evaluated meshes = modifiers applied; instances realised; world space). Every mesh
    is split into connected shells. For every shell a BVH is built and one ray per (x, y) voxel column is cast
    down along z; the hits are paired in order (entry, exit), and the voxels whose centres lie between a pair
    are filled. A hit without a partner marks only the voxel it lies in. Shells that are not closed are cast
    together per object (so a tube plus two separate cap faces still fills), with the same pairing rule.
  * The submission is NOT re-aligned. Submission volume outside the core grid counts as surplus (the working
    grid grows to hold the submission, up to 1 m beyond the core grid; anything further away is ignored).

Score (100)
  50 * IoU(target, submission)
  50 * mean over the feature groups of recall_f * precision_f
       region_f    = the group's voxels grown by 20 mm (2 voxels, in x, y and z), minus voxels of other target parts
       recall_f    = share of the group's target voxels that are filled in the submission
       precision_f = share of the submission voxels inside region_f that are target voxels of the group
                     (1.0 if the submission has no voxel in region_f; recall_f is 0 then anyway)
  If the submission has more than 100,000 triangles the total is halved.
  No root object `Target`, or no mesh under it: total 0.

Detail: IoU, IoU after the best whole-voxel xy shift within +-50 mm (tells "misplaced" from "wrong shape"),
bounding boxes, per-feature recall/precision, triangle count, missing root.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time

import numpy as np

H = 0.01            # voxel size (m)
PAD = 0.10          # core grid = target bbox + PAD
EXTRA = 1.0         # the working grid may grow this far beyond the core grid to count surplus volume
JIT = (1.3e-4, 0.7e-4, 0.9e-4)  # sample offset from the voxel centre (m)
EPS = 1e-5          # restart distance below a ray hit (m)
GROW = 2            # feature region: voxels grown by 2 voxels = 20 mm
SHIFT = 5           # best-shift search: +-5 voxels = +-50 mm
TRI_LIMIT = 100_000
ROOT = "Target"


# ---------------------------------------------------------------- grid + analytic target
class Grid:
    """Working grid: `lo` is its minimum corner, `n` its size in voxels, `core` the slice of the core grid."""

    def __init__(self, gt: dict, sub_lo=None, sub_hi=None):
        g_lo = np.array(gt["bbox"]["min"], float) - PAD
        g_n = np.rint((np.array(gt["bbox"]["max"], float) + PAD - g_lo) / H).astype(int)
        before = np.zeros(3, int)
        after = np.zeros(3, int)
        if sub_lo is not None:
            cap = int(round(EXTRA / H))
            before = np.clip(np.ceil((g_lo - np.asarray(sub_lo)) / H).astype(int) + 1, 0, cap)
            after = np.clip(np.ceil((np.asarray(sub_hi) - (g_lo + g_n * H)) / H).astype(int) + 1, 0, cap)
        self.lo = g_lo - before * H
        self.n = g_n + before + after
        self.core = tuple(slice(int(b), int(b + m)) for b, m in zip(before, g_n))
        self.c = [self.lo[i] + (np.arange(self.n[i]) + 0.5) * H + JIT[i] for i in range(3)]  # sample coordinates

    def index_range(self, a: float, b: float, axis: int):
        """Indices [i0, i1) of the samples with a <= coordinate <= b."""
        i0 = int(math.ceil((a - self.lo[axis] - JIT[axis]) / H - 0.5 - 1e-9))
        i1 = int(math.floor((b - self.lo[axis] - JIT[axis]) / H - 0.5 + 1e-9)) + 1
        return max(i0, 0), min(i1, int(self.n[axis]))


def part_extent(p: dict):
    c = np.array(p["position"], float)
    if p["type"] == "box":
        half = np.array(p["size"], float) / 2
    else:
        half = np.full(3, p["diameter"] / 2)
        half["xyz".index(p["axis"])] = p["length"] / 2
    return c - half, c + half


def gt_labels(gt: dict, grid: Grid) -> tuple[np.ndarray, list[str]]:
    """int8 array: 0 = empty, k = voxel belongs to feature group number k (1-based, order of gt['groups'])."""
    names = list(gt["groups"])
    lab = np.zeros(grid.n, np.int8)
    for p in gt["parts"]:
        k = names.index(p["group"]) + 1
        a, b = part_extent(p)
        r = [grid.index_range(a[i], b[i], i) for i in range(3)]
        if any(i0 >= i1 for i0, i1 in r):
            continue
        sl = tuple(slice(i0, i1) for i0, i1 in r)
        if p["type"] == "box":
            lab[sl] = k
        else:
            ax = "xyz".index(p["axis"])
            u, v = [i for i in range(3) if i != ax]
            du = grid.c[u][r[u][0]:r[u][1]] - p["position"][u]
            dv = grid.c[v][r[v][0]:r[v][1]] - p["position"][v]
            disc = (du[:, None] ** 2 + dv[None, :] ** 2) <= (p["diameter"] / 2) ** 2
            shape = [1, 1, 1]
            shape[u], shape[v] = disc.shape
            m = np.broadcast_to(disc.reshape(shape), [i1 - i0 for i0, i1 in r])
            view = lab[sl]
            view[m] = k
    return lab, names


# ---------------------------------------------------------------- submission meshes (inside Blender)
def collect_meshes(root_name: str = ROOT):
    """World-space triangle soups of the visible mesh objects under the root. Returns (list, info)."""
    import bpy

    sc = bpy.context.scene
    root = sc.objects.get(root_name)
    info = {"missing_root": root is None, "objects": 0, "triangles": 0}
    if root is None:
        return [], info

    def under(o):
        seen = 0
        while o is not None and seen < 1000:
            if o == root:
                return True
            o, seen = o.parent, seen + 1
        return False

    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != "MESH":
            continue
        anchor = inst.parent.original if inst.is_instance and inst.parent else ob.original
        if not under(anchor) or anchor.hide_render or ob.original.hide_render:
            continue
        mw = np.array(inst.matrix_world, dtype=np.float64)
        me = ob.to_mesh()
        nv = len(me.vertices)
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if nv == 0 or nt == 0:
            ob.to_mesh_clear()
            continue
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        ob.to_mesh_clear()
        world = co.reshape(-1, 3).astype(np.float64) @ mw[:3, :3].T + mw[:3, 3]
        if not np.isfinite(world).all():
            continue
        out.append({"name": ob.original.name, "verts": world, "tris": tri.reshape(-1, 3)})
        info["objects"] += 1
        info["triangles"] += nt
    return out, info


def _components(nv: int, e: np.ndarray) -> np.ndarray:
    """Connected-component label per vertex (numpy only: Blender's Python has no scipy)."""
    lab = np.arange(nv)
    a, b = e[:, 0], e[:, 1]
    while True:
        m = np.minimum(lab[a], lab[b])
        new = lab.copy()
        np.minimum.at(new, lab[a], m)       # hook the larger root under the smaller one
        np.minimum.at(new, lab[b], m)
        while True:                          # pointer jumping
            nxt = new[new]
            if np.array_equal(nxt, new):
                break
            new = nxt
        if np.array_equal(new, lab):
            return lab
        lab = new


def _grow(m: np.ndarray, r: int) -> np.ndarray:
    """Box dilation by r voxels along x, y and z."""
    for ax in range(3):
        out = m.copy()
        for d in range(1, r + 1):
            src = [slice(None)] * 3
            dst = [slice(None)] * 3
            src[ax], dst[ax] = slice(d, None), slice(None, -d)
            out[tuple(dst)] |= m[tuple(src)]
            out[tuple(src)] |= m[tuple(dst)]
        m = out
    return m


def split_shells(verts: np.ndarray, tris: np.ndarray):
    """Split a triangle soup into connected shells. Returns (closed shells, one merged soup of the open ones)."""
    nv = len(verts)
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    vlab = _components(nv, e)
    tlab = vlab[tris[:, 0]]
    es = np.sort(e, axis=1)
    key = es[:, 0].astype(np.int64) * nv + es[:, 1]
    uniq, cnt = np.unique(key, return_counts=True)
    odd = uniq[cnt % 2 == 1]                       # an edge used an odd number of times: the shell is open there
    open_labels = np.unique(vlab[(odd // nv).astype(np.int64)]) if len(odd) else np.empty(0, int)
    is_open = np.isin(tlab, open_labels)
    closed = []
    idx = np.flatnonzero(~is_open)
    if len(idx):
        order = idx[np.argsort(tlab[idx], kind="stable")]
        cuts = np.flatnonzero(np.diff(tlab[order])) + 1
        closed = [tris[part] for part in np.split(order, cuts)]
    open_soup = tris[is_open] if is_open.any() else None
    return closed, open_soup


def cast_shell(verts: np.ndarray, tris: np.ndarray, grid: Grid, occ: np.ndarray, stats: dict) -> None:
    """Ray-cast one shell down along z for every voxel column under it and fill `occ`."""
    from mathutils.bvhtree import BVHTree

    used = np.unique(tris)
    remap = np.zeros(len(verts), np.int32)
    remap[used] = np.arange(len(used), dtype=np.int32)
    v = verts[used]
    lo, hi = v.min(axis=0), v.max(axis=0)
    i0, i1 = grid.index_range(lo[0], hi[0], 0)
    j0, j1 = grid.index_range(lo[1], hi[1], 1)
    if i0 >= i1 or j0 >= j1:
        return
    bvh = BVHTree.FromPolygons(v.tolist(), remap[tris].tolist(), all_triangles=True, epsilon=0.0)
    ray = bvh.ray_cast
    down = (0.0, 0.0, -1.0)
    ztop = float(hi[2]) + 0.05
    cx, cy = grid.c[0], grid.c[1]
    pi, pj, pa, pb = [], [], [], []      # paired hits: column i, j, upper z, lower z
    si, sj, sz = [], [], []              # single hits
    for i in range(i0, i1):
        x = float(cx[i])
        for j in range(j0, j1):
            y = float(cy[j])
            z = ztop
            hits = []
            while len(hits) < 256:
                h = ray((x, y, z), down)[0]
                if h is None:
                    break
                z = h[2]
                hits.append(z)
                z -= EPS
            n = len(hits)
            if not n:
                continue
            for k in range(0, n - 1, 2):
                pi.append(i), pj.append(j), pa.append(hits[k]), pb.append(hits[k + 1])
            if n % 2:
                si.append(i), sj.append(j), sz.append(hits[-1])
    stats["rays"] += (i1 - i0) * (j1 - j0)
    stats["unpaired_hits"] += len(si)
    zl, zo = grid.lo[2], JIT[2]
    nz = int(grid.n[2])
    if pi:
        pi_, pj_ = np.array(pi), np.array(pj)
        k0 = np.ceil((np.array(pb) - zl - zo) / H - 0.5 - 1e-9).astype(int)           # first sample >= lower z
        k1 = np.floor((np.array(pa) - zl - zo) / H - 0.5 + 1e-9).astype(int) + 1      # one past last sample <= upper z
        k0, k1 = np.clip(k0, 0, nz), np.clip(k1, 0, nz)
        ok = k1 > k0
        if ok.any():
            pi_, pj_, k0, k1 = pi_[ok], pj_[ok], k0[ok], k1[ok]
            za, zb = int(k0.min()), int(k1.max())
            diff = np.zeros((i1 - i0, j1 - j0, zb - za + 1), np.int16)
            np.add.at(diff, (pi_ - i0, pj_ - j0, k0 - za), 1)
            np.add.at(diff, (pi_ - i0, pj_ - j0, k1 - za), -1)
            occ[i0:i1, j0:j1, za:zb] |= np.cumsum(diff, axis=2, dtype=np.int16)[:, :, :-1] > 0
    if si:
        k = np.floor((np.array(sz) - zl) / H).astype(int)
        ok = (k >= 0) & (k < nz)
        occ[np.array(si)[ok], np.array(sj)[ok], k[ok]] = True


def voxelise(meshes: list, grid: Grid) -> tuple[np.ndarray, dict]:
    occ = np.zeros(grid.n, bool)
    stats = {"shells_closed": 0, "open_objects": 0, "rays": 0, "unpaired_hits": 0}
    for m in meshes:
        closed, open_soup = split_shells(m["verts"], m["tris"])
        for t in closed:
            cast_shell(m["verts"], t, grid, occ, stats)
        stats["shells_closed"] += len(closed)
        if open_soup is not None:
            stats["open_objects"] += 1
            cast_shell(m["verts"], open_soup, grid, occ, stats)
    return occ, stats


# ---------------------------------------------------------------- comparison
def best_shift(G: np.ndarray, S: np.ndarray, n_g: int, n_s: int):
    nx, ny = G.shape[:2]
    best = (-1.0, 0, 0)
    for dx in range(-SHIFT, SHIFT + 1):
        gx, sx = slice(max(dx, 0), nx + min(dx, 0)), slice(max(-dx, 0), nx + min(-dx, 0))
        for dy in range(-SHIFT, SHIFT + 1):
            gy, sy = slice(max(dy, 0), ny + min(dy, 0)), slice(max(-dy, 0), ny + min(-dy, 0))
            inter = int(np.count_nonzero(G[gx, gy] & S[sx, sy]))
            v = inter / (n_g + n_s - inter) if n_g + n_s - inter else 0.0
            if v > best[0] + 1e-12 or (abs(v - best[0]) <= 1e-12 and abs(dx) + abs(dy) < abs(best[1]) + abs(best[2])):
                best = (v, dx, dy)
    return best


def feature_scores(lab: np.ndarray, names: list[str], S: np.ndarray) -> dict:
    out = {}
    for k, name in enumerate(names, start=1):
        F_full = lab == k
        idx = np.argwhere(F_full)
        if not len(idx):
            out[name] = {"recall": 0.0, "precision": 1.0, "score": 0.0, "gt_voxels": 0}
            continue
        a = np.maximum(idx.min(axis=0) - GROW, 0)
        b = np.minimum(idx.max(axis=0) + 1 + GROW, lab.shape)
        sl = tuple(slice(int(x), int(y)) for x, y in zip(a, b))
        L, F, Sc = lab[sl], F_full[sl], S[sl]
        region = _grow(F, GROW) & ~((L > 0) & ~F)
        hit = int(np.count_nonzero(F & Sc))
        n_f = int(np.count_nonzero(F))
        n_s = int(np.count_nonzero(Sc & region))
        rec = hit / n_f
        prec = hit / n_s if n_s else 1.0
        out[name] = {"recall": round(rec, 4), "precision": round(prec, 4), "score": round(rec * prec, 4),
                     "gt_voxels": n_f, "sub_voxels_in_region": n_s}
    return out


def score(gt: dict, root_name: str = ROOT, keep_arrays: bool = False) -> dict:
    t0 = time.time()
    meshes, info = collect_meshes(root_name)
    gt_lo, gt_hi = np.array(gt["bbox"]["min"]), np.array(gt["bbox"]["max"])
    detail = {"missing_root": info["missing_root"], "objects": info["objects"], "triangles": info["triangles"],
              "triangle_limit": TRI_LIMIT,
              "bbox_gt": {"min": gt["bbox"]["min"], "max": gt["bbox"]["max"], "size": gt["bbox"]["size"]}}
    if not meshes:
        grid = Grid(gt)
        lab, names = gt_labels(gt, grid)
        res = {"stage": "d5", "total": 0.0, "parts": {"iou": 0.0, "features": 0.0},
               "detail": {**detail, "error": "no root object 'Target'" if info["missing_root"] else
                          "no visible mesh objects under 'Target'"}}
        if keep_arrays:
            res["_arrays"] = {"labels": lab, "occ": np.zeros(grid.n, bool), "lo": grid.lo, "names": names}
        return res
    s_lo = np.min([m["verts"].min(axis=0) for m in meshes], axis=0)
    s_hi = np.max([m["verts"].max(axis=0) for m in meshes], axis=0)
    grid = Grid(gt, s_lo, s_hi)
    lab, names = gt_labels(gt, grid)
    S, stats = voxelise(meshes, grid)
    G = lab > 0
    n_g, n_s = int(np.count_nonzero(G)), int(np.count_nonzero(S))
    inter = int(np.count_nonzero(G & S))
    iou = inter / (n_g + n_s - inter)
    b_iou, b_dx, b_dy = best_shift(G, S, n_g, n_s)
    feats = feature_scores(lab, names, S)
    f_mean = float(np.mean([f["recall"] * f["precision"] for f in feats.values()]))
    core = np.zeros(grid.n, bool)
    core[grid.core] = True
    raw = 50 * iou + 50 * f_mean
    over = info["triangles"] > TRI_LIMIT
    total = raw * (0.5 if over else 1.0)
    detail.update({
        "iou": round(iou, 4),
        "iou_best_xy_shift": {"iou": round(b_iou, 4), "shift_mm": [b_dx * 10, b_dy * 10],
                              "note": "submission moved by this much (whole voxels, within +-50 mm) fits best"},
        "bbox_submission": {"min": [round(float(v), 4) for v in s_lo], "max": [round(float(v), 4) for v in s_hi],
                            "size": [round(float(v), 4) for v in s_hi - s_lo]},
        "bbox_size_error_mm": [round(float(v) * 1000, 1) for v in (s_hi - s_lo) - (gt_hi - gt_lo)],
        "bbox_centre_error_mm": [round(float(v) * 1000, 1) for v in (s_hi + s_lo) / 2 - (gt_hi + gt_lo) / 2],
        "voxels": {"gt": n_g, "submission": n_s, "common": inter, "missing": n_g - inter, "surplus": n_s - inter,
                   "submission_outside_core_grid": int(np.count_nonzero(S & ~core))},
        "features": feats, "feature_mean": round(f_mean, 4),
        "over_triangle_limit": over, "raw_total_before_triangle_rule": round(raw, 2),
        "voxeliser": stats, "seconds": round(time.time() - t0, 1),
    })
    res = {"stage": "d5", "total": round(total, 2),
           "parts": {"iou": round(50 * iou * (0.5 if over else 1.0), 2),
                     "features": round(50 * f_mean * (0.5 if over else 1.0), 2)},
           "detail": detail}
    if keep_arrays:
        res["_arrays"] = {"labels": lab, "occ": S, "lo": grid.lo, "names": names}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True, help="target.json (secret)")
    ap.add_argument("--run", help="run directory: open RUN/d5.blend first (if no blend was given on the command line)")
    ap.add_argument("--out")
    ap.add_argument("--save-occ", help="write the occupancy arrays (npz) for d5_compare.py")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = ap.parse_args(argv)
    gt = json.loads(pathlib.Path(a.gt).read_text())
    if a.run:
        import bpy
        blend = pathlib.Path(a.run) / "d5.blend"
        if not blend.exists():
            res = {"stage": "d5", "total": 0.0, "error": f"{blend} missing"}
            print(json.dumps(res))
            if a.out:
                pathlib.Path(a.out).write_text(json.dumps(res, indent=1))
            return
        bpy.ops.wm.open_mainfile(filepath=str(blend))
    res = score(gt, keep_arrays=bool(a.save_occ))
    arr = res.pop("_arrays", None)
    if a.save_occ and arr is not None:
        np.savez_compressed(a.save_occ, labels=arr["labels"], occ=arr["occ"], lo=arr["lo"], names=np.array(arr["names"]))
    print(json.dumps(res, indent=1))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
