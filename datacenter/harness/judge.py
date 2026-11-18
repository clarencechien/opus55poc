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
PRICE = {"gemini-3.8-flash": (0.825, 4.125), "gemini-4-argon": (2.0, 10.0), "gemini-4-carbon": (2.0, 10.0), "gemini-4-hydrogen": (1.5, 7.5)}

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

S2_ITEMS = {
    "A": ["perforated_front_door", "perforated_rear_door", "solid_side_panels", "top_panel_cable_entry",
          "feet_or_casters", "mounting_rails", "servers_varied_heights", "blanking_panels", "status_leds", "dark_finish"],
    "B": ["four_posts_with_holes_or_rails", "top_and_bottom_frame", "cable_management", "partial_population",
          "no_doors_or_side_panels"],
}
RUBRIC["s2"] = """The task given to the modeller: from the reference photos (first images), build two rack models in Blender.
Rack A, a closed server cabinet like the black cabinets in the NERSC photos: 600 W x 1200 D x 2000 H mm, perforated front
and rear doors, solid side panels, top panel with cable-entry openings, leveling feet or casters, 19-inch mounting rails,
servers of varied heights visible through the front door with blanking panels and status LEDs, dark finish.
Rack B, an open 4-post frame like the open racks on the raised floor: 600 W x 1000 D x 2000 H mm, four posts with holes or
rails, top and bottom frame, cable management, partially populated (equipment, patch panels, cabling, open space), no doors
or side panels. Both stand on the floor with the front facing the viewer of the 'front' render.
You get renders of each rack (Cycles renders with lighting and materials when available, including a view with the doors
hidden so the interior is visible).
Judge each checklist item as present / partial / absent from what the renders show, and rate how closely each rack
resembles its reference photos (1 = not at all, 5 = convincingly the same kind of equipment), allowing for the flat
preview shading."""
S2_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["checks", "likeness", "summary"],
    "properties": {
        "checks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["rack", "item", "verdict", "note"],
            "properties": {"rack": {"type": "string", "enum": ["A", "B"]},
                           "item": {"type": "string", "enum": S2_ITEMS["A"] + S2_ITEMS["B"]},
                           "verdict": {"type": "string", "enum": ["present", "partial", "absent"]},
                           "note": {"type": "string"}}}},
        "likeness": {"type": "object", "additionalProperties": False, "required": ["A", "B"],
                     "properties": {"A": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "B": {"type": "integer", "minimum": 1, "maximum": 5}}},
        "summary": {"type": "string"},
    },
}
S2_PAIR_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["better_rack_A", "better_rack_B", "better_overall", "confidence", "reason"],
    "properties": {k: {"type": "string", "enum": ["X", "Y", "tie"]} for k in ("better_rack_A", "better_rack_B", "better_overall")}
    | {"confidence": {"type": "string", "enum": ["low", "medium", "high"]}, "reason": {"type": "string"}},
}


S3_ITEMS = ["rack_count_matches_plan", "rack_positions_match_plan", "racks_face_cold_aisle", "racks_on_raised_floor",
            "no_collisions_or_floating", "containment_roof", "containment_end_doors", "perforated_tiles_in_cold_aisle",
            "cable_trays_over_rows", "overall_coherence"]
RUBRIC["s3"] = """The task given to the modeller: in a prepared Blender room (walls, columns, a raised floor whose top is at 0.6 m),
place a copy of a template closed rack cabinet (0.6 x 1.2 x 2.0 m) for every rack in the layout (first image: the layout
redrawn as a plan; a triangle on the thick front edge marks each rack's front), standing on the raised floor, at the right
position and facing the right way, so that the rack fronts face each other across the cold aisle. Then add cold-aisle
containment (a roof over the cold aisle at rack-top height and a door panel at each open end), 600 mm perforated floor tiles
in the cold aisle, and a 300 mm overhead cable tray above each rack row, 300 mm above the rack tops. Racks must not overlap
each other, walls or columns. Template racks parked outside the room (west of it) are not part of the result.
You get Workbench (flat-shaded) renders: top, isometric, a view from inside the cold aisle, and an overview.
Judge each checklist item as present / partial / absent from the renders and the layout."""
S3_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["checks", "summary"],
    "properties": {
        "checks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["item", "verdict", "note"],
            "properties": {"item": {"type": "string", "enum": S3_ITEMS},
                           "verdict": {"type": "string", "enum": ["present", "partial", "absent"]},
                           "note": {"type": "string"}}}},
        "summary": {"type": "string"},
    },
}
S3_PAIR_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["better_placement", "better_aisle_fitout", "better_overall", "confidence", "reason"],
    "properties": {k: {"type": "string", "enum": ["X", "Y", "tie"]} for k in ("better_placement", "better_aisle_fitout", "better_overall")}
    | {"confidence": {"type": "string", "enum": ["low", "medium", "high"]}, "reason": {"type": "string"}},
}


