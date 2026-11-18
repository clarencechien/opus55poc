import heapq, json, time, random
import numpy as np

C = 0.102
SEP = 0.153
ZMIN, ZMAX = 2.75, 3.498
TIME_BUDGET = globals().get('TIME_BUDGET', 60.0)
ORDERS = globals().get('ORDERS', None)

PORTS = {'P1': (23.55, 7.7, 3.0), 'P2': (23.55, 7.95, 3.0), 'P3': (23.55, 8.2, 3.0),
         'P4': (23.55, 8.45, 3.0), 'P5': (23.55, 8.7, 3.0), 'P6': (23.55, 8.95, 3.0)}
TGTS = {'P1': (3.6, 15.0, 2.6), 'P2': (10.5, 6.0, 2.6), 'P3': (6.9, 8.4, 2.6),
        'P4': (13.6, 4.3, 2.6), 'P5': (18.9, 1.9, 2.6), 'P6': (6.0, 16.8, 2.6)}
IDS = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']

static = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        l = o.matrix_world.translation; d = o.dimensions
        static.append(((l.x - d.x / 2, l.y - d.y / 2, l.z - d.z / 2), (l.x + d.x / 2, l.y + d.y / 2, l.z + d.z / 2), o.name))


def boxdist(p, lo, hi):
    s = 0.0
    for a in range(3):
        if p[a] < lo[a]: s += (lo[a] - p[a]) ** 2
        elif p[a] > hi[a]: s += (p[a] - hi[a]) ** 2
    return s ** 0.5


def seg_boxes(pts, infl):
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        lo = tuple(min(a[i], b[i]) - infl for i in range(3))
        hi = tuple(max(a[i], b[i]) + infl for i in range(3))
        out.append((lo, hi))
    return out


