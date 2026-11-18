"""Per-stage submission checks shared by `bench submit` (format only; scoring lives in score/)."""
from __future__ import annotations

import json
import pathlib

FACINGS = {"N", "S", "E", "W"}


def _num_pair(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)


def check_s1(run: pathlib.Path) -> list[str]:
    p = run / "layout_pred.json"
    if not p.exists():
        return ["layout_pred.json missing in the run directory"]
    try:
        d = json.loads(p.read_text())
    except Exception as e:
        return [f"layout_pred.json is not valid JSON: {e}"]
    probs = []
    room = d.get("room", {})
    if not (isinstance(room.get("polygon"), list) and len(room["polygon"]) >= 3 and all(_num_pair(v) for v in room["polygon"])):
        probs.append("room.polygon must be a list of [x, y] points (mm)")
    for k in ("wall_thickness", "clear_height", "raised_floor_height"):
        if not isinstance(room.get(k), (int, float)):
            probs.append(f"room.{k} must be a number (mm)")
    racks = d.get("racks")
    if not isinstance(racks, list) or not racks:
        probs.append("racks must be a non-empty list")
    else:
        for i, r in enumerate(racks):
            if not isinstance(r.get("id"), str) or not _num_pair(r.get("center")) or not _num_pair(r.get("size")) \
                    or r.get("facing") not in FACINGS:
                probs.append(f"racks[{i}] needs id (str), center [x,y], size [w,d], facing N/S/E/W")
                break
    for key in ("columns", "crah", "doors", "aisles"):
        if not isinstance(d.get(key), list):
            probs.append(f"{key} must be a list (can be empty)")
    return probs


def check_s2(run: pathlib.Path, scene) -> list[str]:
    if scene is None:
        return []
    names = {o["name"] for o in scene}
    parent = {o["name"]: o["parent"] for o in scene}

    def under(n, root):
        while n:
            if n == root:
                return True
            n = parent.get(n)
        return False
    probs = [f"missing object {n}" for n in ("RackA", "RackA_FrontDoor", "RackA_RearDoor", "RackB",
                                             "RackB_Post_1", "RackB_Post_2", "RackB_Post_3", "RackB_Post_4") if n not in names]
    stray = [o["name"] for o in scene if o["type"] == "MESH" and not under(o["name"], "RackA") and not under(o["name"], "RackB")]
    if stray:
        probs.append(f"{len(stray)} mesh objects are not parented under RackA or RackB, e.g. {stray[:5]}")
    return probs


def check_submission(stage: str, run: pathlib.Path, scene=None) -> list[str]:
    if stage == "s1":
        return check_s1(run)
    if stage == "s2":
        return check_s2(run, scene)
    return []
