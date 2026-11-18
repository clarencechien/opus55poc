"""Build the hidden D5 target: a coolant distribution unit (CDU) made of boxes and cylinders only.

    blender -b --factory-startup --python gen/d5_target.py -- --seed N --out DIR

Writes DIR/target.blend and DIR/target.json (both SECRET: they are the answer key).

Conventions: metres, +z up, the unit stands on z = 0, the xy bounding box of the whole unit is centred on the
origin, the front (door) faces -y, the control box is on the +x (right) side, the louvre on the -x (left) side.
Every dimension is a multiple of 10 mm: box faces lie on the 10 mm lattice, cylinder axes on the lattice with
radii that are multiples of 10 mm, so the 10 mm voxel scorer sees the target exactly.

The design itself (function `design`) is pure Python and can be imported without Blender.
"""
from __future__ import annotations

import json
import math
import pathlib
import random
import sys

SEGMENTS = 64  # cylinder mesh resolution in target.blend

COLORS = {  # a few distinct flat colours (group -> sRGB)
    "body": (0.74, 0.76, 0.79), "plinth": (0.36, 0.37, 0.40), "feet": (0.15, 0.15, 0.16),
    "door": (0.36, 0.52, 0.72), "display": (0.12, 0.16, 0.20), "handle": (0.95, 0.95, 0.97),
    "control_box": (0.92, 0.70, 0.12), "top_pipes": (0.80, 0.36, 0.14), "rear_manifold": (0.80, 0.36, 0.14),
    "louvre": (0.36, 0.37, 0.40), "lifting_eyes": (0.75, 0.12, 0.12), "gland_box": (0.25, 0.55, 0.30),
}
GROUP_ORDER = list(COLORS)