def route(pid, extra, maxb=8):
    """extra: list of (lo,hi) already-inflated boxes (other pipes / reservations); checked over full length."""
    port = PORTS[pid]; tgt = TGTS[pid]
    obs = []
    for lo, hi, nm in static:
        lo2 = tuple(v - C for v in lo); hi2 = tuple(v + C for v in hi)
        if hi2[2] > ZMIN - 1e-9 and lo2[2] < ZMAX + 1e-9:
            obs.append((lo2, hi2))
    for lo, hi in extra:
        if hi[2] > ZMIN - 1e-9 and lo[2] < ZMAX + 1e-9:
            obs.append((lo, hi))
    lines = [set(), set(), set()]
    for lo, hi in obs:
        for a in range(3):
            lines[a].add(round(lo[a], 6)); lines[a].add(round(hi[a], 6))
    for a in range(3):
        lines[a].add(round(port[a], 6))
    lines[0].add(tgt[0]); lines[1].add(tgt[1])
    lines[2].update([ZMIN, ZMAX])
    xs = np.array(sorted(v for v in lines[0] if 0.0 <= v <= 24.0))
    ys = np.array(sorted(v for v in lines[1] if 0.0 <= v <= 18.0))
    zs = np.array(sorted(v for v in lines[2] if ZMIN <= v <= ZMAX))
    nx, ny, nz = len(xs), len(ys), len(zs)
    mx = (xs[:-1] + xs[1:]) / 2; my = (ys[:-1] + ys[1:]) / 2; mz = (zs[:-1] + zs[1:]) / 2
    bn = np.zeros((nx, ny, nz), bool)
    bex = np.zeros((nx - 1, ny, nz), bool); bey = np.zeros((nx, ny - 1, nz), bool); bez = np.zeros((nx, ny, nz - 1), bool)
    eps = 1e-7

    def rng(arr, lo, hi):
        return np.searchsorted(arr, lo + eps, 'right'), np.searchsorted(arr, hi - eps, 'left')
    for lo, hi in obs:
        xi = rng(xs, lo[0], hi[0]); yi = rng(ys, lo[1], hi[1]); zi = rng(zs, lo[2], hi[2])
        mxi = rng(mx, lo[0], hi[0]); myi = rng(my, lo[1], hi[1]); mzi = rng(mz, lo[2], hi[2])
        bn[xi[0]:xi[1], yi[0]:yi[1], zi[0]:zi[1]] = True
        bex[mxi[0]:mxi[1], yi[0]:yi[1], zi[0]:zi[1]] = True
        bey[xi[0]:xi[1], myi[0]:myi[1], zi[0]:zi[1]] = True
        bez[xi[0]:xi[1], yi[0]:yi[1], mzi[0]:mzi[1]] = True
    BN = bn.ravel().tolist()
    # edge blocked lists indexed by lower node flat index
    def flat(i, j, k): return (i * ny + j) * nz + k
    BEX = np.ones((nx, ny, nz), bool); BEX[:-1] = bex; BEX = BEX.ravel().tolist()
    BEY = np.ones((nx, ny, nz), bool); BEY[:, :-1] = bey; BEY = BEY.ravel().tolist()
    BEZ = np.ones((nx, ny, nz), bool); BEZ[:, :, :-1] = bez; BEZ = BEZ.ravel().tolist()
    XL = xs.tolist(); YL = ys.tolist(); ZL = zs.tolist()
    sx = XL.index(round(port[0], 6)) if round(port[0], 6) in XL else int(np.argmin(abs(xs - port[0])))
    s = flat(int(np.argmin(abs(xs - port[0]))), int(np.argmin(abs(ys - port[1]))), int(np.argmin(abs(zs - port[2]))))
    ti = int(np.argmin(abs(xs - tgt[0]))); tj = int(np.argmin(abs(ys - tgt[1])))
    # goal column validity
    goal = {}
    for k in range(nz):
        zk = ZL[k]
        ok = True
        z = tgt[2]
        while z <= zk + 1e-9:
            p = (tgt[0], tgt[1], min(z, zk))
            if z > 2.9 - 1e-9:
                for lo, hi, nm in static:
                    if boxdist(p, lo, hi) < 0.1015: ok = False; break
            if ok:
                for lo, hi in extra:
                    if lo[0] + 1e-9 < p[0] < hi[0] - 1e-9 and lo[1] + 1e-9 < p[1] < hi[1] - 1e-9 and lo[2] + 1e-9 < p[2] < hi[2] - 1e-9:
                        ok = False; break
            if not ok: break
            z += 0.005
        if ok and not BN[flat(ti, tj, k)]:
            goal[flat(ti, tj, k)] = zk - tgt[2]
    SX = ny * nz; SY = nz
    nxyz = (nx, ny, nz)
    GOAL = -2
    heap = [(0.0, 0.0, 0, s, -1, None)]
    settled = {}
    parents = {}
    opp = [1, 0, 3, 2, 5, 4]
    found = None
    while heap:
        cost, L, b, n, d, par = heapq.heappop(heap)
        if n == GOAL:
            found = (L, b, par); break
        key = n * 7 + d + 1
        if settled.get(key, 99) <= b: continue
        settled[key] = b
        parents[(n, d, b)] = par
        me = (n, d, b)
        if n in goal:
            nb = b + (0 if d in (5, -1) else 1)
            if nb <= maxb:
                dl = goal[n]
                heapq.heappush(heap, (L + dl + 1e-4 * nb, L + dl, nb, GOAL, 5, me))
        i = n // SX; j = (n // SY) % ny; k = n % nz
        for nd in range(6):
            if d >= 0 and nd == opp[d]: continue
            nb = b + (1 if (d >= 0 and nd != d) else 0)
            if nb > maxb: continue
            if nd == 0:
                if i + 1 >= nx or BEX[n]: continue
                m = n + SX; dl = XL[i + 1] - XL[i]
            elif nd == 1:
                if i == 0: continue
                m = n - SX
                if BEX[m]: continue
                dl = XL[i] - XL[i - 1]
            elif nd == 2:
                if j + 1 >= ny or BEY[n]: continue
                m = n + SY; dl = YL[j + 1] - YL[j]
            elif nd == 3:
                if j == 0: continue
                m = n - SY
                if BEY[m]: continue
                dl = YL[j] - YL[j - 1]
            elif nd == 4:
                if k + 1 >= nz or BEZ[n]: continue
                m = n + 1; dl = ZL[k + 1] - ZL[k]
            else:
                if k == 0: continue
                m = n - 1
                if BEZ[m]: continue
                dl = ZL[k] - ZL[k - 1]
            if BN[m]: continue
            if settled.get(m * 7 + nd + 1, 99) <= nb: continue
            heapq.heappush(heap, (L + dl + 1e-4 * nb, L + dl, nb, m, nd, me))
    if found is None:
        return None
    L, b, par = found
    seq = []
    cur = par
    while cur is not None:
        n = cur[0]
        seq.append((XL[n // SX], YL[(n // SY) % ny], ZL[n % nz]))
        cur = parents[cur]
    seq.reverse()
    seq.append(tgt)
    seq[0] = port
    return simplify(seq)


def simplify(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if max(abs(p[i] - out[-1][i]) for i in range(3)) < 1e-7: continue
        out.append(p)
    res = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = res[-1], out[i], out[i + 1]
        d1 = [round(b[t] - a[t], 7) != 0 for t in range(3)]
        d2 = [round(c[t] - b[t], 7) != 0 for t in range(3)]
        s1 = [(b[t] - a[t]) > 0 for t in range(3)]
        s2 = [(c[t] - b[t]) > 0 for t in range(3)]
        if d1 == d2 and s1 == s2: continue
        res.append(b)
    res.append(out[-1])
    return [list(map(lambda v: round(v, 6), p)) for p in res]


def length(pts):
    return sum(sum(abs(b[i] - a[i]) for i in range(3)) for a, b in zip(pts[:-1], pts[1:]))


def samples(pts, step=0.01):
    out = []; s = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        L = sum(abs(b[i] - a[i]) for i in range(3))
        n = max(1, int(L / step + 0.999))
        for t in range(n):
            f = t / n
            out.append(((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f), s + L * f))
        s += L
    out.append((tuple(pts[-1]), s))
    return out, s


def check(routes):
    errs = {}
    S = {}
    for pid, pts in routes.items():
        e = []
        if pts is None: errs[pid] = ['none']; continue
        for a, b in zip(pts[:-1], pts[1:]):
            nd = sum(1 for i in range(3) if abs(b[i] - a[i]) > 1e-6)
            if nd != 1: e.append('C1 seg')
        if max(abs(pts[0][i] - PORTS[pid][i]) for i in range(3)) > 0.01: e.append('C1 port')
        if max(abs(pts[-1][i] - TGTS[pid][i]) for i in range(3)) > 0.01: e.append('C1 tgt')
        sm, Ltot = samples(pts)
        S[pid] = sm
        md = 9
        for p, s in sm:
            if s <= 0.3 or s >= Ltot - 0.3: continue
            for lo, hi, nm in static:
                dd = boxdist(p, lo, hi)
                if dd < md: md = dd; mn = nm
        if md < 0.1: e.append('C2 %.4f %s' % (md, mn))
        t = TGTS[pid]
        for p, s in sm:
            if p[2] > 3.5 + 1e-9: e.append('C3 high'); break
            if p[2] < 2.75 - 1e-9:
                if ((p[0] - t[0]) ** 2 + (p[1] - t[1]) ** 2) ** 0.5 > 0.3 or p[2] < 2.6 - 1e-9: e.append('C3 low'); break
        bends = len(pts) - 2
        if bends > 8: e.append('C4 %d' % bends)
        errs[pid] = e
    ids = [k for k in routes if routes[k] is not None]
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            A = np.array([p for p, s in S[ids[x]]]); B = np.array([p for p, s in S[ids[y]]])
            md = 9
            for chunk in range(0, len(A), 500):
                D = np.sqrt(((A[chunk:chunk + 500, None, :] - B[None, :, :]) ** 2).sum(-1)).min()
                md = min(md, D)
            if md < 0.15:
                errs[ids[x]].append('C5 %s %.4f' % (ids[y], md)); errs[ids[y]].append('C5 %s %.4f' % (ids[x], md))
    return errs


t0 = time.time()
LREF = {}
for pid in IDS:
    r = route(pid, [])
    LREF[pid] = length(r) if r else None
print('LREF', {k: round(v, 3) for k, v in LREF.items()}, 'time %.1f' % (time.time() - t0))


def run_order(order):
    done = {}
    for pid in order:
        extra = []
        for q, pts in done.items():
            extra += seg_boxes(pts, SEP)
        for q in IDS:
            if q != pid and q not in done:
                extra += seg_boxes([PORTS[q], (PORTS[q][0] - 0.05, PORTS[q][1], PORTS[q][2])], SEP)
                t = TGTS[q]
                extra += seg_boxes([t, (t[0], t[1], 2.75)], SEP)
        r = route(pid, extra)
        done[pid] = r
        if r is None:
            break
    return done


def score(done):
    sc = 0
    for pid in IDS:
        r = done.get(pid)
        if r: sc += 60 + 40 * min(1, LREF[pid] / length(r))
    return sc / 6


best = None
tried = set()
orders = ORDERS or [IDS, IDS[::-1], sorted(IDS, key=lambda k: LREF[k]), sorted(IDS, key=lambda k: -LREF[k])]
rnd = random.Random(1)
while time.time() - t0 < TIME_BUDGET:
    if orders:
        order = list(orders.pop(0))
    else:
        order = IDS[:]; rnd.shuffle(order)
    if tuple(order) in tried: continue
    tried.add(tuple(order))
    done = run_order(order)
    sc = score(done)
    print('order', order, 'score %.2f' % sc, 'time %.1f' % (time.time() - t0))
    if best is None or sc > best[0]:
        best = (sc, order, done)

sc, order, done = best
errs = check(done)
for pid in IDS:
    r = done.get(pid)
    if r:
        print(pid, 'L=%.3f ref=%.3f bends=%d' % (length(r), LREF[pid], len(r) - 2), errs.get(pid))
out = {'units': 'm', 'routes': [{'id': pid, 'points': done[pid]} for pid in IDS if done.get(pid)]}
print('BEST', order, '%.2f' % sc)
print('JSON' + json.dumps(out))
