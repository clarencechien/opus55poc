import bpy, numpy as np, os

W, H = 1280, 960
NX, NY = 240, 180
RES = 0.1

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

Z = 2.55
cnt = np.zeros((NY, NX), np.int16)
for i in [1, 2, 3, 4, 5]:
    cn = 'Cam_%d' % i
    p, fwd, right, up = cam_basis(cn)
    d = fwd[None, None, :] + XD[..., None] * right + YD[..., None] * up
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    t = (Z - p[2]) / d[..., 2]
    ok = t > 0
    P = p[None, None, :] + t[..., None] * d
    ok &= (P[..., 0] > 0.2) & (P[..., 0] < 23.8) & (P[..., 1] > 0.2) & (P[..., 1] < 17.8)
    im = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % i), check_existing=False)
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    m = ok & (lum > 0.48) & (lum < 0.80)
    gx = np.clip((P[..., 0] / RES).astype(np.int32), 0, NX - 1)
    gy = np.clip((P[..., 1] / RES).astype(np.int32), 0, NY - 1)
    c = np.zeros((NY, NX), np.int16)
    np.add.at(c, (gy[m], gx[m]), 1)
    cnt += (c > 0).astype(np.int16)
    print('cam%d hits %d' % (i, int(m.sum())))

rgb = np.zeros((NY, NX, 3), np.float32)
rgb[..., 0] = np.clip(cnt / 3.0, 0, 1)
rgb[..., 1] = 0.08
rgb[..., 2] = np.clip(cnt / 5.0, 0, 1) * 0.4
for iy in range(0, NY, 60): rgb[iy, :, 1] = 0.9
for ix in range(0, NX, 60): rgb[:, ix, 1] = 0.9
r = np.repeat(np.repeat(rgb, 4, 0), 4, 1)
old = bpy.data.images.get('CRAHM')
if old: bpy.data.images.remove(old)
im = bpy.data.images.new('CRAHM', r.shape[1], r.shape[0], alpha=True)
rgba = np.ones(r.shape[:2] + (4,), np.float32); rgba[..., :3] = r
im.pixels = rgba.reshape(-1).tolist()
im.filepath_raw = os.path.abspath('out/crahmap.png'); im.file_format = 'PNG'; im.save()
np.save('npy/crah.npy', cnt)
print('wrote out/crahmap.png')
# numeric: find blobs with count>=3
mask = cnt >= 3
print('cells with >=3 views:', int(mask.sum()))
ys2, xs2 = np.nonzero(mask)
if len(xs2):
    print(' x range %.1f..%.1f  y range %.1f..%.1f' % (xs2.min()*RES, xs2.max()*RES, ys2.min()*RES, ys2.max()*RES))
