#!/usr/bin/env python3
"""Plan overlay for S1P: true racks/CRAH (grey outline) under the model's answer (filled; green = matched with the
right facing, orange = matched but wrong facing, red = no match within 600 mm), each with a front arrow.

    python s1p_overlay.py --run RUN_DIR --gt GT/layout.json --out OUT.png
"""
import argparse
import json
import math
import pathlib

from PIL import Image, ImageDraw, ImageFont

import s1p_photo as sc

ARROW = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def foot(it):
    w, d = it["size"]
    if it["facing"] in "EW":
        w, d = d, w
    x, y = it["center"]
    return x - w / 2, y - d / 2, x + w / 2, y + d / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gt = json.loads(pathlib.Path(a.gt).read_text())
    pred = json.loads((pathlib.Path(a.run) / "layout_pred.json").read_text())
    W, D = max(gt["grid"]["x"].values()), max(gt["grid"]["y"].values())
    s, m = 0.075, 60
    img = Image.new("RGB", (int(W * s) + 2 * m, int(D * s) + 2 * m + 40), "white")
    d = ImageDraw.Draw(img)
    X = lambda x: m + x * s
    Y = lambda y: m + (D - y) * s
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    d.polygon([(X(x), Y(y)) for x, y in gt["room"]["polygon"]], outline=(90, 90, 90), width=3)
    for c in gt["columns"]:
        x, y = c["center"]
        d.rectangle([X(x - 300), Y(y + 300), X(x + 300), Y(y - 300)], fill=(40, 40, 40))
    for key, ms in (("racks", sc.match(gt["racks"], sc.valid(pred.get("racks")))), ("crah", sc.match(gt["crah"], sc.valid(pred.get("crah"))))):
        g, p = gt[key], sc.valid(pred.get(key))
        for it in g:
            x0, y0, x1, y1 = foot(it)
            d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], outline=(120, 120, 120), width=2)
        pm = {j: (i, dist) for i, j, dist in ms}
        for j, it in enumerate(p):
            x0, y0, x1, y1 = foot(it)
            if j in pm:
                ok = g[pm[j][0]]["facing"] == it["facing"]
                col = (40, 160, 90) if ok else (230, 140, 20)
            else:
                col = (215, 50, 50)
            d.rectangle([X(x0) + 2, Y(y1) + 2, X(x1) - 2, Y(y0) - 2], fill=col + (0,), outline=col)
            cx, cy = it["center"]
            ax, ay = ARROW.get(it["facing"], (0, 0))
            L = 450
            d.line([(X(cx), Y(cy)), (X(cx + ax * L), Y(cy + ay * L))], fill="white", width=2)
        for i, j, dist in ms:
            if dist > 100:
                d.line([(X(g[i]["center"][0]), Y(g[i]["center"][1])), (X(p[j]["center"][0]), Y(p[j]["center"][1]))], fill=(20, 20, 20), width=1)
    for k, (col, txt) in enumerate((((40, 160, 90), "matched, facing right"), ((230, 140, 20), "matched, facing wrong"),
                                    ((215, 50, 50), "no match within 600 mm"), ((120, 120, 120), "true position (outline)"))):
        x = m + k * 250
        d.rectangle([x, img.height - 32, x + 18, img.height - 14], fill=col)
        d.text((x + 26, img.height - 32), txt, fill="black", font=font)
    img.save(a.out)


if __name__ == "__main__":
    main()
