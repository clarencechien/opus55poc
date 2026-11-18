"""Run inside Blender: dump object bounding boxes and answer ray queries.

    blender -b FILE.blend --python blender_probe.py -- QUERY.json OUT.json
QUERY.json: {"rays": [[ox, oy, oz, dx, dy, dz, max_dist], ...]}   (metres)
"""
import json
import sys

import bpy
import mathutils

q_path, out_path = sys.argv[sys.argv.index("--") + 1:][:2]
q = json.load(open(q_path))
dg = bpy.context.evaluated_depsgraph_get()
objs = []
for o in bpy.context.scene.objects:
    if o.type != "MESH" or o.name.startswith("__bench"):
        continue
    pts = [o.matrix_world @ mathutils.Vector(c) for c in o.evaluated_get(dg).bound_box]
    objs.append({
        "name": o.name, "type": "MESH",
        "min": [min(p[i] for p in pts) for i in range(3)],
        "max": [max(p[i] for p in pts) for i in range(3)],
        "props": {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in o.items() if not k.startswith("_")},
        "verts": len(o.data.vertices),
        "tris": sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).data.polygons),
        "parent": o.parent.name if o.parent else None,
        "materials": [m.name for m in o.data.materials if m],
    })
for o in bpy.context.scene.objects:  # non-mesh objects (empties as roots) for the parent chain
    if o.type != "MESH":
        objs.append({"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None, "min": None, "max": None,
                     "tris": 0, "verts": 0, "materials": [],
                     "props": {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in o.items() if not k.startswith("_")},
                     "instance": o.instance_collection.name if o.instance_type == "COLLECTION" and o.instance_collection else None})
for e in objs:  # world transform of every object
    ob = bpy.context.scene.objects.get(e["name"])
    if ob:
        mw = ob.matrix_world
        e["loc"] = list(mw.translation)
        f = mw.to_3x3() @ mathutils.Vector((0, -1, 0))  # template front direction
        e["front"] = [f.x, f.y, f.z]
hits = []
for ox, oy, oz, dx, dy, dz, dist in q.get("rays", []):
    ok, loc, _n, _i, obj, _m = bpy.context.scene.ray_cast(dg, mathutils.Vector((ox, oy, oz)),
                                                         mathutils.Vector((dx, dy, dz)).normalized(), distance=dist)
    hits.append(obj.name if ok else None)
json.dump({"objects": objs, "hits": hits}, open(out_path, "w"))