def design(seed: int) -> dict:
    """Return the target description. Internally everything is in integer centimetres."""
    R = random.Random(seed)
    parts: list[dict] = []

    def box(name, group, lo, hi):
        assert all(a < b for a, b in zip(lo, hi)), (name, lo, hi)
        parts.append({"name": name, "group": group, "type": "box", "lo": list(lo), "hi": list(hi)})

    # ---- body, plinth, feet (local frame: body spans x 0..W, y 0..D, front at y = 0)
    W, D = R.randrange(80, 101), R.randrange(110, 131)
    top = R.randrange(190, 211)                      # height of the cabinet top above the floor
    hf, rf = R.choice([3, 4, 5]), R.choice([3, 4])   # foot height / radius
    hp = R.randrange(8, 13)                          # plinth height
    px, pf, pr = R.randrange(3, 6), R.randrange(5, 9), R.randrange(1, 4)  # plinth inset: sides / front / rear
    zb = hf + hp
    box("Body", "body", (0, 0, zb), (W, D, top))
    box("Plinth", "plinth", (px, pf, hf), (W - px, D - pr, zb))
    fa = R.randrange(1, 4)
    for i, (fx, fy) in enumerate([(px + rf + fa, pf + rf + fa), (W - px - rf - fa, pf + rf + fa),
                                  (px + rf + fa, D - pr - rf - fa), (W - px - rf - fa, D - pr - rf - fa)]):
        parts.append({"name": f"Foot_{i + 1}", "group": "feet", "type": "cylinder", "c2": [2 * fx, 2 * fy, hf],
                      "radius": rf, "length": hf, "axis": "z"})

    # ---- door (proud 20 mm, covers the left part of the front), display, handle
    dx0 = R.randrange(3, 7)
    dx1 = dx0 + round(W * R.uniform(0.60, 0.70))
    dz0, dz1 = zb + R.randrange(4, 10), top - R.randrange(8, 16)
    box("Door", "door", (dx0, -2, dz0), (dx1, 0, dz1))
    hx = dx1 - R.randrange(6, 10)                    # handle bar centre x (near the door's right edge)
    hg = R.choice([3, 4, 5])                         # clear gap door face -> bar
    hl = R.randrange(40, 71, 2)                      # bar length
    hz = R.randrange(95, 121)                        # bar centre z
    hy = -2 - hg - 2
    parts.append({"name": "Handle_Bar", "group": "handle", "type": "cylinder", "c2": [2 * hx, 2 * hy, 2 * hz],
                  "radius": 2, "length": hl, "axis": "z"})
    box("Handle_Standoff_1", "handle", (hx - 2, hy, hz - hl // 2 + 4), (hx + 2, -2, hz - hl // 2 + 8))
    box("Handle_Standoff_2", "handle", (hx - 2, hy, hz + hl // 2 - 8), (hx + 2, -2, hz + hl // 2 - 4))
    dd, dw_, dh_ = R.choice([2, 3]), R.randrange(20, 31), R.randrange(12, 19)
    sx0 = R.randrange(dx0 + 4, max(dx0 + 5, hx - 8 - dw_))
    sz1 = dz1 - R.randrange(14, 30)
    box("Display", "display", (sx0, -2 - dd, sz1 - dh_), (sx0 + dw_, -2, sz1))

    # ---- control box on the right side, louvre block on the left side
    pc, cl, ch = R.randrange(12, 19), R.randrange(30, 51), R.randrange(40, 61)
    cy0 = R.randrange(8, D - cl - 30)
    cz0 = R.randrange(80, top - ch - 15)
    lp, sh = R.choice([3, 4]), R.choice([3, 4])
    if (W + pc + lp) % 2:                            # keep the overall x extent even (bbox centre on the lattice)
        pc += 1
    box("ControlBox", "control_box", (W, cy0, cz0), (W + pc, cy0 + cl, cz0 + ch))
    pitch = sh + R.choice([4, 5, 6])
    ll = R.randrange(40, 71)
    ly0 = R.randrange(25, D - ll - 8)
    lz0 = R.randrange(100, top - 4 * pitch - sh - 8)
    for i in range(5):
        box(f"Louvre_Slat_{i + 1}", "louvre", (-lp, ly0, lz0 + i * pitch), (0, ly0 + ll, lz0 + i * pitch + sh))

    # ---- top of the cabinet: gland box (rear), 2 lifting eyes, 4 pipe stubs at irregular positions
    used: list[tuple] = []                           # rectangles (x0, y0, x1, y1) already taken

    def free(r, margin):
        return all(r[2] + margin <= u[0] or u[2] + margin <= r[0] or r[3] + margin <= u[1] or u[3] + margin <= r[1]
                   for u in used)

    gw, gd, gh = R.randrange(26, 41), R.randrange(12, 19), R.randrange(8, 13)
    gx0 = R.randrange(6, W - gw - 20)
    gy1 = D - R.randrange(3, 7)
    box("GlandBox", "gland_box", (gx0, gy1 - gd, top), (gx0 + gw, gy1, top + gh))
    used.append((gx0, gy1 - gd, gx0 + gw, gy1))
    re = R.choice([4, 5])
    zones = [((re + 5, W // 2 - re - 4), (6, 20)), ((W // 2 + re + 4, W - re - 5), (D // 2 + 5, D - 8))]
    for i, (zx, zy) in enumerate(zones):             # eye 1 front-left, eye 2 rear-right
        for _ in range(1000):
            ex, ey = R.randrange(zx[0], zx[1] + 1), R.randrange(zy[0], zy[1] + 1)
            r = (ex - re, ey - 1, ex + re, ey + 1)
            if free(r, 3):
                break
        else:
            raise RuntimeError("no room for lifting eye")
        used.append(r)
        box(f"LiftingEye_{i + 1}_Lug", "lifting_eyes", (ex - re, ey - 1, top), (ex + re, ey + 1, top + re))
        parts.append({"name": f"LiftingEye_{i + 1}_Disc", "group": "lifting_eyes", "type": "cylinder",
                      "c2": [2 * ex, 2 * ey, 2 * (top + re)], "radius": re, "length": 2, "axis": "y"})
    r_small, r_big = R.choice([3, 4]), R.choice([5, 6])
    h_short, h_tall = R.randrange(10, 17), R.randrange(22, 33)
    combos = [(r_big, h_tall), (r_big, h_short), (r_small, h_tall), (r_small, h_short)]
    R.shuffle(combos)
    for i, (r_, h_) in enumerate(combos):
        for _ in range(5000):
            cx, cy = R.randrange(r_ + 5, W - r_ - 4), R.randrange(r_ + 5, D - r_ - 4)
            r = (cx - r_, cy - r_, cx + r_, cy + r_)
            if free(r, 5):
                break
        else:
            raise RuntimeError("no room for pipe stub")
        used.append(r)
        parts.append({"name": f"TopPipe_{i + 1}", "group": "top_pipes", "type": "cylinder",
                      "c2": [2 * cx, 2 * cy, 2 * top + h_], "radius": r_, "length": h_, "axis": "z"})

    # ---- rear manifold: horizontal pipe low on the rear, 2 brackets, 2 valves (short coaxial cylinders)
    rm, sm = R.choice([4, 5]), R.randrange(4, 8)
    rv, lv = rm + R.choice([2, 3]), R.choice([6, 8, 10])
    front_y = hy - 2                                 # most forward point: the handle bar
    if (D + sm + rm + rv - front_y) % 2:             # keep the overall y extent even
        sm += 1
    my, mz = D + sm + rm, R.randrange(30, 56)
    xa, xb = R.randrange(4, 13), W - R.randrange(8, 21)
    if (xb - xa) % 2:
        xb -= 1
    parts.append({"name": "Manifold_Pipe", "group": "rear_manifold", "type": "cylinder",
                  "c2": [xa + xb, 2 * my, 2 * mz], "radius": rm, "length": xb - xa, "axis": "x"})
    box("Manifold_Bracket_1", "rear_manifold", (xa + 3, D, mz - 2), (xa + 7, my, mz + 2))
    box("Manifold_Bracket_2", "rear_manifold", (xb - 7, D, mz - 2), (xb - 3, my, mz + 2))
    v1 = R.randrange(xa + 8, xa + 16)
    v2 = R.randrange(v1 + lv + 10, xb - 5)
    for i, vx in enumerate((v1, v2)):
        parts.append({"name": f"Manifold_Valve_{i + 1}", "group": "rear_manifold", "type": "cylinder",
                      "c2": [2 * vx, 2 * my, 2 * mz], "radius": rv, "length": lv, "axis": "x"})

    # ---- centre the xy bounding box on the origin, convert to metres
    def extent(p):
        if p["type"] == "box":
            return p["lo"], p["hi"]
        c = [v / 2 for v in p["c2"]]
        k = "xyz".index(p["axis"])
        half = [p["radius"]] * 3
        half[k] = p["length"] / 2
        return [c[i] - half[i] for i in range(3)], [c[i] + half[i] for i in range(3)]

    lo = [min(extent(p)[0][i] for p in parts) for i in range(3)]
    hi = [max(extent(p)[1][i] for p in parts) for i in range(3)]
    assert lo[2] == 0
    sx, sy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    assert sx == int(sx) and sy == int(sy), (sx, sy)
    cm = lambda v: round(v / 100.0, 4)  # noqa: E731
    out_parts = []
    for p in parts:
        a, b = extent(p)
        ctr = [cm((a[0] + b[0]) / 2 - sx), cm((a[1] + b[1]) / 2 - sy), cm((a[2] + b[2]) / 2)]
        e = {"name": p["name"], "group": p["group"], "type": p["type"], "position": ctr,
             "color": list(COLORS[p["group"]])}
        if p["type"] == "box":
            e["size"] = [cm(b[i] - a[i]) for i in range(3)]
            e["axis"] = None
        else:
            e["diameter"], e["length"], e["axis"] = cm(2 * p["radius"]), cm(p["length"]), p["axis"]
            e["size"] = [e["diameter"], e["length"]]
        out_parts.append(e)
    body = next(p for p in out_parts if p["name"] == "Body")
    groups = {g: [p["name"] for p in out_parts if p["group"] == g] for g in GROUP_ORDER}
    return {
        "seed": seed, "units": "m",
        "conventions": "z up, stands on z=0, xy bounding box centred on origin, front faces -y, right side = +x",
        "bbox": {"min": [cm(lo[0] - sx), cm(lo[1] - sy), 0.0], "max": [cm(hi[0] - sx), cm(hi[1] - sy), cm(hi[2])],
                 "size": [cm(hi[i] - lo[i]) for i in range(3)]},
        "body": {"size": body["size"], "position": body["position"], "top_z": cm(top)},
        "groups": groups, "parts": out_parts,
    }


def build(spec: dict, out_dir: pathlib.Path) -> None:
    import bmesh
    import bpy
    import mathutils

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = bpy.data.objects.new("Target", None)
    root.empty_display_size = 0.2
    sc.collection.objects.link(root)
    mats = {}
    for g, c in COLORS.items():
        m = bpy.data.materials.new("D5_" + g)
        lin = tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)  # sRGB -> linear
        m.diffuse_color = (*lin, 1.0)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
        mats[g] = m
    rot = {"z": mathutils.Matrix.Identity(4), "x": mathutils.Matrix.Rotation(math.pi / 2, 4, "Y"),
           "y": mathutils.Matrix.Rotation(math.pi / 2, 4, "X")}
    for p in spec["parts"]:
        bm = bmesh.new()
        if p["type"] == "box":
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=p["size"], verts=bm.verts)
        else:
            r = p["diameter"] / 2
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=SEGMENTS, radius1=r, radius2=r,
                                  depth=p["length"], matrix=rot[p["axis"]])
        me = bpy.data.meshes.new(p["name"])
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mats[p["group"]])
        ob = bpy.data.objects.new(p["name"], me)
        ob.location = p["position"]
        ob.parent = root
        ob["group"] = p["group"]
        sc.collection.objects.link(ob)
    bpy.context.view_layer.update()
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / "target.blend"))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    spec = design(a.seed)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "target.json").write_text(json.dumps(spec, indent=1))
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("no bpy: wrote target.json only")
        return
    build(spec, out)
    print(json.dumps({"seed": a.seed, "bbox": spec["bbox"], "parts": len(spec["parts"]),
                      "groups": {g: len(v) for g, v in spec["groups"].items()}}))


if __name__ == "__main__":
    main()
