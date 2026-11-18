import bpy, numpy as np

img = bpy.data.images.load('/home/user/opus55poc/datacenter/runs/qwen3.8-flash/easy/s1-r2-high/inputs/plan.png')
w, h = img.size[0], img.size[1]
px = np.array(img.pixels[:]).reshape(h, w, 4)
R = px[:,:,0]; Gc = px[:,:,1]; B = px[:,:,2]; g = px[:,:,:3].mean(axis=2)

def boxes(mask, minpx=500, gap=4):
    # crude: project rows/cols
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]
    return (ys.min(), ys.max(), xs.min(), xs.max()) if len(ys) else None

# near-black solid (columns)
solid = g < 0.15
lbls = []
# connected components via simple flood using scipy-free approach
from collections import deque
seen = np.zeros_like(solid, dtype=bool)
comps = []
ys, xs = np.where(solid)
for y, x in zip(ys, xs):
    if seen[y, x]: continue
    q = deque([(y, x)]); seen[y, x] = True; pts = []
    while q:
        cy, cx = q.popleft(); pts.append((cy, cx))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = cy+dy, cx+dx
                if 0 <= ny < h and 0 <= nx < w and solid[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
    if len(pts) > 800:
        arr = np.array(pts)
        comps.append((arr[:,1].mean(), arr[:,0].mean(), len(pts), arr[:,0].min(), arr[:,0].max(), arr[:,1].min(), arr[:,1].max()))
print('solid blobs (cx,cy,n,minx,maxx,miny,maxy):')
for c in comps: print('  ', [round(v,1) for v in c])

# light blue (CRAH)
blue = (B > R + 0.05)
print('blue bbox:', boxes(blue))
ys, xs = np.where(blue)
# split into components roughly by y gaps
order = np.argsort(ys)
ys2 = ys[order]; xs2 = xs[order]
groups = []
cur = [ys2[0]]
for v in ys2[1:]:
    if v - cur[-1] > 10: groups.append(cur); cur = [v]
    else: cur.append(v)
groups.append(cur)
for gr in groups:
    m = (ys >= gr[0]) & (ys <= gr[-1])
    print('  blue comp y', gr[0], gr[-1], 'x', xs[m].min(), xs[m].max())

# east wall presence: scan several x inside wall thickness
dark = g < 0.6
for xv in (2062, 2070, 2078):
    col = dark[:, xv]
    idx = np.where(col)[0]
    idx = idx[(idx > 500) & (idx < 2050)]
    out = []
    for v in idx:
        if out and v - out[-1][1] <= 3: out[-1][1] = v
        else: out.append([v, v])
    print('east wall x', xv, 'dark runs:', [(a,b) for a,b in out if b-a > 3][:20])
