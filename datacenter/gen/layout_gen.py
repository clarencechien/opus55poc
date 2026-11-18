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


def hard(rng: random.Random) -> dict:
    """L-shaped hall (UPS room cut out of the north-east bay), 5 free columns, three row pairs:
    south pair A/B along x with 800 mm GPU racks in row B, middle pair C/D along x with row C running
    through the column line (slots that hit a column are left empty and their ids skipped), and a
    north-west pair E/F running north-south (facing east / west)."""
    bay = rng.choice([6000, 6300])
    nx, ny = 4, 3
    gx = {LETTERS[i]: i * bay for i in range(nx + 1)}
    gy = {str(j + 1): j * bay for j in range(ny + 1)}
    W, D = nx * bay, ny * bay
    h = WALL / 2
    xD, y3 = gx["D"], gy["3"]
    poly = [[h, h], [W - h, h], [W - h, y3 - h], [xD - h, y3 - h], [xD - h, D - h], [h, D - h]]
    columns = [{"id": f"{LETTERS[i]}/{j + 1}", "center": [gx[LETTERS[i]], gy[str(j + 1)]], "size": [COL, COL]}
               for j in range(1, ny) for i in range(1, nx) if not (LETTERS[i] == "D" and j + 1 == 3)]
    racks, aisles = [], []

    def add(row, k, cx, cy, w, facing):
        racks.append({"id": f"{row}{k:02d}", "row": row, "center": [cx, cy], "size": [w, RACK_D], "facing": facing})

    # --- south pair A/B along x, east half; row B starts with 3 GPU racks (800 wide); rows equal length
    nA = rng.choice([11, 12])
    xS0 = rng.choice([12600, 13200]) + (bay - 6000) * 2
    yA0 = h + 1200
    x = xS0
    for k in range(nA):
        add("A", k + 1, x + 300, yA0 + 600, RACK_W, "N")
        x += RACK_W
    xS1 = x
    x = xS0
    k = 0
    for w in [800] * 3 + [RACK_W] * (nA - 4):
        k += 1
        add("B", k, x + w / 2, yA0 + 2400 + 600, w, "S")
        x += w
    assert abs(x - xS1) < 1e-6
    aisles.append({"type": "cold", "rect": [xS0, yA0 + 1200, xS1, yA0 + 2400]})
    # --- middle pair C/D along x, west part; row C straddles grid line 2 and skips slots that hit columns
    g2 = gy["2"]
    xM0 = rng.choice([2400, 3000])
    nM = rng.choice([13, 14])
    yC0 = g2 - 600
    k = 0
    for i in range(nM):
        x0 = xM0 + i * RACK_W
        k += 1
        hit = any(c["center"][1] == g2 and x0 < c["center"][0] + COL / 2 and x0 + RACK_W > c["center"][0] - COL / 2 for c in columns)
        if not hit:
            add("C", k, x0 + 300, yC0 + 600, RACK_W, "N")
        add("D", k, x0 + 300, yC0 + 2400 + 600, RACK_W, "S")
    xM1 = xM0 + nM * RACK_W
    aisles.append({"type": "cold", "rect": [xM0, yC0 + 1200, xM1, yC0 + 2400]})
    # --- north-west pair E/F running north-south: E faces east, F faces west
    xE0 = rng.choice([2400, 3000])
    nE = rng.choice([5, 6])
    yE0 = y3 + COL / 2 + 1200
    for i in range(nE):
        cy = yE0 + 300 + i * RACK_W
        add("E", i + 1, xE0 + 600, cy, RACK_W, "E")
        add("F", i + 1, xE0 + 2400 + 600, cy, RACK_W, "W")
    aisles.append({"type": "cold", "rect": [xE0 + 1200, yE0, xE0 + 2400, yE0 + nE * RACK_W]})
    # CRAH: two on the west wall (discharging east), one on the east wall (discharging west)
    crah = [{"id": "CRAH-1", "center": [h + 450, 3000], "size": [1800, 900], "facing": "E"},
            {"id": "CRAH-2", "center": [h + 450, g2 + 3600], "size": [1800, 900], "facing": "E"},
            {"id": "CRAH-3", "center": [W - h - 450, g2 + 3000], "size": [1800, 900], "facing": "W"}]
    doors = [{"id": "D1", "center": [rng.choice([8400, 9000]), 0], "width": 1800, "wall": "S"},
             {"id": "D2", "center": [(xD + W) // 2, y3], "width": 1200, "wall": "N"}]
    lay = {"units": "mm", "scenario": "hard", "grid": {"x": gx, "y": gy},
           "room": {"polygon": poly, "wall_thickness": WALL, "clear_height": 3000, "raised_floor_height": 600},
           "ups_room": {"polygon": [[xD + h, y3 + h], [W - h, y3 + h], [W - h, D - h], [xD + h, D - h]]},
           "columns": columns, "doors": doors, "crah": crah, "racks": racks, "aisles": aisles}
    validate_poly(lay)
    return lay


def validate_poly(lay: dict) -> None:
    from shapely.geometry import Polygon, box
    room = Polygon(lay["room"]["polygon"])
    items = [(r["id"], footprint(r["center"], r["size"], r["facing"])) for r in lay["racks"]]
    items += [(c["id"], footprint(c["center"], c["size"], c["facing"])) for c in lay["crah"]]
    for name, b in items:
        assert room.buffer(1).contains(box(*b)), f"{name} outside room"
    items += [(c["id"], footprint(c["center"], c["size"], "N")) for c in lay["columns"]]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            assert not rect_overlap(items[i][1], items[j][1], gap=-1), f"{items[i][0]} overlaps {items[j][0]}"
    for a in lay["aisles"]:
        for c in lay["columns"]:
            assert not rect_overlap(a["rect"], footprint(c["center"], c["size"], "N")), f"aisle hits column {c['id']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="easy")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lay = {"easy": easy, "hard": hard}[a.scenario](random.Random(a.seed))
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.json").write_text(json.dumps(lay, indent=1))
    print(f"{len(lay['racks'])} racks, room {lay['room']['polygon'][2]} -> {out / 'layout.json'}")


if __name__ == "__main__":
    main()
