"""Reference S3 solution (bench exec, after writing LAYOUT path on the first line)."""
import json
import math

import bpy

lay = json.load(open(LAYOUT))  # noqa: F821  (prepended by the runner)
mm = 0.001
ROT = {"S": 0.0, "N": math.pi, "E": math.pi / 2, "W": -math.pi / 2}  # template front is -y
tmpl = bpy.data.objects["RackA"]
coll = bpy.context.scene.collection


def dup_tree(src, parent):
    o = src.copy()  # linked mesh data
    coll.objects.link(o)
    o.parent = parent
    o.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    for c in src.children:
        dup_tree(c, o)
    return o


for r in lay["racks"]:
    src = bpy.data.objects["RackG"] if r["size"][0] == 800 and "RackG" in bpy.data.objects else tmpl
    root = dup_tree(src, None)
    root.name = f"Rack_{r['id']}"
    root["rackId"] = r["id"]
    root.location = (r["center"][0] * mm, r["center"][1] * mm, 0.6)
    root.rotation_euler = (0, 0, ROT[r["facing"]])


def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    return o


for k, a in enumerate([a for a in lay["aisles"] if a["type"] == "cold"]):
    x0, y0, x1, y1 = [v * mm for v in a["rect"]]
    box(f"Containment_Roof_{k}", x0, x1, y0, y1, 2.58, 2.6)
    if (x1 - x0) >= (y1 - y0):  # aisle runs east-west: doors at its west and east ends
        box(f"Containment_DoorW_{k}", x0 - 0.03, x0, y0, y1, 0.6, 2.58)
        box(f"Containment_DoorE_{k}", x1, x1 + 0.03, y0, y1, 0.6, 2.58)
    else:  # aisle runs north-south
        box(f"Containment_DoorS_{k}", x0, x1, y0 - 0.03, y0, 0.6, 2.58)
        box(f"Containment_DoorN_{k}", x0, x1, y1, y1 + 0.03, 0.6, 2.58)
    i0, i1 = math.ceil(round(x0 / 0.6, 6)), math.floor(round(x1 / 0.6, 6))
    j0, j1 = math.ceil(round(y0 / 0.6, 6)), math.floor(round(y1 / 0.6, 6))
    for i in range(i0, i1):
        for j in range(j0, j1):
            box(f"PerfTile_{k}_{i}_{j}", i * 0.6 + 0.002, (i + 1) * 0.6 - 0.002, j * 0.6 + 0.002, (j + 1) * 0.6 - 0.002, 0.57, 0.6)
rows = {}
for r in lay["racks"]:
    rows.setdefault(r["row"], []).append(r)
for row, rs in rows.items():
    ax = 0 if rs[0]["facing"] in "NS" else 1
    a0 = min(r["center"][ax] - r["size"][0] / 2 for r in rs) * mm
    a1 = max(r["center"][ax] + r["size"][0] / 2 for r in rs) * mm
    c = sum(r["center"][1 - ax] for r in rs) / len(rs) * mm
    if ax == 0:
        box(f"CableTray_{row}", a0, a1, c - 0.15, c + 0.15, 2.9, 2.98)
    else:
        box(f"CableTray_{row}", c - 0.15, c + 0.15, a0, a1, 2.9, 2.98)
print("racks placed:", len(lay["racks"]))
