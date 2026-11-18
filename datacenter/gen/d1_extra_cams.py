"""Task D1: add extra survey cameras to the output of make_photo_scene.py (which has five fixed corner cameras).

    blender -b --factory-startup --python d1_extra_cams.py -- PHOTODIR NAME:x,y,z:tx,ty,tz [NAME:...] [--render] [--samples 24]

PHOTODIR is the OUTDIR of make_photo_scene.py. For every NAME (for example 6) a camera Cam_NAME at x,y,z aiming at
tx,ty,tz (metres) is added to PHOTODIR/photo_scene.blend and PHOTODIR/start.blend and appended to PHOTODIR/cameras.json;
with --render, PHOTODIR/photo_NAME.jpg is rendered with the same lens, resolution and Cycles settings as the other photos.

The published D1 inputs (seed 4, hall 24.0 x 18.0 m) use two extra cameras, both 3.25 m up like the corner cameras:
    6:12.0,0.45,3.25:19.2,5.4,0.9      middle of the south wall, looking north-east
    7:17.55,11.55,3.25:8.0,7.0,0.9     inner corner of the hall next to the UPS room, looking south-west
"""
import json
import os
import sys

import bpy
import mathutils

args = sys.argv[sys.argv.index("--") + 1:]
outdir = args[0]
do_render = "--render" in args
samples = int(args[args.index("--samples") + 1]) if "--samples" in args else 24
specs = []
for a in args[1:]:
    if a.count(":") == 2:
        name, p, t = a.split(":")
        specs.append((name, tuple(float(v) for v in p.split(",")), tuple(float(v) for v in t.split(","))))
if not specs:
    raise SystemExit("no camera given (NAME:x,y,z:tx,ty,tz)")
LENS, RES = 16.0, (1280, 960)   # same as make_photo_scene.py


def add_cameras():
    sc = bpy.context.scene
    for name, p, t in specs:
        old = bpy.data.objects.get(f"Cam_{name}")
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        cd = bpy.data.cameras.new(f"Cam_{name}")
        cd.lens, cd.sensor_width, cd.sensor_fit, cd.clip_start, cd.clip_end = LENS, 36.0, "AUTO", 0.05, 200
        co = bpy.data.objects.new(f"Cam_{name}", cd)
        sc.collection.objects.link(co)
        co.location = p
        co.rotation_euler = (mathutils.Vector(t) - mathutils.Vector(p)).to_track_quat("-Z", "Y").to_euler()


# ---- cameras.json ----
cj_path = os.path.join(outdir, "cameras.json")
cj = json.load(open(cj_path))
new_names = {f"Cam_{n}" for n, _, _ in specs}
cj["cameras"] = [c for c in cj["cameras"] if c["camera_object"] not in new_names]
for name, p, t in specs:
    cj["cameras"].append({
        "photo": f"photo_{name}.jpg", "camera_object": f"Cam_{name}", "position_m": [round(v, 3) for v in p],
        "target_m": [round(v, 3) for v in t], "lens_mm": LENS, "sensor_width_mm": 36.0, "resolution": list(RES),
        "bench_render": f"bench render 'cam:{p[0]:.3f},{p[1]:.3f},{p[2]:.3f}>{t[0]:.3f},{t[1]:.3f},{t[2]:.3f}' --lens {LENS:g} --res {RES[0]}x{RES[1]}"})
json.dump(cj, open(cj_path, "w"), indent=1)

# ---- start scene for the participants ----
bpy.ops.wm.open_mainfile(filepath=os.path.join(outdir, "start.blend"))
add_cameras()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, "start.blend"))

# ---- furnished scene, photos ----
bpy.ops.wm.open_mainfile(filepath=os.path.join(outdir, "photo_scene.blend"))
add_cameras()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, "photo_scene.blend"))
if do_render:
    import time
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = -0.6
    for name, _, _ in specs:
        sc.camera = bpy.data.objects[f"Cam_{name}"]
        sc.render.filepath = os.path.join(outdir, f"photo_{name}.jpg")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print("RENDERED", name, round(time.time() - t0, 1), flush=True)
