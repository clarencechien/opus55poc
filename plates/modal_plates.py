"""Bake photographic "plates" for each chapter on Modal.

Each chapter's fixed camera shot is rendered from the three.js scene (beauty, depth, water mask).
Here the beauty render is repainted with SDXL img2img, while a depth ControlNet locks the
geometry (bridge piers, arch, river banks) to the historically-dimensioned 3D model.

Behind an HTTP proxy (e.g. a Claude Code cloud sandbox) install the proxy extra first:
    pip install 'modal[api-proxy-support]'
Run (needs MODAL_TOKEN_ID / MODAL_TOKEN_SECRET):
    modal run plates/modal_plates.py --only "00_reopen,08_widen" --variants 2
Outputs: plates/raw/<id>_v<n>.jpg
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


@app.cls(gpu="L40S", image=image, volumes={"/cache": cache}, timeout=3600, max_containers=2)
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


@app.local_entrypoint()
def main(only: str = "", variants: int = 2):
    spec = json.loads((ROOT / "prompts.json").read_text())
    ids = [s.strip() for s in only.split(",") if s.strip()] or list(spec["plates"].keys())
    out = ROOT / "raw"; out.mkdir(exist_ok=True)
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
