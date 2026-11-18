import json, math
from collections import deque
import numpy as np

RUN = "/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d2-r1"
room = json.load(open(RUN + "/inputs/room.json"))
POLY = room["room"]["polygon"]
EXCL = (18800, 12500, 25100, 18800)

def rect_c(c, sx, sy):
    return (c[0]-sx/2, c[1]-sy/2, c[0]+sx/2, c[1]+sy/2)

COLS = [rect_c(c["center"], 600, 600) for c in room["columns"]]
CRAHS = []
CZONES = []
for u in room["crah"]:
    w, d = u["size"]
    cx, cy = u["center"]
    f = u["facing"]
    if f in "EW":
        r = rect_c((cx, cy), d, w)
        if f == "E": z = (r[2], r[1], r[2]+1500, r[3])
        else: z = (r[0]-1500, r[1], r[0], r[3])
    else:
        r = rect_c((cx, cy), w, d)
        if f == "N": z = (r[0], r[3], r[2], r[3]+1500)
        else: z = (r[0], r[1]-1500, r[2], r[1])
    CRAHS.append(r); CZONES.append(z)
CRAH_C = [u["center"] for u in room["crah"]]
DZONES = []
for dd in room["doors"]:
    cx, cy = dd["center"]; hw = (dd["width"]+600)/2
    if dd["wall"] == "S": DZONES.append((cx-hw, cy+100, cx+hw, cy+100+1500))
    else: DZONES.append((cx-hw, cy-100-1500, cx+hw, cy-100))
D1 = [d for d in room["doors"] if d["id"] == "D1"][0]
START = (D1["center"][0], D1["center"][1] + 100 + 600) if D1["wall"] == "S" else None
OBST = COLS + CRAHS
print("CRAH", CRAHS, "zones", CZONES, "doorzones", DZONES, "start", START)

E = 1e-6
def ov(a, b):
    return a[0] < b[2]-E and b[0] < a[2]-E and a[1] < b[3]-E and b[1] < a[3]-E

def inside(r):
    if r[0] < 100-E or r[1] < 100-E or r[2] > 25100+E or r[3] > 18800+E: return False
    return not ov(r, EXCL)

def fp(k):
    w = k["size"][0]; cx, cy = k["center"]
    if k["facing"] in "NS": return rect_c((cx, cy), w, 1200)
    return rect_c((cx, cy), 1200, w)

def zone(r, f, dist):
    x0, y0, x1, y1 = r
    if f == "N": return (x0, y1, x1, y1+dist)
    if f == "S": return (x0, y0-dist, x1, y0)
    if f == "E": return (x1, y0, x1+dist, y1)
    return (x0-dist, y0, x0, y1)
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
BACK = OPP

def access_pts(k):
    r = fp(k); cx, cy = k["center"]; f = k["facing"]
    v = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}[f]
    h = (1200/2)
    fpnt = (cx + v[0]*(h+600), cy + v[1]*(h+600))
    rpnt = (cx - v[0]*(h+450), cy - v[1]*(h+450))
    return fpnt, rpnt

