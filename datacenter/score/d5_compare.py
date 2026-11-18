"""Review images for stage D5: target vs submission from the same cameras, plus a volume-difference picture.

    blender -b --factory-startup --python score/d5_compare.py -- --gt GT_DIR --sub RUN/d5.blend --out OUT_DIR

GT_DIR holds target.blend and target.json (secret). Writes into OUT_DIR:
    compare_views.png  top row: target, bottom row: submission (only what is under `Target`), from the same
                       4 cameras (front-right, front-left, back-left, back-right, all from above)
    compare_diff.png   top / front / right-side projections of the 10 mm voxel grids used by d5_voxel.py:
                       grey = volume present in both, red = missing (in the target, not in the submission),
                       blue = surplus (in the submission, not in the target); stronger colour = thicker error
    compare_score.json the d5_voxel.py result for this submission

Blender's Python has no PIL, so the sheets are composed by re-running this file with the system python3
(`--post META.json`).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

CAMS = [("front-right", (0.60, -0.68, 0.42)), ("front-left", (-0.60, -0.68, 0.42)),
        ("back-left", (-0.60, 0.68, 0.42)), ("back-right", (0.60, 0.68, 0.42))]
RES = (560, 730)
BG = (0.955, 0.955, 0.94)


def render_set(tag: str, ctr, tmp: pathlib.Path) -> list[str]:
    import bpy
    import mathutils

    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("__cmp_cam")
    cam = bpy.data.objects.new("__cmp_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam_data.type, cam_data.lens = "PERSP", 50
    cam_data.sensor_fit = "AUTO"
    cam_data.clip_start, cam_data.clip_end = 0.1, 100
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "MATERIAL"
    sh.show_object_outline, sh.show_cavity, sh.show_shadows = True, True, False
    sh.cavity_type = "BOTH"
    sc.display.render_aa = "8"
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.color = BG
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES[0], RES[1], 100
    for m in bpy.data.materials:  # show node-built materials in their base colour
        if m.use_nodes and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    c = n.inputs["Base Color"].default_value
                    m.diffuse_color = (c[0], c[1], c[2], 1.0)
                    break
    files = []
    for i, (_name, d) in enumerate(CAMS):
        p = ctr + mathutils.Vector(d).normalized() * 5.2
        cam.location = p
        cam.rotation_euler = (ctr - p).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = str(tmp / f"{tag}_{i}.png")
        bpy.ops.render.render(write_still=True)
        files.append(sc.render.filepath)
    return files


def blender_main(gt_dir: pathlib.Path, sub: pathlib.Path, out: pathlib.Path):
    import bpy
    import mathutils
    import numpy as np

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import d5_voxel

    gt = json.loads((gt_dir / "target.json").read_text())
    ctr = (mathutils.Vector(gt["bbox"]["min"]) + mathutils.Vector(gt["bbox"]["max"])) / 2
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="d5cmp_"))
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(gt_dir / "target.blend"))
    gt_files = render_set("gt", ctr, tmp)
    bpy.ops.wm.open_mainfile(filepath=str(sub))
    res = d5_voxel.score(gt, keep_arrays=True)
    arr = res.pop("_arrays")
    np.savez_compressed(tmp / "occ.npz", gt=arr["labels"] > 0, sub=arr["occ"])
    (out / "compare_score.json").write_text(json.dumps(res, indent=1))
    root = bpy.context.scene.objects.get(d5_voxel.ROOT)
    for o in bpy.context.scene.objects:  # show only what is scored
        p, keep = o, False
        while p is not None:
            if p == root:
                keep = True
                break
            p = p.parent
        if not keep and o.type not in {"CAMERA"}:
            o.hide_render = True
    sub_files = render_set("sub", ctr, tmp)
    d = res.get("detail", {})
    meta = {"out": str(out), "gt": gt_files, "sub": sub_files, "occ": str(tmp / "occ.npz"),
            "cams": [c[0] for c in CAMS],
            "caption": f"total {res.get('total')}   IoU {d.get('iou')}   best-shift IoU "
                       f"{(d.get('iou_best_xy_shift') or {}).get('iou')} at {(d.get('iou_best_xy_shift') or {}).get('shift_mm')} mm"
                       f"   feature mean {d.get('feature_mean')}   triangles {d.get('triangles')}"
                       f"{'   NO ROOT Target' if d.get('missing_root') else ''}"}
    mp = tmp / "meta.json"
    mp.write_text(json.dumps(meta))
    subprocess.run(["python3", str(pathlib.Path(__file__).resolve()), "--post", str(mp)], check=True)


def post(meta_path: str):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    meta = json.loads(pathlib.Path(meta_path).read_text())
    out = pathlib.Path(meta["out"])
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    # --- side-by-side renders
    w, h = Image.open(meta["gt"][0]).size
    head = 30
    sheet = Image.new("RGB", (w * 4, (h + head) * 2 + head), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((8, 5), meta["caption"], fill=(0, 0, 0), font=font)
    for r, (tag, files) in enumerate((("TARGET", meta["gt"]), ("SUBMISSION", meta["sub"]))):
        for c, f in enumerate(files):
            x, y = c * w, head + r * (h + head)
            d.text((x + 8, y + 5), f"{tag} - {meta['cams'][c]}", fill=(0, 0, 0), font=font)
            sheet.paste(Image.open(f).convert("RGB"), (x, y + head))
    sheet.save(out / "compare_views.png", optimize=True)
    # --- difference projections
    z = np.load(meta["occ"])
    G, S = z["gt"], z["sub"]
    miss, plus, both = G & ~S, S & ~G, G & S
    k = 4  # px per voxel

    def panel(axis, flip_x=False):
        m, p, b = miss.sum(axis=axis).astype(float), plus.sum(axis=axis).astype(float), both.any(axis=axis)
        img = np.full(m.shape + (3,), 255.0)
        img[b] = (205, 205, 205)
        am = np.clip(m / 10.0, 0, 1) * 0.7 + 0.3 * (m > 0)   # 1 voxel = faint, >= 100 mm = full colour
        ap = np.clip(p / 10.0, 0, 1) * 0.7 + 0.3 * (p > 0)
        red, blue, purple = np.array([220.0, 30, 30]), np.array([30.0, 60, 230]), np.array([150.0, 40, 200])
        img = img * (1 - am[..., None]) + red * am[..., None]
        mix = np.where((m > 0)[..., None], purple, blue)
        img = img * (1 - ap[..., None]) + mix * ap[..., None]
        img = np.transpose(img, (1, 0, 2))[::-1]              # first remaining axis -> image x, second -> up
        if flip_x:
            img = img[:, ::-1]
        im = Image.fromarray(img.astype(np.uint8))
        return im.resize((im.width * k, im.height * k), Image.NEAREST)

    panels = [("TOP (right = +x, up = +y)", panel(2)), ("FRONT (right = +x, up = +z)", panel(1)),
              ("RIGHT SIDE (right = +y, up = +z)", panel(0))]
    head = 56
    W = sum(p.width for _, p in panels) + 20 * (len(panels) + 1)
    Hh = max(p.height for _, p in panels) + head + 40
    sheet = Image.new("RGB", (W, Hh), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((8, 5), meta["caption"], fill=(0, 0, 0), font=font)
    d.text((8, 28), "grey = in both    red = missing (target only)    blue = surplus (submission only)"
                    "    purple = both kinds along the line of sight", fill=(0, 0, 0), font=font)
    x = 20
    for name, p in panels:
        sheet.paste(p, (x, head + 30))
        d.rectangle([x - 1, head + 29, x + p.width, head + 30 + p.height], outline=(120, 120, 120))
        d.text((x, head + 5), name, fill=(0, 0, 0), font=font)
        x += p.width + 20
    sheet.save(out / "compare_diff.png", optimize=True)
    print("wrote", out / "compare_views.png", out / "compare_diff.png")


def main():
    if "--post" in sys.argv:
        post(sys.argv[sys.argv.index("--post") + 1])
        return
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True, help="folder with target.blend and target.json")
    ap.add_argument("--sub", required=True, help="submission .blend (RUN/d5.blend)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    blender_main(pathlib.Path(a.gt).resolve(), pathlib.Path(a.sub).resolve(), pathlib.Path(a.out).resolve())


if __name__ == "__main__":
    main()
