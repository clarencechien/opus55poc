"""Interior pipeline on Modal: plan rasterizing (CPU) and Blender Cycles renders / lightmap bakes (GPU).

    pip install 'modal[api-proxy-support]'          # behind an HTTP proxy
    modal run interior/modal_interior.py::plan                   # out/plan_empty.png from out/plan_empty.svg
    modal run interior/modal_interior.py::render --variant empty --shots axo,living
    modal run interior/modal_interior.py::render --variant wa --shots living,washitsu,master --res 1920x1080 --samples 512
    modal run interior/modal_interior.py::bake --variant wa        # viewer/<variant>.glb with baked lighting
"""
from __future__ import annotations

import pathlib
import subprocess
import time

import modal

HERE = pathlib.Path(__file__).resolve().parent
REMOTE = "/root/interior"
BLENDER_VERSION = "4.2.23"
BLENDER_URL = f"https://download.blender.org/release/Blender4.2/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
IGNORE = ["out", "viewer", "ref", "renders", "__pycache__", "*.webp", "*.html"]

cpu_image = (modal.Image.debian_slim(python_version="3.11")
             .apt_install("librsvg2-bin", "fonts-noto-cjk")
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
MODELS = ["potted_plant_01", "potted_plant_04", "tea_set_01", "ceramic_vase_02", "rock_moss_set_01", "shrub_02", "tree_small_02"]
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
        if (base / f"{aid}_1k.blend").exists():
            continue
        try:
            b = s.get(f"https://api.polyhaven.com/files/{aid}", timeout=60).json()["blend"]["1k"]["blend"]
            for rel, inc in b.get("include", {}).items():
                new += get(inc["url"], base / rel)
            new += get(b["url"], base / f"{aid}_1k.blend")
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
    name = f"{variant}_{shot}" + ("_night" if "--night" in extra else "")
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
