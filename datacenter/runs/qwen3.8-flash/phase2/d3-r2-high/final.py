import json, math, itertools
from mathutils import Vector

boxes = json.load(open("obstacles.json"))
TER = {r["id"]: (r["from"], r["to"]) for r in json.load(open("inputs/terminals.json"))["routes"]}

def pdist(p, lo, hi):
    d = 0.0
    for i in range(3):
        t = max(lo[i] - p[i], p[i] - hi[i], 0.0)
        d += t * t
    return math.sqrt(d)

def seg_sample(pts, step=0.02):
    smp = [(0.0, list(pts[0]))]; s = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ln = math.dist(a, b)
        k = int(math.floor(ln / step))
        for j in range(1, k + 1):
            t = min(j * step, ln)
            smp.append((s + t, [a[m] + (b[m] - a[m]) * t / ln for m in range(3)]))
        s += ln
    if math.dist(smp[-1][1], pts[-1]) > 1e-9:
        smp.append((s, list(pts[-1])))
    return smp, s

def seg_seg_dist(p1, p2, q1, q2):
    u = [p2[i] - p1[i] for i in range(3)]; v = [q2[i] - q1[i] for i in range(3)]
    w = [p1[i] - q1[i] for i in range(3)]
    a = sum(x*x for x in u); b = sum(u[i]*v[i] for i in range(3)); c = sum(x*x for x in v)
    d = sum(u[i]*w[i] for i in range(3)); e = sum(v[i]*w[i] for i in range(3))
    EPS = 1e-9
    if a < EPS and c < EPS: return math.dist(p1, q1)
    if a < EPS:
        t = max(0.0, min(1.0, e/c)); return math.dist(p1, [q1[i]+t*v[i] for i in range(3)])
    if c < EPS:
        s = max(0.0, min(1.0, -d/a)); return math.dist([p1[i]+s*u[i] for i in range(3)], q1)
    denom = a*c - b*b
    if denom < EPS:
        best = 1e9
        for s in (0.0, 1.0):
            sc = [p1[i]+s*u[i] for i in range(3)]
            t = max(0.0, min(1.0, (b*s+e)/c)); best = min(best, math.dist(sc, [q1[i]+t*v[i] for i in range(3)]))
        for t in (0.0, 1.0):
            tc = [q1[i]+t*v[i] for i in range(3)]
            s = max(0.0, min(1.0, (b*t-d)/a)); best = min(best, math.dist([p1[i]+s*u[i] for i in range(3)], tc))
        return best
    s = max(0.0, min(1.0, (b*e-c*d)/denom)); t = max(0.0, min(1.0, (a*e-b*d)/denom))
    return math.dist([p1[i]+s*u[i] for i in range(3)], [q1[i]+t*v[i] for i in range(3)])

def poly_poly_dist(A, B):
    return min(seg_seg_dist(A[i], A[i+1], B[j], B[j+1])
               for i in range(len(A)-1) for j in range(len(B)-1))

def seg_dir(a, b):
    for k in range(3):
        if abs(b[k]-a[k]) > 1e-6: return (k, 1 if b[k] > a[k] else -1)
    return None

def check(routes, fine=False, verbose=True):
    step = 0.005 if fine else 0.02
    res = {}
    for rid in sorted(routes):
        pts = routes[rid]; msgs = []
        if len(pts) < 2: msgs.append("C1: too few points")
        for i in range(len(pts)-1):
            diff = [k for k in range(3) if abs(pts[i][k]-pts[i+1][k]) > 1e-6]
            if len(diff) != 1: msgs.append("C1: seg %d not axial" % i)
        p0, pt = TER[rid]
        if math.dist(pts[0], p0) > 0.01: msgs.append("C1: start off port")
        if math.dist(pts[-1], pt) > 0.01: msgs.append("C1: end off target")
        dirs = [seg_dir(pts[i], pts[i+1]) for i in range(len(pts)-1)]
        bends = sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i-1])
        if bends > 8: msgs.append("C4: %d bends" % bends)
        smp, L = seg_sample(pts, step)
        worst2 = (1e9, None, None)
        for s, p in smp:
            if min(s, L-s) > 0.30:
                for n, lo, hi in boxes:
                    dd = pdist(p, lo, hi)
                    if dd < worst2[0]: worst2 = (dd, n, (round(s,2), [round(v,3) for v in p]))
                    if dd < 0.10 - 0.001: msgs.append("C2: %.4f to %s @%s" % (dd, n, [round(v,3) for v in p]))
            z = p[2]; hd = math.hypot(p[0]-pt[0], p[1]-pt[1])
            zmin = 2.60 if hd < 0.30 else 2.75
            if z > 3.50 + 0.001 or z < zmin - 0.001: msgs.append("C3: z=%.3f hd=%.2f" % (z, hd))
        sep = (1e9, None)
        for other in sorted(routes):
            if other == rid: continue
            dd = poly_poly_dist(pts, routes[other])
            if dd < sep[0]: sep = (dd, other)
            if dd < 0.15 - 0.001: msgs.append("C5: %.4f from %s" % (dd, other))
        res[rid] = (len(msgs) == 0, msgs, L, bends, worst2, sep)
        if verbose:
            print("%s: %s L=%.3f bends=%d minObst=%.3f(%s) minSep=%.3f(%s)" %
                  (rid, "OK " if not msgs else "FAIL", L, bends, worst2[0], worst2[1], sep[0], sep[1]))
            for m in msgs[:10]: print("      ", m)
    return res