def check(racks, verbose=False):
    bad = {}
    def mark(i, why):
        bad.setdefault(i, set()).add(why)
    n = len(racks)
    F = [fp(k) for k in racks]
    FR = [zone(F[i], racks[i]["facing"], 1200) for i in range(n)]
    RR = [zone(F[i], BACK[racks[i]["facing"]], 900) for i in range(n)]
    CO = [zone(F[i], racks[i]["facing"], 3000) for i in range(n)]
    for i, k in enumerate(racks):
        if k["size"][1] != 1200 or k["size"][0] not in (600, 800) or k["facing"] not in "NSEW":
            mark(i, "size")
        if not inside(F[i]): mark(i, "R1")
        for o in OBST:
            if ov(F[i], o): mark(i, "R2o")
            if ov(FR[i], o): mark(i, "R3o")
            if ov(RR[i], o): mark(i, "R4o")
        if not inside(FR[i]): mark(i, "R3in")
        if not inside(RR[i]): mark(i, "R4in")
        for z in CZONES:
            if ov(F[i], z): mark(i, "R6")
        for z in DZONES:
            if ov(F[i], z): mark(i, "R7")
        if k["size"][0] == 800:
            if min(math.hypot(k["center"][0]-c[0], k["center"][1]-c[1]) for c in CRAH_C) > 7000+E:
                mark(i, "R9")
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if j > i and ov(F[i], F[j]): mark(i, "R2"); mark(j, "R2")
            if ov(FR[i], F[j]): mark(i, "R3"); mark(j, "R3")
            if ov(RR[i], F[j]): mark(i, "R4"); mark(j, "R4")
            if ov(CO[i], F[j]) and racks[j]["facing"] != OPP[racks[i]["facing"]]:
                mark(i, "R5"); mark(j, "R5")
    # R8
    xs = np.arange(0, 25201, 50.0); ys = np.arange(0, 18901, 50.0)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    ins = ((X > 100) & (X < 25100) & (Y > 100) & (Y < 12500)) | ((X > 100) & (X < 18800) & (Y >= 12500) & (Y < 18800))
    wd = np.full(X.shape, 1e9)
    for a in range(len(POLY)):
        p = POLY[a]; q = POLY[(a+1) % len(POLY)]
        x0, x1 = sorted((p[0], q[0])); y0, y1 = sorted((p[1], q[1]))
        dx = np.maximum(np.maximum(x0 - X, 0), X - x1)
        dy = np.maximum(np.maximum(y0 - Y, 0), Y - y1)
        wd = np.minimum(wd, np.hypot(dx, dy))
    walk = ins & (wd >= 450 - E)
    for r in OBST + F:
        i0 = max(0, int((r[0]-500)//50)); i1 = min(len(xs)-1, int((r[2]+500)//50)+1)
        j0 = max(0, int((r[1]-500)//50)); j1 = min(len(ys)-1, int((r[3]+500)//50)+1)
        sx = X[i0:i1+1, j0:j1+1]; sy = Y[i0:i1+1, j0:j1+1]
        dx = np.maximum(np.maximum(r[0]-sx, 0), sx-r[2]); dy = np.maximum(np.maximum(r[1]-sy, 0), sy-r[3])
        d = np.hypot(dx, dy)
        sub = walk[i0:i1+1, j0:j1+1]
        sub[d < 450 - E] = False
    reach = np.zeros(X.shape, bool)
    si, sj = int(round(START[0]/50)), int(round(START[1]/50))
    print("start walkable", bool(walk[si, sj]))
    if walk[si, sj]:
        dq = deque([(si, sj)]); reach[si, sj] = True
        W, H = walk.shape
        while dq:
            a, b = dq.popleft()
            for na, nb in ((a+1, b), (a-1, b), (a, b+1), (a, b-1)):
                if 0 <= na < W and 0 <= nb < H and walk[na, nb] and not reach[na, nb]:
                    reach[na, nb] = True; dq.append((na, nb))
    def ok(p):
        ci, cj = int(round(p[0]/50)), int(round(p[1]/50))
        for a in range(ci-4, ci+5):
            for b in range(cj-4, cj+5):
                if 0 <= a < reach.shape[0] and 0 <= b < reach.shape[1] and reach[a, b]:
                    if math.hypot(a*50-p[0], b*50-p[1]) <= 150 + E: return True
        return False
    for i, k in enumerate(racks):
        fpnt, rpnt = access_pts(k)
        if not ok(fpnt): mark(i, "R8f")
        if not ok(rpnt): mark(i, "R8r")
    return bad

# ---------------- generator ----------------
def sub_intervals(base, blocks):
    segs = [base]
    for b0, b1 in blocks:
        new = []
        for s0, s1 in segs:
            if b1 <= s0 or b0 >= s1: new.append((s0, s1)); continue
            if b0 > s0: new.append((s0, b0))
            if b1 < s1: new.append((b1, s1))
        segs = new
    return [s for s in segs if s[1]-s[0] >= 600]

def row_segments(axis, lo, facing, a0, a1, extra):
    # axis 'y': band x [lo,lo+1200], racks stacked along y
    if axis == "y":
        band = (lo, lo+1200)
    else:
        band = (lo, lo+1200)
    fdir = facing
    # clearance span perpendicular to row
    if axis == "y":
        if facing == "E": span = (lo-900, lo+1200+1200)
        else: span = (lo-1200, lo+1200+900)
    else:
        if facing == "N": span = (lo-900, lo+1200+1200)
        else: span = (lo-1200, lo+1200+900)
    blocks = list(extra)
    def perp(r):  # (perp lo, perp hi, along lo, along hi)
        return (r[0], r[2], r[1], r[3]) if axis == "y" else (r[1], r[3], r[0], r[2])
    for o in OBST:
        p0, p1, q0, q1 = perp(o)
        if p0 < span[1] and span[0] < p1: blocks.append((q0, q1))
    for z in CZONES + DZONES:
        p0, p1, q0, q1 = perp(z)
        if p0 < band[1] and band[0] < p1: blocks.append((q0, q1))
    return sub_intervals((a0, a1), blocks)

ROWS = [
    ("y", 1000, "E", 1000, 18650, [(3900, 4800), (10800, 11700)]),
    ("y", 3400, "W", 1000, 18650, []),
    ("y", 5500, "E", 1000, 18650, []),
    ("y", 7900, "W", 1000, 18650, []),
    ("y", 10000, "E", 1000, 18650, []),
    ("y", 12400, "W", 1000, 18650, []),
    ("y", 14500, "E", 1000, 18650, []),
    ("y", 16900, "W", 1000, 11650, []),
    ("y", 19000, "E", 1000, 12350, []),
    ("y", 21400, "W", 1000, 12350, []),
    ("x", 1000, "N", 23500, 25100, []),
    ("x", 3400, "S", 23500, 25100, []),
    ("x", 5500, "N", 23500, 25100, []),
]
NGPU = 8
segs = []
for (axis, lo, f, a0, a1, extra) in ROWS:
    for s in row_segments(axis, lo, f, a0, a1, extra):
        segs.append(dict(axis=axis, lo=lo, f=f, s0=s[0], s1=s[1]))

def make(seg, ngpu, gpu_end):
    L = seg["s1"] - seg["s0"]
    n = int(L // 600)
    widths = [600]*n
    for t in range(ngpu):
        if gpu_end: widths[n-1-t] = 800
        else: widths[t] = 800
    out = []; a = seg["s0"]
    for w in widths:
        c_al = a + w/2; a += w
        if seg["axis"] == "y": c = [seg["lo"]+600, c_al]
        else: c = [c_al, seg["lo"]+600]
        out.append(dict(center=c, size=[w, 1200], facing=seg["f"]))
    return out

def gdist(c):
    return min(math.hypot(c[0]-q[0], c[1]-q[1]) for q in CRAH_C)

# allocate free GPU swaps
alloc = []
for si, s in enumerate(segs):
    L = s["s1"]-s["s0"]; n = int(L//600); free = min(int((L-600*n)//200), n)
    best = (0, True)
    for g in range(free, 0, -1):
        for end in (True, False):
            rk = make(s, g, end)
            if all(gdist(r["center"]) <= 6900 for r in rk if r["size"][0] == 800):
                if g > best[0]: best = (g, end)
    s["gfree"], s["gend"] = best
total_free = sum(s["gfree"] for s in segs)
print("free gpu slots", total_free)
left = NGPU
for s in sorted(segs, key=lambda s: -s["gfree"]):
    g = min(s["gfree"], left); s["g"] = g; left -= g
if left > 0: print("NOT ENOUGH FREE GPU SLOTS", left)
racks = []
for s in segs:
    racks += make(s, s.get("g", 0), s.get("gend", True))
for i, r in enumerate(racks):
    r["id"] = "R%03d" % (i+1)
print("generated", len(racks), "gpu", sum(1 for r in racks if r["size"][0] == 800))
for s in segs:
    print(s["axis"], s["lo"], s["f"], s["s0"], s["s1"], "n", int((s["s1"]-s["s0"])//600), "g", s.get("g", 0))

bad = check(racks)
print("bad first pass", len(bad))
for i, w in sorted(bad.items()):
    print("  ", racks[i]["id"], racks[i]["center"], racks[i]["facing"], racks[i]["size"][0], sorted(w))
it = 0
while bad and it < 10:
    racks = [r for i, r in enumerate(racks) if i not in bad]
    bad = check(racks); it += 1
    print("iter", it, "bad", len(bad))
ng = sum(1 for r in racks if r["size"][0] == 800)
print("FINAL valid", len(racks), "gpu", ng, "net", len(racks) - 2*abs(ng-8))
json.dump({"units": "mm", "racks": [dict(id=r["id"], center=r["center"], size=r["size"], facing=r["facing"]) for r in racks]},
          open(RUN + "/layout_design.json", "w"), indent=1)

# scene
try:
    for o in list(bpy.data.objects):
        if o.name.startswith("P_"): bpy.data.objects.remove(o, do_unlink=True)
    rot = {"S": 0, "N": math.pi, "E": math.pi/2, "W": -math.pi/2}
    for r in racks:
        t = bpy.data.objects["RackG" if r["size"][0] == 800 else "RackA"]
        o = t.copy(); o.name = "P_" + r["id"]
        o.location = (r["center"][0]/1000, r["center"][1]/1000, 0.6)
        o.rotation_euler = (0, 0, rot[r["facing"]])
        bpy.context.scene.collection.objects.link(o)
    for i, u in enumerate(room["crah"]):
        t = bpy.data.objects["CRAH"]; o = t.copy(); o.name = "P_CRAH%d" % i
        o.location = (u["center"][0]/1000, u["center"][1]/1000, 0.6)
        o.rotation_euler = (0, 0, rot[u["facing"]])
        bpy.context.scene.collection.objects.link(o)
except Exception as ex:
    print("scene err", ex)
