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