# ============ final routes ============
L1 = 2.78   # highway level: 0.12 under cable trays, 0.16-0.18 above rack/containment tops
BR = 2.96   # bridge level: 0.18 above highway, >=0.1 horizontally clear of tray footprints

routes = {
 "P1": [[23.55, 7.70, 3.00], [23.55, 7.70, L1], [ 3.60, 7.70, L1], [ 3.60, 15.00, L1], [ 3.60, 15.00, 2.60]],
 "P2": [[23.55, 7.95, 3.00], [23.55, 7.95, L1], [10.50, 7.95, L1], [10.50, 7.95, BR],
        [10.50, 6.35, BR], [10.50, 6.35, L1], [10.50, 6.00, L1], [10.50, 6.00, 2.60]],
 "P3": [[23.55, 8.20, 3.00], [23.55, 8.20, L1], [ 6.90, 8.20, L1], [ 6.90, 8.40, L1], [ 6.90, 8.40, 2.60]],
 "P4": [[23.55, 8.45, 3.00], [23.55, 8.45, L1], [13.60, 8.45, L1], [13.60, 8.45, BR],
        [13.60, 4.65, BR], [13.60, 4.65, L1], [13.60, 4.30, L1], [13.60, 4.30, 2.60]],
 "P5": [[23.55, 8.70, 3.00], [23.55, 8.70, L1], [18.90, 8.70, L1], [18.90, 8.70, BR],
        [18.90, 7.50, BR], [18.90, 7.50, L1], [18.90, 1.90, L1], [18.90, 1.90, 2.60]],
 "P6": [[23.55, 8.95, 3.00], [23.55, 8.95, L1], [ 6.55, 8.95, L1], [ 6.55, 16.80, L1],
        [ 6.00, 16.80, L1], [ 6.00, 16.80, 2.60]],
}

r = check(routes); print()
rf = check(routes, fine=True)
allok = all(v[0] for v in rf.values())
print("ALL VALID:", allok)
for rid in sorted(rf):
    lb = sum(abs(TER[rid][0][i]-TER[rid][1][i]) for i in range(3))
    print("  %s  L=%.3f  lowerbound=%.3f  est.score=%.2f" % (rid, rf[rid][2], lb, 60+40*min(1.0, lb/rf[rid][2])))

if allok:
    out = {"units": "m", "routes": [{"id": k, "points": [[round(c, 4) for c in p] for p in routes[k]]}
                                   for k in ["P1","P2","P3","P4","P5","P6"]]}
    json.dump(out, open("routes.json", "w"), indent=1)
    print("wrote routes.json")

# ---- draw pipes in blender for a visual check ----
for o in list(bpy.data.objects):
    if o.name.startswith("Pipe_"):
        bpy.data.objects.remove(o, do_unlink=True)
for rid, pts in routes.items():
    cu = bpy.data.curves.new("Pipe_%s" % rid, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts)-1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    cu.bevel_depth = 0.05; cu.bevel_resolution = 2
    ob = bpy.data.objects.new("Pipe_%s" % rid, cu)
    bpy.context.scene.collection.objects.link(ob)
ce = bpy.data.objects.get("Ceiling")
if ce: ce.hide_render = True; ce.hide_viewport = True
bpy.context.scene.view_settings.exposure = 0.0
