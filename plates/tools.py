"""Helpers for the plate pipeline (run locally; needs pillow + numpy).

  python plates/tools.py prep  <bake_dir>   # three.js passes -> plates/passes (ControlNet inputs)
  python plates/tools.py web                # passes + chosen AI plates -> plates/web + manifest.json
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).parent
TIME = {"reopen": "night", "ferry": "night", "kawabata": "dusk", "petition": "day", "piers": "day", "girders": "day",
        "open": "day", "rename": "dusk", "widen": "day", "toll": "day", "danger": "dusk", "heritage": "night",
        "newbuild": "day", "newopen": "day", "restore": "dusk", "finale": "night"}


def stretch_depth(img):
    a = np.asarray(img.convert("L")).astype(np.float32)
    sky = a < 2
    lo, hi = np.percentile(a[~sky], 0.5), np.percentile(a[~sky], 99.8)
    d = np.clip((a - lo) / max(hi - lo, 1), 0, 1) * 0.92 + 0.08
    d[sky] = 0
    return Image.fromarray((d * 255).astype(np.uint8))


def prep(bake):
    bake = pathlib.Path(bake)
    out = ROOT / "passes"; out.mkdir(exist_ok=True)
    for f in sorted(bake.glob("*_beauty.png")):
        pid = f.name[:-len("_beauty.png")]
        Image.open(f).convert("RGB").save(out / f"{pid}_beauty.jpg", quality=90)
        stretch_depth(Image.open(bake / f"{pid}_depth.png")).save(out / f"{pid}_depth.png", optimize=True)
        Image.open(bake / f"{pid}_water.png").convert("L").resize((960, 540), Image.BILINEAR).save(out / f"{pid}_water.png", optimize=True)
        print("prepped", pid)
    (out / "labels.json").write_text((bake / "labels.json").read_text())


def web():
    spec = json.loads((ROOT / "prompts.json").read_text())
    sel_path = ROOT / "selection.json"
    sel = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    labels = json.loads((ROOT / "passes" / "labels.json").read_text())
    out = ROOT / "web"; out.mkdir(exist_ok=True)
    manifest = {}
    for pid, p in spec["plates"].items():
        scene = pid.split("_", 1)[1]
        choice = sel.get(pid)
        src = ROOT / "raw" / f"{pid}_v{choice}.jpg" if choice is not None else ROOT / "passes" / f"{pid}_beauty.jpg"
        img = Image.open(src).convert("RGB").resize((1920, 1080), Image.LANCZOS)
        keep = ROOT / "passes" / f"keep_{pid}.json"
        if choice is not None and keep.exists():  # paste exact regions (e.g. inscribed name plaques) back from the render
            base = Image.open(ROOT / "passes" / f"{pid}_beauty.jpg").convert("RGB").resize((1920, 1080))
            mask = Image.new("L", (1920, 1080), 0)
            from PIL import ImageDraw
            dr = ImageDraw.Draw(mask)
            for x0, y0, x1, y1 in json.loads(keep.read_text()):
                dr.rectangle([x0 * 1920 - 4, y0 * 1080 - 4, x1 * 1920 + 4, y1 * 1080 + 4], fill=255)
            # match the render's tone to the painted plate (luminance/contrast of the surrounding stone) and add grain
            b = np.asarray(base).astype(np.float32); t = np.asarray(img).astype(np.float32); m = np.asarray(mask) > 0
            for c in range(3):
                bs, ts = b[..., c][m], t[..., c][m]
                b[..., c] = (b[..., c] - bs.mean()) / (bs.std() + 1e-3) * ts.std() * 0.9 + ts.mean()
            b += np.random.default_rng(1).normal(0, 5, b.shape)
            base = Image.fromarray(np.clip(b, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
            img = Image.composite(base, img, mask.filter(ImageFilter.GaussianBlur(3)))
        for x0, y0, x1, y1 in p.get("clean", []):  # wipe AI pseudo-text: smear the region into plain wall
            box = tuple(int(v) for v in (x0 * 1920, y0 * 1080, x1 * 1920, y1 * 1080))
            patch = img.crop(box)
            plain = patch.resize((1, patch.height), Image.BOX).resize(patch.size, Image.BILINEAR)
            plain = Image.fromarray(np.clip(np.asarray(plain).astype(np.float32) + np.random.default_rng(2).normal(0, 3, np.asarray(plain).shape), 0, 255).astype(np.uint8))
            img.paste(plain, box)
        img.save(out / f"{pid}.jpg", quality=82, progressive=True, optimize=True)
        d = Image.open(ROOT / "passes" / f"{pid}_depth.png").convert("L").resize((960, 540), Image.BILINEAR)
        d.filter(ImageFilter.GaussianBlur(1.6)).save(out / f"{pid}_d.png", optimize=True)
        Image.open(ROOT / "passes" / f"{pid}_water.png").convert("L").filter(ImageFilter.GaussianBlur(2)).save(out / f"{pid}_w.png", optimize=True)
        manifest[scene] = {"id": pid, "era": p["era"], "time": TIME[scene], "ai": choice is not None, "labels": labels.get(pid, [])}
        print("web", pid, "AI" if choice is not None else "render")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"prep": lambda: prep(sys.argv[2]), "web": web}[sys.argv[1]]()
