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
walls = {"S": (x0 - t / 2, x1 + t / 2, y0), "N": (x0 - t / 2, x1 + t / 2, y1),
         "W": (y0 - t / 2, y1 + t / 2, x0), "E": (y0 - t / 2, y1 + t / 2, x1)}
for side, (a, b, c) in walls.items():
    cuts = sorted((d["center"][1 if side in "EW" else 0] * mm - d["width"] * mm / 2,
                   d["center"][1 if side in "EW" else 0] * mm + d["width"] * mm / 2) for d in lay["doors"] if d["wall"] == side)
    segs, cur = [], a
    for ca, cb in cuts:
        segs.append((cur, ca)); cur = cb
    segs.append((cur, b))
    for i, (sa, sb) in enumerate(segs):
        if sb - sa < 1e-6:
            continue
        if side in "NS":
            box(f"Wall_{side}{i}", (sa + sb) / 2, c, sb - sa, t, 0, H, grey)
        else:
            box(f"Wall_{side}{i}", c, (sa + sb) / 2, t, sb - sa, 0, H, grey)
    for ca, cb in cuts:  # lintel above the door (2.1 m above raised floor)
        zl = room["raised_floor_height"] * mm + 2.1
        if side in "NS":
            box(f"Wall_{side}_lintel", (ca + cb) / 2, c, cb - ca, t, zl, H, grey)
        else:
            box(f"Wall_{side}_lintel", c, (ca + cb) / 2, t, cb - ca, zl, H, grey)
for col in lay["columns"]:
    box("Column_" + col["id"].replace("/", "_"), col["center"][0] * mm, col["center"][1] * mm,
        col["size"][0] * mm, col["size"][1] * mm, 0, H, (0.35, 0.35, 0.38, 1))
ix0, ix1, iy0, iy1 = min(xs), max(xs), min(ys), max(ys)
box("RaisedFloor", (ix0 + ix1) / 2, (iy0 + iy1) / 2, ix1 - ix0, iy1 - iy0, 0, room["raised_floor_height"] * mm, (0.85, 0.86, 0.88, 1))
print("shell objects:", len(bpy.data.objects))
'''


def main():
    gt, run = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
    lay = json.loads(gt.read_text())
    (run / "layout_pred.json").write_text(json.dumps(lay, indent=1))
    (run / "oracle_s1.py").write_text(f"LAYOUT = {str(run / 'layout_pred.json')!r}\n" + SHELL)


if __name__ == "__main__":
    main()
