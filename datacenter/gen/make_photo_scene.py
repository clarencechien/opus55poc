"""Photo task (S1P): build the furnished hall from a ground-truth layout and/or the empty start scene for the models.

    blender -b --factory-startup --python make_photo_scene.py -- LAYOUT.json OUTDIR [--render] [--samples 48]

Writes OUTDIR/photo_scene.blend (furnished, for the photos), OUTDIR/start.blend (empty hall + templates + cameras,
for the models), OUTDIR/cameras.json and, with --render, OUTDIR/photo_N.jpg.
Racks carry a white label strip and LED strip across the top of the FRONT door so the front is recognisable.
"""
import json
import math
import os
import sys

import bpy
import mathutils

here = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index("--") + 1:]
layout_path, outdir = args[0], args[1]
do_render = "--render" in args
samples = int(args[args.index("--samples") + 1]) if "--samples" in args else 48
os.makedirs(outdir, exist_ok=True)
lay = json.load(open(layout_path))
mm = 0.001
room = lay["room"]
H = (room["raised_floor_height"] + room["clear_height"]) * mm
FLOOR = room["raised_floor_height"] * mm


def mat(name, rgb, emit=0.0, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (*rgb, 1)
    return m


def box(name, x0, x1, y0, y1, z0, z1, m, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    if parent:
        o.parent = parent
    return o


# ---- templates: RackA (600) with a front marker, RackG (800), CRAH ----
exec(open(os.path.join(here, "..", "oracle", "s2_oracle.py")).read(), {"__name__": "__photo__"})
for o in [o for o in bpy.data.objects if o.name.startswith("RackB")]:
    bpy.data.objects.remove(o, do_unlink=True)
A = bpy.data.objects["RackA"]
WHITE, LEDB = mat("label_white", (0.95, 0.95, 0.92), emit=1.5), mat("led_blue", (0.15, 0.45, 1.0), emit=10.0)
box("RackA_FrontLabel", -0.25, 0.25, -0.616, -0.606, 1.78, 1.94, WHITE, A)
box("RackA_FrontLED", -0.25, 0.25, -0.616, -0.606, 1.70, 1.74, LEDB, A)


def dup(src, parent, old, new):
    o = src.copy()
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    o.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    o.name = src.name.replace(old, new)
    for c in src.children:
        dup(c, o, old, new)
    return o


G = dup(A, None, "RackA", "RackG")
G.name = "RackG"
G.scale = (800 / 600, 1, 1)
CR = bpy.data.objects.new("CRAH", None)
bpy.context.scene.collection.objects.link(CR)
CRM, GRILLE = mat("crah", (0.82, 0.83, 0.82)), mat("grille", (0.18, 0.19, 0.2))
box("CRAH_Body", -0.9, 0.9, -0.45, 0.45, 0.0, 1.95, CRM, CR)
box("CRAH_Grille", -0.8, 0.8, -0.457, -0.449, 0.25, 1.75, GRILLE, CR)  # front (supply side) faces -y
A.location, G.location, CR.location = (-3.0, 2.0, 0.0), (-3.0, -0.5, 0.0), (-3.0, -3.5, 0.0)

# ---- room shell (polygon walls, columns, raised floor) ----
sys.path.insert(0, os.path.join(here, "..", "oracle"))
from s1_oracle import SHELL  # noqa: E402
exec(f"LAYOUT = {layout_path!r}\n" + SHELL.replace("for o in list(bpy.data.objects):\n    bpy.data.objects.remove(o)\n", ""),
     {"__name__": "__photo__"})
rf = bpy.data.objects["RaisedFloor"]
fm = bpy.data.materials.new("floor_tiles")
fm.use_nodes = True
nt = fm.node_tree
bsdf = nt.nodes["Principled BSDF"]
tc, sep = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Object"], sep.inputs[0])
lines = []
for axis in ("X", "Y"):
    d = nt.nodes.new("ShaderNodeMath"); d.operation = "DIVIDE"; d.inputs[1].default_value = 0.6
    f = nt.nodes.new("ShaderNodeMath"); f.operation = "FRACT"
    lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.012
    nt.links.new(sep.outputs[axis], d.inputs[0]); nt.links.new(d.outputs[0], f.inputs[0]); nt.links.new(f.outputs[0], lt.inputs[0])
    lines.append(lt)
mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
nt.links.new(lines[0].outputs[0], mx.inputs[0]); nt.links.new(lines[1].outputs[0], mx.inputs[1])
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
mix.inputs[6].default_value = (0.66, 0.67, 0.68, 1); mix.inputs[7].default_value = (0.25, 0.26, 0.28, 1)
nt.links.new(mx.outputs[0], mix.inputs[0]); nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
rf.data.materials.clear(); rf.data.materials.append(fm)
for o in bpy.data.objects:
    if o.name.startswith("Wall_"):
        o.data.materials.clear(); o.data.materials.append(mat("wall", (0.62, 0.64, 0.66)))
    if o.name.startswith("Column_"):
        o.data.materials.clear(); o.data.materials.append(mat("column", (0.7, 0.7, 0.68)))

# ceiling with light panels (photos only)
xs = [p[0] * mm for p in room["polygon"]]
ys = [p[1] * mm for p in room["polygon"]]
photo_only = []
CEIL, LIGHT = mat("ceiling", (0.8, 0.8, 0.8)), mat("lightpanel", (1.0, 0.98, 0.94), emit=5.0)
photo_only.append(box("Ceiling", min(xs) - 0.3, max(xs) + 0.3, min(ys) - 0.3, max(ys) + 0.3, H, H + 0.05, CEIL))
y = min(ys) + 1.2
while y < max(ys) - 0.6:
    x = min(xs) + 1.5
    while x < max(xs) - 0.6:
        photo_only.append(box(f"Light_{x:.1f}_{y:.1f}", x - 0.6, x + 0.6, y - 0.15, y + 0.15, H - 0.02, H, LIGHT))
        x += 3.0
    y += 2.4

# ---- cameras (survey positions just under the ceiling at the hall's corners) ----
W, D = max(lay["grid"]["x"].values()) * mm, max(lay["grid"]["y"].values()) * mm
xD, y3 = lay["grid"]["x"]["D"] * mm, lay["grid"]["y"]["3"] * mm
cams = [
    ("1", (0.45, 0.45, 3.25), (W * 0.45, D * 0.40, 0.9)),
    ("2", (W - 0.45, 0.45, 3.25), (W * 0.40, D * 0.45, 0.9)),
    ("3", (0.45, D - 0.45, 3.25), (W * 0.35, D * 0.35, 0.9)),
    ("4", (W - 0.45, y3 - 0.45, 3.25), (W * 0.30, D * 0.30, 0.9)),
    ("5", (xD - 0.45, D - 0.45, 3.25), (W * 0.25, D * 0.45, 0.9)),
]
LENS, RES = 16.0, (1280, 960)
cam_json = []
for name, p, t in cams:
    cd = bpy.data.cameras.new(f"Cam_{name}")
    cd.lens, cd.sensor_width, cd.sensor_fit, cd.clip_start, cd.clip_end = LENS, 36.0, "AUTO", 0.05, 200
    co = bpy.data.objects.new(f"Cam_{name}", cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = p
    co.rotation_euler = (mathutils.Vector(t) - mathutils.Vector(p)).to_track_quat("-Z", "Y").to_euler()
    cam_json.append({"photo": f"photo_{name}.jpg", "camera_object": f"Cam_{name}", "position_m": [round(v, 3) for v in p],
                     "target_m": [round(v, 3) for v in t], "lens_mm": LENS, "sensor_width_mm": 36.0,
                     "resolution": list(RES), "bench_render": f"bench render 'cam:{p[0]:.3f},{p[1]:.3f},{p[2]:.3f}>{t[0]:.3f},{t[1]:.3f},{t[2]:.3f}' --lens {LENS:g} --res {RES[0]}x{RES[1]}"})
json.dump({"cameras": cam_json, "note": "Blender camera: sensor 36 mm wide (fit AUTO), aims from position at target with +z up."},
          open(os.path.join(outdir, "cameras.json"), "w"), indent=1)

# ---- start scene for the models: empty hall + templates + cameras (no ceiling) ----
for o in photo_only:
    o.hide_render = True
    o.hide_set(True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, "start.blend"), copy=True)
for o in photo_only:
    o.hide_render = False
    o.hide_set(False)

# ---- furnish from the layout (racks, CRAH, perforated tiles) ----
ROT = {"S": 0.0, "N": math.pi, "E": math.pi / 2, "W": -math.pi / 2}
for r in lay["racks"]:
    src = G if r["size"][0] == 800 else A
    root = dup(src, None, src.name, f"Rack_{r['id']}")
    root.location = (r["center"][0] * mm, r["center"][1] * mm, FLOOR)
    root.rotation_euler = (0, 0, ROT[r["facing"]])
    root.scale = src.scale
for c in lay["crah"]:
    root = dup(CR, None, "CRAH", c["id"])
    root.location = (c["center"][0] * mm, c["center"][1] * mm, FLOOR)
    root.rotation_euler = (0, 0, ROT[c["facing"]])
PERF = mat("perf_tile", (0.55, 0.57, 0.6), rough=0.7)
for k, a in enumerate([a for a in lay["aisles"] if a["type"] == "cold"]):
    x0, y0, x1, y1 = [v * mm for v in a["rect"]]
    for i in range(math.ceil(round(x0 / 0.6, 6)), math.floor(round(x1 / 0.6, 6))):
        for j in range(math.ceil(round(y0 / 0.6, 6)), math.floor(round(y1 / 0.6, 6))):
            box(f"PerfTile_{k}_{i}_{j}", i * 0.6 + 0.006, (i + 1) * 0.6 - 0.006, j * 0.6 + 0.006, (j + 1) * 0.6 - 0.006,
                FLOOR - 0.01, FLOOR + 0.002, PERF)
for o in (A, G, CR):  # templates are not in the photos
    for x in [o] + list(o.children_recursive):
        x.hide_render = True
sc = bpy.context.scene
sc.world = sc.world or bpy.data.worlds.new("World")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, "photo_scene.blend"), copy=True)

if do_render:
    import time
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = -0.6
    only = os.environ.get("ONLY_CAM")
    for name, _, _ in cams:
        if only and name != only:
            continue
        sc.camera = bpy.data.objects[f"Cam_{name}"]
        sc.render.filepath = os.path.join(outdir, f"photo_{name}.jpg")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print("RENDERED", name, round(time.time() - t, 1), flush=True)
