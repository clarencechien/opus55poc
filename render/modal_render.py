"""Render chapter plates with Blender Cycles on Modal (portable Blender 4.2 LTS, headless).

Physically based path tracing with CC0 Poly Haven PBR textures, HDRI skies and tree models.
The approach (PBR box-projected scans, bevelled edges, HDRI + aligned sun, mist haze, AgX) follows
pirrer/meiji-bridge-3d (MIT); the geometry here is the Kawabata Bridge model of this repo.

    pip install 'modal[api-proxy-support]'          # behind an HTTP proxy
    modal run render/modal_render.py --shots open,reopen
    modal run render/modal_render.py --shots open --res 960x540 --samples 32    # quick test

Outputs: render/out/<shot>.png (+ <shot>_depth.png, <shot>_ids.png for the AI detail pass)
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

import modal

HERE = pathlib.Path(__file__).resolve().parent
REMOTE = "/root/render"
BLENDER_VERSION = "4.2.23"
BLENDER_URL = f"https://download.blender.org/release/Blender4.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "curl", "xz-utils", "libx11-6", "libxi6", "libxxf86vm1", "libxfixes3", "libxrender1",
        "libxkbcommon0", "libgl1", "libglu1-mesa", "libegl1", "libsm6", "libice6", "libgomp1",
        "libxcursor1", "libxinerama1", "libxrandr2", "libwayland-client0", "libdbus-1-3",
    )
    .run_commands(
        f"curl -fsSL {BLENDER_URL} -o /tmp/blender.tar.xz",
        "mkdir -p /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/blender.tar.xz",
        "/opt/blender/blender --version",
    )
    .pip_install("requests==2.32.3")
    .add_local_dir(str(HERE), REMOTE, ignore=["out", "__pycache__"])
)
app = modal.App("kawabata-cycles", image=image)
assets_vol = modal.Volume.from_name("kawabata-polyhaven", create_if_missing=True)
ASSETS = "/assets"

TEXTURES = ["rough_concrete", "dirty_concrete", "concrete_wall_004", "green_metal_rust", "rusty_metal_02",
            "painted_metal_shutter", "brown_planks_05", "weathered_planks", "coast_sand_01", "aerial_grass_rock",
            "sparse_grass", "brown_mud_leaves_01", "clay_roof_tiles", "roof_tiles", "plastered_wall_02",
            "asphalt_02", "red_brick_03", "gravelly_sand", "river_small_rocks", "metal_plate"]
HDRIS = [("kloofendal_48d_partly_cloudy_puresky", "4k"), ("qwantani_night_puresky", "4k")]
MODELS = ["island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02"]
MAPS = ["Diffuse", "nor_gl", "Rough"]


def fetch_assets(root: str) -> None:
    import requests
    s = requests.Session(); s.headers["User-Agent"] = "kawabata-bridge-render/1.0"

    def get(url, dst):
        dst = pathlib.Path(dst)
        if dst.exists() and dst.stat().st_size > 0:
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        r = s.get(url, timeout=300); r.raise_for_status()
        dst.with_suffix(dst.suffix + ".part").write_bytes(r.content)
        dst.with_suffix(dst.suffix + ".part").rename(dst)
        return True

    files = lambda aid: s.get(f"https://api.polyhaven.com/files/{aid}", timeout=60).json()
    new = 0
    for aid in TEXTURES:
        d = None
        for m in MAPS:
            dst = pathlib.Path(root) / "textures" / aid / f"{aid}_{m}_2k.jpg"
            if dst.exists():
                continue
            d = d or files(aid)
            if m in d and "2k" in d[m] and "jpg" in d[m]["2k"]:
                new += get(d[m]["2k"]["jpg"]["url"], dst)
    for aid, res in HDRIS:
        dst = pathlib.Path(root) / "hdri" / f"{aid}_{res}.hdr"
        if not dst.exists():
            new += get(files(aid)["hdri"][res]["hdr"]["url"], dst)
    for aid in MODELS:
        base = pathlib.Path(root) / "models" / aid
        if (base / f"{aid}_1k.blend").exists():
            continue
        b = files(aid)["blend"]["1k"]["blend"]
        for rel, inc in b.get("include", {}).items():
            get(inc["url"], base / rel)
        new += get(b["url"], base / f"{aid}_1k.blend")
    print(f"[assets] {new} new files", flush=True)


@app.function(gpu="L40S", volumes={ASSETS: assets_vol}, timeout=3600, cpu=8.0, memory=32768)
def render(shot: str, res: str, samples: int, extra: list[str], name: str = "") -> dict:
    t0 = time.time()
    fetch_assets(ASSETS)
    assets_vol.commit()
    out = pathlib.Path("/tmp/out"); out.mkdir(exist_ok=True)
    cmd = ["/opt/blender/blender", "-b", "--python-exit-code", "1", "--python", f"{REMOTE}/kawabata_scene.py", "--",
           "--shot", shot, "--assets", ASSETS, "--out", str(out / f"{name or shot}.png"), "--res", res, "--samples", str(samples), *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, text=True, capture_output=True)
    log = [l for l in p.stdout.splitlines() if not l.startswith(("Fra:", "Read prefs")) and "| Sample" not in l]
    fra = [l for l in p.stdout.splitlines() if l.startswith("Fra:")]
    log += fra[-3:]
    print("\n".join(log[-80:]), flush=True)
    if p.returncode != 0:
        print(p.stderr[-6000:], flush=True)
        raise RuntimeError(f"blender exited {p.returncode}")
    res_files = {f.name: f.read_bytes() for f in out.glob(f"{name or shot}*.png")}
    return {"files": res_files, "seconds": round(time.time() - t0, 1), "log": "\n".join(log[-40:])}


@app.local_entrypoint()
def main(shots: str = "open,reopen", res: str = "1920x1080", samples: int = 256, extra: str = "", cams: str = ""):
    dst = HERE / "out"; dst.mkdir(exist_ok=True)
    names = [s.strip() for s in shots.split(",") if s.strip()]
    args = [(n, res, samples, extra.split() if extra else [], n) for n in names]
    if cams:  # camera trials: every shot × every "x,y,z,tx,ty,tz,lens"
        args = [(n, res, samples, (extra.split() if extra else []) + [f"--cam={c}"], f"{n}_c{i}")
                for n in names for i, c in enumerate(cams.split(";"))]
        names = [a[4] for a in args]
    for n, r in zip(names, render.starmap(args)):
        for fname, data in r["files"].items():
            (dst / fname).write_bytes(data)
        print(f"[done] {n}: {sorted(r['files'])} in {r['seconds']} s")
        print(r["log"][-1500:])


# ============================================================== documentary clips (animation)
# Frames go to a Volume in parallel GPU chunks; a CPU function adds captions and encodes H.264.
frames_vol = modal.Volume.from_name("kawabata-frames", create_if_missing=True)
FRAMES = "/frames"
FONT_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
FONT_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
enc_image = (modal.Image.debian_slim(python_version="3.11")
             .apt_install("ffmpeg", "fonts-noto-cjk")
             .pip_install("pillow==11.0.0", "numpy==2.1.3")
             .add_local_dir(str(HERE), REMOTE, ignore=["out", "__pycache__"]))

# (first frame, last frame, headline, sub-line) — 30 fps
CAPTIONS = {
    "build": [
        (20, 228, "1935.06.01　川端橋動工", "13 座雙柱式拱型鋼筋混凝土橋墩，自新店溪河床立起"),
        (250, 468, "架設鋼鈑梁", "14 跨上承式鋼鈑梁，三菱重工業神戶造船所製造"),
        (560, 742, "1937.03.25　川端橋開通", "全長 300.56 m・寬 5.2 m　臺北市川端町 ⇄ 中和庄永和"),
    ],
    "night": [
        (30, 228, "卸甲・抬升・還原", "拆除戰後拓寬構造，只留日治原橋並整體抬升；鋼梁補強、護欄依原樣復刻"),
        (262, 468, "新橋如琴、舊橋如瑟", "一旁的新中正橋：三點式透空鋼拱，拱跨 215 m・拱高 50 m"),
        (540, 742, "2026.09.21　川端橋修復啟用", "人行與自行車橋｜臺北 紀州庵文學森林 ⇄ 永和 楊三郎美術館"),
    ],
}
TAGS = {"build": "川端橋　1935–1937　建橋", "night": "川端橋　2026　修復啟用"}


@app.function(gpu="L40S", volumes={ASSETS: assets_vol, FRAMES: frames_vol}, timeout=6 * 3600, cpu=8.0, memory=32768)
def render_chunk(job: str, shot: str, first: int, last: int, res: str, samples: int) -> dict:
    t0 = time.time()
    fetch_assets(ASSETS)
    outdir = pathlib.Path(FRAMES) / job; outdir.mkdir(parents=True, exist_ok=True)
    cmd = ["/opt/blender/blender", "-b", "--python-exit-code", "1", "--python", f"{REMOTE}/kawabata_scene.py", "--",
           "--shot", shot, "--assets", ASSETS, "--out", f"/tmp/{job}.png", "--res", res, "--samples", str(samples),
           "--frames", f"{first}:{last}", "--outdir", str(outdir)]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = []
    for line in p.stdout:
        if line.startswith("Saved:") or "Traceback" in line or "Error" in line or line.startswith(("[", "objects:")):
            print(line.rstrip(), flush=True)
        tail = (tail + [line.rstrip()])[-60:]
    p.wait()
    frames_vol.commit()
    if p.returncode != 0:
        raise RuntimeError(f"blender exited {p.returncode}\n" + "\n".join(tail))
    return {"first": first, "last": last, "seconds": round(time.time() - t0, 1)}


def _font(path, size, want="TC"):
    from PIL import ImageFont
    for i in range(10):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[0].endswith(want):
            return f
    return ImageFont.truetype(path, size)


@app.function(image=enc_image, volumes={FRAMES: frames_vol}, timeout=3600, cpu=8.0, memory=16384)
def encode(job: str, clip: str, fps: int = 30, crf: int = 18) -> dict:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    frames_vol.reload()
    src = sorted((pathlib.Path(FRAMES) / job).glob("f_*.png"))
    assert src, f"no frames for {job}"
    W, H = Image.open(src[0]).size
    s = H / 1080
    head, sub, small = _font(FONT_SERIF, int(62 * s)), _font(FONT_SANS, int(30 * s)), _font(FONT_SANS, int(22 * s))
    print("fonts:", head.getname(), sub.getname(), flush=True)

    def card(h, t):
        """Lower-third: headline + thin rule + sub-line, with a soft shadow."""
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x, y = int(96 * s), int(H - 250 * s)
        d.text((x, y), h, font=head, fill=(255, 250, 238, 255))
        hb = d.textbbox((x, y), h, font=head)
        d.rectangle((x, hb[3] + int(18 * s), x + int(64 * s), hb[3] + int(21 * s)), fill=(214, 170, 96, 255))
        d.text((x, hb[3] + int(36 * s)), t, font=sub, fill=(236, 232, 222, 255))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(6 * s)).point(lambda v: int(v * 0.75)))
        return Image.alpha_composite(sh, im)

    # bottom gradient so white type always reads, plus a constant chapter tag and credit
    grad = np.zeros((H, W, 4), np.uint8)
    ramp = np.clip((np.arange(H) - H * 0.55) / (H * 0.45), 0, 1) ** 1.6
    grad[..., 3] = (ramp * 150).astype(np.uint8)[:, None]
    base = Image.fromarray(grad, "RGBA"); d = ImageDraw.Draw(base)
    d.text((int(96 * s), int(64 * s)), TAGS.get(clip, ""), font=small, fill=(255, 255, 255, 200))
    cr = "3D 重建示意・Blender Cycles"
    d.text((W - int(96 * s) - d.textlength(cr, font=small), H - int(64 * s)), cr, font=small, fill=(255, 255, 255, 150))
    cards = [(a, b, card(h, t)) for a, b, h, t in CAPTIONS.get(clip, [])]

    out = pathlib.Path("/tmp") / f"{job}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
                           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    n = len(src); fade = int(0.8 * fps); poster = None
    for k, fp in enumerate(src):
        f = int(fp.stem.split("_")[1])
        im = Image.open(fp).convert("RGBA")
        im = Image.alpha_composite(im, base)
        for a, b, c in cards:
            if a <= f <= b:
                al = min(1.0, (f - a) / fade, (b - f) / fade)
                al = al * al * (3 - 2 * al)
                im = Image.alpha_composite(im, c if al >= 1 else Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), c, al))
        g = min(1.0, k / fade, (n - 1 - k) / fade)   # fade in from / out to black
        rgb = im.convert("RGB")
        if g < 1:
            rgb = Image.blend(Image.new("RGB", (W, H)), rgb, max(g, 0))
        if f == 700:
            poster = rgb
        ff.stdin.write(rgb.tobytes())
    ff.stdin.close(); ff.wait()
    import io
    buf = io.BytesIO(); (poster or rgb).save(buf, "JPEG", quality=90)
    return {"mp4": out.read_bytes(), "poster": buf.getvalue(), "frames": n, "size": f"{W}x{H}"}


@app.function(volumes={FRAMES: frames_vol}, timeout=600)
def fetch_frames(job: str, frames: list[int]) -> dict:
    frames_vol.reload()
    d = pathlib.Path(FRAMES) / job
    return {f: (d / f"f_{f:04d}.png").read_bytes() for f in frames if (d / f"f_{f:04d}.png").exists()}


@app.local_entrypoint()
def anim(clip: str = "build", job: str = "", res: str = "1920x1080", samples: int = 128, chunks: int = 10,
         frames: str = "1:750", probe: str = "", encode_only: bool = False):
    """Render a documentary clip in parallel chunks, then caption + encode.

    --probe 60,200,330,500,700   renders only those single frames (quick check) and downloads them.
    """
    dst = HERE / "out"; dst.mkdir(exist_ok=True)
    job = job or f"{clip}_{res}_{samples}"
    if probe:
        fs = [int(v) for v in probe.split(",")]
        for r in render_chunk.starmap([(job, clip, f, f, res, samples) for f in fs]):
            print("[probe]", r)
        for f, data in fetch_frames.remote(job, fs).items():
            (dst / f"{job}_f{f:04d}.png").write_bytes(data)
        print("probe frames in", dst)
        return
    if not encode_only:
        a, b = (int(v) for v in frames.split(":"))
        step = -(-(b - a + 1) // chunks)
        jobs = [(job, clip, s, min(b, s + step - 1), res, samples) for s in range(a, b + 1, step)]
        t0 = time.time()
        for r in render_chunk.starmap(jobs):
            print(f"[chunk] {r['first']}–{r['last']} in {r['seconds']} s", flush=True)
        print(f"[render] wall {round(time.time() - t0)} s")
    r = encode.remote(job, clip)
    (dst / f"pilot_{clip}.mp4").write_bytes(r["mp4"]); (dst / f"pilot_{clip}_poster.jpg").write_bytes(r["poster"])
    print(f"[encode] {r['frames']} frames {r['size']} → {dst / f'pilot_{clip}.mp4'}")
