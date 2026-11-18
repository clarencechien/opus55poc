"""Cycles review renders for an S2 submission (lit, with materials), plus a door-less view of the interior.

    blender -b s2.blend --python render_cycles_s2.py -- OUT_DIR [--samples 32]

For each of RackA and RackB: front, front_open (objects whose name contains 'Door' hidden, with their children),
back, close (3/4 front at eye height) and side. Also writes OUT_DIR/structure.json: per rack, object counts by
name keyword and the heights (in U) of server-like parts, for the reviewers.
"""
import json
import math
import os
import re
import sys

import bpy
import mathutils

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0]
samples = int(args[args.index("--samples") + 1]) if "--samples" in args else 32
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()


def under(o, root):
    while o:
        if o.name == root:
            return True
        o = o.parent
    return False


def bounds(objs):
    pts = []
    for o in objs:
        if o.type == "MESH":
            pts += [o.matrix_world @ mathutils.Vector(c) for c in o.evaluated_get(dg).bound_box]
    lo = mathutils.Vector([min(p[i] for p in pts) for i in range(3)])
    hi = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


# structure stats (for the reviewers)
U = 0.04445
KEYS = ["server", "blank", "led", "rail", "foot", "caster", "door", "panel", "side", "top", "cable", "patch", "post",
        "switch", "pdu", "manager", "tray", "perf", "hole", "handle", "lock"]
stats = {}
for root in ("RackA", "RackB"):
    objs = [o for o in sc.objects if under(o, root)]
    counts = {k: sum(1 for o in objs if k in o.name.lower()) for k in KEYS}
    heights = {}
    for o in objs:
        n = o.name.lower()
        if o.type == "MESH" and re.search("server|srv|chassis|switch|unit|blank", n) and not re.search("led|bay|drive|handle|ear|vent|light", n):
            lo, hi = bounds([o])
            u = round((hi.z - lo.z) / U)
            kind = "blank" if "blank" in n else "equipment"
            heights.setdefault(kind, {}).setdefault(f"{u}U", 0)
            heights[kind][f"{u}U"] += 1
    tris = sum(sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).data.polygons) for o in objs if o.type == "MESH")
    stats[root] = {"objects": len(objs), "mesh_objects": sum(o.type == "MESH" for o in objs), "triangles": tris,
                   "name_keyword_counts": {k: v for k, v in counts.items() if v}, "part_heights": heights,
                   "materials": sorted({m.name for o in objs if o.type == "MESH" for m in o.data.materials if m})[:40]}
json.dump(stats, open(os.path.join(out, "structure.json"), "w"), indent=1)

# studio: light floor, three area lights, Cycles
sc.render.engine = "CYCLES"
sc.cycles.device, sc.cycles.samples, sc.cycles.use_denoising = "CPU", samples, True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 900, 1000, 100
sc.render.image_settings.file_format, sc.render.image_settings.quality = "JPEG", 88
sc.view_settings.view_transform = "AgX"
sc.world = sc.world or bpy.data.worlds.new("World")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.001))
floor = bpy.context.object
fm = bpy.data.materials.new("__review_floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.72, 0.73, 0.75, 1)
floor.data.materials.append(fm)
lights = []
for name, loc, energy in (("key", (-2.5, -3.5, 3.5), 900), ("fill", (3.0, -2.5, 2.0), 350), ("rim", (0.5, 3.5, 3.0), 500)):
    ld = bpy.data.lights.new(f"__{name}", "AREA")
    ld.energy, ld.size = energy, 2.0
    lo_ = bpy.data.objects.new(f"__{name}", ld)
    sc.collection.objects.link(lo_)
    lights.append((lo_, mathutils.Vector(loc)))
cd = bpy.data.cameras.new("__cyc_cam")
cam = bpy.data.objects.new("__cyc_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam

roots = [o for o in sc.objects if o.name in ("RackA", "RackB")]
for root in ("RackA", "RackB"):
    objs = [o for o in sc.objects if under(o, root)]
    if not any(o.type == "MESH" for o in objs):
        continue
    for o in sc.objects:
        if o.type in ("MESH", "CURVE") and o is not floor:
            o.hide_render = not under(o, root)
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    size = hi - lo
    floor.location = (c.x, c.y, lo.z - 0.001)
    for lo_, off in lights:
        lo_.location = c + off
        lo_.rotation_euler = (c - lo_.location).to_track_quat("-Z", "Y").to_euler()
    views = {
        "front": (c + mathutils.Vector((0, -3.2, 0.1)), c, 40),
        "back": (c + mathutils.Vector((0, 3.2, 0.1)), c, 40),
        "side": (c + mathutils.Vector((3.2, 0, 0.1)), c, 40),
        "close": (mathutils.Vector((c.x - 1.0, lo.y - 1.7, lo.z + 1.55)), mathutils.Vector((c.x, lo.y, lo.z + size.z * 0.55)), 30),
    }
    order = ["front", "front_open", "close", "back", "side"]
    doors = [o for o in objs if "door" in o.name.lower()]
    door_tree = set()
    for d in doors:
        door_tree.add(d)
        door_tree.update(d.children_recursive)
    for v in order:
        key = "front" if v == "front_open" else v
        p, t, lens = views[key]
        cd.lens, cd.clip_start = lens, 0.05
        cam.location = p
        cam.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
        for o in door_tree:
            o.hide_render = (v == "front_open")
        if v == "front_open" and not door_tree:
            continue
        sc.render.filepath = os.path.join(out, f"cyc_{root}_{v}.jpg")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", root, v, flush=True)
    for o in door_tree:
        o.hide_render = False
