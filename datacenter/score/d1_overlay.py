#!/usr/bin/env python3
"""Plan overlay for D1 (as-built check).

    python d1_overlay.py --run RUN_DIR --design design.json --gt asbuilt.json --out OUT.png

Design items: light grey outline. True changes: blue outline (at the design position for an item that is gone, at the
as-built position for a new item). Predicted items: filled green; a predicted change that is not a true change is
orange (filled if the item was added, an X in an orange outline if a design item was left out). A design item the
prediction correctly leaves out gets a green X. True changes the prediction missed are hatched red.
"""
import argparse
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

import d1_asbuilt as sc

GREY, BLUE, GREEN, ORANGE, RED = (185, 185, 185), (30, 90, 220), (60, 170, 100), (240, 150, 30), (215, 45, 45)
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
    ap.add_argument("--design", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    design_lay = json.loads(pathlib.Path(a.design).read_text())
    gt_lay = json.loads(pathlib.Path(a.gt).read_text())
    try:
        pred_lay = json.loads((pathlib.Path(a.run) / "asbuilt_pred.json").read_text())
        assert isinstance(pred_lay, dict)
    except Exception:
        pred_lay = {}
    ev = sc.evaluate(design_lay, gt_lay, pred_lay)
    W, D = max(design_lay["grid"]["x"].values()), max(design_lay["grid"]["y"].values())
    s, m = 0.075, 60
    img = Image.new("RGB", (int(W * s) + 2 * m, int(D * s) + 2 * m + 90), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)

    def X(x):
        return m + x * s

    def Y(y):
        return m + (D - y) * s

    def px(it, shrink=0):
        x0, y0, x1, y1 = foot(it)
        return [X(x0) + shrink, Y(y1) + shrink, X(x1) - shrink, Y(y0) - shrink]

    def cross(it, col):
        b = px(it, 4)
        d.line([b[0], b[1], b[2], b[3]], fill=col, width=3)
        d.line([b[0], b[3], b[2], b[1]], fill=col, width=3)

    def hatch(box, col):
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        w, h = max(x1 - x0, 1), max(y1 - y0, 1)
        tile = Image.new("RGB", (w, h), "white")
        td = ImageDraw.Draw(tile)
        for o in range(-h, w, 7):
            td.line([o, h, o + h, 0], fill=col, width=2)
        td.rectangle([0, 0, w - 1, h - 1], outline=col, width=2)
        img.paste(tile, (x0, y0))

    d.polygon([(X(x), Y(y)) for x, y in design_lay["room"]["polygon"]], outline=(90, 90, 90), width=3)
    for c in design_lay.get("columns", []):
        x, y = c["center"]
        d.rectangle([X(x - 300), Y(y + 300), X(x + 300), Y(y - 300)], fill=(40, 40, 40))
    for name, v in design_lay["grid"]["x"].items():
        d.text((X(v), m - 30), name, fill=(120, 120, 120), font=font, anchor="mm")
    for name, v in design_lay["grid"]["y"].items():
        d.text((m - 30, Y(v)), name, fill=(120, 120, 120), font=font, anchor="mm")

    gt_ch, pr_ch = ev["gt_changes"], ev["pred_changes"]
    found_g = {i for i, _ in ev["change_pairs"]}
    found_p = {j for _, j in ev["change_pairs"]}
    false_new = {c["other_index"] for j, c in enumerate(pr_ch) if c["label"] == "new" and j not in found_p}
    # predicted items (filled), with a white tick towards the front
    for j, it in enumerate(ev["pred"]):
        col = ORANGE if j in false_new else GREEN
        d.rectangle(px(it, 2), fill=col)
        cx, cy = it["center"]
        ax, ay = ARROW[it["facing"]]
        L = it["size"][1] * 0.42
        d.line([(X(cx), Y(cy)), (X(cx + ax * L), Y(cy + ay * L))], fill="white", width=2)
    # true changes the prediction missed: red hatch (covers whatever the prediction put there)
    for i, c in enumerate(gt_ch):
        if i not in found_g:
            hatch(px(c, 1), RED)
    # design outline
    for it in ev["design"]:
        d.rectangle(px(it), outline=GREY, width=1)
    # design items the prediction leaves out: green X if truly gone, orange X + outline if not
    for j, c in enumerate(pr_ch):
        if c["label"] == "gone":
            if j in found_p:
                cross(c, GREEN)
            else:
                d.rectangle(px(c, 2), outline=ORANGE, width=3)
                cross(c, ORANGE)
    # true changes: blue outline
    for c in gt_ch:
        d.rectangle(px(c, -2 if c["label"] == "gone" else 0), outline=BLUE, width=2)

    y0 = img.height - 78
    d.text((m, y0 - 4), f"D1 as-built check: {len(ev['change_pairs'])} of {len(gt_ch)} true changes found, "
                        f"{len(pr_ch) - len(ev['change_pairs'])} false alarms   (change = item gone or new against the design)",
           fill="black", font=bold)
    legend = [("outline", GREY, "design"), ("outline", BLUE, "true change"), ("fill", GREEN, "predicted item (no false alarm)"),
              ("cross", GREEN, "left out, truly gone"), ("fill", ORANGE, "false alarm: added item"),
              ("cross", ORANGE, "false alarm: item left out"), ("hatch", RED, "true change missed")]
    x = m
    for k, (kind, col, txt) in enumerate(legend):
        if k == 4:
            x, y0 = m, y0 + 26
        yy = y0 + 24
        box = [x, yy, x + 22, yy + 18]
        if kind == "fill":
            d.rectangle(box, fill=col)
        elif kind == "hatch":
            hatch(box, col)
        else:
            d.rectangle(box, outline=col, width=2)
            if kind == "cross":
                d.line([box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3], fill=col, width=3)
                d.line([box[0] + 3, box[3] - 3, box[2] - 3, box[1] + 3], fill=col, width=3)
        d.text((x + 30, yy + 1), txt, fill="black", font=font)
        x += 46 + int(d.textlength(txt, font=font)) + 24
    img.save(a.out)


if __name__ == "__main__":
    main()
