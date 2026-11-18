"""Objective defect audit of an S2 submission (run inside Blender on s2.blend).

    blender -b s2.blend --python audit_s2.py -- OUT.json

Per rack (RackA closed cabinet, RackB open frame): floating parts, coincident duplicates, equipment that overlaps,
equipment off the 1U grid, open fraction of each face (ray grid: does a ray pass the outer 30 mm?), LED / blank counts.
Every finding carries a world position so it can be marked on the review renders.
"""
import json
import re
import sys

import bpy
import mathutils

out_path = sys.argv[sys.argv.index("--") + 1]
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
U = 0.04445


def under(o, root):
    while o:
        if o.name == root:
            return True
        o = o.parent
    return False


def aabb(o):
    pts = [o.matrix_world @ mathutils.Vector(c) for c in o.evaluated_get(dg).bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def touch(a, b, tol=0.004):
    return all(a[0][i] - tol <= b[1][i] and b[0][i] - tol <= a[1][i] for i in range(3))


def ctr(bb):
    return [round((bb[0][i] + bb[1][i]) / 2, 3) for i in range(3)]


res = {}
for root in ("RackA", "RackB"):
    objs = [o for o in sc.objects if o.type == "MESH" and under(o, root)]
    if not objs:
        res[root] = {"error": "no meshes"}
        continue
    bbs = {o.name: aabb(o) for o in objs}
    lo = [min(b[0][i] for b in bbs.values()) for i in range(3)]
    hi = [max(b[1][i] for b in bbs.values()) for i in range(3)]
    size = [hi[i] - lo[i] for i in range(3)]
    names = list(bbs)
    f = {"bbox": {"lo": [round(v, 3) for v in lo], "hi": [round(v, 3) for v in hi]}, "parts": len(objs)}
    # floating parts
    floating = []
    for n in names:
        if not any(m != n and touch(bbs[n], bbs[m]) for m in names):
            floating.append({"name": n, "pos": ctr(bbs[n]), "size": [round(bbs[n][1][i] - bbs[n][0][i], 3) for i in range(3)]})
    f["floating_parts"] = floating
    # coincident duplicates
    dup, seen = [], {}
    for n in names:
        key = tuple(round(v, 3) for v in bbs[n][0] + bbs[n][1])
        if key in seen:
            dup.append({"a": seen[key], "b": n, "pos": ctr(bbs[n])})
        else:
            seen[key] = n
    f["coincident_duplicates"] = dup
    # equipment stack: wide flat boxes inside the frame
    eq = []
    for n in names:
        b = bbs[n]
        w, d, h = (b[1][i] - b[0][i] for i in range(3))
        if w >= 0.38 and d >= 0.15 and 0.03 <= h <= 0.4 and not re.search("door|panel|top|base|plinth|roof|tray|frame|floor", n, re.I):
            eq.append((b[0][2], b[1][2], n))
    eq.sort()
    overlaps, offgrid = [], []
    for (z0, z1, n), (y0, y1, m) in zip(eq, eq[1:]):
        if y0 < z1 - 0.003 and touch(bbs[n], bbs[m], 0):
            overlaps.append({"a": n, "b": m, "overlap_mm": round((z1 - y0) * 1000, 1), "pos": ctr(bbs[m])})
    if eq:
        base = eq[0][0]
        for z0, z1, n in eq:
            k = (z0 - base) / U
            hu = (z1 - z0) / U
            if abs(k - round(k)) > 0.12:
                offgrid.append({"name": n, "bottom_U": round(k, 2), "pos": ctr(bbs[n])})
        f["equipment"] = {"count": len(eq), "heights_U": sorted({round((z1 - z0) / U, 1) for z0, z1, _ in eq}),
                          "span_U": round((eq[-1][1] - eq[0][0]) / U, 1), "overlaps": overlaps, "off_1U_grid": offgrid[:12],
                          "off_grid_count": len(offgrid)}
    # face openness by ray grid (fraction of rays that get past the outer 30 mm of the face)
    def openness(axis, sign):
        o_axes = [a for a in range(3) if a != axis]
        n_open = n_all = 0
        first_gap = None
        steps = 60
        for i in range(steps):
            for j in range(steps):
                p = [0, 0, 0]
                p[o_axes[0]] = lo[o_axes[0]] + size[o_axes[0]] * (0.08 + 0.84 * (i + 0.5) / steps)
                p[o_axes[1]] = lo[o_axes[1]] + size[o_axes[1]] * (0.08 + 0.84 * (j + 0.5) / steps)
                start = (lo[axis] - 0.5) if sign > 0 else (hi[axis] + 0.5)
                p[axis] = start
                d = [0, 0, 0]
                d[axis] = sign
                ok, loc, _n, _i, ob, _m = sc.ray_cast(dg, mathutils.Vector(p), mathutils.Vector(d), distance=1.0 + size[axis])
                n_all += 1
                depth = abs(loc[axis] - start) - 0.5 if ok else 9
                if not ok or not under(ob, root) or depth > 0.03:
                    n_open += 1
                    if first_gap is None:
                        q = list(p)
                        q[axis] = lo[axis] if sign > 0 else hi[axis]
                        first_gap = [round(v, 3) for v in q]
        return round(n_open / n_all, 3), first_gap
    f["open_fraction"] = {}
    for nm, (ax, sg) in {"front": (1, 1), "rear": (1, -1), "left": (0, 1), "right": (0, -1), "top": (2, -1)}.items():
        frac, gap = openness(ax, sg)
        f["open_fraction"][nm] = {"open": frac, "sample_gap_pos": gap}
    f["name_counts"] = {k: sum(1 for n in names if k in n.lower()) for k in ("led", "blank", "foot", "feet", "caster", "rail", "hole", "perf")}
    f["emissive_parts"] = sum(1 for o in objs if any(m and m.use_nodes and any(
        nd.type == "BSDF_PRINCIPLED" and nd.inputs["Emission Strength"].default_value > 0 for nd in m.node_tree.nodes) for m in o.data.materials))
    f["floor_contact"] = {"lowest_z": round(lo[2], 4), "parts_touching_floor": sum(1 for b in bbs.values() if b[0][2] <= 0.002)}
    res[root] = f
json.dump(res, open(out_path, "w"), indent=1)
print("AUDIT_DONE")
