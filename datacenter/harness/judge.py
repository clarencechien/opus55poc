#!/usr/bin/env python3
"""Independent second grader: a third model family (Gemini, called directly with $gemini_key) reviews blinded submissions.

    python judge.py --stage s1 --scenario easy --runs RUN_A RUN_B [--model gemini-3.8-flash] [--repeats 2]

The judge never sees the answer key or the first grader's scores. It gets the original input, each
submission's deliverables, and fixed review renders, under neutral labels in a random order:
  - absolute grading of each submission against the stage rubric (repeated for a consistency check);
  - one pairwise comparison.
Writes datacenter/judge/<stage>-<scenario>/{judge.json, mapping.json}.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import random
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# rough cost estimate per 1M tokens (input, output incl. thinking) for gemini-3.8-flash
PRICE = {"gemini-3.8-flash": (0.825, 4.125)}

RUBRIC = {
    "s1": """The task given to the modeller: read the equipment layout plan (first image) and produce
(1) layout_pred.json, all plan elements in mm (origin at grid A/1, +x east, +y north): grid line positions; room inner-face
polygon, wall thickness, clear height, raised-floor height; columns; doors (centre on wall centreline, width, wall);
CRAH units and racks (centre, [width, depth], facing = compass direction of the equipment front); cold and hot aisles as
rectangles between rack faces, or between a rack face and a wall;
(2) a Blender room shell in metres: Wall_* objects from z=0 to raised floor + clear height with door openings,
Column_<id> objects, and a RaisedFloor object with its top at the raised-floor height. Racks/CRAH must NOT be modelled.

Grade it yourself from the drawing. Work out the correct values from the drawing's grid, dimension chains, notes and legend,
then check the submission. Score these categories (maximum in brackets):
  racks [50]: count, centre positions, facing, ids, sizes
  room [10]: inner polygon, wall thickness, clear height, raised-floor height
  columns [5], crah [5] (position + facing), doors [5] (position + width)
  aisles [10]: cold/hot classification and extents
  shell [15]: the 3D renders: walls, door opening, heights, raised floor, columns, nothing extra
Images after the plan: a redraw of the submission's layout_pred.json in the same drawing style (if it matches the
original plan, the numbers are right), then a top and an isometric render of the Blender shell.""",
}

GRADE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["checks", "category_scores", "total", "summary"],
    "properties": {
        "checks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["category", "item", "verdict", "note"],
            "properties": {"category": {"type": "string", "enum": ["racks", "room", "columns", "crah", "doors", "aisles", "shell"]},
                           "item": {"type": "string"},
                           "verdict": {"type": "string", "enum": ["correct", "minor_error", "wrong", "missing", "ambiguous"]},
                           "note": {"type": "string"}}}},
        "category_scores": {"type": "object", "additionalProperties": False,
                            "required": ["racks", "room", "columns", "crah", "doors", "aisles", "shell"],
                            "properties": {k: {"type": "number"} for k in
                                           ["racks", "room", "columns", "crah", "doors", "aisles", "shell"]}},
        "total": {"type": "number"},
        "summary": {"type": "string"},
    },
}
PAIR_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["better", "confidence", "per_category", "reason"],
    "properties": {
        "better": {"type": "string", "enum": ["X", "Y", "tie"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "per_category": {"type": "object", "additionalProperties": False,
                         "required": ["racks", "room", "columns", "crah", "doors", "aisles", "shell"],
                         "properties": {k: {"type": "string", "enum": ["X", "Y", "tie"]} for k in
                                        ["racks", "room", "columns", "crah", "doors", "aisles", "shell"]}},
        "reason": {"type": "string"},
    },
}


MAXES = {"s1": {"racks": 50, "room": 10, "columns": 5, "crah": 5, "doors": 5, "aisles": 10, "shell": 15}}
CREDIT = {"correct": 1.0, "ambiguous": 1.0, "minor_error": 0.5, "wrong": 0.0, "missing": 0.0}


def derived_score(stage, grade):
    """Score from the judge's own per-item verdicts (its free-form numbers proved poorly calibrated)."""
    out = {}
    for cat, mx in MAXES[stage].items():
        items = [c for c in grade["checks"] if c["category"] == cat]
        out[cat] = round(mx * sum(CREDIT[c["verdict"]] for c in items) / len(items), 2) if items else None
    have = [v for v in out.values() if v is not None]
    out["total"] = round(sum(have) * 100 / sum(MAXES[stage][k] for k, v in out.items() if k != "total" and v is not None), 2) if have else None
    return out


def img(path: pathlib.Path):
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()}}


