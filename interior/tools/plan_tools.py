"""Floor-plan utilities for interior/plan.json.

    python interior/tools/plan_tools.py overlay OUT.png   # traced walls over the source image (needs Pillow)
    python interior/tools/plan_tools.py areas             # room areas in m² and 坪
    python interior/tools/plan_tools.py svg OUT.svg       # clean empty-unit plan (pure Python)
    python interior/tools/plan_tools.py metres OUT.json   # plan converted to metres (x east, y north) for Blender / three.js
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
PLAN = json.loads((HERE / "plan.json").read_text(encoding="utf-8"))
S = PLAN["scale"]
OX, OY = PLAN["origin_px"]
PING = 3.305785


def rect_poly(r):
    x0, y0, x1, y1 = r
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def poly_area_px(p):
    a = 0.0
    for i in range(len(p)):
        x0, y0 = p[i]; x1, y1 = p[(i + 1) % len(p)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def to_m(x, y):
    return round((x - OX) * S, 4), round((OY - y) * S, 4)


def rect_m(r):
    (ax, ay), (bx, by) = to_m(r[0], r[3]), to_m(r[2], r[1])
    return [ax, ay, bx, by]            # x0, y0, x1, y1 with y north


def areas():
    tot_in = tot_out = 0.0
    rows = []
    for rm in PLAN["rooms"]:
        if "poly" not in rm:
            continue
        a = poly_area_px(rm["poly"]) * S * S
        rows.append((rm["name"], a))
        if rm.get("outdoor"):
            tot_out += a
        else:
            tot_in += a
    walls = sum(poly_area_px(rect_poly(w["r"])) for w in PLAN["walls"]) * S * S
    walls += sum(poly_area_px(rect_poly(c)) for c in PLAN["columns"]) * S * S
    walls += sum(poly_area_px(rect_poly(o["r"])) for o in PLAN["openings"]) * S * S
    return rows, tot_in, tot_out, walls


# ------------------------------------------------------------------ SVG plan
def svg(out):
    xs = [p for c in PLAN["columns"] for p in (c[0], c[2])] + [p for w in PLAN["walls"] for p in (w["r"][0], w["r"][2])]
    ys = [p for c in PLAN["columns"] for p in (c[1], c[3])] + [p for w in PLAN["walls"] for p in (w["r"][1], w["r"][3])]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = 50.0  # svg units per metre
    pad = 120
    W = (x1 - x0) * S * k + 2 * pad
    H = (y1 - y0) * S * k + 2 * pad + 90

    def P(x, y):
        return (x - x0) * S * k + pad, (y - y0) * S * k + pad + 40

    def R(r, **attrs):
        (ax, ay), (bx, by) = P(r[0], r[1]), P(r[2], r[3])
        a = " ".join(f'{kk.replace("_", "-")}="{v}"' for kk, v in attrs.items())
        return f'<rect x="{ax:.1f}" y="{ay:.1f}" width="{bx - ax:.1f}" height="{by - ay:.1f}" {a}/>'

    def poly(p, **attrs):
        pts = " ".join(f"{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for x, y in p)
        a = " ".join(f'{kk.replace("_", "-")}="{v}"' for kk, v in attrs.items())
        return f'<polygon points="{pts}" {a}/>'

    fills = {"public": "#f4efe6", "wood": "#efe4d2", "stone": "#e7ecef", "tile": "#eceae4", "outdoor": "#e6ebe0", "planter": "#dde8d3"}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" '
         f'font-family="Noto Sans TC, Noto Sans CJK TC, sans-serif">',
         f'<rect width="{W:.0f}" height="{H:.0f}" fill="#fbfaf7"/>',
         f'<text x="{pad}" y="52" font-size="26" font-weight="700" fill="#2b2b2b">{PLAN["name"]}</text>',
         f'<text x="{pad}" y="80" font-size="15" fill="#777">空屋平面示意・依原家具配置圖描繪牆柱門窗（非施工圖）</text>']
    # floors
    for rm in PLAN["rooms"]:
        if "poly" in rm:
            o.append(poly(rm["poly"], fill=fills.get(rm["floor"], "#f4efe6")))
    # hatch for outdoor
    o.append('<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<line x1="0" y1="0" x2="0" y2="8" stroke="#b9c4ae" stroke-width="1"/></pattern>'
             '<pattern id="rc" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<line x1="0" y1="0" x2="0" y2="6" stroke="#777" stroke-width="1.2"/></pattern></defs>')
    for rm in PLAN["rooms"]:
        if rm.get("outdoor") and "poly" in rm:
            o.append(poly(rm["poly"], fill="url(#hatch)"))
    # walls and columns
    for w in PLAN["walls"]:
        col = {"ext": "#2f2f2f", "int": "#4a4a4a", "shaft": "#9a9a9a"}[w["t"]]
        o.append(R(w["r"], fill=col))
    for c in PLAN["columns"]:
        o.append(R(c, fill="#262626"))
        o.append(R(c, fill="url(#rc)"))
    for p in PLAN["parapets"]:
        o.append(R(p, fill="#8a8a8a"))
    # openings
    for op in PLAN["openings"]:
        r = op["r"]; kind = op["kind"]
        horiz = (r[2] - r[0]) > (r[3] - r[1])
        if kind in ("window", "window_high", "slider", "railing"):
            o.append(R(r, fill="#ffffff", stroke="#6f8796", stroke_width="1"))
            (ax, ay), (bx, by) = P(r[0], r[1]), P(r[2], r[3])
            if horiz:
                m = (ay + by) / 2
                o.append(f'<line x1="{ax:.1f}" y1="{m:.1f}" x2="{bx:.1f}" y2="{m:.1f}" stroke="#6f8796" stroke-width="1.2"/>')
                if kind == "slider":
                    mx = (ax + bx) / 2
                    o.append(f'<line x1="{ax:.1f}" y1="{m - 2:.1f}" x2="{mx + 6:.1f}" y2="{m - 2:.1f}" stroke="#6f8796" stroke-width="2"/>')
                    o.append(f'<line x1="{mx - 6:.1f}" y1="{m + 2:.1f}" x2="{bx:.1f}" y2="{m + 2:.1f}" stroke="#6f8796" stroke-width="2"/>')
            else:
                m = (ax + bx) / 2
                o.append(f'<line x1="{m:.1f}" y1="{ay:.1f}" x2="{m:.1f}" y2="{by:.1f}" stroke="#6f8796" stroke-width="1.2"/>')
        elif kind in ("door", "entry"):
            (ax, ay), (bx, by) = P(r[0], r[1]), P(r[2], r[3])
            o.append(R(r, fill="#fbfaf7"))
            if kind == "entry":
                cx = (ax + bx) / 2
                o.append(f'<path d="M{cx - 9:.1f},{by + 26:.1f} L{cx:.1f},{by + 12:.1f} L{cx + 9:.1f},{by + 26:.1f} Z" fill="#2f2f2f"/>')
                o.append(f'<text x="{cx:.1f}" y="{by + 44:.1f}" font-size="13" text-anchor="middle" fill="#555">入口</text>')
                o.append(f'<line x1="{ax:.1f}" y1="{(ay + by) / 2:.1f}" x2="{bx:.1f}" y2="{(ay + by) / 2:.1f}" stroke="#2f2f2f" stroke-width="2.5"/>')
                continue
            s = op.get("side", 1)
            if horiz:
                w = bx - ax
                hx = ax if op.get("hinge") == "start" else bx
                ex = bx if op.get("hinge") == "start" else ax
                yy = (ay if s < 0 else by)
                leaf_y = yy + s * w
                o.append(f'<line x1="{hx:.1f}" y1="{yy:.1f}" x2="{hx:.1f}" y2="{leaf_y:.1f}" stroke="#555" stroke-width="1.6"/>')
                sweep = 1 if (s > 0) == (op.get("hinge") == "start") else 0
                o.append(f'<path d="M{hx:.1f},{leaf_y:.1f} A{w:.1f},{w:.1f} 0 0 {sweep} {ex:.1f},{yy:.1f}" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="3,2"/>')
            else:
                h = by - ay
                hy = ay if op.get("hinge") == "start" else by
                ey = by if op.get("hinge") == "start" else ay
                xx = (ax if s < 0 else bx)
                leaf_x = xx + s * h
                o.append(f'<line x1="{xx:.1f}" y1="{hy:.1f}" x2="{leaf_x:.1f}" y2="{hy:.1f}" stroke="#555" stroke-width="1.6"/>')
                sweep = 0 if (s > 0) == (op.get("hinge") == "start") else 1
                o.append(f'<path d="M{leaf_x:.1f},{hy:.1f} A{h:.1f},{h:.1f} 0 0 {sweep} {xx:.1f},{ey:.1f}" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="3,2"/>')
    # labels
    for rm in PLAN["rooms"]:
        if rm.get("hidden") or "label" not in rm:
            continue
        x, y = P(*rm["label"])
        o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="17" font-weight="600" text-anchor="middle" fill="#333">{rm["name"]}</text>')
        if "poly" in rm:
            a = poly_area_px(rm["poly"]) * S * S
            o.append(f'<text x="{x:.1f}" y="{y + 19:.1f}" font-size="12.5" text-anchor="middle" fill="#777">{a:.1f} m²・{a / PING:.1f} 坪</text>')
    # overall dimensions
    (ax, ay), (bx, by) = P(x0, y0), P(x1, y1)
    wm, hm = (x1 - x0) * S, (y1 - y0) * S
    o.append(f'<line x1="{ax:.1f}" y1="{ay - 26:.1f}" x2="{bx:.1f}" y2="{ay - 26:.1f}" stroke="#888" stroke-width="1"/>')
    for xx in (ax, bx):
        o.append(f'<line x1="{xx:.1f}" y1="{ay - 32:.1f}" x2="{xx:.1f}" y2="{ay - 20:.1f}" stroke="#888" stroke-width="1"/>')
    o.append(f'<text x="{(ax + bx) / 2:.1f}" y="{ay - 32:.1f}" font-size="13" text-anchor="middle" fill="#666">{wm:.2f} m</text>')
    o.append(f'<line x1="{bx + 30:.1f}" y1="{ay:.1f}" x2="{bx + 30:.1f}" y2="{by:.1f}" stroke="#888" stroke-width="1"/>')
    for yy in (ay, by):
        o.append(f'<line x1="{bx + 24:.1f}" y1="{yy:.1f}" x2="{bx + 36:.1f}" y2="{yy:.1f}" stroke="#888" stroke-width="1"/>')
    o.append(f'<text x="{bx + 46:.1f}" y="{(ay + by) / 2:.1f}" font-size="13" fill="#666" transform="rotate(90 {bx + 46:.1f} {(ay + by) / 2:.1f})" text-anchor="middle">{hm:.2f} m</text>')
    # north arrow (top of the drawing = balconies; assume north up) and scale bar
    sx, sy = pad, H - 38
    o.append(f'<rect x="{sx}" y="{sy}" width="{k * 5:.0f}" height="6" fill="none" stroke="#555"/>')
    for i in range(5):
        if i % 2 == 0:
            o.append(f'<rect x="{sx + i * k:.0f}" y="{sy}" width="{k:.0f}" height="6" fill="#555"/>')
    o.append(f'<text x="{sx + k * 5 + 10:.0f}" y="{sy + 7}" font-size="13" fill="#555">5 m</text>')
    rows, tin, tout, _ = areas()
    o.append(f'<text x="{W - pad:.0f}" y="{H - 30:.0f}" font-size="14" text-anchor="end" fill="#444">'
             f'室內淨面積約 {tin:.0f} m²（{tin / PING:.1f} 坪）＋陽台 {tout:.0f} m²；計牆柱約 {(tin + _) / PING:.0f} 坪</text>')
    o.append("</svg>")
    pathlib.Path(out).write_text("\n".join(o), encoding="utf-8")


def metres(out):
    m = {"name": PLAN["name"], "heights": PLAN["heights"], "unit": "m (x east, y north)",
         "columns": [rect_m(c) for c in PLAN["columns"]],
         "walls": [{"r": rect_m(w["r"]), "t": w["t"]} for w in PLAN["walls"]],
         "openings": [{**op, "r": rect_m(op["r"])} for op in PLAN["openings"]],
         "parapets": [rect_m(p) for p in PLAN["parapets"]],
         "rooms": []}
    for rm in PLAN["rooms"]:
        r = {k: v for k, v in rm.items() if k not in ("poly", "label")}
        if "poly" in rm:
            r["poly"] = [list(to_m(x, y)) for x, y in rm["poly"]]
            r["area"] = round(poly_area_px(rm["poly"]) * S * S, 2)
        if "label" in rm:
            r["label"] = list(to_m(*rm["label"]))
        m["rooms"].append(r)
    pathlib.Path(out).write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def overlay(out):
    from PIL import Image, ImageDraw
    im = Image.open(HERE / PLAN["source"].split(" ")[0]).convert("RGB")
    im = im.resize((im.width * 2, im.height * 2))
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    s2 = lambda r: [2 * v for v in r]
    for rm in PLAN["rooms"]:
        if "poly" in rm:
            d.polygon([(2 * x, 2 * y) for x, y in rm["poly"]], outline=(0, 160, 0, 255))
    for w in PLAN["walls"]:
        d.rectangle(s2(w["r"]), fill=(255, 0, 0, 150))
    for c in PLAN["columns"]:
        d.rectangle(s2(c), fill=(160, 0, 160, 120))
    for p in PLAN["parapets"]:
        d.rectangle(s2(p), fill=(255, 140, 0, 160))
    col = {"window": (0, 120, 255), "window_high": (0, 200, 255), "slider": (0, 60, 255), "railing": (255, 200, 0),
           "door": (0, 200, 0), "entry": (0, 120, 0)}
    for op in PLAN["openings"]:
        d.rectangle(s2(op["r"]), fill=(*col[op["kind"]], 190))
    Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB").save(out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "areas":
        rows, tin, tout, walls = areas()
        for n, a in rows:
            print(f"{n:10s} {a:7.2f} m²  {a / PING:5.2f} 坪")
        print(f"indoor net {tin:.1f} m² = {tin / PING:.1f} 坪; outdoor {tout:.1f} m² = {tout / PING:.1f} 坪; walls/cols {walls:.1f} m²")
        print(f"indoor + walls = {(tin + walls) / PING:.1f} 坪")
    else:
        {"overlay": overlay, "svg": svg, "metres": metres}[cmd](sys.argv[2])