def s3_score(g):
    credit = {"present": 1.0, "partial": 0.5, "absent": 0.0}
    v = {c["item"]: credit[c["verdict"]] for c in g["checks"] if c["item"] in S3_ITEMS}
    return {"pct": round(100 * sum(v.get(i, 0.0) for i in S3_ITEMS) / len(S3_ITEMS), 1),
            "missing_items": [i for i in S3_ITEMS if i not in v]}


def s2_score(g):
    """60 points from the judge's own verdicts: rack A checklist 30, rack B checklist 20, likeness 10 (A 6, B 4)."""
    credit = {"present": 1.0, "partial": 0.5, "absent": 0.0}
    out = {}
    for rack, pts in (("A", 30), ("B", 20)):
        v = {}
        for c in g["checks"]:
            if c["rack"] == rack and c["item"] in S2_ITEMS[rack]:
                v[c["item"]] = credit[c["verdict"]]
        out[f"checklist_{rack}"] = round(pts * sum(v.get(i, 0.0) for i in S2_ITEMS[rack]) / len(S2_ITEMS[rack]), 2)
    out["likeness"] = round(6 * (g["likeness"]["A"] - 1) / 4 + 4 * (g["likeness"]["B"] - 1) / 4, 2)
    out["total_60"] = round(sum(out.values()), 2)
    out["pct"] = round(out["total_60"] / 60 * 100, 1)
    return out


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


def small_img(path: pathlib.Path, width=1024):
    from io import BytesIO
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=85)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


def s2_reference_parts():
    ref = ROOT / "ref"
    parts = [{"type": "text", "text": "Reference photos:"}]
    for f in ("rack_row_front_nersc.jpg", "rack_rear_cray_nersc.jpg", "rack_open_frame_raised_floor.jpg"):
        parts += [{"type": "text", "text": f}, small_img(ref / f)]
    return parts


def s2_submission_parts(label, run):
    rv, cyc = run / "review", run / "review_cycles"
    parts = []
    if cyc.exists():
        for rack in ("A", "B"):
            for v, cap in (("front", "front"), ("front_open", "front with the doors hidden (interior)"), ("close", "close 3/4 view"),
                           ("back", "back"), ("side", "side")):
                f = cyc / f"cyc_Rack{rack}_{v}.jpg"
                if f.exists():
                    parts += [{"type": "text", "text": f"Submission {label}, rack {rack}, {cap} (Cycles render)"}, small_img(f)]
        st = cyc / "structure.json"
        if st.exists():
            parts.append({"type": "text", "text": f"Submission {label}: scene statistics derived from object NAMES (hints only; a part may "
                                                  f"exist under another name, so trust the images):\n{st.read_text()}"})
    else:
        for rack in ("A", "B"):
            for v in ("front", "back", "right", "iso", "close"):
                f = rv / f"review_Rack{rack}_{v}.png"
                if f.exists():
                    parts += [{"type": "text", "text": f"Submission {label}, rack {rack}, {v} view"}, small_img(f)]
    if not parts:
        parts = [{"type": "text", "text": f"Submission {label}: no renders (nothing was built)"}]
    return parts