def submission_parts(label: str, run: pathlib.Path):
    rv = run / "review"
    layout = (run / "layout_pred.json").read_text() if (run / "layout_pred.json").exists() else "(missing)"
    parts = [{"type": "text", "text": f"--- Submission {label}: layout_pred.json ---\n{layout}"}]
    for name, cap in (("redrawn_plan.png", "redraw of its layout_pred.json"), ("review_top.png", "Blender shell, top view"),
                      ("review_iso.png", "Blender shell, isometric view")):
        if (rv / name).exists():
            parts += [{"type": "text", "text": f"Submission {label}: {cap}"}, img(rv / name)]
    return parts


def to_gemini(parts):
    out = []
    for p in parts:
        if p["type"] == "text":
            out.append({"text": p["text"]})
        else:
            head, data = p["image_url"]["url"].split(",", 1)
            out.append({"inline_data": {"mime_type": head[5:].split(";")[0], "data": data}})
    return out


def call(model, messages, schema, name):
    key = os.environ["gemini_key"]
    system = messages[0]["content"]
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": to_gemini(messages[1]["content"])}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "thinkingConfig": {"thinkingLevel": "high"}}}
    r = None
    for attempt in range(5):
        r = requests.post(API.format(model=model), headers={"x-goog-api-key": key}, json=body, timeout=900)
        if r.status_code == 200:
            d = r.json()
            try:
                txt = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"] if not p.get("thought"))
                u = d.get("usageMetadata", {})
                pin, pout = PRICE.get(model, (0, 0))
                out_tok = u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
                u["cost"] = (u.get("promptTokenCount", 0) * pin + out_tok * pout) / 1e6
                return json.loads(txt), u
            except (KeyError, IndexError, json.JSONDecodeError):
                pass
        elif r.status_code == 400:
            raise SystemExit(f"judge call rejected: {r.text[:800]}")
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"judge call failed: {r.status_code if r is not None else '-'} {r.text[:500] if r is not None else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="s1")
    ap.add_argument("--scenario", default="easy")
    ap.add_argument("--runs", nargs=2, required=True)
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--repeats", type=int, default=2)
    a = ap.parse_args()
    runs = [pathlib.Path(r).resolve() for r in a.runs]
    rng = random.SystemRandom()
    order = runs[:]
    rng.shuffle(order)
    mapping = {"X": str(order[0]), "Y": str(order[1])}
    outdir = ROOT / "judge" / f"{a.stage}-{a.scenario}"
    outdir.mkdir(parents=True, exist_ok=True)
    plan = ROOT / "inputs" / a.scenario / "plan.png"
    sysmsg = ("You are an independent reviewer of 3D modelling submissions. You have no answer key: derive the correct "
              "answer from the inputs yourself, be strict and specific, and mark anything genuinely ambiguous in the "
              "drawing as 'ambiguous' rather than wrong.")
    result = {"model": a.model, "api": "Gemini API (direct)", "cost_note": "estimated from token counts", "absolute": {"X": [], "Y": []}, "pairwise": None, "cost_usd": 0.0}
    for label, run in (("X", order[0]), ("Y", order[1])):
        for k in range(a.repeats):
            msgs = [{"role": "system", "content": sysmsg},
                    {"role": "user", "content": [{"type": "text", "text": RUBRIC[a.stage] + "\n\nThe original plan:"}, img(plan)]
                     + submission_parts(label, run)
                     + [{"type": "text", "text": "Grade this submission. List one check per thing you verified (several per category; for racks cover count, positions, facing, ids, sizes), each tagged with its category. Category scores must not exceed their maxima; total = their sum."}]}]
            g, u = call(a.model, msgs, GRADE_SCHEMA, "grade")
            result["cost_usd"] += float(u.get("cost") or 0)
            g["derived"] = derived_score(a.stage, g)
            result["absolute"][label].append(g)
            print(label, k, "raw", g["total"], "derived", g["derived"], flush=True)
    msgs = [{"role": "system", "content": sysmsg},
            {"role": "user", "content": [{"type": "text", "text": RUBRIC[a.stage] + "\n\nThe original plan:"}, img(plan)]
             + submission_parts("X", order[0]) + submission_parts("Y", order[1])
             + [{"type": "text", "text": "Compare submissions X and Y. Which is better overall and per category?"}]}]
    p, u = call(a.model, msgs, PAIR_SCHEMA, "pairwise")
    result["cost_usd"] += float(u.get("cost") or 0)
    result["pairwise"] = p
    print("pairwise", p["better"], p["confidence"], p["per_category"], flush=True)
    (outdir / "judge.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    (outdir / "mapping.json").write_text(json.dumps(mapping, indent=1))
    print("cost", round(result["cost_usd"], 4))


if __name__ == "__main__":
    main()
