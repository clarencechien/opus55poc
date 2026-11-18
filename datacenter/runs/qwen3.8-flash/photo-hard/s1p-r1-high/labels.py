import bpy, numpy as np, os, json
from collections import deque

W, H = 1280, 960
ZL = 1.86

def cam_basis(name):
    M = bpy.data.objects[name].matrix_world
    R = np.array([[M[a][b] for b in range(3)] for a in range(3)])
    p = np.array([M[0][3], M[1][3], M[2][3]])
    fwd = -(R @ np.array([0, 0, 1.0])); right = R @ np.array([1, 0, 0.0]); up = R @ np.array([0, 1, 0.0])
    return p, fwd / np.linalg.norm(fwd), right / np.linalg.norm(right), up / np.linalg.norm(up)

cam = bpy.data.cameras['Cam_1']
fl, sw = cam.lens, cam.sensor_width
xs = (np.arange(W) + 0.5 - W / 2.0) * sw / W
ys = (np.arange(H) + 0.5 - H / 2.0) * sw / W
XD, YD = np.meshgrid(xs / fl, ys / fl)

def rays(cn):
    p, fwd, right, up = cam_basis(cn)
    d = fwd[None, None, :] + XD[..., None] * right + YD[..., None] * up
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    return p, d

allpts = []
for i in [1, 2, 3, 4, 5]:
    cn = 'Cam_%d' % i
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % i), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    p, d = rays(cn)
    t = (ZL - p[2]) / d[..., 2]
    inb = (t > 0) & (np.arange(H)[:, None] >= 0)
    P = p[None, None, :] + t[..., None] * d
    inb &= (P[..., 0] > 0.0) & (P[..., 0] < 24.0) & (P[..., 1] > 0.0) & (P[..., 1] < 18.0)
    thr = 0.62
    m = (lum > thr) & inb
    print(cn, 'bright px', int(m.sum()), 'lum>0.75:', int(((lum > 0.75) & inb).sum()),
          'max lum in-bounds %.2f' % lum[inb].max())
    # connected components (8-neigh)
    lab = np.zeros((H, W), np.int32)
    cur = 0
    idx = np.argwhere(m)
    mset = set(map(tuple, idx.tolist()))
    seen = set()
    comps = []
    for s in mset:
        if s in seen: continue
        cur += 1
        q = deque([s]); seen.add(s); comp = []
        while q:
            y, x = q.popleft(); comp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in mset and n not in seen:
                        seen.add(n); q.append(n)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    print('  comps:', len(comps), 'sizes:', [len(c) for c in comps[:12]])
    pts = []
    for c in comps:
        if len(c) < 8 or len(c) > 6000: continue
        yy = np.array([a[0] for a in c]); xx = np.array([a[1] for a in c])
        sel = inb[yy, xx]
        yy, xx = yy[sel], xx[sel]
        if len(yy) < 8: continue
        pts.append((P[yy, xx, 0].mean(), P[yy, xx, 1].mean(), len(c),
                    xx.min(), xx.max(), yy.min(), yy.max()))
    for (x, y, n, x0, x1, y0, y1) in pts:
        allpts.append(dict(cam=i, x=round(float(x), 3), y=round(float(y), 3), n=n,
                           u0=int(x0), u1=int(x1), v0=int(y0), v1=int(y1)))
    print('  kept', len(pts))

json.dump(allpts, open('labels_raw.json', 'w'), indent=0)
print('total', len(allpts))
