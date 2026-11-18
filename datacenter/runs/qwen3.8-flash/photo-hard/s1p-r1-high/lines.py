import json
pts = json.load(open('labels2.json'))   # (cam, x, y, n, u0, u1)
CAM = {1: (0.45, 0.45), 2: (23.55, 0.45), 3: (0.45, 17.55), 4: (23.55, 11.55), 5: (17.55, 17.55)}

def transform(zp1):
    s = 0.79 / (3.25 - zp1)
    out = []
    for (i, x, y, n, u0, u1) in pts:
        px, py = CAM[i]
        out.append((i, px + (x - px) * s, py + (y - py) * s, n, u0, u1))
    return out

for zp1 in [2.40, 2.432, 2.46, 2.48]:
    print('=== z_p = %.3f  (scale %.3f)' % (zp1, 0.79 / (3.25 - zp1)))
    T = transform(zp1)
    # group by camera and rounded coordinate
    for i in [1, 2, 3, 4, 5]:
        rows = {}
        for (j, x, y, n, u0, u1) in T:
            if j != i: continue
            rows.setdefault(round(y, 1), []).append((x, n, u0, u1))
            rows.setdefault(('x', round(x, 1)), []).append((y, n, u0, u1))
        for k in sorted(rows, key=lambda a: str(a)):
            v = rows[k]
            if len(v) < 3: continue
            vals = sorted(v)
            print('  cam%d %s n=%d  ' % (i, k, len(v)), ' '.join('%.2f' % a[0] for a in vals))
