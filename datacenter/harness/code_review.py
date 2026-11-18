#!/usr/bin/env python3
"""Blind code review of the Blender code each model wrote in a run (Gemini API, $gemini_key).

    python code_review.py --stage s3 --prompt s3-hard --runs RUN_A RUN_B [...] [--model gemini-4-carbon] [--tag hard]

The reviewer sees the task text and, per submission, every `bench exec` script in the order it ran, whether it
succeeded, and a short excerpt of its output. Submissions are relabelled X/Y/Z in random order.
Writes datacenter/judge/code-<stage>[-tag]/{review.json, mapping.json}.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import pathlib
import random
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PRICE = {"gemini-4-carbon": (2.0, 10.0), "gemini-4-argon": (2.0, 10.0), "gemini-3.8-flash": (0.825, 4.125)}
DIMS = ["spec_compliance", "derives_from_inputs", "self_verification", "code_quality", "efficiency"]

REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["scores", "bugs", "strengths", "summary"],
    "properties": {
        "scores": {"type": "object", "additionalProperties": False, "required": DIMS,
                   "properties": {d: {"type": "integer", "minimum": 1, "maximum": 5} for d in DIMS}},
        "bugs": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["severity", "where", "what"],
                                             "properties": {"severity": {"type": "string", "enum": ["high", "medium", "low"]},
                                                            "where": {"type": "string"}, "what": {"type": "string"}}}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
}
PAIR_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["better", "confidence", "reason"],
    "properties": {"better": {"type": "string", "enum": ["X", "Y", "tie"]},
                   "confidence": {"type": "string", "enum": ["low", "medium", "high"]}, "reason": {"type": "string"}},
}
RUBRIC = """You review the Blender Python a modelling agent wrote to complete a task. The agent could only act through a
`bench` tool: `bench exec FILE.py` ran a script inside a persistent Blender session (bpy available, scene state kept
between scripts). Below are the task and, in execution order, every script it ran, whether it succeeded, and an excerpt
of its output. Score each dimension 1-5 (5 = excellent):
- spec_compliance: does the code implement what the task asks (names, units, positions, required parts), as far as the
  code itself shows?
- derives_from_inputs: are values computed from the inputs (layout file, drawing, photos/cameras) rather than typed in
  by hand? Hand-typed values are fine when the task only provides an image; judge whether the derivation is sound.
- self_verification: does the agent check its own result (assertions, printed measurements, inspections) and act on it?
- code_quality: structure, naming, reuse, readability, clean-up of earlier attempts.
- efficiency: economy of the scene (linked duplicates / instancing / reasonable object counts) and of the process
  (few wasted or repeated scripts).
List concrete bugs (wrong maths, wrong axis or rotation, off-by-one, objects left behind, unused results), each with
severity and location (script number). Be specific; do not invent problems that the code does not show."""


def gather(run: pathlib.Path, max_chars=250_000) -> str:
    out, n = [], 0
    for line in (run / "bench_log.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e.get("cmd") != "exec" or "code" not in e:
            continue
        n += 1
        status = "ok" if e.get("ok") else "FAILED"
        o = (e.get("stdout") or "")[:800]
        err = (e.get("stderr") or "")[-800:]
        out.append(f"### script {n}: {(e.get('args') or ['?'])[0].split('/')[-1]} ({status})\n```python\n{e['code']}\n```\n"
                   + (f"stdout (excerpt):\n```\n{o}\n```\n" if o.strip() else "")
                   + (f"stderr (tail):\n```\n{err}\n```\n" if err.strip() else ""))
    text = "\n".join(out)
    if len(text) > max_chars:
        text = text[:max_chars // 2] + "\n\n[... middle scripts omitted for length ...]\n\n" + text[-max_chars // 2:]
    return f"{n} scripts ran.\n\n{text}"


def call(model, system, parts, schema):
    key = os.environ["gemini_key"]
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": t} for t in parts]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "thinkingConfig": {"thinkingLevel": "high"}}}
    r = None
    for attempt in range(8):
        try:
            r = requests.post(API.format(model=model), headers={"x-goog-api-key": key}, json=body, timeout=900)
        except requests.RequestException as e:  # proxy / connection blips: back off and retry
            print("network error, retrying:", type(e).__name__, flush=True)
            time.sleep(20 * (attempt + 1))
            continue
        if r.status_code == 200:
            d = r.json()
            try:
                txt = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"] if not p.get("thought"))
                u = d.get("usageMetadata", {})
                pin, pout = PRICE.get(model, (0, 0))
                cost = (u.get("promptTokenCount", 0) * pin + (u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)) * pout) / 1e6
                return json.loads(txt), cost
            except (KeyError, IndexError, json.JSONDecodeError):
                pass
        elif r.status_code == 400:
            raise SystemExit(f"rejected: {r.text[:800]}")
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"failed: {r.status_code if r is not None else 'network'} {r.text[:400] if r is not None else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--prompt", help="task prompt name in prompts/ (default: stage)")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--model", default="gemini-4-carbon")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    runs = [pathlib.Path(r).resolve() for r in a.runs]
    rng = random.SystemRandom()
    order = runs[:]
    rng.shuffle(order)
    L = "XYZW"
    task = (ROOT / "harness" / "prompts" / f"{a.prompt or a.stage}.md").read_text()
    system = "You are a strict, specific senior reviewer of 3D-automation code. You do not know which model wrote which submission."
    res = {"model": a.model, "stage": a.stage, "reviews": {}, "pairs": [], "cost_usd": 0.0}
    code = {L[i]: gather(r) for i, r in enumerate(order)}
    for i in range(len(order)):
        lab = L[i]
        g, c = call(a.model, system, [RUBRIC, "## The task\n" + task, f"## Submission {lab}\n" + code[lab],
                                      "Review submission " + lab + "."], REVIEW_SCHEMA)
        res["cost_usd"] += c
        res["reviews"][lab] = g
        print(lab, g["scores"], len(g["bugs"]), "bugs", flush=True)
    for i, j in itertools.combinations(range(len(order)), 2):
        x, y = (i, j) if rng.random() < 0.5 else (j, i)
        p, c = call(a.model, system, [RUBRIC, "## The task\n" + task, "## Submission X\n" + code[L[x]], "## Submission Y\n" + code[L[y]],
                                      "Which submission's code is better overall for this task?"], PAIR_SCHEMA)
        res["cost_usd"] += c
        p["X_is"], p["Y_is"] = L[x], L[y]
        res["pairs"].append(p)
        print("pair", L[x], "vs", L[y], p["better"], p["confidence"], flush=True)
    out = ROOT / "judge" / (f"code-{a.stage}" + (f"-{a.tag}" if a.tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    (out / "review.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (out / "mapping.json").write_text(json.dumps({L[i]: str(r) for i, r in enumerate(order)}, indent=1))
    print("cost", round(res["cost_usd"], 3))


if __name__ == "__main__":
    main()