def call(model, messages, schema, name):
    key = os.environ["gemini_key"]
    system = messages[0]["content"]
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": to_gemini(messages[1]["content"])}],
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
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--tag", default="", help="suffix for the output folder")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--repeats", type=int, default=2)
    a = ap.parse_args()
    runs = [pathlib.Path(r).resolve() for r in a.runs]
    rng = random.SystemRandom()
    order = runs[:]
    rng.shuffle(order)
    LABELS = "XYZW"
    mapping = {LABELS[i]: str(r) for i, r in enumerate(order)}
    outdir = ROOT / "judge" / (f"{a.stage}-{a.scenario}" + (f"-{a.tag}" if a.tag else ""))
    outdir.mkdir(parents=True, exist_ok=True)
    plan = ROOT / "inputs" / a.scenario / "plan.png"
    sysmsg = ("You are an independent reviewer of 3D modelling submissions. You have no answer key: derive the correct "
              "answer from the inputs yourself, be strict and specific, and mark anything genuinely ambiguous in the "
              "drawing as 'ambiguous' rather than wrong.")
    result = {"model": a.model, "api": "Gemini API (direct)", "cost_note": "estimated from token counts",
              "absolute": {LABELS[i]: [] for i in range(len(order))}, "pairwise": None, "pairs": [], "cost_usd": 0.0}
    if a.stage == "s3":
        head = [{"type": "text", "text": RUBRIC["s3"]}] + s3_layout_parts(a.scenario)
        for label, run in (("X", order[0]), ("Y", order[1])):
            for k in range(a.repeats):
                msgs = [{"role": "system", "content": sysmsg},
                        {"role": "user", "content": head + s3_submission_parts(label, run)
                         + [{"type": "text", "text": "Grade this submission: one check for every checklist item."}]}]
                g, u = call(a.model, msgs, S3_SCHEMA, "grade")
                result["cost_usd"] += float(u.get("cost") or 0)
                g["derived"] = s3_score(g)
                result["absolute"][label].append(g)
                print(label, k, g["derived"], flush=True)
        msgs = [{"role": "system", "content": sysmsg},
                {"role": "user", "content": head + s3_submission_parts("X", order[0]) + s3_submission_parts("Y", order[1])
                 + [{"type": "text", "text": "Compare submissions X and Y: which places the racks better, which fits out the aisle better, and overall?"}]}]
        p, u = call(a.model, msgs, S3_PAIR_SCHEMA, "pairwise")
        result["cost_usd"] += float(u.get("cost") or 0)
        result["pairwise"] = p
        print("pairwise", p, flush=True)
    elif a.stage == "s2":
        import itertools
        head = [{"type": "text", "text": RUBRIC["s2"]}] + s2_reference_parts()
        for i, run in enumerate(order):
            label = LABELS[i]
            for k in range(a.repeats):
                msgs = [{"role": "system", "content": sysmsg},
                        {"role": "user", "content": head + s2_submission_parts(label, run)
                         + [{"type": "text", "text": "Grade this submission: one check for every checklist item of both racks, then the likeness ratings."}]}]
                g, u = call(a.model, msgs, S2_SCHEMA, "grade")
                result["cost_usd"] += float(u.get("cost") or 0)
                g["derived"] = s2_score(g)
                result["absolute"][label].append(g)
                print(label, k, g["derived"], flush=True)
        for i, j in itertools.combinations(range(len(order)), 2):
            x, y = (i, j) if rng.random() < 0.5 else (j, i)
            msgs = [{"role": "system", "content": sysmsg},
                    {"role": "user", "content": head + s2_submission_parts("X", order[x]) + s2_submission_parts("Y", order[y])
                     + [{"type": "text", "text": "Compare submissions X and Y: which rack A is better, which rack B, and overall?"}]}]
            p, u = call(a.model, msgs, S2_PAIR_SCHEMA, "pairwise")
            result["cost_usd"] += float(u.get("cost") or 0)
            p["X_is"], p["Y_is"] = LABELS[x], LABELS[y]
            result["pairs"].append(p)
            print("pair", LABELS[x], "vs", LABELS[y], {k: p[k] for k in ("better_rack_A", "better_rack_B", "better_overall", "confidence")}, flush=True)
    else:
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
