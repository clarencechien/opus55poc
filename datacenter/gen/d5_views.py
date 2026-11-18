"""Render the participant views of the D5 target (orthographic engineering views + 2 perspective pictures).

    blender -b --factory-startup --python gen/d5_views.py -- --target GT_DIR --out inputs/d5

GT_DIR holds target.blend and target.json (from d5_target.py). Writes into the output folder:
    view_front.png view_back.png view_left.png view_right.png view_top.png persp_1.png persp_2.png

Orthographic views, all with the same framing rule:
  * scale exactly 1 px = 2 mm;
  * the image centre is the centre of the target's bounding box as seen in that view, and the image is the
    bounding box plus a 100 px (200 mm) margin on every side;
  * front: looking +y (image right = +x, up = +z)      back:  looking -y (image right = -x, up = +z)
    left:  looking +x (image right = -y, up = +z)      right: looking -x (image right = +y, up = +z)
    top:   looking -z (image right = +x, up = +y)
  * every part is drawn in a flat colour with a dark 2 px outline centred on its true edge;
  * rulers along the bottom and left edges: a tick every 100 mm, a longer tick every 500 mm, counted from the
    red tick, which marks the left / bottom edge of the bounding box. No dimension numbers are written.
Perspective pictures (not to scale): persp_1 from front-right-top, persp_2 from back-left-top.

Blender's Python has no PIL, so the rulers and labels are drawn by re-running this file with the system
python3 (`--post META.json`).
"""
from __future__ import annotations

import json
import math
import pathlib
import subprocess
import sys
import tempfile

MM_PER_PX = 2.0
MARGIN = 100        # px on every side of the bounding box
BG = (0.955, 0.955, 0.94)
VIEWS = {           # name: (camera direction from the centre, camera rotation euler, image right axis, image up axis)
    "front": ((0, -1, 0), (math.pi / 2, 0, 0), "x", "z", "right = +x, up = +z"),
    "back": ((0, 1, 0), (math.pi / 2, 0, math.pi), "x", "z", "right = -x, up = +z"),
    "left": ((-1, 0, 0), (math.pi / 2, 0, -math.pi / 2), "y", "z", "right = -y (front), up = +z"),
    "right": ((1, 0, 0), (math.pi / 2, 0, math.pi / 2), "y", "z", "right = +y (back), up = +z"),
    "top": ((0, 0, 1), (0, 0, 0), "x", "y", "right = +x, up = +y (back)"),
}
PERSP = {"persp_1": ((0.60, -0.68, 0.42), "PERSPECTIVE 1 - from front, right, above (not to scale)"),
         "persp_2": ((-0.60, 0.68, 0.42), "PERSPECTIVE 2 - from back, left, above (not to scale)")}


def setup_workbench(sc, flat: bool):
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT" if flat else "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_object_outline = True
    sh.object_outline_color = (0.0, 0.0, 0.0)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor, sh.cavity_valley_factor = 0.6, 1.2
    sh.curvature_ridge_factor, sh.curvature_valley_factor = 1.0, 1.5
    sc.display.matcap_ssao_distance = 0.06
    sc.display.matcap_ssao_attenuation = 1.0
    sc.display.matcap_ssao_samples = 64
    sh.show_shadows = False
    sh.show_specular_highlight = False
    sc.display.render_aa = "8"
    sc.render.film_transparent = False
    sc.world = sc.world or __import__("bpy").data.worlds.new("World")
    sc.world.color = BG
    sc.display.shading.show_shadows = False
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.render.resolution_percentage = 100


