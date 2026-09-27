"""Bake photographic "plates" for each chapter on Modal.

Each chapter's fixed camera shot is rendered from the three.js scene (beauty, depth, water mask).
Here the beauty render is repainted with SDXL img2img, while a depth ControlNet locks the
geometry (bridge piers, arch, river banks) to the historically-dimensioned 3D model.

Behind an HTTP proxy (e.g. a Claude Code cloud sandbox) install the proxy extra first:
    pip install 'modal[api-proxy-support]'
Run (needs MODAL_TOKEN_ID / MODAL_TOKEN_SECRET):
    modal run plates/modal_plates.py --only "00_reopen,08_widen" --variants 2
Outputs: plates/raw/<id>_v<n>.jpg

Detail pass (after picking variants in plates/selection.json):
    modal run plates/modal_plates.py --detail
Crops every person / vehicle / tree / house / boat region found in plates/passes/<id>_ids.png,
upscales it to 1024 px, repaints it with a category- and era-specific prompt (depth ControlNet keeps
the silhouette), and pastes it back feathered. Output: plates/raw/<id>_v<n>d.jpg
"""
import io
import json
import os
import pathlib

import modal

ROOT = pathlib.Path(__file__).parent
app = modal.App("kawabata-plates")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.4.1", "diffusers==0.31.0", "transformers==4.46.3", "accelerate==1.1.1",
    "safetensors==0.4.5", "pillow==11.0.0", "numpy<2", "opencv-python-headless==4.10.0.84",
)
cache = modal.Volume.from_name("kawabata-hf-cache", create_if_missing=True)

BASE_MODEL = "SG161222/RealVisXL_V4.0"
CONTROLNET = "diffusers/controlnet-depth-sdxl-1.0"
CONTROLNET_EDGE = "diffusers/controlnet-canny-sdxl-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"


