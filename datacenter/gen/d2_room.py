#!/usr/bin/env python3
"""Stage D2 inputs: an EMPTY data hall (walls, columns, doors, fixed CRAH units) for the rack-layout design task.

    python d2_room.py --seed N --out DIR [--start-blend]

Writes DIR/room.json (the `hard` hall of layout_gen with `racks` and `aisles` emptied) and DIR/plan_empty.png.
With --start-blend it also runs make_photo_scene.py in Blender and copies its start.blend (empty hall + RackA / RackG /
CRAH templates outside the room; the fixed CRAH units are not placed in that scene) to DIR/start.blend.
Deterministic from --seed. There is no answer key: the layout is the participant's design.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import shutil
import subprocess
import tempfile

import draw_plan
import layout_gen

TITLE = "DATA HALL 02 - EMPTY ROOM (RACK LAYOUT TO BE DESIGNED)"


class EmptyPlan(draw_plan.Plan):
    """Same drawing as draw_plan, with notes that fit an empty room."""

    def notes(self):
        lay, d = self.lay, self.d
        MB, CW, INK = draw_plan.MB, draw_plan.CANVAS_W, draw_plan.INK
        x, y = 40, self.H - MB + 250
        self.text((x, y), lay.get("title", TITLE), sz=30, bold=True, anchor="lm")
        doors = ".  ".join(f"{dr['id']}: {dr['width']} DOOR" for dr in lay["doors"])
        lines = [
            "1. ALL DIMENSIONS IN mm. GRID LINES ARE ON WALL / COLUMN CENTRELINES.",
            "2. WALLS 200 THK. COLUMNS 600 x 600 ON GRID INTERSECTIONS.",
            "3. RAISED FLOOR: FINISHED FLOOR +600 ABOVE SLAB. CLEAR HEIGHT 3000 ABOVE RAISED FLOOR.",
            "4. CRAH UNITS (EXISTING, FIXED) 1800 W x 900 D AGAINST THE WALLS; CENTRELINES DIMENSIONED.",
            f"5. {doors}.  EXACT COORDINATES: SEE room.json.",
        ]
        for i, s in enumerate(lines):
            self.text((x, y + 45 + i * 32), s, sz=19, anchor="lm")
        lx, ly = CW - 780, self.H - MB + 260
        d.rectangle([lx, ly, lx + 60, ly + 30], fill=(215, 228, 240), outline=INK, width=2)
        d.line([(lx, ly), (lx + 60, ly)], fill=INK, width=5)
        d.polygon([(lx + 18, ly), (lx + 42, ly), (lx + 30, ly - 20)], fill=INK)
        self.text((lx + 80, ly + 10), "CRAH UNIT, FRONT (SUPPLY AIR) SIDE MARKED", sz=18, anchor="lm")
        nx, ny = CW - 120, draw_plan.MT - 200
        d.polygon([(nx, ny - 60), (nx - 20, ny), (nx + 20, ny)], fill=INK)
        self.text((nx, ny + 22), "N", sz=24, bold=True)
        sx, sy = CW - 780, self.H - MB + 340
        for i in range(5):
            d.rectangle([sx + i * 1000 * self.s, sy, sx + (i + 1) * 1000 * self.s, sy + 12],
                        fill=INK if i % 2 == 0 else "white", outline=INK)
        self.text((sx, sy + 30), "0", sz=16)
        self.text((sx + 5000 * self.s, sy + 30), "5 m", sz=16)


def make_room(seed: int) -> dict:
    lay = layout_gen.hard(random.Random(seed))
    return {"units": "mm", "scenario": "hard", "title": TITLE,
            "grid": lay["grid"], "room": lay["room"], "ups_room": lay["ups_room"],
            "columns": lay["columns"], "doors": lay["doors"], "crah": lay["crah"],
            "racks": [], "aisles": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-blend", action="store_true", help="also build DIR/start.blend with Blender")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    room = make_room(a.seed)
    (out / "room.json").write_text(json.dumps(room, indent=1))
    EmptyPlan(room).draw().save(out / "plan_empty.png")
    print(f"room {max(room['grid']['x'].values())} x {max(room['grid']['y'].values())}, {len(room['columns'])} columns, "
          f"{len(room['crah'])} CRAH, {len(room['doors'])} doors -> {out / 'room.json'}, {out / 'plan_empty.png'}")
    if a.start_blend:
        here = pathlib.Path(__file__).resolve().parent
        blender = os.environ.get("BENCH_BLENDER", "/opt/blender/blender")
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([blender, "-b", "--factory-startup", "--python", str(here / "make_photo_scene.py"), "--",
                            str(out / "room.json"), tmp], check=True, stdout=subprocess.DEVNULL)
            shutil.copy(pathlib.Path(tmp) / "start.blend", out / "start.blend")
        print(f"start scene -> {out / 'start.blend'}")


if __name__ == "__main__":
    main()
