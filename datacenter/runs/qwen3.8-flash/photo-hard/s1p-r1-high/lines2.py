import os
exec(open('labdetect.py').read().replace('ZL = 1.86', 'ZL = 2.46'))
import collections
pts = []
for idx in [1, 2, 3, 4, 5]:
    for r in comps('inputs/photo_%d.jpg' % idx, 'Cam_%d' % idx, thr=0.50):
        if r[4] < 25: continue
        pts.append((idx, r[5], r[6], r[4]))
print('n comps', len(pts))
# group into lines: horizontal (constant y) and vertical (constant x)
byy = collections.defaultdict(list)
byx = collections.defaultdict(list)
for (i, x, y, n) in pts:
    byy[round(y, 1)].append((i, x, y, n))
    byx[round(x, 1)].append((i, x, y, n))
print('--- horizontal lines (>=3 comps, sorted by count)')
for k, v in sorted(byy.items(), key=lambda a: -len(a[1])):
    if len(v) >= 3:
        xs = sorted([p[1] for p in v])
        cams = sorted(set(p[0] for p in v))
        print('  y=%5.1f n=%2d cams%s  x %.1f..%.1f  %s' % (k, len(v), cams, xs[0], xs[-1],
              ' '.join('%.1f' % a for a in xs)))
print('--- vertical lines')
for k, v in sorted(byx.items(), key=lambda a: -len(a[1])):
    if len(v) >= 3:
        ys = sorted([p[2] for p in v])
        cams = sorted(set(p[0] for p in v))
        print('  x=%5.1f n=%2d cams%s  y %.1f..%.1f  %s' % (k, len(v), cams, ys[0], ys[-1],
              ' '.join('%.1f' % a for a in ys)))
