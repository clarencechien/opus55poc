import bpy, numpy as np, os

W, H = 1280, 960

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

def planpts(idx, box, z0):
    cn = 'Cam_%d' % idx
    p, fwd, right, up = cam_basis(cn)
    d = fwd[None, None, :] + XD[..., None] * right + YD[..., None] * up
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    t = (z0 - p[2]) / d[..., 2]
    P = p[None, None, :] + t[..., None] * d
    im = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % idx), check_existing=False)
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    u0, v0, u1, v1 = box
    sl = (slice(H - v1, H - v0), slice(u0, u1))
    ok = (t[sl] > 0)
    X = P[..., 0][sl][ok]; Y = P[..., 1][sl][ok]; L = lum[sl][ok]
    return X, Y, L

tests = [
    (1, (0, 540, 235, 700), 2.55, 'photo1 bottom-left grey box (CRAH top)'),
    (1, (690, 395, 775, 490), 2.55, 'photo1 mid grey box'),
    (3, (0, 540, 120, 700), 2.55, 'photo3 bottom-left'),
    (3, (930, 420, 1090, 650), 2.55, 'photo3 right grey box'),
    (2, (1190, 430, 1280, 570), 2.55, 'photo2 right edge dark panel'),
    (5, (0, 400, 300, 580), 2.0, 'photo5 far left row top'),
]
for idx, box, z0, desc in tests:
    X, Y, L = planpts(idx, box, z0)
    if len(X) == 0:
        print(desc, 'EMPTY'); continue
    print('%-45s n=%5d  x %.2f..%.2f  y %.2f..%.2f  lum %.2f/%.2f/%.2f' % (
        desc, len(X), X.min(), X.max(), Y.min(), Y.max(), np.percentile(L, 10), np.median(L), np.percentile(L, 90)))
