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
    pts = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    objs.append({
        "name": o.name,
        "min": [min(p[i] for p in pts) for i in range(3)],
        "max": [max(p[i] for p in pts) for i in range(3)],
        "props": {k: (v if isinstance(v, (int, float, str, bool)) else str(v)) for k, v in o.items() if not k.startswith("_")},
        "verts": len(o.data.vertices),
    })
hits = []
for ox, oy, oz, dx, dy, dz, dist in q.get("rays", []):
    ok, loc, _n, _i, obj, _m = bpy.context.scene.ray_cast(dg, mathutils.Vector((ox, oy, oz)),
                                                         mathutils.Vector((dx, dy, dz)).normalized(), distance=dist)
    hits.append(obj.name if ok else None)
json.dump({"objects": objs, "hits": hits}, open(out_path, "w"))
