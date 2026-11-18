#!/usr/bin/env python3
"""Task D1 (as-built check): a design layout and an as-built layout that differs from it in seven places.

    python d1_asbuilt.py --seed N --out DIR
        -> DIR/design.json    the design (given to the participants)
           DIR/asbuilt.json   the hall as built            (SECRET: answer key)
           DIR/changes.json   human-readable change list   (SECRET)

design = layout_gen.hard(Random(seed)). The as-built hall gets one change of each kind, on different rows
(every rack row A..F gets exactly one of a..f):
  a  the 2 racks at one end of a row are missing
  b  1 rack in the middle of a row is missing (a rack-sized gap)
  c  1 extra 600 mm rack at a free end of a row (>= 1200 mm clear to walls and columns)
  d  3 adjacent racks of a row are turned by 180 deg (same footprints, opposite facing)
  e  the 600 mm rack at a row end is replaced by an 800 mm GPU rack (same inner edge, grows outward)
  f  a whole short row (E or F) is shifted by 600 mm along its axis
  g  one CRAH is moved 1800 mm along its wall
Floor tiles are not relaid: `aisles` (and so the perforated tiles in the photos) stay as designed.

Photos and start scene (run from datacenter/, ~2 min per photo):
    /opt/blender/blender -b --factory-startup --python gen/make_photo_scene.py -- DIR/asbuilt.json DIR/photo --render --samples 24
    /opt/blender/blender -b --factory-startup --python gen/d1_extra_cams.py -- DIR/photo 6:x,y,z:tx,ty,tz 7:... --render --samples 24
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import layout_gen as lg  # noqa: E402

FLIP = {"N": "S", "S": "N", "E": "W", "W": "E"}
EXTRA_CLEAR = 1200   # change c: clearance of the extra rack to walls and columns
MOVE_CLEAR = 600     # changes e, f, g: clearance of the moved / grown item to walls (e, f), columns and other equipment (g)


def axis(row_racks):
    """0 if the row runs along x (facing N/S), 1 if it runs along y (facing E/W)."""
    return 0 if row_racks[0]["facing"] in "NS" else 1


def rows_of(lay):
    rows = {}
    for r in lay["racks"]:
        rows.setdefault(r["row"], []).append(r)
    for row, rs in rows.items():
        ax = axis(rs)
        rs.sort(key=lambda r: r["center"][ax])
    return rows


def touching(a, b, ax):
    return abs(abs(a["center"][ax] - b["center"][ax]) - (a["size"][0] + b["size"][0]) / 2) < 1


def fp(it):
    return lg.footprint(it["center"], it["size"], it["facing"])


def rect_dist(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def placement_ok(lay, item, others, wall_clear=0.0, column_clear=0.0, equip_clear=0.0):
    """item inside the hall, clear of walls / columns / the other equipment by the given distances (0 = no overlap)."""
    from shapely.geometry import Polygon, box
    b = fp(item)
    room = Polygon(lay["room"]["polygon"])
    if not room.buffer(1).contains(box(*b)):
        return False
    if wall_clear and room.exterior.distance(box(*b)) < wall_clear - 1:
        return False
    for c in lay["columns"]:
        cb = lg.footprint(c["center"], c["size"], "N")
        if lg.rect_overlap(b, cb, gap=-1) or rect_dist(b, cb) < column_clear - 1:
            return False
    for o in others:
        ob = fp(o)
        if lg.rect_overlap(b, ob, gap=-1) or rect_dist(b, ob) < equip_clear - 1:
            return False
    return True


def everything(lay, skip=()):
    return [x for x in lay["racks"] + lay["crah"] if x["id"] not in skip]


# ---- the seven changes: each returns a change record and edits `lay` in place, or returns None if it does not fit ----

def ch_a(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    for side in rng.sample(["low", "high"], 2):
        pair = rs[:2] if side == "low" else rs[-2:]
        if len(rs) >= 5 and touching(pair[0], pair[1], ax):
            ids = [r["id"] for r in pair]
            lay["racks"] = [r for r in lay["racks"] if r["id"] not in ids]
            return {"kind": "a", "row": row, "racks": ids,
                    "text": f"row {row}: the two end racks {ids[0]} and {ids[1]} are missing ({end_name(ax, side)} end)"}
    return None


def ch_b(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    cand = [i for i in range(2, len(rs) - 2) if touching(rs[i - 1], rs[i], ax) and touching(rs[i], rs[i + 1], ax)]
    if not cand:
        return None
    r = rs[rng.choice(cand)]
    lay["racks"] = [x for x in lay["racks"] if x["id"] != r["id"]]
    return {"kind": "b", "row": row, "racks": [r["id"]], "text": f"row {row}: rack {r['id']} in the middle of the row is missing (gap)"}


def ch_c(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    for side in rng.sample(["low", "high"], 2):
        end = rs[0] if side == "low" else rs[-1]
        sgn = -1 if side == "low" else 1
        c = list(end["center"])
        c[ax] += sgn * (end["size"][0] / 2 + lg.RACK_W / 2)
        num = int(end["id"][1:]) + sgn
        new = {"id": f"{row}{num:02d}", "row": row, "center": c, "size": [lg.RACK_W, lg.RACK_D], "facing": end["facing"]}
        if num >= 0 and placement_ok(lay, new, everything(lay), wall_clear=EXTRA_CLEAR, column_clear=EXTRA_CLEAR):
            lay["racks"].append(new)
            return {"kind": "c", "row": row, "racks": [new["id"]],
                    "text": f"row {row}: one extra 600 mm rack {new['id']} at the {end_name(ax, side)} end, next to {end['id']}"}
    return None


def ch_d(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    cand = [i for i in range(len(rs) - 2) if touching(rs[i], rs[i + 1], ax) and touching(rs[i + 1], rs[i + 2], ax)]
    if not cand:
        return None
    i = rng.choice(cand)
    for r in rs[i:i + 3]:
        r["facing"] = FLIP[r["facing"]]
    ids = [r["id"] for r in rs[i:i + 3]]
    return {"kind": "d", "row": row, "racks": ids,
            "text": f"row {row}: racks {ids[0]}, {ids[1]}, {ids[2]} are turned by 180 deg (now facing {rs[i]['facing']})"}


def ch_e(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    for side in rng.sample(["low", "high"], 2):
        end = rs[0] if side == "low" else rs[-1]
        if end["size"][0] != lg.RACK_W:
            continue
        sgn = -1 if side == "low" else 1
        new = copy.deepcopy(end)
        new["size"] = [800, lg.RACK_D]
        new["center"][ax] += sgn * 100
        if placement_ok(lay, new, everything(lay, skip=[end["id"]]), wall_clear=MOVE_CLEAR, column_clear=MOVE_CLEAR):
            end.update(new)
            return {"kind": "e", "row": row, "racks": [end["id"]],
                    "text": f"row {row}: end rack {end['id']} ({end_name(ax, side)} end) is an 800 mm GPU rack instead of a 600 mm rack"}
    return None


def ch_f(lay, row, rng):
    rs = rows_of(lay)[row]
    ax = axis(rs)
    ids = [r["id"] for r in rs]
    for sgn in rng.sample([-1, 1], 2):
        moved = copy.deepcopy(rs)
        for r in moved:
            r["center"][ax] += sgn * 600
        others = everything(lay, skip=ids)
        if all(placement_ok(lay, r, others, wall_clear=MOVE_CLEAR, column_clear=MOVE_CLEAR) for r in moved):
            for r, m in zip(rs, moved):
                r["center"] = m["center"]
            return {"kind": "f", "row": row, "racks": ids,
                    "text": f"row {row}: the whole row is shifted 600 mm to the {compass(ax, sgn)}"}
    return None


def ch_g(lay, rng):
    for c in rng.sample(lay["crah"], len(lay["crah"])):
        ax = 1 if c["facing"] in "EW" else 0   # a CRAH stands with its back to its wall and moves along it
        for sgn in rng.sample([-1, 1], 2):
            new = copy.deepcopy(c)
            new["center"][ax] += sgn * 1800
            if placement_ok(lay, new, everything(lay, skip=[c["id"]]), column_clear=MOVE_CLEAR, equip_clear=MOVE_CLEAR):
                c["center"] = new["center"]
                return {"kind": "g", "row": None, "racks": [c["id"]],
                        "text": f"{c['id']} is moved 1800 mm to the {compass(ax, sgn)} along its wall"}
    return None


def compass(ax, sgn):
    return {(0, 1): "east", (0, -1): "west", (1, 1): "north", (1, -1): "south"}[(ax, sgn)]


def end_name(ax, side):
    return compass(ax, -1 if side == "low" else 1)


def build(seed: int):
    design = lg.hard(random.Random(seed))
    rng = random.Random(f"d1-changes-{seed}")
    funcs = {"a": ch_a, "b": ch_b, "c": ch_c, "d": ch_d, "e": ch_e}
    for _ in range(500):
        lay = copy.deepcopy(design)
        f_row = rng.choice(["E", "F"])
        rest = [r for r in "ABCDEF" if r != f_row]
        rng.shuffle(rest)
        plan = dict(zip("abcde", rest))
        changes = []
        for kind in "abcde":
            changes.append(funcs[kind](lay, plan[kind], rng))
        changes.append(ch_f(lay, f_row, rng))
        changes.append(ch_g(lay, rng))
        if any(c is None for c in changes):
            continue
        try:
            lg.validate_poly(lay)
        except AssertionError:
            continue
        return design, lay, changes
    raise SystemExit(f"seed {seed}: no valid set of changes found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    design, asbuilt, changes = build(a.seed)
    design["title"] = "DATA HALL 01 - EQUIPMENT LAYOUT PLAN (DESIGN)"
    asbuilt["title"] = "DATA HALL 01 - EQUIPMENT LAYOUT PLAN (AS BUILT)"
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "design.json").write_text(json.dumps(design, indent=1))
    (out / "asbuilt.json").write_text(json.dumps(asbuilt, indent=1))
    (out / "changes.json").write_text(json.dumps({"seed": a.seed, "changes": changes}, indent=1))
    print(f"seed {a.seed}: design {len(design['racks'])} racks, as built {len(asbuilt['racks'])} racks -> {out}")
    for c in changes:
        print(f"  {c['kind']}  {c['text']}")


if __name__ == "__main__":
    main()
