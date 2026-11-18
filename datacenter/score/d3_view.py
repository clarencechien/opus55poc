"""Stage D3 review renders: draw the submitted routes into the start scene and render three Workbench views.

    blender -b start.blend --python d3_view.py -- routes.json score.json OUTDIR

Each route becomes a tube of 0.05 m radius, green if the scorer found it valid and red if not (score.json is the output
of d3_routes.py). Views: d3_top.png (plan, ceiling and beams hidden), d3_iso.png (cutaway without the ceiling and the two
near walls), d3_manifold.png (close view along the manifold wall).
"""
import json
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from render_common import do_render  # noqa: E402

routes_path, score_path, out = sys.argv[sys.argv.index("--") + 1:][:3]
os.makedirs(out, exist_ok=True)
try:
    routes = json.load(open(routes_path)).get("routes", [])
except Exception as e:  # nothing to draw
    print("cannot read routes:", e)
    routes = []
try:
    detail = json.load(open(score_path))["detail"]["routes"]
except Exception:
    detail = {}


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


GOOD, BAD = mat("d3_route_valid", (0.05, 0.75, 0.15)), mat("d3_route_invalid", (0.9, 0.08, 0.05))
seen = set()
for r in routes if isinstance(routes, list) else []:
    try:
        rid, pts = str(r["id"]), [[float(v) for v in p] for p in r["points"]]
        assert len(pts) >= 2 and all(len(p) == 3 for p in pts) and rid not in seen
    except Exception:
        continue
    seen.add(rid)
    cu = bpy.data.curves.new("Route_" + rid, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = 0.05, 3, True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for q, p in zip(sp.points, pts):
        q.co = (*p, 1.0)
    cu.materials.append(GOOD if detail.get(rid, {}).get("valid") else BAD)
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("Route_" + rid, cu))


def show_all_but(prefixes):
    for o in bpy.context.scene.objects:
        hide = o.name.startswith(tuple(prefixes))
        o.hide_render = hide
        o.hide_set(hide)


show_all_but(["Ceiling", "Beam_"])
print(do_render({"view": "top", "res": "1600x1200"}, path=os.path.join(out, "d3_top.png")))
show_all_but(["Ceiling", "Wall_S", "Wall_W"])
print(do_render({"view": "iso", "res": "1600x1200"}, path=os.path.join(out, "d3_iso.png")))

# close view along the manifold wall: try a few camera spots beside the manifold and keep the first one whose line of
# sight to the ports is not blocked by an obstacle box
show_all_but(["Ceiling"])
ports = sorted((o for o in bpy.context.scene.objects if o.name.startswith("Port_")), key=lambda o: o.name)
man = bpy.data.objects.get("Manifold")
if ports and man:
    boxes = []
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.name not in ("Manifold", "Ceiling"):
            c = [o.matrix_world @ mathutils.Vector(v) for v in o.bound_box]
            boxes.append(([min(v[i] for v in c) - 0.05 for i in range(3)], [max(v[i] for v in c) + 0.05 for i in range(3)]))

    def clear(p, q):
        for k in range(41):
            x = p + (q - p) * (k / 40)
            if any(all(lo[i] <= x[i] <= hi[i] for i in range(3)) for lo, hi in boxes):
                return False
        return True
    a, b = ports[0].location.copy(), ports[-1].location.copy()
    along = (b - a).normalized()
    inward = a - man.location
    inward.z = 0
    inward -= along * inward.dot(along)
    inward.normalize()
    tgt = (a + b) / 2
    tgt.z = 2.9
    best = None
    for inn in (1.5, 1.0, 0.7):
        for dist in (2.0, 2.5, 1.5, 3.0, 3.5, 4.5):
            for z in (2.95, 2.75, 3.25):
                for end, sgn in ((a, -1.0), (b, 1.0)):
                    cam = end + along * sgn * dist + inward * inn
                    cam.z = z
                    if best is None and clear(cam, tgt) and clear(cam, a) and clear(cam, b):
                        best = cam
    cam = best or (a - along * 3.0 + inward * 0.7 + mathutils.Vector((0, 0, 0.05)))
    view = f"cam:{cam.x:.3f},{cam.y:.3f},{cam.z:.3f}>{tgt.x:.3f},{tgt.y:.3f},{tgt.z:.3f}"
    print(do_render({"view": view, "res": "1600x1200", "lens": 18}, path=os.path.join(out, "d3_manifold.png")))
