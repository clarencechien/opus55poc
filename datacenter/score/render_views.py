"""Render fixed review views of a submitted .blend (same Workbench look as bench previews).

    blender -b FILE.blend --python render_views.py -- OUT_DIR [--isolate ROOT] [views...]
default views: top iso.  Extra view `close`: perspective 3/4 view of the front at eye height.
With --isolate, only ROOT and its descendants are visible and file names get the ROOT prefix.
"""
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
from render_common import do_render, scene_bounds  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out = args.pop(0)
iso_root = None
if "--isolate" in args:
    i = args.index("--isolate")
    iso_root = args[i + 1]
    del args[i:i + 2]
views = args or ["top", "iso"]
os.makedirs(out, exist_ok=True)


def under(o, root):
    while o:
        if o.name == root:
            return True
        o = o.parent
    return False


if iso_root:
    for o in bpy.context.scene.objects:
        hide = not under(o, iso_root)
        o.hide_render = hide
        o.hide_set(hide)
prefix = f"{iso_root}_" if iso_root else ""
for v in views:
    view = v
    if v == "close":
        lo, hi = scene_bounds()
        ctr = (lo + hi) / 2
        tgt = mathutils.Vector((ctr.x, lo.y, lo.z + (hi.z - lo.z) * 0.55))
        cam = tgt + mathutils.Vector((-1.2, -2.3, 0.25))
        view = f"cam:{cam.x:.3f},{cam.y:.3f},{cam.z:.3f}>{tgt.x:.3f},{tgt.y:.3f},{tgt.z:.3f}"
    print(do_render({"view": view, "res": "1024x768", "lens": 35 if v == "close" else 24}, path=os.path.join(out, f"review_{prefix}{v}.png")))
