import numpy as np
cnt = np.load('npy/crah.npy')
RES = 0.1
m = cnt >= 3
# simple clustering
from collections import deque
seen = set(); comps = []
idx = np.argwhere(m)
S = set(map(tuple, idx.tolist()))
for s in S:
    if s in seen: continue
    q = deque([s]); seen.add(s); comp = []
    while q:
        a, b = q.popleft(); comp.append((a, b))
        for da in (-2, -1, 0, 1, 2):
            for db in (-2, -1, 0, 1, 2):
                n = (a + da, b + db)
                if n in S and n not in seen:
                    seen.add(n); q.append(n)
    comps.append(comp)
comps.sort(key=len, reverse=True)
for c in comps[:12]:
    ys = np.array([a[0] for a in c]); xs = np.array([a[1] for a in c])
    print('n=%4d  x %.1f..%.1f (cx %.2f)  y %.1f..%.1f (cy %.2f)  views %d' % (
        len(c), xs.min()*RES, xs.max()*RES, xs.mean()*RES, ys.min()*RES, ys.max()*RES, ys.mean()*RES,
        max(cnt[c].max(), 0)))
print('--- also >=2 views')
m2 = cnt >= 2
ys, xs = np.nonzero(m2)
print('cells', len(xs))
import collections
h = collections.Counter()
for x, y in zip(xs, ys):
    h[(int(x // 12), int(y // 12))] += 1
for k, v in sorted(h.items(), key=lambda a: -a[1])[:20]:
    print('  block x %.1f-%.1f y %.1f-%.1f : %d' % (k[0]*1.2, k[0]*1.2+1.2, k[1]*1.2, k[1]*1.2+1.2, v))
