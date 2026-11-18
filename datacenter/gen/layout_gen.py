#!/usr/bin/env python3
"""Random data-hall layouts with a known answer.

    python layout_gen.py --scenario easy --seed N --out DIR      -> DIR/layout.json (ground truth, keep out of git)

Coordinates are millimetres. Origin = intersection of grid lines A and 1 (the south-west wall centrelines),
+x east (letters increase), +y north (numbers increase). Walls sit on the outer grid lines.
Rack `size` is [width along the row, depth front-to-back]; `facing` is the compass direction the front
(cold-air intake) points to.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random

WALL = 200
RACK_W, RACK_D = 600, 1200
COL = 600
LETTERS = "ABCDEFGHJK"


def rect_overlap(a, b, gap=0):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def footprint(center, size, facing):
    w, d = size
    if facing in ("E", "W"):
        w, d = d, w
    return [center[0] - w / 2, center[1] - d / 2, center[0] + w / 2, center[1] + d / 2]


def easy(rng: random.Random) -> dict:
    bay_x = rng.choice([4800, 5000, 5200])
    bay_y = rng.choice([6000, 6300])
    nx, ny = 3, 2
    gx = {LETTERS[i]: i * bay_x for i in range(nx + 1)}
    gy = {str(j + 1): j * bay_y for j in range(ny + 1)}
    W, D = nx * bay_x, ny * bay_y
    h = WALL / 2
    inner = [h, h, W - h, D - h]  # x0 y0 x1 y1 of the room's inner wall faces
    columns = [{"id": f"{LETTERS[i]}/{j + 1}", "center": [gx[LETTERS[i]], gy[str(j + 1)]], "size": [COL, COL]}
               for i in range(1, nx) for j in range(1, ny)]

    # CRAH units against the west wall, discharging east
    crah = []
    crah_d, crah_w = 900, 1800
    for k, yy in enumerate((round(D * 0.25 / 100) * 100, round(D * 0.70 / 100) * 100)):
        crah.append({"id": f"CRAH-{k + 1}", "center": [inner[0] + crah_d / 2, yy], "size": [crah_w, crah_d], "facing": "E"})

    # one pair of rows in the south bay sharing a cold aisle
    n = rng.randint(8, 10)
    hot_back = rng.choice([1000, 1100, 1200])
    aisle = rng.choice([1200, 1200, 1500])
    x_start = inner[0] + crah_d + rng.choice([1500, 1800, 2000, 2400])
    x_start = min(x_start, inner[2] - 1200 - n * RACK_W)
    y_s_back = inner[1] + hot_back                 # south row: back edge (hot aisle against south wall)
    y_s_front = y_s_back + RACK_D
    y_n_front = y_s_front + aisle
    y_n_back = y_n_front + RACK_D
    racks = []
    for i in range(n):
        cx = x_start + RACK_W / 2 + i * RACK_W
        racks.append({"id": f"A{i + 1:02d}", "row": "A", "center": [cx, y_s_back + RACK_D / 2], "size": [RACK_W, RACK_D], "facing": "N"})
        racks.append({"id": f"B{i + 1:02d}", "row": "B", "center": [cx, y_n_front + RACK_D / 2], "size": [RACK_W, RACK_D], "facing": "S"})
    aisles = [
        {"type": "cold", "rect": [x_start, y_s_front, x_start + n * RACK_W, y_n_front]},
        {"type": "hot", "rect": [x_start, inner[1], x_start + n * RACK_W, y_s_back]},
        {"type": "hot", "rect": [x_start, y_n_back, x_start + n * RACK_W, inner[3]]},  # open to the north wall
    ]
    # door on the east wall, north bay, double leaf
    door = {"id": "D1", "center": [W, round((gy["2"] + D) / 2 / 100) * 100], "width": 1800, "wall": "E"}

    lay = {
        "units": "mm", "scenario": "easy",
        "grid": {"x": gx, "y": gy},
        "room": {"polygon": [[inner[0], inner[1]], [inner[2], inner[1]], [inner[2], inner[3]], [inner[0], inner[3]]],
                 "wall_thickness": WALL, "clear_height": 3000, "raised_floor_height": 600},
        "columns": columns, "doors": [door], "crah": crah, "racks": racks, "aisles": aisles,
    }
    validate(lay)
    return lay


def validate(lay: dict) -> None:
    x0, y0 = lay["room"]["polygon"][0]
    x1, y1 = lay["room"]["polygon"][2]
    boxes = [(r["id"], footprint(r["center"], r["size"], r["facing"])) for r in lay["racks"]]
    boxes += [(c["id"], footprint(c["center"], c["size"], c["facing"])) for c in lay["crah"]]
    boxes += [(c["id"], footprint(c["center"], c["size"], "N")) for c in lay["columns"]]
    for name, b in boxes:
        if name[0] in "AB" and "/" not in name or name.startswith("CRAH"):
            assert b[0] >= x0 - 1 and b[1] >= y0 - 1 and b[2] <= x1 + 1 and b[3] <= y1 + 1, f"{name} outside room"
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            assert not rect_overlap(boxes[i][1], boxes[j][1], gap=-1), f"{boxes[i][0]} overlaps {boxes[j][0]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="easy")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lay = {"easy": easy}[a.scenario](random.Random(a.seed))
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.json").write_text(json.dumps(lay, indent=1))
    print(f"{len(lay['racks'])} racks, room {lay['room']['polygon'][2]} -> {out / 'layout.json'}")


if __name__ == "__main__":
    main()
