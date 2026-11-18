"""Preview rendering shared by the bench server and the scoring scripts (runs inside Blender)."""
import math
import os
import time

import bpy
import mathutils


def scene_bounds():
    pts = []
    for o in bpy.context.scene.objects:
        if o.type in {"MESH", "CURVE", "FONT"} and o.visible_get():
            pts += [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    if not pts:
        return mathutils.Vector((-5, -5, 0)), mathutils.Vector((5, 5, 3))
    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def sync_viewport_colors():
    """Workbench shows material.diffuse_color; copy Principled base colour so node-built materials read right."""
    for m in bpy.data.materials:
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    c = n.inputs["Base Color"].default_value
                    m.diffuse_color = (c[0], c[1], c[2], 1.0)
                    break


def do_render(req, renders_dir=None, path=None):
    sc = bpy.context.scene
    view = req.get("view", "iso")
    w, h = (int(v) for v in req.get("res", "1024x768").split("x"))
    lo, hi = scene_bounds()
    ctr, size = (lo + hi) / 2, hi - lo
    cam_data = bpy.data.cameras.get("__bench_cam") or bpy.data.cameras.new("__bench_cam")
    cam = bpy.data.objects.get("__bench_cam") or bpy.data.objects.new("__bench_cam", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.hide_viewport = False
    cam_data.clip_start, cam_data.clip_end = 0.01, 1000
    aspect = w / h
    if view == "top":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(size.x, size.y * aspect) * 1.08 + 0.5
        cam.location = (ctr.x, ctr.y, hi.z + 20)
        cam.rotation_euler = (0, 0, 0)
    elif view in {"front", "back", "left", "right"}:
        cam_data.type = "ORTHO"
        horiz = size.x if view in {"front", "back"} else size.y
        cam_data.ortho_scale = max(horiz, size.z * aspect) * 1.08 + 0.5
        d = 50
        loc, rot = {
            "front": ((ctr.x, lo.y - d, ctr.z), (math.pi / 2, 0, 0)),
            "back": ((ctr.x, hi.y + d, ctr.z), (math.pi / 2, 0, math.pi)),
            "left": ((lo.x - d, ctr.y, ctr.z), (math.pi / 2, 0, -math.pi / 2)),
            "right": ((hi.x + d, ctr.y, ctr.z), (math.pi / 2, 0, math.pi / 2)),
        }[view]
        cam.location, cam.rotation_euler = loc, rot
    elif view.startswith("cam:"):
        a, b = view[4:].split(">")
        p = mathutils.Vector([float(v) for v in a.split(",")])
        t = mathutils.Vector([float(v) for v in b.split(",")])
        cam_data.type = "PERSP"
        cam_data.lens = float(req.get("lens", 24))
        cam.location = p
        cam.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
    else:  # iso
        cam_data.type = "PERSP"
        cam_data.lens = 35
        r = max(size.length, 1.0)
        p = ctr + mathutils.Vector((-0.55, -0.75, 0.6)).normalized() * r * 1.25
        cam.location = p
        cam.rotation_euler = (ctr - p).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_cavity, sh.show_object_outline = True, True
    sh.show_shadows = view not in {"top"}
    sync_viewport_colors()
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World")
    if path is None:
        idx = len([f for f in os.listdir(renders_dir) if f.endswith(".png")]) + 1
        safe = "".join(ch if ch.isalnum() else "_" for ch in view)[:40]
        path = os.path.join(renders_dir, f"{idx:03d}_{safe}.png")
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    cam.hide_viewport = True
    return {"ok": True, "path": path, "seconds": round(time.time() - t, 2),
            "bounds_m": {"min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi]}}
