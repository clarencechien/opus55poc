"""Task D3: build the participants' start scene from scene.json.

    blender -b --factory-startup --python d3_blend.py -- scene.json start.blend

Every obstacle box (and the manifold) becomes one box mesh object named as in scene.json, with its origin at the box
centre and its dimensions equal to the box size, so `bench inspect` lists the boxes exactly (loc = centre, dims = size).
The terminals are empties Port_P1..P6 and Target_P1..P6. Nothing else is in the scene.
"""
import json
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
scene = json.load(open(args[0]))
out = args[1]

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

COLOURS = {  # group prefix -> viewport colour
    "Wall": (0.62, 0.64, 0.66), "Column": (0.45, 0.46, 0.47), "RaisedFloor": (0.50, 0.52, 0.56), "Ceiling": (0.90, 0.90, 0.90),
    "Rack": (0.08, 0.08, 0.10), "CRAH": (0.55, 0.75, 0.60), "Containment": (0.45, 0.70, 0.95), "CableTray": (0.95, 0.60, 0.10),
    "Beam": (0.55, 0.30, 0.20), "Duct": (0.70, 0.85, 0.90), "Manifold": (0.75, 0.15, 0.75),
}
MATS = {}


def mat(group):
    if group not in MATS:
        m = bpy.data.materials.new("d3_" + group)
        m.diffuse_color = (*COLOURS[group], 1.0)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*COLOURS[group], 1.0)
        MATS[group] = m
    return MATS[group]


FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
coll = bpy.context.scene.collection


def add_box(b):
    lo, hi = b["min"], b["max"]
    ctr = [(a + c) / 2 for a, c in zip(lo, hi)]
    half = [(c - a) / 2 for a, c in zip(lo, hi)]
    verts = [((-1) ** (1 - i) * half[0], (-1) ** (1 - j) * half[1], (-1) ** (1 - k) * half[2])
             for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    me = bpy.data.meshes.new(b["name"])
    me.from_pydata(verts, [], FACES)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    o = bpy.data.objects.new(b["name"], me)
    o.location = ctr
    group = b["name"].split("_")[0]
    me.materials.append(mat(group))
    o.color = (*COLOURS[group], 1.0)
    coll.objects.link(o)
    return o


for b in scene["obstacles"]:
    add_box(b)
add_box(scene["manifold"])
for kind, items in (("Port", scene["manifold"]["ports"]), ("Target", scene["targets"])):
    for it in items:
        e = bpy.data.objects.new(f"{kind}_{it['id']}", None)
        e.empty_display_type = "SPHERE" if kind == "Port" else "PLAIN_AXES"
        e.empty_display_size = 0.08
        e.location = it["point"]
        coll.objects.link(e)
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=out)
print("objects", len(bpy.data.objects), "->", out)
