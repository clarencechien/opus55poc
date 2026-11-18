import json, math, itertools
from mathutils import Vector

# ---------- obstacles from scene ----------
boxes = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = [min(v[i] for v in bb) for i in range(3)]
    hi = [max(v[i] for v in bb) for i in range(3)]
    loc, d = o.location, o.dimensions
    lo2 = [loc[i] - d[i] / 2 for i in range(3)]
    hi2 = [loc[i] + d[i] / 2 for i in range(3)]
    if any(abs(lo[i] - lo2[i]) > 1e-6 for i in range(3)) or any(abs(hi[i] - hi2[i]) > 1e-6 for i in range(3)):
        print("MISMATCH", o.name, lo, hi, lo2, hi2)
    boxes.append((o.name, lo, hi))

print("n obstacles =", len(boxes))
print("--- boxes reaching above z=2.6 ---")
for n, lo, hi in sorted(boxes, key=lambda b: b[1][2]):
    if hi[2] > 2.6:
        print("%-22s x[%6.3f,%6.3f] y[%6.3f,%6.3f] z[%6.3f,%6.3f]" % (n, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
json.dump(boxes, open("obstacles.json", "w"))

# ---------- geometry helpers ----------
def pdist(p, lo, hi):
    d = 0.0
    for i in range(3):
        t = max(lo[i] - p[i], p[i] - hi[i], 0.0)
        d += t * t
    return math.sqrt(d)

def seg_sample(pts, step=0.02):
    smp = []
    L = 0.0
    s = 0.0
    smp.append((0.0, list(pts[0])))
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ln = math.dist(a, b)
        k = int(math.floor(ln / step))
        for j in range(1, k + 1):
            t = min(j * step, ln)
            smp.append((s + t, [a[m] + (b[m] - a[m]) * t / ln for m in range(3)]))
        s += ln
        if abs(s - L - ln) > 1e-9: pass
        L = s
    if math.dist(smp[-1][1], pts[-1]) > 1e-9:
        smp.append((L, list(pts[-1])))
    return smp, L

def seg_seg_dist(p1, p2, q1, q2):
    u = [p2[i] - p1[i] for i in range(3)]
    v = [q2[i] - q1[i] for i in range(3)]
    w = [p1[i] - q1[i] for i in range(3)]
    a = sum(x * x for x in u); b = sum(u[i] * v[i] for i in range(3)); c = sum(x * x for x in v)
    d = sum(u[i] * w[i] for i in range(3)); e = sum(v[i] * w[i] for i in range(3))
    EPS = 1e-9
    if a < EPS and c < EPS: return math.dist(p1, q1)
    if a < EPS:
        t = max(0.0, min(1.0, e / c)); sc = [q1[i] + t * v[i] for i in range(3)]
        return math.dist(p1, sc)
    if c < EPS:
        s = max(0.0, min(1.0, -d / a)); sc = [p1[i] + s * u[i] for i in range(3)]
        return math.dist(sc, q1)
    denom = a * c - b * b
    if denom < EPS:
        best = 1e9
        for s in (0.0, 1.0):
            sc = [p1[i] + s * u[i] for i in range(3)]
            t = max(0.0, min(1.0, (b * s + e) / c))
            tc = [q1[i] + t * v[i] for i in range(3)]
            best = min(best, math.dist(sc, tc))
        for t in (0.0, 1.0):
            tc = [q1[i] + t * v[i] for i in range(3)]
            s = max(0.0, min(1.0, (b * t - d) / a))
            sc = [p1[i] + s * u[i] for i in range(3)]
            best = min(best, math.dist(sc, tc))
        return best
    s = max(0.0, min(1.0, (b * e - c * d) / denom))
    t = max(0.0, min(1.0, (a * e - b * d) / denom))
    sc = [p1[i] + s * u[i] for i in range(3)]
    tc = [q1[i] + t * v[i] for i in range(3)]
    return math.dist(sc, tc)

def poly_poly_dist(A, B):
    m = 1e9
    for i in range(len(A) - 1):
        for j in range(len(B) - 1):
            m = min(m, seg_seg_dist(A[i], A[i + 1], B[j], B[j + 1]))
    return m

TER = {r["id"]: (r["from"], r["to"]) for r in json.load(open("inputs/terminals.json"))["routes"]}

def seg_dir(a, b):
    for k in range(3):
        if abs(b[k] - a[k]) > 1e-6:
            return (k, 1 if b[k] > a[k] else -1)
    return None

def check(routes, verbose=True, fine=False):
    step = 0.005 if fine else 0.02
    res = {}
    for rid in sorted(routes):
        pts = routes[rid]
        msgs = []
        if len(pts) < 2: msgs.append("C1: too few points")
        for i in range(len(pts) - 1):
            diff = [k for k in range(3) if abs(pts[i][k] - pts[i + 1][k]) > 1e-6]
            if len(diff) != 1: msgs.append("C1: seg %d not axial (%s)" % (i, diff))
        p0, p1t = TER[rid]
        if math.dist(pts[0], p0) > 0.01: msgs.append("C1: start off port %.4f" % math.dist(pts[0], p0))
        if math.dist(pts[-1], p1t) > 0.01: msgs.append("C1: end off target %.4f" % math.dist(pts[-1], p1t))
        dirs = [seg_dir(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        bends = sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1])
        if bends > 8: msgs.append("C4: %d bends" % bends)
        smp, L = seg_sample(pts, step)
        worst2 = 1e9; bad2 = None; worst3 = None
        for s, p in smp:
            if min(s, L - s) > 0.30:
                for n, lo, hi in boxes:
                    d = pdist(p, lo, hi)
                    if d < 0.10 - 0.001:
                        msgs.append("C2: %.4f to %s at s=%.2f p=%s" % (d, n, s, [round(v, 3) for v in p]))
                    if d < worst2: worst2 = d; bad2 = (n, round(s, 2), [round(v, 3) for v in p])
            z = p[2]
            hd = math.hypot(p[0] - p1t[0], p[1] - p1t[1])
            zmin = 2.60 if hd < 0.30 else 2.75
            if z > 3.50 + 0.001 or z < zmin - 0.001:
                msgs.append("C3: z=%.3f at s=%.2f (hd=%.2f)" % (z, s, hd))
        for other in sorted(routes):
            if other == rid: continue
            d = poly_poly_dist(pts, routes[other])
            if d < 0.15 - 0.001:
                msgs.append("C5: %.4f from %s" % (d, other))
        res[rid] = (len(msgs) == 0, msgs, L, bends, worst2, bad2)
        if verbose:
            print("%s: %s L=%.3f bends=%d worstObst=%.3f @%s" % (rid, "OK  " if not msgs else "FAIL", L, bends, worst2, bad2))
            for m in msgs[:10]: print("      ", m)
    return res

# ---------- candidate routes ----------
L1 = 2.78
BR = 2.95

routes = {
 "P1": [[23.55, 7.70, 3.00], [23.55, 7.70, L1], [3.60, 7.70, L1], [3.60, 15.00, L1], [3.60, 15.00, 2.60]],
 "P2": [[23.55, 7.95, 3.00], [23.55, 7.95, L1], [10.50, 7.95, L1], [10.50, 7.95, BR],
        [10.50, 6.30, BR], [10.50, 6.30, L1], [10.50, 6.00, L1], [10.50, 6.00, 2.60]],
 "P3": [[23.55, 8.20, 3.00], [23.55, 8.20, L1], [6.90, 8.20, L1], [6.90, 8.40, L1], [6.90, 8.40, 2.60]],
 "P4": [[23.55, 8.45, 3.00], [23.55, 8.45, L1], [13.60, 8.45, L1], [13.60, 8.45, BR],
        [13.60, 4.60, BR], [13.60, 4.60, L1], [13.60, 4.30, L1], [13.60, 4.30, 2.60]],
 "P5": [[23.55, 8.70, 3.00], [23.55, 8.70, L1], [18.90, 8.70, L1], [18.90, 8.70, BR],
        [18.90, 7.50, BR], [18.90, 7.50, L1], [18.90, 1.90, L1], [18.90, 1.90, 2.60]],
 "P6": [[23.55, 8.95, 3.00], [23.55, 8.95, L1], [6.55, 8.95, L1], [6.55, 16.80, L1],
        [6.00, 16.80, L1], [6.00, 16.80, 2.60]],
}

print("\n=== check (step 0.02) ===")
r = check(routes)
print("\n=== pairwise separation ===")
for a, b in itertools.combinations(sorted(routes), 2):
    print("  %s-%s : %.3f" % (a, b, poly_poly_dist(routes[a], routes[b])))
print("\n=== fine re-check (step 0.005) ===")
check(routes, fine=True)
print("\nlower bound (dx+dy+dz):")
for rid in sorted(TER):
    a, b = TER[rid]
    print("  %s %.3f   actual %.3f" % (rid, sum(abs(a[i]-b[i]) for i in range(3)), r[rid][2]))

out = {"units": "m", "routes": [{"id": k, "points": [[round(c, 4) for c in p] for p in routes[k]]}
                               for k in ["P1", "P2", "P3", "P4", "P5", "P6"]]}
json.dump(out, open("routes.json", "w"), indent=1)
print("\nwrote routes.json")
