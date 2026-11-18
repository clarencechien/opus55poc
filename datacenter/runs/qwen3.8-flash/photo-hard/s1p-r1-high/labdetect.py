import bpy, numpy as np, os
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

def comps(path, cn, thr=0.62):
    p, fwd, right, up = cam_basis(cn)
    d = fwd[None, None, :] + XD[..., None] * right + YD[..., None] * up
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    t = (ZL - p[2]) / d[..., 2]
    ok = t > 0
    P = p[None, None, :] + t[..., None] * d
    ok &= (P[..., 0] > 0.0) & (P[..., 0] < 24.0) & (P[..., 1] > 0.0) & (P[..., 1] < 18.0)
    im = bpy.data.images.load(os.path.abspath(path), check_existing=False)
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    m = (lum > thr) & ok
    mset = set(map(tuple, np.argwhere(m).tolist()))
    seen = set(); res = []
    for s in mset:
        if s in seen: continue
        q = deque([s]); seen.add(s); comp = []
        while q:
            y, x = q.popleft(); comp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (y + dy, x + dx)
                    if n in mset and n not in seen:
                        seen.add(n); q.append(n)
        if len(comp) < 8: continue
        yy = np.array([a[0] for a in comp]); xx = np.array([a[1] for a in comp])
        res.append((int(xx.min()), int(xx.max()), int(yy.min()), int(yy.max()), len(comp),
                    float(P[yy, xx, 0].mean()), float(P[yy, xx, 1].mean())))
    res.sort(key=lambda r: r[0])
    return res

if __name__ == '__main__':
    pass