@app.cls(gpu="L40S", image=image, volumes={"/cache": cache}, timeout=3600, max_containers=4)
class Painter:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = "/cache"
        import torch
        from diffusers import (AutoencoderKL, ControlNetModel, DPMSolverMultistepScheduler,
                               StableDiffusionXLControlNetImg2ImgPipeline, StableDiffusionXLImg2ImgPipeline)
        cn = [ControlNetModel.from_pretrained(m, torch_dtype=torch.float16, cache_dir="/cache") for m in (CONTROLNET, CONTROLNET_EDGE)]
        vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16, cache_dir="/cache")
        self.pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
            BASE_MODEL, controlnet=cn, vae=vae, torch_dtype=torch.float16, cache_dir="/cache").to("cuda")
        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config, use_karras_sigmas=True)
        self.refine = StableDiffusionXLImg2ImgPipeline.from_pipe(self.pipe)
        from diffusers import StableDiffusionXLControlNetInpaintPipeline
        self.inpaint = StableDiffusionXLControlNetInpaintPipeline.from_pipe(self.pipe)
        cache.commit()

    @modal.method()
    def paint(self, beauty: bytes, depth: bytes, prompt: str, negative: str, strength: float,
              cn_scale: float, edge_scale: float, seed: int) -> bytes:
        import cv2
        import numpy as np
        import torch
        from PIL import Image
        W1, H1 = 1536, 864
        init = Image.open(io.BytesIO(beauty)).convert("RGB").resize((W1, H1), Image.LANCZOS)
        ctrl = Image.open(io.BytesIO(depth)).convert("RGB").resize((W1, H1), Image.BILINEAR)
        # edges of the 3D render lock the fine structure (arched pier openings, railings, arch truss)
        gray = cv2.cvtColor(np.asarray(init), cv2.COLOR_RGB2GRAY)
        edges = Image.fromarray(cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 60, 160)).convert("RGB")
        g = torch.Generator("cuda").manual_seed(seed)
        img = self.pipe(prompt=prompt, negative_prompt=negative,
                        image=init, control_image=[ctrl, edges],
                        strength=strength, controlnet_conditioning_scale=[cn_scale, edge_scale], control_guidance_end=[0.85, 0.7],
                        num_inference_steps=34, guidance_scale=5.0, generator=g).images[0]
        # second pass at full HD: low-strength refinement adds fine photographic texture
        img = self.refine(prompt=prompt, negative_prompt=negative, image=img.resize((1920, 1080), Image.LANCZOS),
                          strength=0.24, num_inference_steps=30, guidance_scale=4.5, generator=g).images[0]
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=92); return buf.getvalue()


    @modal.method()
    def detail(self, plate: bytes, ids: bytes, depth: bytes, cats: dict, negative: str, seed: int) -> bytes:
        """cats: {category: {"prompt", "strength", "max"}}; ids colours must match CAT_RGB."""
        import cv2
        import numpy as np
        import torch
        from PIL import Image, ImageFilter
        CAT_RGB = {"person": (255, 0, 0), "vehicle": (0, 255, 0), "tree": (0, 0, 255), "house": (255, 255, 0),
                   "building": (0, 255, 255), "boat": (255, 0, 255), "farm": (128, 0, 255)}
        img = Image.open(io.BytesIO(plate)).convert("RGB").resize((1920, 1080), Image.LANCZOS)
        idm = np.asarray(Image.open(io.BytesIO(ids)).convert("RGB").resize((1920, 1080), Image.NEAREST)).astype(np.int32)
        dep = Image.open(io.BytesIO(depth)).convert("RGB").resize((1920, 1080), Image.BILINEAR)
        blank = Image.new("RGB", (1024, 1024))
        g = torch.Generator("cuda").manual_seed(seed)
        H, W = 1080, 1920
        jobs = []
        for cat, cfg in cats.items():
            col = np.array(CAT_RGB[cat])
            m = (np.abs(idm - col).sum(-1) < 90).astype(np.uint8)
            if m.sum() < 40:
                continue
            grouped = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
            n, lab, st, _ = cv2.connectedComponentsWithStats(grouped)
            boxes = sorted([st[i] for i in range(1, n)], key=lambda b: -b[4])
            for x, y, w, h, area in boxes[: cfg.get("max", 6)]:
                if (m[y:y + h, x:x + w]).sum() < 30:
                    continue
                side = int(min(1024, max(160, max(w, h) * 1.5)))
                # large regions are covered by up to 3 tiles along their long side
                tiles_x = [x + w // 2] if w <= side else list(np.linspace(x + side // 2, x + w - side // 2, min(3, int(np.ceil(w / side)))).astype(int))
                tiles_y = [y + h // 2] if h <= side else list(np.linspace(y + side // 2, y + h - side // 2, min(2, int(np.ceil(h / side)))).astype(int))
                for cy in tiles_y:
                    for cx in tiles_x:
                        x0 = int(np.clip(cx - side // 2, 0, W - side)); y0 = int(np.clip(cy - side // 2, 0, H - min(side, H)))
                        jobs.append((cat, cfg, x0, y0, side))
        jobs.sort(key=lambda j: ["building", "house", "farm", "tree", "boat", "vehicle", "person"].index(j[0]))
        for cat, cfg, x0, y0, side in jobs[:26]:
            sideh = min(side, H)
            box = (x0, y0, x0 + side, y0 + sideh)
            col = np.array(CAT_RGB[cat])
            mm = (np.abs(idm[y0:y0 + sideh, x0:x0 + side] - col).sum(-1) < 90).astype(np.uint8) * 255
            if mm.sum() == 0:
                continue
            mm = cv2.dilate(mm, np.ones((5, 5), np.uint8))
            S = 1024
            crop = img.crop(box).resize((S, S), Image.LANCZOS)
            dcrop = dep.crop(box).resize((S, S), Image.BILINEAR)
            mask = Image.fromarray(mm).resize((S, S), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
            out = self.inpaint(prompt=cfg["prompt"], negative_prompt=negative, image=crop, mask_image=mask,
                               control_image=[dcrop, blank], controlnet_conditioning_scale=[0.55, 0.0],
                               strength=cfg.get("strength", 0.55), num_inference_steps=26, guidance_scale=5.0,
                               width=S, height=S, generator=g).images[0]
            out = out.resize((side, sideh), Image.LANCZOS)
            feather = Image.fromarray(cv2.dilate(mm, np.ones((3, 3), np.uint8))).filter(ImageFilter.GaussianBlur(2.5))
            img.paste(out, box[:2], feather)
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=93); return buf.getvalue()


@app.local_entrypoint()
def main(only: str = "", variants: int = 2, detail: bool = False):
    spec = json.loads((ROOT / "prompts.json").read_text())
    ids = [s.strip() for s in only.split(",") if s.strip()] or list(spec["plates"].keys())
    out = ROOT / "raw"; out.mkdir(exist_ok=True)
    if detail:
        sel = json.loads((ROOT / "selection.json").read_text())
        djobs = []
        for pid in ids:
            v = sel.get(pid)
            idsf = ROOT / "passes" / f"{pid}_ids.png"
            if v is None or not idsf.exists():
                continue
            p = spec["plates"][pid]; era = p["era"]
            cats = {c: {"prompt": f'{d["prompt"][era]}, {spec["eras"][era]["style"]}', "strength": d.get("strength", .55), "max": d.get("max", 6)}
                    for c, d in spec["detail"].items() if era in d["prompt"]}
            neg = spec["negative"] + (", " + spec["eras"][era]["negative"] if spec["eras"][era].get("negative") else "")
            djobs.append((pid, v, ((out / f"{pid}_v{v}.jpg").read_bytes(), idsf.read_bytes(), (ROOT / "passes" / f"{pid}_depth.png").read_bytes(), cats, neg, 1945 + sum(map(ord, pid)))))
        for (pid, v, _), img in zip(djobs, Painter().detail.starmap([j[2] for j in djobs])):
            (out / f"{pid}_v{v}d.jpg").write_bytes(img)
            print("wrote detail", pid, v, len(img))
        return
    jobs = []
    for pid in ids:
        p = spec["plates"][pid]
        era = spec["eras"][p["era"]]
        prompt = f'{p["prompt"]}, {era["style"]}'
        negative = spec["negative"] + (", " + era["negative"] if era.get("negative") else "")
        beauty = (ROOT / "passes" / f"{pid}_beauty.jpg").read_bytes()
        depth = (ROOT / "passes" / f"{pid}_depth.png").read_bytes()
        for v in range(variants):
            strength = min(0.82, p.get("strength", era["strength"]) + 0.1 * v)  # v1 repaints more freely
            jobs.append((pid, v, (beauty, depth, prompt, negative, strength,
                                  p.get("cn", 0.7), p.get("edge", 0.45), 1937 + 101 * v + sum(map(ord, pid)))))
    painter = Painter()
    for (pid, v, _), img in zip(jobs, painter.paint.starmap([j[2] for j in jobs])):
        (out / f"{pid}_v{v}.jpg").write_bytes(img)
        print("wrote", pid, v, len(img))
