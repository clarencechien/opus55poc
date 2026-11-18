import json, math, itertools
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = False; o.hide_viewport = False
print("restored visibility")

boxes = json.load(open("obstacles.json"))
term = json.load(open("inputs/terminals.json"))
TER = {r["id"]: (r["from"], r["to"]) for r in term["routes"]}
RU = term["rules"]
data = json.load(open("routes.json"))
assert data["units"] == "m"
routes = {r["id"]: [list(map(float, p)) for p in r["points"]] for r in data["routes"]}
print("ids:", sorted(routes), "counts:", {k: len(v) for k, v in routes.items()})

def pdist(p, lo, hi):
    d = 0.0
    for i in range(3):
        t = max(lo[i]-p[i], p[i]-hi[i], 0.0); d += t*t
    return math.sqrt(d)

def seg_dir(a, b):
    for k in range(3):
        if abs(b[k]-a[k]) > 1e-6: return (k, 1 if b[k] > a[k] else -1)
    return None

def seg_seg_dist(p1, p2, q1, q2):
    u = [p2[i]-p1[i] for i in range(3)]; v = [q2[i]-q1[i] for i in range(3)]
    w = [p1[i]-q1[i] for i in range(3)]
    a = sum(x*x for x in u); b = sum(u[i]*v[i] for i in range(3)); c = sum(x*x for x in v)
    d = sum(u[i]*w[i] for i in range(3)); e = sum(v[i]*w[i] for i in range(3))
    EPS = 1e-9
    if a < EPS and c < EPS: return math.dist(p1, q1)
    if a < EPS:
        t = max(0., min(1., e/c)); return math.dist(p1, [q1[i]+t*v[i] for i in range(3)])
    if c < EPS:
        s = max(0., min(1., -d/a)); return math.dist([p1[i]+s*u[i] for i in range(3)], q1)
    den = a*c-b*b
    if den < EPS:
        best = 1e9
        for s in (0., 1.):
            sc = [p1[i]+s*u[i] for i in range(3)]
            t = max(0., min(1., (b*s+e)/c)); best = min(best, math.dist(sc, [q1[i]+t*v[i] for i in range(3)]))
        for t in (0., 1.):
            tc = [q1[i]+t*v[i] for i in range(3)]
            s = max(0., min(1., (b*t-d)/a)); best = min(best, math.dist([p1[i]+s*u[i] for i in range(3)], tc))
        return best
    s = max(0., min(1., (b*e-c*d)/den)); t = max(0., min(1., (a*e-b*d)/den))
    return math.dist([p1[i]+s*u[i] for i in range(3)], [q1[i]+t*v[i] for i in range(3)])

def ppdist(A, B):
    return min(seg_seg_dist(A[i], A[i+1], B[j], B[j+1]) for i in range(len(A)-1) for j in range(len(B)-1))

ok_all = True
for rid in sorted(routes):
    pts = routes[rid]; msgs = []
    p0, pt = TER[rid]
    if math.dist(pts[0], p0) > RU["endpoint_tol"]: msgs.append("start")
    if math.dist(pts[-1], pt) > RU["endpoint_tol"]: msgs.append("end")
    for i in range(len(pts)-1):
        diff = [k for k in range(3) if abs(pts[i][k]-pts[i+1][k]) > 1e-6]
        if len(diff) != 1: msgs.append("seg%d non-axial" % i)
    dirs = [seg_dir(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    bends = sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i-1])
    if bends > RU["max_bends"]: msgs.append("bends %d" % bends)
    L = 0.0; smp = [(0.0, list(pts[0]))]; s = 0.0
    for i in range(len(pts)-1):
        a, b = pts[i], pts[i+1]; ln = math.dist(a, b)
        for j in range(1, int(math.floor(ln/0.01))+1):
            t = min(j*0.01, ln); smp.append((s+t, [a[m]+(b[m]-a[m])*t/ln for m in range(3)]))
        s += ln
    L = s
    w2 = 1e9; n2 = None
    for ss, p in smp:
        if min(ss, L-ss) > RU["clearance_exempt_len"]:
            for n, lo, hi in boxes:
                dd = pdist(p, lo, hi)
                if dd < w2: w2, n2 = dd, n
                if dd < RU["clearance"]-RU["tolerance"]: msgs.append("C2 %s %.4f" % (n, dd)); break
        z = p[2]; hd = math.hypot(p[0]-pt[0], p[1]-pt[1])
        zmin = RU["target_z_min"] if hd < RU["target_radius"] else RU["z_min"]
        if z > RU["z_max"]+RU["tolerance"] or z < zmin-RU["tolerance"]: msgs.append("C3 %.3f" % z)
    for other in sorted(routes):
        if other == rid: continue
        dd = ppdist(pts, routes[other])
        if dd < RU["separation"]-RU["tolerance"]: msgs.append("C5 %.4f %s" % (dd, other))
    lb = sum(abs(p0[i]-pt[i]) for i in range(3))
    print("%s L=%.3f lb=%.3f bends=%d minObst=%.3f(%s) -> %s %s" %
          (rid, L, lb, bends, w2, n2, "VALID" if not msgs else "INVALID", msgs[:4]))
    ok_all &= (not msgs)
print("ALL VALID:", ok_all)
