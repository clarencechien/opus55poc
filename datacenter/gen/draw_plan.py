#!/usr/bin/env python3
"""Draw an architectural-style equipment layout plan from a layout.json.

    python draw_plan.py LAYOUT.json OUT.png

The drawing carries everything needed to rebuild the layout (grid, dimension chains, notes, legend) but
never states the answer directly: no coordinates, no aisle labels. Rack fronts are marked with the usual
front edge + triangle symbol.
"""
from __future__ import annotations

import json
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
INK = (20, 20, 20)
GRID = (120, 120, 120)
DIM = (40, 40, 40)
CANVAS_W = 2400
ML, MR, MT, MB = 360, 330, 330, 560


def margins(lay):
    if lay.get("scenario", "easy") == "easy":
        return 360, 330, 330, 560
    return 420, 380, 400, 700  # margins (px)


def font(sz, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, sz)


class Plan:
    def __init__(self, lay):
        self.lay = lay
        gx, gy = lay["grid"]["x"], lay["grid"]["y"]
        self.W, self.D = max(gx.values()), max(gy.values())
        global ML, MR, MT, MB
        ML, MR, MT, MB = margins(lay)
        self.s = (CANVAS_W - ML - MR) / self.W
        self.H = int(MT + MB + self.D * self.s)
        self.img = Image.new("RGB", (CANVAS_W, self.H), "white")
        self.d = ImageDraw.Draw(self.img)

    def X(self, x):
        return ML + x * self.s

    def Y(self, y):
        return MT + (self.D - y) * self.s

    def rect(self, x0, y0, x1, y1, **kw):
        self.d.rectangle([self.X(x0), self.Y(y1), self.X(x1), self.Y(y0)], **kw)

    def text(self, xy, s, sz=18, bold=False, anchor="mm", fill=INK):
        self.d.text(xy, s, font=font(sz, bold), fill=fill, anchor=anchor)

    def vtext(self, xy, s, sz=18):
        f = font(sz)
        l, t, r, b = f.getbbox(s)
        im = Image.new("RGBA", (r - l + 4, b - t + 4), (255, 255, 255, 0))
        ImageDraw.Draw(im).text((2 - l, 2 - t), s, font=f, fill=DIM)
        im = im.rotate(90, expand=True)
        self.img.paste(im, (int(xy[0] - im.width / 2), int(xy[1] - im.height / 2)), im)

    def dashed(self, p0, p1, dash=(28, 8, 4, 8), fill=GRID, width=1):
        import math
        (x0, y0), (x1, y1) = p0, p1
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        t, k = 0.0, 0
        while t < L:
            seg = dash[k % len(dash)]
            if k % 2 == 0:
                e = min(t + seg, L)
                self.d.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)], fill=fill, width=width)
            t += seg
            k += 1

    # ---- dimension chains ----
    def hchain(self, xs, ypx, ext_from_px=None):
        xs = sorted(xs)
        self.d.line([(self.X(xs[0]) - 12, ypx), (self.X(xs[-1]) + 12, ypx)], fill=DIM, width=1)
        for x in xs:
            px = self.X(x)
            if ext_from_px is not None:
                self.d.line([(px, ext_from_px), (px, ypx + (8 if ext_from_px < ypx else -8))], fill=(150, 150, 150), width=1)
            self.d.line([(px - 7, ypx + 7), (px + 7, ypx - 7)], fill=DIM, width=2)
        for a, b in zip(xs, xs[1:]):
            self.text(((self.X(a) + self.X(b)) / 2, ypx - 14), f"{round(b - a)}", sz=17)

    def vchain(self, ys, xpx, ext_from_px=None):
        ys = sorted(ys)
        self.d.line([(xpx, self.Y(ys[-1]) - 12), (xpx, self.Y(ys[0]) + 12)], fill=DIM, width=1)
        for y in ys:
            py = self.Y(y)
            if ext_from_px is not None:
                self.d.line([(ext_from_px, py), (xpx + (8 if ext_from_px < xpx else -8), py)], fill=(150, 150, 150), width=1)
            self.d.line([(xpx - 7, py + 7), (xpx + 7, py - 7)], fill=DIM, width=2)
        for a, b in zip(ys, ys[1:]):
            self.vtext((xpx - 14, (self.Y(a) + self.Y(b)) / 2), f"{round(b - a)}", sz=17)

    def triangle(self, cx, cy, facing, size):
        # filled triangle whose tip points along `facing`, base at (cx, cy) on the front edge (mm coords)
        s = size
        if facing == "N":
            pts = [(cx - s, cy), (cx + s, cy), (cx, cy + s * 1.2)]
        elif facing == "S":
            pts = [(cx - s, cy), (cx + s, cy), (cx, cy - s * 1.2)]
        elif facing == "E":
            pts = [(cx, cy - s), (cx, cy + s), (cx + s * 1.2, cy)]
        else:
            pts = [(cx, cy - s), (cx, cy + s), (cx - s * 1.2, cy)]
        self.d.polygon([(self.X(x), self.Y(y)) for x, y in pts], fill=INK)

    def equipment(self, item, label_sz, fill, cross=False):
        cx, cy = item["center"]
        w, dpt = item["size"]
        f = item["facing"]
        hw, hd = (w / 2, dpt / 2) if f in "NS" else (dpt / 2, w / 2)
        x0, y0, x1, y1 = cx - hw, cy - hd, cx + hw, cy + hd
        self.rect(x0, y0, x1, y1, fill=fill, outline=INK, width=2)
        if cross:
            self.d.line([(self.X(x0), self.Y(y0)), (self.X(x1), self.Y(y1))], fill=(140, 140, 140), width=1)
            self.d.line([(self.X(x0), self.Y(y1)), (self.X(x1), self.Y(y0))], fill=(140, 140, 140), width=1)
        edge = {"N": [(x0, y1), (x1, y1)], "S": [(x0, y0), (x1, y0)], "E": [(x1, y0), (x1, y1)], "W": [(x0, y0), (x0, y1)]}[f]
        self.d.line([(self.X(a), self.Y(b)) for a, b in edge], fill=INK, width=5)
        mid = ((edge[0][0] + edge[1][0]) / 2, (edge[0][1] + edge[1][1]) / 2)
        self.triangle(mid[0], mid[1], f, 110)
        self.text((self.X(cx), self.Y(cy)), item["id"], sz=label_sz, bold=True)

    def draw(self):
        lay, d = self.lay, self.d
        gx, gy = lay["grid"]["x"], lay["grid"]["y"]
        t = lay["room"]["wall_thickness"]
        h = t / 2
        # grid lines + bubbles (north and west sides)
        for k, x in gx.items():
            off = 240 if lay.get("scenario", "easy") == "easy" else 290
            self.dashed((self.X(x), self.Y(self.D) - off + 30), (self.X(x), self.Y(0) + 40))
            bx, by = self.X(x), self.Y(self.D) - off
            d.ellipse([bx - 28, by - 28, bx + 28, by + 28], outline=INK, width=2, fill="white")
            self.text((bx, by), k, sz=26, bold=True)
        for k, y in gy.items():
            off = 240 if lay.get("scenario", "easy") == "easy" else 290
            self.dashed((self.X(0) - off + 30, self.Y(y)), (self.X(self.W) + 40, self.Y(y)))
            bx, by = self.X(0) - off, self.Y(y)
            d.ellipse([bx - 28, by - 28, bx + 28, by + 28], outline=INK, width=2, fill="white")
            self.text((bx, by), k, sz=26, bold=True)
        # walls (outer face to inner face), grey; rooms white
        self.rect(-h, -h, self.W + h, self.D + h, fill=(95, 95, 95))
        if lay.get("scenario", "easy") == "easy":
            self.rect(h, h, self.W - h, self.D - h, fill="white")
        else:
            self.d.polygon([(self.X(x), self.Y(y)) for x, y in lay["room"]["polygon"]], fill="white")
            if lay.get("ups_room"):
                up = lay["ups_room"]["polygon"]
                self.d.polygon([(self.X(x), self.Y(y)) for x, y in up], fill=(236, 236, 236))
                xs, ys = [p[0] for p in up], [p[1] for p in up]
                for k in range(0, int((max(xs) - min(xs) + max(ys) - min(ys)) / 400)):
                    a = min(xs) + k * 400
                    pts = [(a, min(ys)), (a - (max(ys) - min(ys)), max(ys))]
                    (x0, y0), (x1, y1) = pts
                    # clip the hatch line to the room box
                    if x1 < min(xs):
                        y1 = y0 + (x0 - min(xs)); x1 = min(xs)
                    if x0 > max(xs):
                        y0 = y0 + (x0 - max(xs)); x0 = max(xs)
                    if y0 < y1:
                        self.d.line([(self.X(x0), self.Y(y0)), (self.X(x1), self.Y(y1))], fill=(205, 205, 205), width=1)
                self.text((self.X((min(xs) + max(xs)) / 2), self.Y((min(ys) + max(ys)) / 2)), "UPS ROOM", sz=26, bold=True)
                self.text((self.X((min(xs) + max(xs)) / 2), self.Y((min(ys) + max(ys)) / 2) + 32), "(NOT PART OF DATA HALL)", sz=16)
        for door in lay["doors"]:
            cx, cy = door["center"]
            w = door["width"]
            if lay.get("scenario", "easy") != "easy":
                self.door_generic(door, h)
                continue
            if door["wall"] in "EW":
                self.rect(cx - h - 2, cy - w / 2, cx + h + 2, cy + w / 2, fill="white")
                sgn = -1 if door["wall"] == "E" else 1
                inner_x = cx + sgn * h
                for yy, a0, a1 in ((cy - w / 2, 0, 90), (cy + w / 2, 270, 360)):
                    r = w / 2 * self.s
                    px, py = self.X(inner_x), self.Y(yy)
                    if sgn < 0:
                        a0, a1 = (90, 180) if a0 == 0 else (180, 270)
                    d.arc([px - r, py - r, px + r, py + r], a0, a1, fill=INK, width=1)
                    ex = inner_x + sgn * w / 2
                    d.line([(px, py), (self.X(ex), py)], fill=INK, width=2)
            self.text((self.X(cx) + 70, self.Y(cy)), door["id"], sz=18, bold=True)
        # raised-floor tile hint inside the room is omitted on purpose (clutter); columns
        for c in lay["columns"]:
            (cx, cy), (w, dd) = c["center"], c["size"]
            self.rect(cx - w / 2, cy - dd / 2, cx + w / 2, cy + dd / 2, fill=INK)
        for c in lay["crah"]:
            self.equipment(c, 15, (215, 228, 240), cross=True)
        for r in lay["racks"]:
            self.equipment(r, 17, (200, 214, 200) if r["size"][0] != 600 else (232, 232, 232))
        if lay.get("scenario", "easy") == "easy":
            self.dims()
        else:
            self.dims_generic()
        self.notes()
        return self.img

    def dims(self):
        lay = self.lay
        gx, gy = lay["grid"]["x"], lay["grid"]["y"]
        top0 = self.Y(self.D) - 110
        self.hchain(list(gx.values()), top0)
        self.hchain([0, self.W], top0 - 50)
        # left: grid chain, overall, plus CRAH centrelines on an inner line
        l0 = self.X(0) - 110
        self.vchain(list(gy.values()), l0)
        self.vchain([0, self.D], l0 - 50)
        crah_ys = [c["center"][1] for c in lay["crah"]]
        self.vchain([0] + crah_ys + [self.D], self.X(0) - 60, ext_from_px=self.X(lay["crah"][0]["center"][0]))
        for c in lay["crah"]:
            self.dashed((self.X(0) - 70, self.Y(c["center"][1])), (self.X(c["center"][0]), self.Y(c["center"][1])),
                        dash=(10, 6), fill=(150, 150, 150))
        # bottom: rack row extents along x
        rx = sorted({round(r["center"][0] - r["size"][0] / 2) for r in lay["racks"]} |
                    {round(r["center"][0] + r["size"][0] / 2) for r in lay["racks"]})
        b0 = self.Y(0) + 90
        self.hchain([0, rx[0], rx[-1], self.W], b0, ext_from_px=self.Y(lay["aisles"][1]["rect"][1]))
        self.hchain([rx[0], rx[0] + 600], b0 + 55, ext_from_px=None)
        # right: rack rows along y, and door
        ys = set()
        for r in lay["racks"]:
            cy, dd = r["center"][1], r["size"][1]
            ys |= {round(cy - dd / 2), round(cy + dd / 2)}
        r0 = self.X(self.W) + 90
        self.vchain([0] + sorted(ys) + [gy["2"]], r0, ext_from_px=self.X(rx[-1]))
        door = lay["doors"][0]
        self.vchain([gy["2"], door["center"][1], self.D], r0 + 55)

    def door_generic(self, door, h):
        d = self.d
        cx, cy = door["center"]
        w = door["width"]
        wall = door["wall"]
        into = {"S": (0, 1), "N": (0, -1), "E": (-1, 0), "W": (1, 0)}[wall]
        if wall in "NS":
            self.rect(cx - w / 2, cy - h - 2, cx + w / 2, cy + h + 2, fill="white")
            leaves = [(cx - w / 2, +1), (cx + w / 2, -1)] if w >= 1500 else [(cx - w / 2, +1)]
            lw = w / 2 if w >= 1500 else w
            for hx, sgn in leaves:
                hy = cy + into[1] * h
                ex, ey = hx, hy + into[1] * lw
                d.line([(self.X(hx), self.Y(hy)), (self.X(ex), self.Y(ey))], fill=INK, width=2)
                r = lw * self.s
                px, py = self.X(hx), self.Y(hy)
                # quarter arc from the open leaf back to the wall
                if into[1] > 0:
                    a0, a1 = (270, 360) if sgn > 0 else (180, 270)
                else:
                    a0, a1 = (0, 90) if sgn > 0 else (90, 180)
                d.arc([px - r, py - r, px + r, py + r], a0, a1, fill=INK, width=1)
            self.text((self.X(cx), self.Y(cy) + (34 if into[1] < 0 else -34)), door["id"], sz=18, bold=True)
        else:
            self.rect(cx - h - 2, cy - w / 2, cx + h + 2, cy + w / 2, fill="white")
            self.text((self.X(cx) + (60 if into[0] < 0 else -60), self.Y(cy)), door["id"], sz=18, bold=True)

    def dims_generic(self):
        lay = self.lay
        gx, gy = lay["grid"]["x"], lay["grid"]["y"]
        W, D = self.W, self.D
        # grid chains and overall (top, left)
        self.hchain(list(gx.values()), self.Y(D) - 150)
        self.hchain([0, W], self.Y(D) - 200)
        self.vchain(list(gy.values()), self.X(0) - 150)
        self.vchain([0, D], self.X(0) - 200)
        xrows = [r for r in lay["racks"] if r["facing"] in "NS"]
        yrows = [r for r in lay["racks"] if r["facing"] in "EW"]
        # x-running rows: one bottom chain per cold-aisle pair (all rack edges where width changes or a gap starts/ends)
        groups = {}
        for r in xrows:
            key = next(i for i, a in enumerate(lay["aisles"]) if a["rect"][0] - 1 <= r["center"][0] <= a["rect"][2] + 1
                       and abs((a["rect"][1] + a["rect"][3]) / 2 - r["center"][1]) < 2500)
            groups.setdefault(key, []).append(r)
        line = 0
        for key in sorted(groups, key=lambda k: min(r["center"][0] for r in groups[k])):
            edges = set()
            for row in {r["row"] for r in groups[key]}:
                rs = sorted((r for r in groups[key] if r["row"] == row), key=lambda r: r["center"][0])
                prev = None
                for r in rs:
                    x0, x1 = r["center"][0] - r["size"][0] / 2, r["center"][0] + r["size"][0] / 2
                    if prev is None or abs(prev[1] - x0) > 1 or prev[2] != r["size"][0]:
                        edges.add(round(x0))
                        if prev is not None:
                            edges.add(round(prev[1]))
                    prev = (x0, x1, r["size"][0])
                edges.add(round(prev[1]))
            self.hchain([0] + sorted(edges), self.Y(0) + 90 + 55 * line)
            line += 1
        for door in lay["doors"]:
            if door["wall"] == "S":
                self.hchain([0, door["center"][0]], self.Y(0) + 90 + 55 * line)
                line += 1
        # right: y edges of x-running rows; east CRAH centrelines on a second line
        ys = sorted({round(r["center"][1] - r["size"][1] / 2) for r in xrows} | {round(r["center"][1] + r["size"][1] / 2) for r in xrows})
        r0 = self.X(W) + 90
        self.vchain([0] + ys + [gy["3"]], r0)
        east = [c for c in lay["crah"] if c["facing"] == "W"]
        if east:
            self.vchain([0] + [c["center"][1] for c in east] + [gy["3"]], r0 + 55)
        # left (inner lines): west CRAH centrelines; north-south rows' y extents
        west = [c for c in lay["crah"] if c["facing"] == "E"]
        if west:
            self.vchain([0] + [c["center"][1] for c in west] + [D], self.X(0) - 55)
        if yrows:
            yv = sorted({round(r["center"][1] - r["size"][0] / 2) for r in yrows} | {round(r["center"][1] + r["size"][0] / 2) for r in yrows})
            self.vchain([gy["3"], yv[0], yv[-1], D], self.X(0) - 100)
            xv = sorted({round(r["center"][0] - r["size"][1] / 2) for r in yrows} | {round(r["center"][0] + r["size"][1] / 2) for r in yrows})
            top_pts = [0] + xv
        else:
            top_pts = [0]
        # top inner line: north-south rows' x edges and the door in the internal wall
        for door in lay["doors"]:
            if door["wall"] == "N":
                top_pts += [gx["D"], door["center"][0], W]
        self.hchain(sorted(set(top_pts)), self.Y(D) - 95)

    def notes(self):
        d = self.d
        x, y = 40, self.H - MB + 250
        self.text((x, y), "DATA HALL 01 - EQUIPMENT LAYOUT PLAN", sz=30, bold=True, anchor="lm")
        lines = [
            "1. ALL DIMENSIONS IN mm. GRID LINES ARE ON WALL / COLUMN CENTRELINES.",
            "2. WALLS 200 THK. COLUMNS 600 x 600.",
            "3. RAISED FLOOR: FINISHED FLOOR +600 ABOVE SLAB. CLEAR HEIGHT 3000 ABOVE RAISED FLOOR.",
            "4. RACKS 600 W x 1200 D TYP.  CRAH UNITS 1800 W x 900 D.  RACKS IN A ROW ARE BUTTED TOGETHER.",
            "5. D1: 1800 DOUBLE DOOR.",
        ]
        if self.lay.get("scenario", "easy") != "easy":
            lines = lines[:4] + ["5. GPU RACKS (SHADED) 800 W x 1200 D.  D1: 1800 DOUBLE DOOR.  D2: 1200 SINGLE DOOR."]
        for i, s in enumerate(lines):
            self.text((x, y + 45 + i * 32), s, sz=19, anchor="lm")
        # legend
        lx, ly = CANVAS_W - 780, self.H - MB + 260
        d.rectangle([lx, ly, lx + 60, ly + 30], fill=(232, 232, 232), outline=INK, width=2)
        d.line([(lx, ly), (lx + 60, ly)], fill=INK, width=5)
        d.polygon([(lx + 18, ly), (lx + 42, ly), (lx + 30, ly - 20)], fill=INK)
        self.text((lx + 80, ly + 10), "EQUIPMENT FRONT (AIR INTAKE)", sz=18, anchor="lm")
        # north arrow + scale bar
        nx, ny = CANVAS_W - 120, MT - 200
        d.polygon([(nx, ny - 60), (nx - 20, ny), (nx + 20, ny)], fill=INK)
        self.text((nx, ny + 22), "N", sz=24, bold=True)
        sx, sy = CANVAS_W - 780, self.H - MB + 340
        for i in range(5):
            d.rectangle([sx + i * 1000 * self.s, sy, sx + (i + 1) * 1000 * self.s, sy + 12],
                        fill=INK if i % 2 == 0 else "white", outline=INK)
        self.text((sx, sy + 30), "0", sz=16)
        self.text((sx + 5000 * self.s, sy + 30), "5 m", sz=16)


def main():
    lay = json.load(open(sys.argv[1]))
    Plan(lay).draw().save(sys.argv[2])


if __name__ == "__main__":
    main()
