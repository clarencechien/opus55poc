"""Bake photographic "plates" for each chapter on Modal.

Each chapter's fixed camera shot is rendered from the three.js scene (beauty, depth, water mask).
Here the beauty render is repainted with SDXL img2img, while a depth ControlNet locks the
geometry (bridge piers, arch, river banks) to the historically-dimensioned 3D model.

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
    "safetensors==0.4.5", "pillow==11.0.0", "numpy<2",
)
cache = modal.Volume.from_name("kawabata-hf-cache", create_if_missing=True)

BASE_MODEL = "SG161222/RealVisXL_V4.0"
CONTROLNET = "diffusers/controlnet-depth-sdxl-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"


@app.cls(gpu="L40S", image=image, volumes={"/cache": cache}, timeout=3600, max_containers=2)
class Painter:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = "/cache"
        import torch
        from diffusers import (AutoencoderKL, ControlNetModel, DPMSolverMultistepScheduler,
                               StableDiffusionXLControlNetImg2ImgPipeline, StableDiffusionXLImg2ImgPipeline)
        cn = ControlNetModel.from_pretrained(CONTROLNET, torch_dtype=torch.float16, cache_dir="/cache")
        vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16, cache_dir="/cache")
        self.pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
            BASE_MODEL, controlnet=cn, vae=vae, torch_dtype=torch.float16, cache_dir="/cache").to("cuda")
        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config, use_karras_sigmas=True)
        self.refine = StableDiffusionXLImg2ImgPipeline.from_pipe(self.pipe)
        cache.commit()

    @modal.method()
    def paint(self, beauty: bytes, depth: bytes, prompt: str, negative: str, strength: float,
              cn_scale: float, seed: int) -> bytes:
        import torch
        from PIL import Image
        init = Image.open(io.BytesIO(beauty)).convert("RGB")
        ctrl = Image.open(io.BytesIO(depth)).convert("RGB")
        W1, H1 = 1536, 864
        g = torch.Generator("cuda").manual_seed(seed)
        img = self.pipe(prompt=prompt, negative_prompt=negative,
                        image=init.resize((W1, H1), Image.LANCZOS), control_image=ctrl.resize((W1, H1), Image.BILINEAR),
                        strength=strength, controlnet_conditioning_scale=cn_scale, control_guidance_end=0.85,
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
            jobs.append((pid, v, (beauty, depth, prompt, negative, p.get("strength", era["strength"]),
                                  p.get("cn", 0.7), 1937 + 101 * v + sum(map(ord, pid)))))
    painter = Painter()
    for (pid, v, _), img in zip(jobs, painter.paint.starmap([j[2] for j in jobs])):
        (out / f"{pid}_v{v}.jpg").write_bytes(img)
        print("wrote", pid, v, len(img))
