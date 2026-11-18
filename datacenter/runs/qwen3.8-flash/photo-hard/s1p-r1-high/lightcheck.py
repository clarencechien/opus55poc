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
FX = fl / sw * W

def proj(cn, q):
    p, fwd, right, up = cam_basis(cn)
    v = np.array(q, float) - p
    x = v.dot(right); y = v.dot(up); z = v.dot(fwd)
    if z <= 1e-6: return None
    return (W / 2.0 + x / z * FX, H / 2.0 - y / z * FX)

lights = []
for o in bpy.data.objects:
    if o.name.startswith('Light_'):
        _, a, b = o.name.split('_')
        lights.append((float(a), float(b)))
print('n lights', len(lights))

for idx in [1, 2, 3, 4, 5]:
    im = bpy.data.images.load(os.path.abspath('inputs/photo_%d.jpg' % idx), check_existing=False)
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(im)
    lum = arr[..., :3] @ np.array([0.299, 0.587, 0.114])
    good = 0; bad = []
    for (lx, ly) in lights:
        pr = proj('Cam_%d' % idx, (lx, ly, 3.585))
        if pr is None: continue
        u, v = pr
        if not (0 <= u < W and 0 <= v < H): continue
        uu, vv = int(round(u)), int(round(H - 1 - v))
        win = lum[max(0, vv - 8):vv + 8, max(0, uu - 20):uu + 20]
        mx = win.max() if win.size else 0
        if mx > 0.75: good += 1
        else: bad.append((lx, ly, int(u), int(v), round(float(mx), 2)))
    print('cam%d: %d lights in frame, %d matched bright' % (idx, good + len(bad), good))
    for b in bad[:8]: print('   miss', b)
