import numpy as np, collections
def dilate(a, it):
    for _ in range(it):
        b = a.copy()
        b[1:,:] |= a[:-1]; b[:-1,:] |= a[1:]; b[:,1:] |= a[:,:-1]; b[:,:-1] |= a[:,1:]
        a = b
    return a
for k in ['front','back','left','right','top']:
    m = np.load('/tmp/m_%s.npy'%k); t = np.load('/tmp/t_%s.npy'%k)
    res = t & ~dilate(m, 3)
    ys,xs = np.nonzero(res)
    print("%-6s theirs-only after 3px dilate: %d" % (k, res.sum()), "mine-only:", (m & ~dilate(t,3)).sum())
    if len(xs):
        c = collections.Counter(zip((ys//25*25).tolist(), (xs//25*25).tolist()))
        print("   hotspots:", [(a,b,n) for (a,b),n in c.most_common(10)])
