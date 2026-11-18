#!/usr/bin/env python3
"""Plan overlay for D2: the submitted rack layout coloured by the rule check.

    python d2_overlay.py --run RUN_DIR --room room.json --out OUT.png [--ref N_REF]

Racks: green = valid, red = bad (with the numbers of the violated rules, e.g. "3,8" = R3 and R8); the thick dark edge
is the front. Light blue = required clearances in front of / behind each rack, hatched orange = CRAH service zones and
door zones, pale green tint = floor a person can reach from door D1 (centre line of a 900 mm wide path).
"""
import argparse
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import d2_design as D

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GREEN, RED, GPU_GREEN = (60, 170, 100), (220, 60, 55), (30, 120, 150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--room", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", type=float, default=None)
    a = ap.parse_args()
    room_json = json.loads(pathlib.Path(a.room).read_text())
    room = D.Room(room_json)
    try:
        entries = D.load_design(pathlib.Path(a.run))
    except Exception as e:
        entries = []
        print(f"layout_design.json: {e}")
    res = D.evaluate(room, entries, a.ref or 1.0)
    racks, V, reached = res["_racks"], res["_V"], res["_reached"]
    det = res["detail"]

    W, Dp = max(room_json["grid"]["x"].values()), max(room_json["grid"]["y"].values())
    s, m, foot = 0.07, 60, 150
    img = Image.new("RGB", (int(W * s) + 2 * m, int(Dp * s) + 2 * m + foot), "white")
    X = lambda x: m + x * s                    # noqa: E731
    Y = lambda y: m + (Dp - y) * s             # noqa: E731
    f_s, f_m, f_b = ImageFont.truetype(FONT, 11), ImageFont.truetype(FONT, 14), ImageFont.truetype(FONT_B, 16)

    def rect(d, r, **kw):
        d.rectangle([X(r[0]), Y(r[3]), X(r[2]), Y(r[1])], **kw)

    # layer 1: reached floor (grid points -> small squares)
    d = ImageDraw.Draw(img, "RGBA")
    d.polygon([(X(x), Y(y)) for x, y in room_json["room"]["polygon"]], fill=(250, 250, 250), outline=None)
    jj, ii = np.where(reached)
    h = D.GRID / 2
    for j, i in zip(jj, ii):
        x, y = room.gx0 + i * D.GRID, room.gy0 + j * D.GRID
        d.rectangle([X(x - h), Y(y + h), X(x + h), Y(y - h)], fill=(196, 235, 205, 255))
    # layer 2: zones
    for z in list(room.crah_zones) + list(room.door_zones):
        rect(d, z, fill=(255, 170, 60, 60), outline=(230, 140, 30, 255))
        for k in range(int((z[2] - z[0] + z[3] - z[1]) / 300) + 1):
            x0, y0 = z[0] + k * 300, z[1]
            x1, y1 = x0 - (z[3] - z[1]), z[3]
            if x1 < z[0]:
                y1, x1 = y0 + (x0 - z[0]), z[0]
            if x0 > z[2]:
                y0, x0 = y0 + (x0 - z[2]), z[2]
            if y0 < y1:
                d.line([(X(x0), Y(y0)), (X(x1), Y(y1))], fill=(230, 140, 30, 150), width=1)
    if racks:
        cx, cy = np.array([r[2] for r in racks]), np.array([r[3] for r in racks])
        w, f = np.array([r[4] for r in racks]), np.array([r[5] for r in racks], dtype=int)
        F = D.footprints(cx, cy, w, f)
        for Z in (D.extend(F, f, D.FRONT_CLR), D.extend(F, D.OPP[f], D.REAR_CLR)):
            for z in Z:
                rect(d, z, fill=(90, 150, 255, 38))
    # layer 3: room, fixed items, racks
    d = ImageDraw.Draw(img)
    pts = [(X(x), Y(y)) for x, y in room_json["room"]["polygon"]]
    d.line(pts + [pts[0]], fill=(70, 70, 70), width=4)
    for c in room.columns:
        rect(d, c, fill=(40, 40, 40))
    for c, r in zip(room_json["crah"], room.crah):
        rect(d, r, fill=(200, 215, 235), outline=(40, 40, 40), width=2)
        d.text(((X(r[0]) + X(r[2])) / 2, (Y(r[1]) + Y(r[3])) / 2), c["id"].replace("CRAH-", "C"), fill="black", font=f_s, anchor="mm")
    for dr in room_json["doors"]:
        x, y = dr["center"]
        hw = dr["width"] / 2
        if dr["wall"] in "NS":
            d.line([(X(x - hw), Y(y)), (X(x + hw), Y(y))], fill=(30, 110, 220), width=7)
            d.text((X(x), Y(y) + (16 if dr["wall"] == "S" else -16)), dr["id"], fill=(30, 110, 220), font=f_b, anchor="mm")
        else:
            d.line([(X(x), Y(y - hw)), (X(x), Y(y + hw))], fill=(30, 110, 220), width=7)
            d.text((X(x) + (22 if dr["wall"] == "E" else -22), Y(y)), dr["id"], fill=(30, 110, 220), font=f_b, anchor="mm")
    if room.start_xy:
        x, y = room.start_xy
        d.ellipse([X(x) - 5, Y(y) - 5, X(x) + 5, Y(y) + 5], fill=(30, 110, 220))
    for i, r in enumerate(racks):
        bad = V[i].any()
        col = RED if bad else (GPU_GREEN if w[i] == D.GPU_W else GREEN)
        x0, y0, x1, y1 = F[i]
        d.rectangle([X(x0) + 1, Y(y1) + 1, X(x1) - 1, Y(y0) - 1], fill=col, outline=(255, 255, 255))
        edge = {0: [(x0, y1), (x1, y1)], 1: [(x0, y0), (x1, y0)], 2: [(x1, y0), (x1, y1)], 3: [(x0, y0), (x0, y1)]}[int(f[i])]
        d.line([(X(p), Y(q)) for p, q in edge], fill=(15, 15, 15), width=4)
        if bad:
            txt = ",".join(str(k + 1) for k in range(9) if V[i, k])
            horiz = f[i] >= 2
            if horiz or len(txt) <= 1:
                d.text(((X(x0) + X(x1)) / 2, (Y(y0) + Y(y1)) / 2), txt, fill="white", font=f_s, anchor="mm")
            else:                                  # narrow upright footprint: write the rule numbers vertically
                for n, ch in enumerate(txt.replace(",", "")):
                    d.text(((X(x0) + X(x1)) / 2, Y(y1) + 12 + n * 12), ch, fill="white", font=f_s, anchor="mm")
    # legend
    ly = img.height - foot + 6
    items = [(GREEN, "valid rack"), (GPU_GREEN, "valid GPU rack (800 wide)"), (RED, "bad rack + violated rule numbers"),
             ((90, 150, 255), "front 1200 / rear 900 clearance"), ((255, 170, 60), "CRAH service zone / door zone"),
             ((196, 235, 205), "reachable from door D1 (path centre line)")]
    for k, (col, txt) in enumerate(items):
        x, y = m + (k % 3) * 470, ly + (k // 3) * 26
        d.rectangle([x, y, x + 20, y + 16], fill=col, outline=(90, 90, 90))
        d.text((x + 28, y), txt, fill="black", font=f_m)
    d.line([(m, ly + 60), (m + 20, ly + 60)], fill=(15, 15, 15), width=4)
    d.text((m + 28, ly + 52), "thick dark edge = rack front;  rule numbers: 1 inside, 2 overlap, 3 front clearance, 4 rear clearance, "
           "5 hot/cold, 6 CRAH zone, 7 door zone, 8 access, 9 GPU distance", fill="black", font=f_s)
    vr = det["violations_per_rule"]
    line = (f"valid {det['n_valid']}   bad {det['n_bad']}   GPU valid {det['n_gpu_valid']} / {det['gpu_required']}   "
            f"net {det['net_racks']}" + (f"   N_REF {a.ref:g}   score {res['total']}" if a.ref else "") +
            "   violations: " + (" ".join(f"{k}={v}" for k, v in vr.items() if v) or "none"))
    d.text((m, ly + 78), line, fill="black", font=f_b)
    img.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
