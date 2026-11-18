import bpy, numpy as np, os

W, H = 1280, 960
NX, NY = 240, 180
RES = 0.1
os.makedirs('out', exist_ok=True)

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

def plan(cn, z0):
    p, fwd, right, up = cam_basis(cn)
    dirs = fwd[None, None, :] + XD[..., None] * right + YD[..., None] * up
    dirs = dirs / np.linalg.norm(dirs, axis=-1, keepdims=True)
    t = (z0 - p[2]) / dirs[..., 2]
    ok = t > 0
    P = p[None, None, :] + t[..., None] * dirs
    ok &= (P[..., 0] > 0.05) & (P[..., 0] < 23.95) & (P[..., 1] > 0.05) & (P[..., 1] < 17.95)
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%s.jpg' % cn.split('_')[1]), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    gx = np.clip((P[..., 0] / RES).astype(np.int32), 0, NX - 1)
    gy = np.clip((P[..., 1] / RES).astype(np.int32), 0, NY - 1)
    return lum, ok, gx, gy

def accumulate(maskfun):
    cnt = np.zeros((NY, NX), np.int16)
    tot = np.zeros((NY, NX), np.int16)
    for i in [1, 2, 3, 4, 5]:
        lum, ok, gx, gy = plan('Cam_%d' % i, 2.0)
        m = ok & maskfun(lum)
        c = np.zeros((NY, NX), np.int16)
        np.add.at(c, (gy[m], gx[m]), 1)
        cnt += (c > 0).astype(np.int16)
        t = np.zeros((NY, NX), np.int16)
        np.add.at(t, (gy[ok], gx[ok]), 1)
        tot += (t > 0).astype(np.int16)
    return cnt, tot

def save(name, arr, lo, hi):
    a = np.clip((arr - lo) / (hi - lo), 0, 1)
    rgb = np.repeat(np.repeat(a, 4, 0), 4, 1)
    old = bpy.data.images.get('n' + name)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new('n' + name, rgb.shape[1], rgb.shape[0], alpha=True)
    rgba = np.ones(rgb.shape + (4,), np.float32)
    rgba[..., 0] = rgb; rgba[..., 1] = 1 - rgb; rgba[..., 2] = 0.1
    im.pixels = rgba.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/%s.png' % name); im.file_format = 'PNG'; im.save()
    print('wrote out/%s.png' % name)

dark = lambda L: L < 0.15
cnt, tot = accumulate(dark)
np.save('npy/dark2.npy', cnt)
save('darkcons', cnt, 0, 5)
# profiles
py = cnt.sum(1)   # per y
px = cnt.sum(0)   # per x
print('per-y dark counts (0.2m bins):')
for k in range(0, NY, 2):
    v = py[k:k + 2].sum() / 2.0
    if v > 20: print('  y %.1f-%.1f : %.0f' % (k * RES, (k + 2) * RES, v))
print('per-x dark counts (0.2m bins):')
for k in range(0, NX, 2):
    v = px[k:k + 2].sum() / 2.0
    if v > 20: print('  x %.1f-%.1f : %.0f' % (k * RES, (k + 2) * RES, v))
print('hide_render lights:', [o.hide_render for o in bpy.data.objects if o.name.startswith('Light_')][:3])
