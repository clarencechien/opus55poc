import bpy, numpy as np, os

W, H = 1280, 960
RES = 0.1
NX, NY = 240, 180
os.makedirs('out', exist_ok=True)
os.makedirs('npy', exist_ok=True)

def cam_basis(name):
    M = bpy.data.objects[name].matrix_world
    R = np.array([[M[a][b] for b in range(3)] for a in range(3)])
    p = np.array([M[0][3], M[1][3], M[2][3]])
    fwd = -(R @ np.array([0, 0, 1.0]))
    right = R @ np.array([1, 0, 0.0])
    up = R @ np.array([0, 1, 0.0])
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
    X, Y = P[..., 0], P[..., 1]
    ok &= (X > 0.05) & (X < 23.95) & (Y > 0.05) & (Y < 17.95)
    img = bpy.data.images.load(os.path.abspath('inputs/photo_%s.jpg' % cn.split('_')[1]), check_existing=True)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    gx = np.clip((X / RES).astype(np.int32), 0, NX - 1)
    gy = np.clip((Y / RES).astype(np.int32), 0, NY - 1)
    acc = np.zeros((NY, NX), np.float32)
    cnt = np.zeros((NY, NX), np.float32)
    np.add.at(acc, (gy[ok], gx[ok]), lum[ok])
    np.add.at(cnt, (gy[ok], gx[ok]), 1.0)
    return np.where(cnt > 0, acc / np.maximum(cnt, 1e-6), -1.0)

for i in [1, 2, 3, 4, 5]:
    cn = 'Cam_%d' % i
    for z0, tag in [(2.0, 'top'), (1.9, 'lab'), (0.6, 'floor')]:
        g = plan_map(cn, z0)
        np.save('npy/%s_%s.npy' % (cn, tag), g)
print('saved npy')
