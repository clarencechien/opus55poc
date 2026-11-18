import bpy, numpy as np, os
from mathutils import Vector

# --- 1. template geometry facts
for nm in ['RackA_Base', 'RackA_FrontDoor', 'RackA_FrontLabel', 'RackA_FrontLED',
           'RackA_RearDoor', 'RackA_Top', 'RackG_Base', 'CRAH_Body', 'CRAH_Grille']:
    ob = bpy.data.objects.get(nm)
    if not ob:
        print(nm, 'MISSING'); continue
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    print('%-18s x %.3f..%.3f  y %.3f..%.3f  z %.3f..%.3f' % (nm, min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

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

def plan_map(cn, z0):
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
    acc = np.zeros((NY, NX), np.float32); cnt = np.zeros((NY, NX), np.float32)
    np.add.at(acc, (gy[ok], gx[ok]), lum[ok]); np.add.at(cnt, (gy[ok], gx[ok]), 1.0)
    return np.where(cnt > 0, acc / np.maximum(cnt, 1e-6), -1.0)

def save_img(name, rgbf, scale=4):
    # rgbf: (NY,NX,3) row0 = ymin
    r = np.repeat(np.repeat(rgbf, scale, 0), scale, 1)
    nh, nw = r.shape[0], r.shape[1]
    old = bpy.data.images.get(name)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new(name, nw, nh, alpha=True)
    rgba = np.ones((nh, nw, 4), np.float32); rgba[..., :3] = r
    im.pixels = rgba.reshape(-1).tolist()
    im.filepath_raw = os.path.abspath('out/%s.png' % name); im.file_format = 'PNG'; im.save()
    print('wrote out/%s.png' % name)

def gridlines(rgb):
    for iy in range(0, NY, 12): rgb[iy, :, 2] = np.maximum(rgb[iy, :, 2], 0.35)
    for ix in range(0, NX, 12): rgb[:, ix, 1] = np.maximum(rgb[:, ix, 1], 0.35)
    for iy in range(0, NY, 60): rgb[iy, :, :] = (0.1, 0.1, 1.0)
    for ix in range(0, NX, 60): rgb[:, ix, :] = (1.0, 0.1, 0.1)
    return rgb

# --- 2. label consensus at several z
for z0 in [1.90, 1.86]:
    st = np.stack([plan_map('Cam_%d' % i, z0) for i in [1, 2, 3, 4, 5]])
    valid = st >= 0
    nvis = valid.sum(0)
    med = np.where(nvis > 0, np.where(valid, st, -1).max(0), -1)
    # consensus: count of cameras seeing bright
    nbright = (valid & (st > 0.62)).sum(0)
    rgb = np.zeros((NY, NX, 3), np.float32)
    rgb[..., 0] = np.clip(nbright / 3.0, 0, 1)
    rgb[..., 1] = np.clip(nvis / 5.0 * 0.4, 0, 1)
    rgb[..., 2] = 0.05
    save_img(gridlines(rgb), 'cons%02d' % int(z0 * 100)) if False else save_img('cons%02d' % int(z0 * 100), gridlines(rgb))
    np.save('npy/cons%02d.npy' % int(z0 * 100), nbright.astype(np.int8))
print('done')
