"""Interior pipeline on Modal: plan rasterizing (CPU) and Blender Cycles renders / lightmap bakes (GPU).

    pip install 'modal[api-proxy-support]'          # behind an HTTP proxy
    modal run interior/modal_interior.py::plan                   # out/plan_empty.png from out/plan_empty.svg
    modal run interior/modal_interior.py::render --variant empty --shots axo,living
    modal run interior/modal_interior.py::render --variant wa --shots living,washitsu,master --res 1920x1080 --samples 512
    modal run interior/modal_interior.py::bake --variant wa        # viewer/<variant>.glb with baked lighting
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

import modal

HERE = pathlib.Path(__file__).resolve().parent
REMOTE = "/root/interior"
BLENDER_VERSION = "4.2.23"
BLENDER_URL = f"https://download.blender.org/release/Blender4.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
IGNORE = ["out", "viewer", "ref", "renders", "tour", "__pycache__", "*.webp", "*.html"]

cpu_image = (modal.Image.debian_slim(python_version="3.11")
             .apt_install("librsvg2-bin", "fonts-noto-cjk", "ffmpeg")
             .pip_install("pillow==11.0.0", "numpy==2.1.3")
             .add_local_dir(str(HERE), REMOTE, ignore=IGNORE))
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "curl", "xz-utils", "libx11-6", "libxi6", "libxxf86vm1", "libxfixes3", "libxrender1",
        "libxkbcommon0", "libgl1", "libglu1-mesa", "libegl1", "libsm6", "libice6", "libgomp1",
        "libxcursor1", "libxinerama1", "libxrandr2", "libwayland-client0", "libdbus-1-3",
    )
    .run_commands(
        f"curl -fsSL {BLENDER_URL} -o /tmp/blender.tar.xz",
        "mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/blender.tar.xz",
    )
    .pip_install("requests==2.32.3")
    .add_local_dir(str(HERE), REMOTE, ignore=IGNORE)
)
app = modal.App("interior-wa")
assets_vol = modal.Volume.from_name("interior-polyhaven", create_if_missing=True)
ASSETS = "/assets"

# CC0 Poly Haven scans used by the scene (2k): floors, walls, stone, fabric, tatami-like weave, paper
TEXTURES = ["laminate_floor_02", "laminate_floor_03", "tatami_mat", "ash_veneer", "oak_veneer_01", "american_walnut_veneer",
            "clay_plaster", "beige_wall_001", "concrete_floor_02", "wool_boucle", "rough_linen", "marble_01", "marble_tiles",
            "gravel_floor", "bamboo_wall", "anti_slip_concrete", "jogging_melange"]
HDRIS = [("ninomaru_teien", "4k")]
MODELS = ["potted_plant_01", "potted_plant_04", "tea_set_01", "ceramic_vase_02", "rock_moss_set_01", "shrub_02", "tree_small_02",
          "potted_plant_02", "ceramic_vase_01", "vintage_electric_kettle", "wooden_cutting_board", "pot_enamel_01", "wooden_bowl_01",
          "wicker_basket_01", "wooden_stool_01", "wooden_bucket_01", "decorative_book_set_01", "outdoor_table_chair_set_01"]
MAPS = ["Diffuse", "nor_gl", "Rough"]


def fetch_assets(root: str) -> None:
    import requests
    s = requests.Session(); s.headers["User-Agent"] = "interior-wa-render/1.0"

    def get(url, dst):
        dst = pathlib.Path(dst)
        if dst.exists() and dst.stat().st_size > 0:
            return 0
        dst.parent.mkdir(parents=True, exist_ok=True)
        r = s.get(url, timeout=300); r.raise_for_status()
        tmp = dst.with_suffix(dst.suffix + ".part"); tmp.write_bytes(r.content); tmp.rename(dst)
        return 1

    new = 0
    for aid in TEXTURES:
        need = [m for m in MAPS if not (pathlib.Path(root) / "textures" / aid / f"{aid}_{m}_2k.jpg").exists()]
        if not need:
            continue
        try:
            d = s.get(f"https://api.polyhaven.com/files/{aid}", timeout=60).json()
        except Exception as e:  # noqa: BLE001
            print("[assets] skip", aid, e); continue
        for m in need:
            if m in d and "2k" in d[m] and "jpg" in d[m]["2k"]:
                new += get(d[m]["2k"]["jpg"]["url"], pathlib.Path(root) / "textures" / aid / f"{aid}_{m}_2k.jpg")
            else:
                print("[assets] no", aid, m)
    for aid, res in HDRIS:
        dst = pathlib.Path(root) / "hdri" / f"{aid}_{res}.hdr"
        if not dst.exists():
            try:
                new += get(s.get(f"https://api.polyhaven.com/files/{aid}", timeout=60).json()["hdri"][res]["hdr"]["url"], dst)
            except Exception as e:  # noqa: BLE001
                print("[assets] skip hdri", aid, e)
    for aid in MODELS:
        base = pathlib.Path(root) / "models" / aid
        if (base / f"{aid}_1k.blend").exists() and (base / ".gltf_checked").exists():
            continue
        try:
            d = s.get(f"https://api.polyhaven.com/files/{aid}", timeout=60).json()
            b = d["blend"]["1k"]["blend"]
            for rel, inc in b.get("include", {}).items():
                new += get(inc["url"], base / rel)
            new += get(b["url"], base / f"{aid}_1k.blend")
            # newer Poly Haven .blend files may not open in Blender 4.2: keep the glTF as a fallback
            g = d.get("gltf", {}).get("1k", {}).get("gltf")
            if g:
                for rel, inc in g.get("include", {}).items():
                    new += get(inc["url"], base / rel)
                new += get(g["url"], base / f"{aid}_1k.gltf")
            (base / ".gltf_checked").touch()
        except Exception as e:  # noqa: BLE001
            print("[assets] skip model", aid, e)
    print(f"[assets] {new} new files", flush=True)


@app.function(image=cpu_image, timeout=600)
def rasterize(svg: bytes, zoom: float = 2.0) -> bytes:
    pathlib.Path("/tmp/p.svg").write_bytes(svg)
    subprocess.run(["rsvg-convert", "-z", str(zoom), "-b", "#fbfaf7", "/tmp/p.svg", "-o", "/tmp/p.png"], check=True)
    return pathlib.Path("/tmp/p.png").read_bytes()


def run_blender(args: list[str]) -> str:
    cmd = ["/opt/blender/blender", "-b", "--python-exit-code", "1", "--python", f"{REMOTE}/blender/interior_scene.py", "--", *args]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    log = [l for l in p.stdout.splitlines() if not l.startswith(("Fra:", "Read prefs")) and "| Sample" not in l]
    print("\n".join(log[-60:]), flush=True)
    if p.returncode != 0:
        print(p.stderr[-6000:], flush=True)
        raise RuntimeError(f"blender exited {p.returncode}")
    return "\n".join(log[-30:])


@app.function(image=gpu_image, gpu="L40S", volumes={ASSETS: assets_vol}, timeout=3600, cpu=8.0, memory=32768)
def render_shot(variant: str, shot: str, res: str, samples: int, extra: list[str]) -> dict:
    t0 = time.time()
    fetch_assets(ASSETS); assets_vol.commit()
    out = pathlib.Path("/tmp/out"); out.mkdir(exist_ok=True)
    name = (f"{variant}_audit" if "," in shot else f"{variant}_{shot}") + ("_night" if "--night" in extra else "")
    log = run_blender(["--variant", variant, "--shot", shot, "--assets", ASSETS, "--plan", f"{REMOTE}/plan.json",
                       "--out", str(out / f"{name}.png"), "--res", res, "--samples", str(samples), *extra])
    return {"files": {f.name: f.read_bytes() for f in out.glob(f"{name}*.png")}, "seconds": round(time.time() - t0, 1), "log": log}


@app.function(image=gpu_image, gpu="L40S", volumes={ASSETS: assets_vol}, timeout=3 * 3600, cpu=8.0, memory=32768)
def bake_variant(variant: str, texel: float, samples: int, extra: list[str]) -> dict:
    t0 = time.time()
    fetch_assets(ASSETS); assets_vol.commit()
    out = pathlib.Path("/tmp/bake"); out.mkdir(exist_ok=True)
    log = run_blender(["--variant", variant, "--bake", str(out), "--assets", ASSETS, "--plan", f"{REMOTE}/plan.json",
                       "--texel", str(texel), "--samples", str(samples), *extra])
    files = {str(f.relative_to(out)): f.read_bytes() for f in out.rglob("*") if f.is_file()}
    return {"files": files, "seconds": round(time.time() - t0, 1), "log": log}


@app.local_entrypoint()
def plan():
    png = rasterize.remote((HERE / "out" / "plan_empty.svg").read_bytes())
    (HERE / "out" / "plan_empty.png").write_bytes(png)
    print("wrote", HERE / "out" / "plan_empty.png", len(png))


@app.local_entrypoint()
def audit(variant: str = "wa", shots: str = "living,washitsu,dining,entry,master,master2,bath,garden,kitchen,br2,br4,br5,ba2,ba3,hall,balcony,svc",
          res: str = "800x500", samples: int = 48, tag: str = "audit"):
    """many shots from one scene build, in one container"""
    dst = HERE / "out" / tag; dst.mkdir(parents=True, exist_ok=True)
    r = render_shot.remote(variant, shots, res, samples, [])
    for fname, data in r["files"].items():
        (dst / fname).write_bytes(data)
    print(f"[audit] {len(r['files'])} images in {r['seconds']} s -> {dst}")


@app.local_entrypoint()
def render(variant: str = "empty", shots: str = "axo", res: str = "1600x1000", samples: int = 256, extra: str = ""):
    dst = HERE / "out"; dst.mkdir(exist_ok=True)
    args = [(v, s, res, samples, extra.split() if extra else []) for v in variant.split(",") for s in shots.split(",")]
    for (v, s, *_), r in zip(args, render_shot.starmap(args)):
        for fname, data in r["files"].items():
            (dst / fname).write_bytes(data)
        print(f"[done] {v}/{s} in {r['seconds']} s: {sorted(r['files'])}")


@app.local_entrypoint()
def bake(variant: str = "empty,wa", texel: float = 64.0, samples: int = 256, extra: str = ""):
    args = [(v, texel, samples, extra.split() if extra else []) for v in variant.split(",")]
    for (v, *_), r in zip(args, bake_variant.starmap(args)):
        for rel, data in r["files"].items():
            p = HERE / "viewer" / "assets" / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        print(f"[bake] {v} in {r['seconds']} s: {len(r['files'])} files")
        print(r["log"][-1500:])


# ============================================================== walkthrough video
frames_vol = modal.Volume.from_name("interior-frames", create_if_missing=True)
FRAMES = "/frames"


@app.function(image=gpu_image, gpu="L40S", volumes={ASSETS: assets_vol, FRAMES: frames_vol}, timeout=3600, cpu=4.0, memory=16384)
def walk_chunk(job: str, variant: str, frames: str, res: str, samples: int) -> dict:
    t0 = time.time()
    outdir = pathlib.Path(FRAMES) / job; outdir.mkdir(parents=True, exist_ok=True)
    run_blender(["--variant", variant, "--walk", frames, "--outdir", str(outdir), "--assets", ASSETS,
                 "--plan", f"{REMOTE}/plan.json", "--res", res, "--samples", str(samples), "--out", "/tmp/x.png"])
    frames_vol.commit()
    return {"frames": frames, "seconds": round(time.time() - t0, 1)}


@app.function(image=cpu_image, volumes={FRAMES: frames_vol}, timeout=1800, cpu=4.0, memory=8192)
def walk_encode(job: str, labels: list, fps_in: int = 18, fps_out: int = 30) -> dict:
    """burn in room captions, fade in/out, motion-interpolate to 30 fps (and keep the native rate), H.264"""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    frames_vol.reload()
    src = sorted((pathlib.Path(FRAMES) / job).glob("f_*.jpg"))
    W, H = Image.open(src[0]).size
    s_ = H / 720

    def font(path, size):
        for i in range(10):
            try:
                f = ImageFont.truetype(path, size, index=i)
            except OSError:
                break
            if f.getname()[0].endswith("TC"):
                return f
        return ImageFont.truetype(path, size)
    big = font("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", int(40 * s_))
    small = font("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", int(17 * s_))

    def card(text):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x, y = int(56 * s_), H - int(96 * s_)
        d.text((x, y), text, font=big, fill=(255, 250, 240, 255))
        b = d.textbbox((x, y), text, font=big)
        d.rectangle((x, b[3] + int(10 * s_), x + int(44 * s_), b[3] + int(12 * s_)), fill=(214, 170, 96, 255))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(5 * s_)).point(lambda v: int(v * 0.7)))
        return Image.alpha_composite(sh, im)
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    tag = "68 坪・和風宅　Blender Cycles 路徑追蹤"
    d.text((int(56 * s_), int(34 * s_)), tag, font=small, fill=(255, 255, 255, 190))
    # label timeline: (first frame, text) -> spans
    spans = []
    for i, (f, t) in enumerate(labels):
        if spans and spans[-1][2] == t:
            continue
        spans.append([f, None, t])
    for i in range(len(spans) - 1):
        spans[i][1] = spans[i + 1][0] - 1
    spans[-1][1] = 10 ** 6
    cards = {t: card(t) for _, _, t in spans}
    tmp = pathlib.Path("/tmp/cap"); tmp.mkdir(exist_ok=True)
    n = len(src); fade = 9
    for k, fp in enumerate(src):
        f = int(fp.stem.split("_")[1])
        im = Image.open(fp).convert("RGBA")
        im = Image.alpha_composite(im, base)
        for a, b, t in spans:
            if a <= f <= b:
                al = min(1.0, (f - a + 1) / fade, (b - f + 1) / fade) if b < 10 ** 6 else min(1.0, (f - a + 1) / fade)
                c = cards[t] if al >= 1 else Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), cards[t], al)
                im = Image.alpha_composite(im, c)
        g = min(1.0, (k + 1) / 8, (n - k) / 8)
        rgb = im.convert("RGB")
        if g < 1:
            rgb = Image.blend(Image.new("RGB", (W, H)), rgb, g)
        rgb.save(tmp / f"c_{k:04d}.png")
    out = pathlib.Path("/tmp/walk.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps_in), "-i", str(tmp / "c_%04d.png"),
                    "-vf", f"minterpolate=fps={fps_out}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-movflags", "+faststart", str(out)], check=True)
    raw = pathlib.Path("/tmp/walk_native.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps_in), "-i", str(tmp / "c_%04d.png"),
                    "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "18", str(raw)], check=True)
    return {"mp4": out.read_bytes(), "mp4_12": raw.read_bytes(), "frames": n, "size": f"{W}x{H}"}


@app.function(volumes={FRAMES: frames_vol}, timeout=600)
def walk_fetch(job: str) -> dict:
    frames_vol.reload()
    return {f.name: f.read_bytes() for f in sorted((pathlib.Path(FRAMES) / job).glob("f_*.jpg"))}


@app.local_entrypoint()
def walk(variant: str = "wa", job: str = "walk_wa", res: str = "1280x720", samples: int = 40, chunks: int = 6,
         total: int = 321, probe: str = "", encode_only: bool = False, labels: str = ""):
    """--probe 1:321:80 renders every 80th frame in one container to measure the cost per frame"""
    dst = HERE / "out"; dst.mkdir(exist_ok=True)
    if probe:
        r = walk_chunk.remote(job + "_probe", variant, probe, res, samples)
        print("[probe]", r)
        for name, data in walk_fetch.remote(job + "_probe").items():
            (dst / f"probe_{name}").write_bytes(data)
        return
    if not encode_only:
        step = -(-total // chunks)
        args = [(job, variant, f"{a}:{min(total, a + step - 1)}", res, samples) for a in range(1, total + 1, step)]
        t0 = time.time()
        for r in walk_chunk.starmap(args):
            print(f"[chunk] {r['frames']} in {r['seconds']} s", flush=True)
        print(f"[render] wall {round(time.time() - t0)} s")
    lab = json.loads(labels) if labels else []
    r = walk_encode.remote(job, lab)
    (dst / f"{job}.mp4").write_bytes(r["mp4"]); (dst / f"{job}_native.mp4").write_bytes(r["mp4_12"])
    print(f"[encode] {r['frames']} frames {r['size']} -> {dst / (job + '.mp4')}")


# ---------------------------------------------------------------- image-based tour proof of concept
TOUR_NODES = {"living": [655, 195, 1.5], "washitsu": [505, 200, 1.66]}
# straight walk through the open shoji; the step onto the tatami platform happens at the sill (x 533)
TOUR_WALK = [[655, 195, 1.5], [545, 199, 1.5], [527, 199.6, 1.63], [505, 200, 1.66]]


def heading(a, b):
    """yaw from plan north, clockwise, of the move a -> b (plan px, y down)"""
    import math
    return math.atan2(b[0] - a[0], a[1] - b[1])


@app.function(image=gpu_image, gpu="L40S", volumes={ASSETS: assets_vol}, timeout=3600, cpu=8.0, memory=32768)
def tour_job(variant: str, jobs: list) -> dict:
    t0 = time.time()
    fetch_assets(ASSETS); assets_vol.commit()
    import shutil
    out = pathlib.Path("/tmp/tour"); shutil.rmtree(out, ignore_errors=True); out.mkdir()   # containers are reused
    log = run_blender(["--variant", variant, "--shot", "tour", "--assets", ASSETS, "--plan", f"{REMOTE}/plan.json",
                       "--tour", json.dumps(jobs), "--outdir", str(out)])
    return {"files": {f.name: f.read_bytes() for f in out.iterdir() if f.is_file()}, "seconds": round(time.time() - t0, 1), "log": log}


@app.local_entrypoint()
def tour(variant: str = "wa", frames: int = 84, chunks: int = 3, turn: int = 72, tchunks: int = 3, probe: bool = False, only: str = "",
         panos: str = "living,washitsu"):
    """360 panoramas at the nodes, perspective walk clips (locked heading) both ways, a turntable of the cutaway model"""
    dst = HERE / "out" / "tour"; dst.mkdir(parents=True, exist_ok=True)
    pres, cres = ("1024x512", "640x360") if probe else ("4096x2048", "1920x1080")
    batches = [[{"kind": "pano", "name": n, "pos": TOUR_NODES[n], "res": pres, "samples": 32 if probe else 160} for n in panos.split(",")]]
    walks = {"living_washitsu": TOUR_WALK, "washitsu_living": TOUR_WALK[::-1]}
    step = -(-frames // chunks)
    for name, pts in walks.items():
        for c in range(0, frames, step):
            batches.append([{"kind": "path", "name": f"walk_{name}", "pts": pts, "n": frames, "first": c, "last": min(frames, c + step),
                             "hfov": 100.0, "yaw": heading(pts[0], pts[-1]), "ease": "smooth",
                             "res": cres, "samples": 16 if probe else 72}])
    tstep = -(-turn // tchunks)
    for c in range(0, turn, tstep):
        batches.append([{"kind": "turn", "name": "turn", "n": turn, "first": c, "last": min(turn, c + tstep), "nodes": TOUR_NODES,
                         "res": "640x400" if probe else "1440x900", "samples": 16 if probe else 96, "scale": 31.0}])
    if only:
        batches = [b for b in batches if b[0]["kind"] in only.split(",")]
    for r in tour_job.map([variant] * len(batches), batches):
        for name, data in r["files"].items():
            (dst / name).write_bytes(data)
        print(f"[tour] {len(r['files'])} files in {r['seconds']} s", flush=True)
