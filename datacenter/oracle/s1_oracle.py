#!/usr/bin/env python3
"""Reference S1 solution from the ground truth (validates the task and the scorer; also the S3 start scene).

    python s1_oracle.py GT/layout.json RUN_DIR    -> RUN_DIR/layout_pred.json, RUN_DIR/oracle_s1.py (run with bench exec)
"""
import json
import pathlib
import sys

SHELL = r'''
import bpy, json
lay = json.load(open(LAYOUT))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
mm = 0.001
room = lay["room"]
t = room["wall_thickness"] * mm
H = (room["raised_floor_height"] + room["clear_height"]) * mm
xs = [p[0] * mm for p in room["polygon"]]; ys = [p[1] * mm for p in room["polygon"]]
x0, x1, y0, y1 = min(xs) - t / 2, max(xs) + t / 2, min(ys) - t / 2, max(ys) + t / 2  # wall centrelines

def box(name, cx, cy, sx, sy, z0, z1, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, (z0 + z1) / 2))
    o = bpy.context.object; o.name = name; o.scale = (sx, sy, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.get(name.split("_")[0]) or bpy.data.materials.new(name.split("_")[0])
    m.diffuse_color = color; o.data.materials.append(m)
    return o

grey = (0.75, 0.75, 0.72, 1)
P = [(x * mm, y * mm) for x, y in room["polygon"]]
n = len(P)
area2 = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))
sgn = 1 if area2 > 0 else -1

def normal(a, b):  # outward unit normal of an axis-aligned edge
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = (dx * dx + dy * dy) ** 0.5
    return (sgn * dy / L, -sgn * dx / L)

C = []  # wall centreline polygon: inner polygon pushed out by t/2 (mitred corners)
for i in range(n):
    n1, n2 = normal(P[i - 1], P[i]), normal(P[i], P[(i + 1) % n])
    C.append((P[i][0] + (n1[0] + n2[0]) * t / 2, P[i][1] + (n1[1] + n2[1]) * t / 2))
zl = room["raised_floor_height"] * mm + 2.1
for i in range(n):
    a, b = C[i], C[(i + 1) % n]
    horiz = abs(a[1] - b[1]) < 1e-6
    lo, hi = (min(a[0], b[0]), max(a[0], b[0])) if horiz else (min(a[1], b[1]), max(a[1], b[1]))
    lo, hi = lo - t / 2, hi + t / 2
    c = a[1] if horiz else a[0]
    cuts = []
    for d in lay["doors"]:
        dx, dy = d["center"][0] * mm, d["center"][1] * mm
        if horiz and abs(dy - c) < 0.01 and lo < dx < hi:
            cuts.append((dx - d["width"] * mm / 2, dx + d["width"] * mm / 2))
        if not horiz and abs(dx - c) < 0.01 and lo < dy < hi:
            cuts.append((dy - d["width"] * mm / 2, dy + d["width"] * mm / 2))
    cuts.sort()
    segs, cur = [], lo
    for ca, cb in cuts:
        segs.append((cur, ca)); cur = cb
    segs.append((cur, hi))
    for j, (sa, sb) in enumerate(segs):
        if sb - sa > 1e-6:
            if horiz:
                box(f"Wall_{i}_{j}", (sa + sb) / 2, c, sb - sa, t, 0, H, grey)
            else:
                box(f"Wall_{i}_{j}", c, (sa + sb) / 2, t, sb - sa, 0, H, grey)
    for k, (ca, cb) in enumerate(cuts):
        if horiz:
            box(f"Wall_{i}_lintel{k}", (ca + cb) / 2, c, cb - ca, t, zl, H, grey)
        else:
            box(f"Wall_{i}_lintel{k}", c, (ca + cb) / 2, t, cb - ca, zl, H, grey)
for col in lay["columns"]:
    box("Column_" + col["id"].replace("/", "_"), col["center"][0] * mm, col["center"][1] * mm,
        col["size"][0] * mm, col["size"][1] * mm, 0, H, (0.35, 0.35, 0.38, 1))
import bmesh
me = bpy.data.meshes.new("RaisedFloor")
bm = bmesh.new()
vs = [bm.verts.new((x, y, 0)) for x, y in P]
f = bm.faces.new(vs if sgn > 0 else list(reversed(vs)))
r = bmesh.ops.extrude_face_region(bm, geom=[f])
for v in [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]:
    v.co.z = room["raised_floor_height"] * mm
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me)
rf = bpy.data.objects.new("RaisedFloor", me)
bpy.context.scene.collection.objects.link(rf)
m = bpy.data.materials.new("RaisedFloor"); m.diffuse_color = (0.85, 0.86, 0.88, 1); me.materials.append(m)
print("shell objects:", len(bpy.data.objects))
'''


def main():
    gt, run = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
    lay = json.loads(gt.read_text())
    (run / "layout_pred.json").write_text(json.dumps(lay, indent=1))
    (run / "oracle_s1.py").write_text(f"LAYOUT = {str(run / 'layout_pred.json')!r}\n" + SHELL)


if __name__ == "__main__":
    main()