def setup_ids(sc):
    """Object-id pass: every object in its own flat colour, no anti-aliasing (used to draw crisp part outlines)."""
    import bpy
    sh = sc.display.shading
    sh.light, sh.color_type = "FLAT", "OBJECT"
    sh.show_object_outline = sh.show_cavity = sh.show_shadows = False
    sc.display.render_aa = "OFF"
    sc.view_settings.view_transform = "Raw"
    sc.world.color = (1.0, 1.0, 1.0)
    levels = [0.0, 0.2, 0.4, 0.6, 0.8]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for i, o in enumerate(meshes):
        o.color = (levels[i % 5], levels[(i // 5) % 5], levels[(i // 25) % 5], 1.0)


def render_all(target_dir: pathlib.Path, out_dir: pathlib.Path):
    import bpy
    import mathutils

    spec = json.loads((target_dir / "target.json").read_text())
    bpy.ops.wm.open_mainfile(filepath=str(target_dir / "target.blend"))
    sc = bpy.context.scene
    lo, hi = mathutils.Vector(spec["bbox"]["min"]), mathutils.Vector(spec["bbox"]["max"])
    ctr, size = (lo + hi) / 2, hi - lo
    cam_data = bpy.data.cameras.new("ViewCam")
    cam = bpy.data.objects.new("ViewCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.clip_start, cam_data.clip_end = 0.1, 100
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="d5views_"))
    meta = {"out": str(out_dir), "views": [], "persp": []}
    setup_workbench(sc, flat=True)
    for name, (d, rot, ax_r, ax_u, hint) in VIEWS.items():
        w = int(round(size["xyz".index(ax_r)] * 1000 / MM_PER_PX)) + 2 * MARGIN
        h = int(round(size["xyz".index(ax_u)] * 1000 / MM_PER_PX)) + 2 * MARGIN
        cam_data.type = "ORTHO"
        cam_data.sensor_fit = "AUTO"
        cam_data.ortho_scale = max(w, h) * MM_PER_PX / 1000.0
        cam.location = ctr + mathutils.Vector(d) * 20.0
        cam.rotation_euler = rot
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.filepath = str(tmp / f"{name}.png")
        setup_workbench(sc, flat=True)
        bpy.ops.render.render(write_still=True)
        raw = sc.render.filepath
        setup_ids(sc)                                   # second pass: one flat colour per object, no anti-aliasing
        sc.render.filepath = str(tmp / f"{name}_id.png")
        bpy.ops.render.render(write_still=True)
        meta["views"].append({"name": name, "raw": raw, "ids": sc.render.filepath, "file": f"view_{name}.png",
                              "label": f"{name.upper()} VIEW   ({hint})"})
    setup_workbench(sc, flat=False)
    sc.display.shading.show_shadows = True
    sc.display.shading.shadow_intensity = 0.25
    for name, (d, label) in PERSP.items():
        cam_data.type = "PERSP"
        cam_data.lens = 50
        cam_data.sensor_fit = "AUTO"
        p = ctr + mathutils.Vector(d).normalized() * 5.2
        cam.location = p
        cam.rotation_euler = (ctr - p).to_track_quat("-Z", "Y").to_euler()
        sc.render.resolution_x, sc.render.resolution_y = 1000, 1300
        sc.render.filepath = str(tmp / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        meta["persp"].append({"raw": sc.render.filepath, "file": f"{name}.png", "label": label})
    mp = tmp / "meta.json"
    mp.write_text(json.dumps(meta))
    subprocess.run(["python3", str(pathlib.Path(__file__).resolve()), "--post", str(mp)], check=True)


def post(meta_path: str):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    meta = json.loads(pathlib.Path(meta_path).read_text())
    out = pathlib.Path(meta["out"])
    out.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    tick = int(round(100 / MM_PER_PX))  # px per 100 mm
    band = 26
    for v in meta["views"]:
        im = Image.open(v["raw"]).convert("RGB")
        w, h = im.size
        ids = np.asarray(Image.open(v["ids"]).convert("RGB")).astype(np.int16)
        edge = np.zeros((h, w), bool)                  # 2 px outline centred on every boundary between two parts
        dx = (np.abs(ids[:, 1:] - ids[:, :-1]).max(axis=2) > 12)
        dy = (np.abs(ids[1:, :] - ids[:-1, :]).max(axis=2) > 12)
        edge[:, 1:] |= dx
        edge[:, :-1] |= dx
        edge[1:, :] |= dy
        edge[:-1, :] |= dy
        px = np.asarray(im).copy()
        px[edge] = (25, 25, 30)
        im = Image.fromarray(px)
        d = ImageDraw.Draw(im)
        d.rectangle([0, h - band, w, h], fill=(255, 255, 255))
        d.rectangle([0, 0, band, h], fill=(255, 255, 255))
        d.line([(0, h - band), (w, h - band)], fill=(0, 0, 0))
        d.line([(band, 0), (band, h)], fill=(0, 0, 0))
        k0 = -(MARGIN // tick) - 1
        for k in range(k0, (max(w, h) // tick) + 2):
            major = k % 5 == 0
            col = (220, 0, 0) if k == 0 else (0, 0, 0)
            ln = band if k == 0 else (16 if major else 8)
            wd = 3 if k == 0 else (2 if major else 1)
            x = MARGIN + k * tick                      # horizontal ruler, counted from the bbox left edge
            if band < x < w:
                d.line([(x, h - band), (x, h - band + ln)], fill=col, width=wd)
            y = h - MARGIN - k * tick                  # vertical ruler, counted from the bbox bottom edge
            if 0 <= y < h - band:
                d.line([(band - ln, y), (band, y)], fill=col, width=wd)
        d.text((band + 10, 8), v["label"], fill=(0, 0, 0), font=font)
        im.save(out / v["file"], optimize=True)
        print("wrote", out / v["file"], im.size)
    for v in meta["persp"]:
        im = Image.open(v["raw"]).convert("RGB")
        ImageDraw.Draw(im).text((12, 8), v["label"], fill=(0, 0, 0), font=font)
        im.save(out / v["file"], optimize=True)
        print("wrote", out / v["file"], im.size)


def main():
    if "--post" in sys.argv:
        post(sys.argv[sys.argv.index("--post") + 1])
        return
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="folder with target.blend and target.json")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    render_all(pathlib.Path(a.target).resolve(), pathlib.Path(a.out).resolve())


if __name__ == "__main__":
    main()
